"""Agent runtime: a Claude tool-use loop with a per-agent tool allowlist.

Each turn streams one Messages API response (large tool inputs such as a whole
manifest section stream as they are generated), validates every tool input
against its JSON schema before running it, appends the full assistant content
(append-only history, so thinking blocks stay valid) and stops when the agent
calls `finish` or runs out of turns."""
from __future__ import annotations

import json
import time

import anthropic
import jsonschema

from factory.agents import AgentSpec
from factory.apppack import now
from factory.config import MAX_TOKENS, MODEL
from factory.tools import RunContext, get


class AgentError(RuntimeError):
    pass


def _short(value, n=160) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= n else text[:n] + "..."


def run_agent(spec: AgentSpec, ctx: RunContext, task: str, client: anthropic.Anthropic | None = None) -> dict:
    client = client or anthropic.Anthropic()
    tools = {t.name: t for t in get(spec.tools)}
    tool_defs = [t.definition() for t in tools.values()]
    system = [{"type": "text", "text": spec.system_prompt()}]
    messages: list[dict] = [{"role": "user", "content": task}]
    tag = f"{spec.name}{'-' + ctx.mode if ctx.mode else ''}"
    log_path = ctx.pack.path("logs", f"{tag}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl")
    usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "turns": 0}
    nudges = 0

    def log(event: dict):
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": now(), **event}, default=str) + "\n")

    print(f"\n=== agent {tag} ({MODEL}, effort {spec.effort}) ===", flush=True)
    log({"event": "start", "task": task})
    for turn in range(spec.max_turns):
        try:
            with client.messages.stream(
                model=MODEL, max_tokens=MAX_TOKENS, system=system, tools=tool_defs, messages=messages,
                output_config={"effort": spec.effort}, cache_control={"type": "ephemeral"},
            ) as stream:
                msg = stream.get_final_message()
        except anthropic.APIStatusError as exc:
            log({"event": "api_error", "status": exc.status_code, "message": str(exc)[:500]})
            raise AgentError(f"{tag}: API error {exc.status_code}: {str(exc)[:300]}") from exc
        u = msg.usage
        usage["turns"] += 1
        usage["input"] += u.input_tokens or 0
        usage["output"] += u.output_tokens or 0
        usage["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
        usage["cache_write"] += getattr(u, "cache_creation_input_tokens", 0) or 0
        if msg.stop_reason == "refusal":
            log({"event": "refusal", "details": str(getattr(msg, "stop_details", ""))})
            raise AgentError(f"{tag}: the model declined the request ({getattr(msg, 'stop_details', '')})")
        messages.append({"role": "assistant", "content": msg.content})
        for b in msg.content:
            if b.type == "text" and b.text.strip():
                print(f"  [{tag}] {_short(b.text.strip(), 240)}", flush=True)
                log({"event": "text", "text": b.text})
        tool_uses = [b for b in msg.content if b.type == "tool_use"]
        if not tool_uses:
            if ctx.finished:
                break
            nudges += 1
            if nudges > 2:
                break
            messages.append({"role": "user", "content": "Continue using your tools. Call `finish` when your stage is complete."})
            continue
        results = []
        for i, b in enumerate(tool_uses):
            t = tools.get(b.name)
            truncated = msg.stop_reason == "max_tokens" and i == len(tool_uses) - 1
            try:
                if t is None:
                    raise ValueError(f"tool {b.name!r} is not available to this agent")
                if truncated:
                    raise ValueError("this tool input was cut off at the output limit; resend it in smaller parts")
                args = b.input if isinstance(b.input, dict) else json.loads(b.input)
                jsonschema.validate(args, t.schema)
                started = time.perf_counter()
                out = t.fn(ctx, **args)
                content = out if isinstance(out, str) else json.dumps(out, default=str)
                is_error = isinstance(out, dict) and "error" in out
                print(f"  [{tag}] {b.name}({_short(args, 90)}) -> {_short(content, 140)}", flush=True)
                log({"event": "tool", "name": b.name, "input": args, "output": content[:20000],
                     "ms": round((time.perf_counter() - started) * 1000)})
            except Exception as exc:  # every failure goes back to the model as a tool error
                content, is_error = f"Error: {type(exc).__name__}: {str(exc)[:1500]}", True
                print(f"  [{tag}] {b.name} ERROR {_short(str(exc), 200)}", flush=True)
                log({"event": "tool_error", "name": b.name, "error": str(exc)[:2000]})
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": content, "is_error": is_error})
        messages.append({"role": "user", "content": results})
        if ctx.finished:
            break
    log({"event": "end", "usage": usage, "finished": ctx.finished})
    handoff = ctx.finished or {"agent": spec.name, "mode": ctx.mode, "status": "blocked",
                               "summary": f"stopped after {usage['turns']} turns without calling finish"}
    handoff["usage"] = usage
    print(f"=== agent {tag} done: {handoff['status']} · turns {usage['turns']} · tokens in {usage['input']:,} "
          f"(cache read {usage['cache_read']:,}) out {usage['output']:,} ===", flush=True)
    return handoff
