"""Okapi BM25 over a small set of documents (one per catalog table).

An index is built from the documents it is given and nothing else: the statistics (document
frequency, average length) therefore never reflect a table the caller may not see.
"""

import math
from collections import Counter
from collections.abc import Mapping, Sequence


class BM25Index:
    def __init__(
        self, documents: Mapping[str, Sequence[str]], *, k1: float = 1.5, b: float = 0.75
    ) -> None:
        self._k1, self._b = k1, b
        self._tf = {key: Counter(tokens) for key, tokens in documents.items()}
        self._length = {key: len(tokens) for key, tokens in documents.items()}
        self._n = len(documents)
        self._avg = (sum(self._length.values()) / self._n) if self._n else 0.0
        frequency: Counter[str] = Counter()
        for counts in self._tf.values():
            frequency.update(counts.keys())
        self._df = frequency

    def idf(self, term: str) -> float:
        df = self._df.get(term, 0)
        return math.log(1.0 + (self._n - df + 0.5) / (df + 0.5))

    def score(self, query: Sequence[str]) -> dict[str, float]:
        scores = dict.fromkeys(self._tf, 0.0)
        for term in set(query):
            if term not in self._df:
                continue
            idf = self.idf(term)
            for key, counts in self._tf.items():
                f = counts.get(term, 0)
                if not f:
                    continue
                norm = (
                    1.0 - self._b + self._b * (self._length[key] / self._avg if self._avg else 0.0)
                )
                scores[key] += idf * (f * (self._k1 + 1.0)) / (f + self._k1 * norm)
        return scores
