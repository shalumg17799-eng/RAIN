"""Dependency-free text templating for the RAIN v0.4 persona contracts.

Persona contracts and persona copy are stored as TEMPLATES whose numbers are
placeholders.  At request time they are rendered against the computed
``sections`` dict (``constants``, ``records``, ``datasets``, ``governance``,
same shape and keys as the seed's ``sections``).

Placeholder syntax
------------------
    {{ <expr> | <filter> | <filter>:<arg> }}

Anything outside ``{{ ... }}`` is literal text.  Whitespace inside a
placeholder is ignored.

Expression grammar
------------------
    expr    := term (('+' | '-') term)*
    term    := unary (('*' | '/') unary)*
    unary   := '-' unary | atom
    atom    := NUMBER | '(' expr ')' | FUNC '(' path ')' | path
    FUNC    := len | count | sum | min | max
    path    := NAME segment*                     (NAME is a sections key)
    segment := '.' NAME                          dict key, or projection over a list
             | '[' INT ']'                       list index (negative allowed)
             | '[' cond (',' cond)* ']'          list selection, all conds must hold
    cond    := NAME '=' VALUE | NAME '!=' VALUE  field equals / differs
             | NAME                              field is truthy (non-empty, true, non-zero)
    VALUE   := text up to ',' or ']' (trimmed); 'true' / 'false' / 'null' and
               numbers are typed, anything else is a string (no quotes needed)

Examples
    constants.CONTRACT.actualPmpm
    constants.SITES[id=winnemucca].pmpm
    constants.GAP[0].value
    records.campaignMembers[id=M-40107].driveMin
    count(records.campaignMembers[siteId=winnemucca,status!=Reached and booked])
    sum(constants.LV_MEASURES.services)
    max(constants.COUNTIES[id!=lander,id!=pershing].pcVisitChangePct)
    constants.CONTRACT.actualPmpm - constants.CONTRACT.expectedPmpm
    count(records.previsitSummaries[mode=Telehealth]) / len(records.previsitSummaries) * 100

Selection semantics: ``[cond]`` yields the matching items and a following
``.key`` projects over them.  Outside a function the result must be exactly one
item (``SITES[id=elko].pmpm`` -> 398); zero or several matches raise.  Inside
``count``/``len`` the list is counted, inside ``sum``/``min``/``max`` its numeric
values are aggregated.  A ``.key`` applied to a plain list also projects.

Filters (applied left to right to the expression value)
-------------------------------------------------------
    num        thousands separators, whole numbers without ".0"  (9400 -> 9,400)
    num:N      fixed N decimals with separators                  (5.5 -> 5.50)
    usd        "$" + num                                         (412 -> $412)
    usd:N      "$" + num:N                                       (0.5 -> $0.50)
    usdK[:N]   thousands, N decimals (default 0), trailing zeros dropped (618000 -> $618K)
    usdM[:N]   millions, N decimals (default 1), trailing zeros dropped (2900000 -> $2.9M)
    round:N    round half-up to N decimals (default 0); stays a number
    pct        num + "%"                                         (6.7 -> 6.7%)
    abs, int   absolute value / truncate to integer; stay numbers
    lower, upper
    words      0..20 as English words (6 -> six), larger numbers as num
    cap        capitalise the first letter                       (six -> Six)
    native     only meaningful in render_obj: a string that is exactly one
               placeholder ending in "| native" renders to the raw value with
               its type (int stays int); in running text it behaves like no filter

With no filter a number renders minimally (no separators, no trailing ".0").

Errors
------
Unknown keys, out-of-range indexes, selections matching zero or several items,
unknown fields in a selection, non-numeric arithmetic, division by zero, null
values and unknown filters all raise ``TemplateError`` naming the placeholder.
Nothing ever renders silently empty.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable

__all__ = ["TemplateError", "render", "render_obj", "evaluate", "PLACEHOLDER"]


class TemplateError(ValueError):
    """Raised when a placeholder cannot be resolved or formatted."""


# A placeholder never contains "}}" (so two placeholders are never merged).
PLACEHOLDER = re.compile(r"\{\{((?:(?!\}\}).)*)\}\}", re.S)

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_INT = re.compile(r"-?\d+")
_WORDS = ("zero one two three four five six seven eight nine ten eleven twelve "
          "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty").split()


class _Sel(list):
    """Multi-valued result of a selection or projection."""


# --------------------------------------------------------------------------- #
# number helpers
# --------------------------------------------------------------------------- #

def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _num(v: Any, ctx: str) -> float | int:
    if _is_num(v):
        return v
    raise TemplateError(f"{ctx}: expected a number, got {v!r}")


def _dec(v: float | int) -> Decimal:
    return Decimal(repr(v)) if isinstance(v, float) else Decimal(v)


def _round_half_up(v: float | int, places: int) -> Decimal:
    return _dec(v).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _fmt(v: float | int, fixed: int | None = None, sep: bool = True) -> str:
    """Format a number: fixed decimals, or minimal (whole numbers without .0)."""
    if fixed is not None:
        q = _round_half_up(v, fixed)
        return format(q, f",.{fixed}f") if sep else format(q, f".{fixed}f")
    if isinstance(v, int):
        return f"{v:,}" if sep else str(v)
    s = _fmt_min(_round_half_up(v, 9))
    return s if sep else s.replace(",", "")


def _to_text(v: Any, ctx: str) -> str:
    if v is None:
        raise TemplateError(f"{ctx}: resolved to null")
    if isinstance(v, bool):
        return "true" if v else "false"
    if _is_num(v):
        return _fmt(v, sep=False)
    if isinstance(v, str):
        return v
    raise TemplateError(f"{ctx}: resolved to a {type(v).__name__}, not a scalar")


def _int_arg(arg: str | None, default: int, ctx: str, name: str) -> int:
    if arg is None or arg == "":
        return default
    if not _INT.fullmatch(arg):
        raise TemplateError(f"{ctx}: filter {name} expects an integer argument, got {arg!r}")
    return int(arg)


def _fmt_min(q: Decimal) -> str:
    """Decimal with separators, trailing zeros (and a bare '.0') dropped."""
    q = q.normalize()
    if q == q.to_integral_value():
        return f"{int(q):,}"
    return format(q, ",f")


def _scaled(v: Any, div: int, suffix: str, arg: str | None, default: int, ctx: str, name: str) -> str:
    n = _num(v, ctx)
    places = _int_arg(arg, default, ctx, name)
    q = _round_half_up(n / div, places)
    sign = "-" if q < 0 else ""
    return f"{sign}${_fmt_min(abs(q))}{suffix}"


# --------------------------------------------------------------------------- #
# filters
# --------------------------------------------------------------------------- #

def _f_num(v, arg, ctx):
    n = _num(v, ctx)
    return _fmt(n, None if arg in (None, "") else _int_arg(arg, 0, ctx, "num"))


def _f_usd(v, arg, ctx):
    n = _num(v, ctx)
    body = _fmt(abs(n), None if arg in (None, "") else _int_arg(arg, 0, ctx, "usd"))
    return ("-" if n < 0 else "") + "$" + body


def _f_round(v, arg, ctx):
    places = _int_arg(arg, 0, ctx, "round")
    q = _round_half_up(_num(v, ctx), places)
    return int(q) if places <= 0 else float(q)


def _f_pct(v, arg, ctx):
    if isinstance(v, str):
        return v + "%"
    return _fmt(_num(v, ctx)) + "%"


def _f_words(v, arg, ctx):
    n = _num(v, ctx)
    if float(n).is_integer() and 0 <= n < len(_WORDS):
        return _WORDS[int(n)]
    return _fmt(n)


def _f_cap(v, arg, ctx):
    s = _to_text(v, ctx)
    return s[:1].upper() + s[1:]


FILTERS: dict[str, Callable[[Any, str | None, str], Any]] = {
    "num": _f_num,
    "usd": _f_usd,
    "usdK": lambda v, a, c: _scaled(v, 1_000, "K", a, 0, c, "usdK"),
    "usdM": lambda v, a, c: _scaled(v, 1_000_000, "M", a, 1, c, "usdM"),
    "round": _f_round,
    "pct": _f_pct,
    "abs": lambda v, a, c: abs(_num(v, c)),
    "int": lambda v, a, c: int(_num(v, c)),
    "lower": lambda v, a, c: _to_text(v, c).lower(),
    "upper": lambda v, a, c: _to_text(v, c).upper(),
    "words": _f_words,
    "cap": _f_cap,
    "native": lambda v, a, c: v,
}


# --------------------------------------------------------------------------- #
# path resolution
# --------------------------------------------------------------------------- #

def _parse_value(raw: str) -> Any:
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw == "null":
        return None
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    return raw


def _equals(field: Any, value: Any, raw: str) -> bool:
    if isinstance(field, bool) or isinstance(value, bool) or value is None:
        return field is value
    if _is_num(field) and _is_num(value):
        return field == value
    return str(field) == raw


def _parse_conds(text: str, ctx: str) -> list[tuple[str, str, Any, str]]:
    conds = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            raise TemplateError(f"{ctx}: empty condition in [{text}]")
        if "!=" in part:
            field, raw = part.split("!=", 1)
            op = "!="
        elif "=" in part:
            field, raw = part.split("=", 1)
            op = "="
        else:
            field, raw, op = part, "", "truthy"
        field, raw = field.strip(), raw.strip()
        if not _NAME.fullmatch(field):
            raise TemplateError(f"{ctx}: bad field name {field!r} in [{text}]")
        conds.append((field, op, _parse_value(raw), raw))
    return conds


def _select(items: list, conds, ctx: str, where: str) -> _Sel:
    for field, _, _, _ in conds:
        if items and not any(isinstance(it, dict) and field in it for it in items):
            raise TemplateError(f"{ctx}: no item of {where} has a field {field!r}")
    out = _Sel()
    for it in items:
        if not isinstance(it, dict):
            raise TemplateError(f"{ctx}: {where} holds non-objects, cannot select by field")
        ok = True
        for field, op, value, raw in conds:
            present = field in it
            if op == "truthy":
                ok = present and bool(it[field])
            elif op == "=":
                ok = present and _equals(it[field], value, raw)
            else:
                ok = not (present and _equals(it[field], value, raw))
            if not ok:
                break
        if ok:
            out.append(it)
    return out


def _key(obj: Any, name: str, ctx: str, where: str) -> Any:
    if isinstance(obj, dict):
        if name not in obj:
            raise TemplateError(f"{ctx}: unknown key {name!r} at {where}")
        return obj[name]
    if isinstance(obj, list):
        return _Sel(_key(it, name, ctx, where + "[*]") for it in obj)
    raise TemplateError(f"{ctx}: cannot read {name!r} from a {type(obj).__name__} at {where}")


def _resolve(segments: list[tuple], sections: dict, ctx: str) -> Any:
    cur: Any = sections
    where = ""
    for kind, val in segments:
        if kind == "key":
            cur = _key(cur, val, ctx, where or "sections")
            where = f"{where}.{val}" if where else val
        elif kind == "index":
            if not isinstance(cur, list):
                raise TemplateError(f"{ctx}: cannot index a {type(cur).__name__} at {where}")
            try:
                cur = cur[val]
            except IndexError:
                raise TemplateError(f"{ctx}: index [{val}] out of range at {where} (len {len(cur)})") from None
            where = f"{where}[{val}]"
        else:  # select
            text, conds = val
            if not isinstance(cur, list):
                raise TemplateError(f"{ctx}: cannot select [{text}] from a {type(cur).__name__} at {where}")
            cur = _select(cur, conds, ctx, where)
            where = f"{where}[{text}]"
    return cur, where


# --------------------------------------------------------------------------- #
# aggregate functions (module-level so tests can wrap them)
# --------------------------------------------------------------------------- #

def _numbers(v: Any, ctx: str, fn: str) -> list:
    if not isinstance(v, list):
        raise TemplateError(f"{ctx}: {fn}() needs a list, got {type(v).__name__}")
    for x in v:
        if not _is_num(x):
            raise TemplateError(f"{ctx}: {fn}() over non-number {x!r}")
    return list(v)


def _fn_len(v, ctx):
    if isinstance(v, (list, dict, str)):
        return len(v)
    raise TemplateError(f"{ctx}: len() of a {type(v).__name__}")


def _fn_count(v, ctx):
    if isinstance(v, list):
        return len(v)
    raise TemplateError(f"{ctx}: count() needs a list, got {type(v).__name__}")


def _fn_sum(v, ctx):
    return sum(_numbers(v, ctx, "sum"))


def _fn_min(v, ctx):
    xs = _numbers(v, ctx, "min")
    if not xs:
        raise TemplateError(f"{ctx}: min() of an empty list")
    return min(xs)


def _fn_max(v, ctx):
    xs = _numbers(v, ctx, "max")
    if not xs:
        raise TemplateError(f"{ctx}: max() of an empty list")
    return max(xs)


FUNCS: dict[str, Callable[[Any, str], Any]] = {
    "len": _fn_len, "count": _fn_count, "sum": _fn_sum, "min": _fn_min, "max": _fn_max,
}


# --------------------------------------------------------------------------- #
# expression parser / evaluator
# --------------------------------------------------------------------------- #

class _Parser:
    def __init__(self, text: str, sections: dict, ctx: str):
        self.s, self.i, self.sections, self.ctx = text, 0, sections, ctx

    def err(self, msg: str) -> TemplateError:
        return TemplateError(f"{self.ctx}: {msg} at position {self.i} in {self.s.strip()!r}")

    def ws(self) -> None:
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def peek(self) -> str:
        self.ws()
        return self.s[self.i] if self.i < len(self.s) else ""

    def parse(self) -> Any:
        v = self.expr()
        if self.peek():
            raise self.err(f"unexpected {self.s[self.i]!r}")
        return v

    def expr(self) -> Any:
        v = self.term()
        while self.peek() in ("+", "-"):
            op = self.s[self.i]
            self.i += 1
            v = self.arith(v, op, self.term())
        return v

    def term(self) -> Any:
        v = self.unary()
        while self.peek() in ("*", "/"):
            op = self.s[self.i]
            self.i += 1
            v = self.arith(v, op, self.unary())
        return v

    def unary(self) -> Any:
        if self.peek() == "-":
            self.i += 1
            return -_num(self.unary(), self.ctx)
        return self.atom()

    def atom(self) -> Any:
        c = self.peek()
        if not c:
            raise self.err("expression ends early")
        if c == "(":
            self.i += 1
            v = self.expr()
            if self.peek() != ")":
                raise self.err("missing ')'")
            self.i += 1
            return v
        m = _NUMBER.match(self.s, self.i)
        if m:
            self.i = m.end()
            t = m.group(0)
            return float(t) if "." in t else int(t)
        m = _NAME.match(self.s, self.i)
        if not m:
            raise self.err(f"unexpected {c!r}")
        name = m.group(0)
        after = m.end()
        j = after
        while j < len(self.s) and self.s[j].isspace():
            j += 1
        if name in FUNCS and j < len(self.s) and self.s[j] == "(":
            self.i = j + 1
            value, _ = self.path(want_single=False)
            if self.peek() != ")":
                raise self.err(f"missing ')' after {name}(")
            self.i += 1
            return FUNCS[name](value, self.ctx)
        value, where = self.path(want_single=True)
        return value

    def path(self, want_single: bool) -> tuple[Any, str]:
        self.ws()
        m = _NAME.match(self.s, self.i)
        if not m:
            raise self.err("expected a path")
        segments: list[tuple] = [("key", m.group(0))]
        self.i = m.end()
        while self.i < len(self.s):
            c = self.s[self.i]
            if c == ".":
                m = _NAME.match(self.s, self.i + 1)
                if not m:
                    raise self.err("expected a key after '.'")
                segments.append(("key", m.group(0)))
                self.i = m.end()
            elif c == "[":
                end = self.s.find("]", self.i)
                if end < 0:
                    raise self.err("missing ']'")
                inner = self.s[self.i + 1:end].strip()
                if _INT.fullmatch(inner):
                    segments.append(("index", int(inner)))
                else:
                    segments.append(("select", (inner, _parse_conds(inner, self.ctx))))
                self.i = end + 1
            else:
                break
        value, where = _resolve(segments, self.sections, self.ctx)
        if want_single and isinstance(value, _Sel):
            if len(value) != 1:
                raise TemplateError(f"{self.ctx}: {where} matched {len(value)} items, expected exactly 1")
            value = value[0]
        if want_single and value is None:
            raise TemplateError(f"{self.ctx}: {where} is null")
        return value, where

    def arith(self, a: Any, op: str, b: Any) -> Any:
        a, b = _num(a, self.ctx), _num(b, self.ctx)
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if b == 0:
            raise TemplateError(f"{self.ctx}: division by zero")
        return a / b


def _split_top(body: str, sep: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in body:
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def _parse_filters(raw_filters: list[str], ctx: str) -> list[tuple[str, str | None]]:
    out = []
    for f in raw_filters:
        f = f.strip()
        name, _, arg = f.partition(":")
        name, arg = name.strip(), arg.strip()
        if name not in FILTERS:
            raise TemplateError(f"{ctx}: unknown filter {name!r}")
        out.append((name, arg if _ else None))
    return out


def _evaluate(body: str, sections: dict, ctx: str) -> tuple[Any, list[tuple[str, str | None]]]:
    parts = _split_top(body, "|")
    expr = parts[0]
    if not expr.strip():
        raise TemplateError(f"{ctx}: empty expression")
    filters = _parse_filters(parts[1:], ctx)
    value = _Parser(expr, sections, ctx).parse()
    for name, arg in filters:
        value = FILTERS[name](value, arg, ctx)
    return value, filters


def evaluate(body: str, sections: dict) -> Any:
    """Evaluate the inside of one placeholder (expression and filters) to a value."""
    return _evaluate(body, sections, "{{" + body + "}}")[0]


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #

def render(text: str, sections: dict) -> str:
    """Render every placeholder in ``text`` against ``sections``."""
    if not isinstance(text, str):
        raise TypeError("render() expects a string")

    def repl(m: re.Match) -> str:
        ctx = m.group(0)
        value, _ = _evaluate(m.group(1), sections, ctx)
        return _to_text(value, ctx)

    return PLACEHOLDER.sub(repl, text)


def render_obj(obj: Any, sections: dict) -> Any:
    """Recursively render every string inside dicts/lists; other values are kept.

    A string that is exactly one placeholder whose last filter is ``native``
    becomes the raw value (e.g. an int for a numeric ``count`` field).
    """
    if isinstance(obj, str):
        m = PLACEHOLDER.fullmatch(obj)
        if m:
            parts = _split_top(m.group(1), "|")
            if len(parts) > 1 and parts[-1].strip().partition(":")[0].strip() == "native":
                value, _ = _evaluate(m.group(1), sections, m.group(0))
                if value is None:
                    raise TemplateError(f"{m.group(0)}: resolved to null")
                return value
        return render(obj, sections)
    if isinstance(obj, dict):
        return {k: render_obj(v, sections) for k, v in obj.items()}
    if isinstance(obj, list):
        return [render_obj(v, sections) for v in obj]
    return obj
