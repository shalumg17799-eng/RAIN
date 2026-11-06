"""Tokenising and a light stemmer for matching questions to catalog text.

Deliberately simple and deterministic. It does not understand language; the curated glossary
carries synonyms and the embedder (pluggable) carries meaning. This only gets `loans` to match
`loan` and `branches` to match `branch`.
"""

import re

_WORD = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "or",
        "our",
        "per",
        "should",
        "show",
        "tell",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "us",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
        "give",
        "list",
        "get",
        "find",
        "all",
        "any",
        "each",
        "every",
        "some",
        "many",
        "much",
        "more",
        "most",
        "less",
        "least",
        "number",
        "total",
    ]
)

TIME_WORDS = frozenset(
    [
        "last",
        "this",
        "next",
        "previous",
        "current",
        "past",
        "recent",
        "latest",
        "today",
        "yesterday",
        "tomorrow",
        "week",
        "weeks",
        "day",
        "days",
        "month",
        "months",
        "quarter",
        "quarters",
        "year",
        "years",
        "ytd",
        "fiscal",
        "calendar",
        "ago",
        "since",
        "between",
        "during",
        "before",
        "after",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "q1",
        "q2",
        "q3",
        "q4",
        "fy",
    ]
)


def tokenize(text: str) -> list[str]:
    """Lower-case alphanumeric words; underscores and punctuation split words."""
    return _WORD.findall(text.lower())


def stem(word: str) -> str:
    if len(word) <= 3:
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("sses"):
        return word[:-2]
    if word.endswith(("ches", "shes", "xes", "zes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    if word.endswith("ed") and len(word) > 4:
        word = word[:-2]
    if word.endswith("e") and len(word) > 3:
        word = word[:-1]
    return word


def stems(text: str) -> list[str]:
    return [stem(t) for t in tokenize(text)]


def content_tokens(question: str) -> list[str]:
    """The concepts in a question: stemmed words that are not filler, time words or numbers."""
    out = []
    for token in tokenize(question):
        if token in STOPWORDS or token in TIME_WORDS or token.isdigit():
            continue
        out.append(stem(token))
    return out
