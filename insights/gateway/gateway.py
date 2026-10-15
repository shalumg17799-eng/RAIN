"""The gateway: policy in front of a provider. This is `gateway.complete(...)` from the spec.

For every call it, in order:
  1. looks up the purpose in the app profile (disabled means refused) and pins sampling settings;
  2. refuses result rows unless the purpose may see them, and marks such calls no-store;
  3. refuses any identifier of the caller in the prompt (never in a prompt);
  4. refuses values from this run's result rows in a prompt that was not flagged as carrying rows;
  5. serves an exact-match cache hit, scoped to the principal, unless the call is no-store;
  6. calls the provider, records token usage on the run's meter, validates structured output.
Skills never name a model or a provider; the profile names a model group and configuration maps it.
"""

import json
import logging
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import jsonschema
from pydantic import ValidationError

from insights.contracts.enums import Purpose
from insights.contracts.gateway import CompletionResult, Message, Usage
from insights.contracts.principal import Principal
from insights.gateway.base import (
    GatewayError,
    PrincipalInPromptError,
    Provider,
    ProviderError,
    ProviderRequest,
    PurposeDisabledError,
    ResponseSchemaError,
    RowsNotAllowedError,
    UnflaggedRowsError,
    canonical_messages_sha256,
)
from insights.gateway.cache import InMemoryExactCache, cache_key
from insights.obs.logging import log_event

_log = logging.getLogger("insights.gateway")

MIN_IDENTIFIER_LENGTH = 4
"""Principal values shorter than this are not scanned: they would block ordinary words."""
_FENCE = re.compile(r"^```(?:json)?\s*\n(?P<body>.*?)\n?```\s*$", re.DOTALL)


def _coerce_string_lengths(data: Any, schema: dict[str, Any]) -> Any:
    """Truncate string values that exceed their schema `maxLength` to fit. The endpoint cannot
    enforce the schema (structured output "none"), and models are unreliable about length limits;
    an advisory field (a `reason`, an `assumption`) that runs long is trimmed rather than rejecting
    the whole answer. Functional fields have generous limits, so this only trims free-form text."""
    if not isinstance(data, dict) or not isinstance(schema.get("properties"), dict):
        return data
    for key, spec in schema["properties"].items():
        if key not in data or not isinstance(spec, dict):
            continue
        limit = spec.get("maxLength")
        if spec.get("type") == "string" and isinstance(data[key], str) and isinstance(limit, int):
            data[key] = data[key][:limit]
        elif spec.get("type") == "array" and isinstance(data[key], list):
            item = spec.get("items")
            ilimit = item.get("maxLength") if isinstance(item, dict) else None
            if isinstance(ilimit, int):
                data[key] = [v[:ilimit] if isinstance(v, str) else v for v in data[key]]
    return data


def _first_json_object(text: str) -> str | None:
    """The first balanced {...} substring, matching braces while skipping string literals and
    escapes. Returns None if there is no complete object. Never evaluates the text."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


class LLMGateway:
    def __init__(
        self,
        provider: Provider,
        *,
        model_for: Callable[[str], str],
        cache: InMemoryExactCache | None = None,
        providers: Mapping[str, Provider] | None = None,
    ) -> None:
        self.provider = provider
        self.cache = cache
        self._model_for = model_for
        # per-model-group providers (DIF-38); a group not listed uses the default provider
        self._providers: dict[str, Provider] = dict(providers or {})

    def complete(
        self,
        messages: Sequence[Message | Mapping[str, Any]],
        purpose: Purpose,
        ctx: Mapping[str, Any],
        response_schema: dict[str, Any] | None = None,
    ) -> CompletionResult:
        prompt = self._coerce(messages)
        app, principal = ctx["app"], ctx["principal"]

        policy = app.model_policy.get(purpose)
        if policy is None or not policy.enabled:
            raise PurposeDisabledError(
                f"purpose {purpose.value!r} is not enabled for app {app.id!r}"
            )
        if purpose is Purpose.SQL and policy.temperature != 0:
            raise GatewayError("the sql purpose must run at temperature 0")
        if response_schema is not None:
            try:
                jsonschema.Draft202012Validator.check_schema(response_schema)
            except jsonschema.SchemaError as exc:
                raise GatewayError(f"invalid response schema: {exc.message[:100]}") from exc

        carries_rows = any(m.contains_rows for m in prompt)
        if carries_rows and policy.rows_in_prompt == "never":
            raise RowsNotAllowedError(f"purpose {purpose.value!r} may not receive result rows")
        self._refuse_principal(prompt, principal)
        if not carries_rows:
            self._refuse_unflagged_rows(prompt, ctx)

        model = self._model_for(policy.model_group)
        digest = canonical_messages_sha256(prompt)

        key = None
        if self.cache is not None and not carries_rows:  # no-store: never read, never write
            key = cache_key(
                app=app,
                principal=principal,
                purpose=purpose,
                model=model,
                temperature=policy.temperature,
                max_tokens=policy.max_tokens,
                messages=prompt,
                response_schema=response_schema,
            )
            hit = self.cache.get(key)
            if hit is not None:
                self._log(ctx, purpose, hit.model, digest, Usage(), True, carries_rows)
                return CompletionResult(
                    content=hit.content, usage=Usage(), model=hit.model, cache_hit=True
                )

        request = ProviderRequest(
            model=model,
            messages=prompt,
            purpose=purpose,
            temperature=policy.temperature,
            max_tokens=policy.max_tokens,
            response_schema=response_schema,
            no_store=carries_rows,
        )
        provider = self._providers.get(policy.model_group, self.provider)
        try:
            response = provider.complete(request)
        except GatewayError:
            raise
        except Exception as exc:
            raise ProviderError(f"provider failed: {type(exc).__name__}") from exc

        ctx["usage"].add(response.usage.prompt_tokens, response.usage.completion_tokens)
        content: str | dict[str, Any] = response.text
        if response_schema is not None:
            content = self._structured(response.text, response_schema)

        result = CompletionResult(
            content=content, usage=response.usage, model=response.model, cache_hit=False
        )
        if key is not None and self.cache is not None:
            self.cache.put(key, result)
        self._log(ctx, purpose, response.model, digest, response.usage, False, carries_rows)
        return result

    # ---- checks ----------------------------------------------------------------------------

    @staticmethod
    def _coerce(messages: Sequence[Message | Mapping[str, Any]]) -> tuple[Message, ...]:
        if not messages:
            raise GatewayError("a call needs at least one message (got no messages)")
        out = []
        for index, item in enumerate(messages):
            if isinstance(item, Message):
                out.append(item)
                continue
            try:
                out.append(Message.model_validate(dict(item)))
            except (ValidationError, TypeError) as exc:
                raise GatewayError(f"invalid message #{index}") from exc
        return tuple(out)

    @staticmethod
    def _refuse_principal(prompt: Sequence[Message], principal: Principal) -> None:
        values = {v for v in principal.prompt_forbidden_values() if len(v) >= MIN_IDENTIFIER_LENGTH}
        for value in values:
            token = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(value)}(?![A-Za-z0-9_])")
            for index, message in enumerate(prompt):
                if token.search(message.content):
                    raise PrincipalInPromptError(
                        f"message #{index} contains an identifier of the caller; "
                        "principal data never goes into a prompt"
                    )

    @staticmethod
    def _refuse_unflagged_rows(prompt: Sequence[Message], ctx: Mapping[str, Any]) -> None:
        for value in ctx["results"].run_sensitive_strings(ctx["run_id"]):
            if any(value in message.content for message in prompt):
                raise UnflaggedRowsError(
                    "a prompt contains a value from this run's result rows but is not flagged "
                    "contains_rows"
                )

    @staticmethod
    def _structured(text: str, schema: dict[str, Any]) -> dict[str, Any]:
        stripped = text.strip()
        fenced = _FENCE.match(stripped)
        if fenced:
            stripped = fenced.group("body").strip()
        try:
            data = json.loads(stripped)
        except ValueError:
            # a model may wrap the object in prose; extract the first balanced {...} and parse that.
            # This is strict brace-matching, string-aware -- never eval.
            extracted = _first_json_object(stripped)
            if extracted is None:
                raise ResponseSchemaError("response is not valid JSON") from None
            try:
                data = json.loads(extracted)
            except ValueError:
                raise ResponseSchemaError("response is not valid JSON") from None
        data = _coerce_string_lengths(data, schema)
        errors = sorted(
            jsonschema.Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path)
        )
        if errors:
            where = "/".join(str(p) for p in errors[0].path) or "(root)"
            raise ResponseSchemaError(
                f"response does not match the schema at {where}: {errors[0].message[:120]}"
            )
        if not isinstance(data, dict):
            raise ResponseSchemaError("structured responses must be JSON objects")
        return data

    @staticmethod
    def _log(
        ctx: Mapping[str, Any],
        purpose: Purpose,
        model: str,
        digest: str,
        usage: Usage,
        cache_hit: bool,
        no_store: bool,
    ) -> None:
        log_event(
            _log,
            logging.INFO,
            "llm_call",
            run_id=ctx["run_id"],
            purpose=purpose.value,
            model=model,
            prompt_sha256=digest,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cache_hit=cache_hit,
            no_store=no_store,
        )
