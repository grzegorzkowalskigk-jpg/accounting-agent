"""Wykrywanie duplikatów i wartości odstających w paczce faktur.

Duplikaty — ten sam numer faktury pojawia się więcej niż raz (klasyczny problem w obiegu).
Outliery — nienaturalnie wysokie kwoty brutto względem reszty (metoda IQR, odporna na skos).
"""
from __future__ import annotations

from collections import Counter

from .schema import Invoice


def find_duplicates(invoices: list[Invoice]) -> set[int]:
    """Indeksy faktur, których numer występuje w paczce więcej niż raz."""
    counts = Counter(inv.invoice_number for inv in invoices)
    return {i for i, inv in enumerate(invoices) if counts[inv.invoice_number] > 1}


def find_outliers(invoices: list[Invoice], k: float = 1.5) -> set[int]:
    """Indeksy faktur z kwotą brutto odstającą (górny wąs IQR: > Q3 + k·IQR)."""
    if len(invoices) < 4:
        return set()
    vals = sorted(inv.total_gross for inv in invoices)
    n = len(vals)

    def q(p: float) -> float:
        pos = p * (n - 1)
        lo = int(pos)
        frac = pos - lo
        return vals[lo] if lo + 1 >= n else vals[lo] * (1 - frac) + vals[lo + 1] * frac

    q1, q3 = q(0.25), q(0.75)
    hi = q3 + k * (q3 - q1)
    return {i for i, inv in enumerate(invoices) if inv.total_gross > hi}


def flags_for(invoices: list[Invoice]) -> list[list[str]]:
    """Dla każdej faktury lista tagów: 'duplikat' i/lub 'kwota odstająca'."""
    dups, outs = find_duplicates(invoices), find_outliers(invoices)
    out: list[list[str]] = []
    for i in range(len(invoices)):
        tags = []
        if i in dups:
            tags.append("duplikat")
        if i in outs:
            tags.append("kwota odstająca")
        out.append(tags)
    return out
