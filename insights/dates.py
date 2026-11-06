"""Resolve relative time phrases in a question to explicit date ranges, from the app calendar.

The model never does date arithmetic: "last quarter" reaches the prompt as an explicit half-open
range `[start, end)` with the assumption spelled out ("previous fiscal quarter"). The calendar
decides what a quarter is: when the fiscal year does not start in January, a bare "quarter" or
"year" means the FISCAL one and the assumption text says so; "calendar quarter" and "calendar
year" force the calendar meaning, "fiscal ..." the fiscal one. A fiscal year is named by the
calendar year in which it ends (FY2027 runs October 2026 to September 2027 when it starts in
October).

Resolution is deterministic for a given `today`, so a fixed clock gives reproducible golden runs.
"""

import calendar as _cal
import datetime as dt
import re
from dataclasses import dataclass
from typing import Literal

from insights.contracts.profile import Calendar

Kind = Literal[
    "day",
    "week",
    "month",
    "quarter",
    "fiscal_quarter",
    "year",
    "fiscal_year",
    "year_to_date",
    "fiscal_year_to_date",
    "trailing",
    "named_month",
    "named_year",
    "named_quarter",
]

_MONTHS = {name.lower(): i for i, name in enumerate(_cal.month_name) if name}
_MONTHS.update({name.lower(): i for i, name in enumerate(_cal.month_abbr) if name})
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "twenty-four": 24,
}  # fmt: skip
MAX_TRAILING = {"day": 3660, "week": 520, "month": 120, "quarter": 40, "year": 10}


@dataclass(frozen=True)
class DateRange:
    phrase: str
    """The text as it appeared in the question."""
    kind: Kind
    start: dt.date
    end: dt.date
    """Exclusive end: the range is `start <= d < end`."""
    assumption: str
    """One sentence for the answer's assumptions list."""

    def as_sql_literals(self) -> tuple[str, str]:
        return self.start.isoformat(), self.end.isoformat()


# ---- calendar arithmetic ------------------------------------------------------------------------


def _span(start: dt.date, end: dt.date) -> str:
    """`first to last` with an inclusive last day, for the assumption text."""
    return f"{start.isoformat()} to {(end - dt.timedelta(days=1)).isoformat()}"


def _add_months(day: dt.date, months: int) -> dt.date:
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    last = _cal.monthrange(year, month + 1)[1]
    return dt.date(year, month + 1, min(day.day, last))


def _month_start(day: dt.date) -> dt.date:
    return day.replace(day=1)


def _week_start(day: dt.date, cal: Calendar) -> dt.date:
    weekday = day.weekday() if cal.week_starts_on == "monday" else (day.weekday() + 1) % 7
    return day - dt.timedelta(days=weekday)


def _fiscal_year_start(day: dt.date, cal: Calendar) -> dt.date:
    """First day of the fiscal year that contains `day`."""
    start_month = cal.fiscal_year_start_month
    year = day.year if day.month >= start_month else day.year - 1
    return dt.date(year, start_month, 1)


def fiscal_year_label(day: dt.date, cal: Calendar) -> int:
    """The fiscal year is named by the calendar year in which it ends."""
    start = _fiscal_year_start(day, cal)
    return start.year + (1 if cal.fiscal_year_start_month > 1 else 0)


def _quarter_start(day: dt.date, cal: Calendar, *, fiscal: bool) -> dt.date:
    anchor = _fiscal_year_start(day, cal) if fiscal else dt.date(day.year, 1, 1)
    months_in = (day.year - anchor.year) * 12 + day.month - anchor.month
    return _add_months(anchor, (months_in // 3) * 3)


def _quarter_number(start: dt.date, cal: Calendar, *, fiscal: bool) -> int:
    anchor = _fiscal_year_start(start, cal) if fiscal else dt.date(start.year, 1, 1)
    return ((start.year - anchor.year) * 12 + start.month - anchor.month) // 3 + 1


def _quarter_is_fiscal(words: str, cal: Calendar) -> tuple[bool, str]:
    if "fiscal" in words:
        return True, "fiscal"
    if "calendar" in words:
        return False, "calendar"
    if cal.fiscal_year_start_month != 1:
        return True, "fiscal (the fiscal year starts in " + _cal.month_name[
            cal.fiscal_year_start_month
        ] + ")"
    return False, "calendar"


# ---- patterns ----------------------------------------------------------------------------------

_RELATIVE = re.compile(
    r"\b(?P<rel>last|previous|prior|this|current)\s+(?P<q>fiscal\s+|calendar\s+)?"
    r"(?P<unit>day|week|month|quarter|year)\b",
    re.IGNORECASE,
)
_TRAILING = re.compile(
    r"\b(?:(?:in|over|for|during)\s+the\s+)?(?:last|past|previous|trailing)\s+"
    r"(?P<n>\d{1,4}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty-four)\s+"
    r"(?P<unit>days?|weeks?|months?|quarters?|years?)\b",
    re.IGNORECASE,
)
_YTD = re.compile(r"\b(?P<q>fiscal\s+|calendar\s+)?(?:year[\s-]to[\s-]date|ytd)\b", re.IGNORECASE)
_NAMED_QUARTER = re.compile(
    r"\b(?:(?P<pre>fiscal|calendar|fy)\s*)?q(?P<n>[1-4])(?:\s*(?:of\s+)?(?:fy\s*)?(?P<year>20\d{2}))?\b"
    r"|\b(?P<year2>20\d{2})[\s-]q(?P<n2>[1-4])\b",
    re.IGNORECASE,
)
_NAMED_MONTH = re.compile(
    rf"\b(?P<prep>in\s+|of\s+|for\s+|during\s+)?(?P<month>{_MONTH_RE})\b(?:\s+(?P<year>20\d{{2}}))?",
    re.IGNORECASE,
)
_SHORT_MONTHS = frozenset(m for m in _MONTHS if len(m) == 3)
"""Abbreviations such as `mar` or `may` are also words; alone they are not a month."""
_NAMED_YEAR = re.compile(
    r"\b(?:in|for|during|of)\s+(?P<fy>fy\s*)?(?P<year>20\d{2})\b|\b(?P<fy2>fy)\s*(?P<year2>20\d{2})\b",
    re.IGNORECASE,
)
_SIMPLE = re.compile(r"\b(?P<word>today|yesterday)\b", re.IGNORECASE)


def _overlaps(span: tuple[int, int], taken: list[tuple[int, int]]) -> bool:
    return any(a < span[1] and span[0] < b for a, b in taken)


# ---- the resolver -------------------------------------------------------------------------------


def resolve_dates(question: str, today: dt.date, cal: Calendar) -> list[DateRange]:
    """Every time phrase found, left to right, each resolved to an explicit range."""
    found: list[tuple[tuple[int, int], DateRange]] = []
    taken: list[tuple[int, int]] = []

    def add(match: re.Match[str], item: DateRange | None) -> None:
        if item is None or _overlaps(match.span(), taken):
            return
        taken.append(match.span())
        found.append((match.span(), item))

    for m in _TRAILING.finditer(question):
        add(m, _trailing(m, today))
    for m in _RELATIVE.finditer(question):
        add(m, _relative(m, today, cal))
    for m in _YTD.finditer(question):
        add(m, _ytd(m, today, cal))
    for m in _NAMED_QUARTER.finditer(question):
        add(m, _named_quarter(m, today, cal))
    for m in _NAMED_YEAR.finditer(question):
        add(m, _named_year(m, cal))
    for m in _NAMED_MONTH.finditer(question):
        add(m, _named_month(m, today))
    for m in _SIMPLE.finditer(question):
        add(m, _simple(m, today))
    return [item for _, item in sorted(found, key=lambda pair: pair[0][0])]


def _relative(m: re.Match[str], today: dt.date, cal: Calendar) -> DateRange | None:
    rel, unit = m.group("rel").lower(), m.group("unit").lower()
    qualifier = (m.group("q") or "").strip().lower()
    previous = rel in ("last", "previous", "prior")
    phrase = m.group(0)
    if unit == "day":
        start = today - dt.timedelta(days=1) if previous else today
        return DateRange(
            phrase, "day", start, start + dt.timedelta(days=1), f"{phrase} = {start.isoformat()}"
        )
    if unit == "week":
        start = _week_start(today, cal) - (dt.timedelta(days=7) if previous else dt.timedelta(0))
        end = start + dt.timedelta(days=7)
        return DateRange(
            phrase,
            "week",
            start,
            end,
            f"{phrase} = the week of {_span(start, end)} ({cal.week_starts_on} first)",
        )
    if unit == "month":
        start = _add_months(_month_start(today), -1 if previous else 0)
        end = _add_months(start, 1)
        return DateRange(phrase, "month", start, end, f"{phrase} = {start.strftime('%B %Y')}")
    if unit == "quarter":
        fiscal, why = _quarter_is_fiscal(qualifier, cal)
        start = _quarter_start(today, cal, fiscal=fiscal)
        if previous:
            start = _add_months(start, -3)
        end = _add_months(start, 3)
        number = _quarter_number(start, cal, fiscal=fiscal)
        label = (
            f"Q{number} FY{fiscal_year_label(start, cal)}" if fiscal else f"Q{number} {start.year}"
        )
        kind: Kind = "fiscal_quarter" if fiscal else "quarter"
        return DateRange(
            phrase,
            kind,
            start,
            end,
            f"{phrase} = {label}, {_span(start, end)}, taken as a {why} quarter",
        )
    # year
    fiscal, why = _quarter_is_fiscal(qualifier, cal)
    if fiscal:
        start = _fiscal_year_start(today, cal)
        if previous:
            start = _add_months(start, -12)
        end = _add_months(start, 12)
        return DateRange(
            phrase,
            "fiscal_year",
            start,
            end,
            f"{phrase} = FY{fiscal_year_label(start, cal)}, {_span(start, end)}, "
            f"taken as a {why} year",
        )
    year = today.year - (1 if previous else 0)
    return DateRange(
        phrase,
        "year",
        dt.date(year, 1, 1),
        dt.date(year + 1, 1, 1),
        f"{phrase} = calendar year {year}",
    )


def _trailing(m: re.Match[str], today: dt.date) -> DateRange | None:
    raw = m.group("n").lower()
    n = _NUMBER_WORDS.get(raw) or int(raw)
    unit = m.group("unit").lower().rstrip("s")
    if n < 1 or n > MAX_TRAILING[unit]:
        return None
    end = today + dt.timedelta(days=1)  # the window includes today
    if unit == "day":
        start = end - dt.timedelta(days=n)
    elif unit == "week":
        start = end - dt.timedelta(days=7 * n)
    elif unit == "month":
        start = _add_months(end, -n)
    elif unit == "quarter":
        start = _add_months(end, -3 * n)
    else:
        start = _add_months(end, -12 * n)
    phrase = m.group(0)
    return DateRange(
        phrase,
        "trailing",
        start,
        end,
        f"{phrase} = {start.isoformat()} to {today.isoformat()} (inclusive of today)",
    )


def _ytd(m: re.Match[str], today: dt.date, cal: Calendar) -> DateRange:
    qualifier = (m.group("q") or "").strip().lower()
    fiscal, why = _quarter_is_fiscal(qualifier, cal)
    end = today + dt.timedelta(days=1)
    phrase = m.group(0)
    if fiscal:
        start = _fiscal_year_start(today, cal)
        return DateRange(
            phrase,
            "fiscal_year_to_date",
            start,
            end,
            f"{phrase} = FY{fiscal_year_label(today, cal)} to date, {_span(start, end)}, "
            f"taken as a {why} year",
        )
    start = dt.date(today.year, 1, 1)
    return DateRange(
        phrase,
        "year_to_date",
        start,
        end,
        f"{phrase} = {start.isoformat()} to {today.isoformat()} (calendar year)",
    )


def _named_quarter(m: re.Match[str], today: dt.date, cal: Calendar) -> DateRange | None:
    number = int(m.group("n") or m.group("n2"))
    year_text = m.group("year") or m.group("year2")
    pre = (m.group("pre") or "").lower()
    fiscal, why = _quarter_is_fiscal("fiscal" if pre in ("fiscal", "fy") else pre, cal)
    phrase = m.group(0)
    if fiscal:
        fy = int(year_text) if year_text else fiscal_year_label(today, cal)
        fy_start = dt.date(
            fy - (1 if cal.fiscal_year_start_month > 1 else 0), cal.fiscal_year_start_month, 1
        )
        start = _add_months(fy_start, 3 * (number - 1))
        label = f"Q{number} FY{fy}"
    else:
        year = int(year_text) if year_text else today.year
        start = dt.date(year, 3 * (number - 1) + 1, 1)
        label = f"Q{number} {year}"
    end = _add_months(start, 3)
    kind: Kind = "fiscal_quarter" if fiscal else "named_quarter"
    return DateRange(
        phrase,
        kind,
        start,
        end,
        f"{phrase} = {label}, {_span(start, end)}, taken as a {why} quarter",
    )


def _named_year(m: re.Match[str], cal: Calendar) -> DateRange | None:
    year = int(m.group("year") or m.group("year2"))
    fiscal = bool(m.group("fy") or m.group("fy2"))
    phrase = m.group(0)
    if fiscal:
        start = dt.date(
            year - (1 if cal.fiscal_year_start_month > 1 else 0), cal.fiscal_year_start_month, 1
        )
        end = _add_months(start, 12)
        return DateRange(
            phrase,
            "fiscal_year",
            start,
            end,
            f"{phrase} = FY{year}, {_span(start, end)}",
        )
    return DateRange(
        phrase,
        "named_year",
        dt.date(year, 1, 1),
        dt.date(year + 1, 1, 1),
        f"{phrase} = calendar year {year}",
    )


def _named_month(m: re.Match[str], today: dt.date) -> DateRange | None:
    word = m.group("month").lower()
    if word in _SHORT_MONTHS and not (m.group("prep") or m.group("year")):
        return None
    month = _MONTHS[word]
    if m.group("year"):
        year = int(m.group("year"))
    else:  # the most recent such month that has started
        year = today.year if month <= today.month else today.year - 1
    start = dt.date(year, month, 1)
    end = _add_months(start, 1)
    phrase = m.group(0)
    note = "" if m.group("year") else " (the most recent one)"
    return DateRange(
        phrase, "named_month", start, end, f"{phrase.strip()} = {start.strftime('%B %Y')}{note}"
    )


def _simple(m: re.Match[str], today: dt.date) -> DateRange:
    word = m.group("word").lower()
    day = today if word == "today" else today - dt.timedelta(days=1)
    return DateRange(word, "day", day, day + dt.timedelta(days=1), f"{word} = {day.isoformat()}")


def today_for(cal: Calendar, now: dt.datetime | None = None) -> dt.date:
    """Today in the app's timezone, unless the calendar pins a fixed clock (synthetic apps)."""
    if cal.today is not None:
        return cal.today
    from zoneinfo import ZoneInfo

    moment = now or dt.datetime.now(dt.UTC)
    return moment.astimezone(ZoneInfo(cal.timezone)).date()
