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


def _num_pattern(s: str) -> str:
    """Szkielet formatu numeru: cyfry→9, litery→A, separatory bez zmian. 'FV/2026/06/0001' → 'AA/9999/99/9999'."""
    return "".join("9" if c.isdigit() else "A" if c.isalpha() else c for c in s)


def find_format_mismatches(invoices: list[Invoice]) -> set[int]:
    """Indeksy faktur o formacie numeru odbiegającym od dominującego — przy TYM SAMYM
    kontrahencie (NIP), który ma też fakturę w formacie standardowym.

    Sygnał: ten sam kontrahent, inny szablon/system numeracji → możliwe podszycie się
    lub zmiana systemu → żółte światło, kontrola ręczna.
    """
    if len(invoices) < 3:
        return set()
    fmts = [_num_pattern(inv.invoice_number) for inv in invoices]
    dominant = Counter(fmts).most_common(1)[0][0]
    by_nip: dict[str, list[int]] = {}
    for i, inv in enumerate(invoices):
        by_nip.setdefault(inv.seller_nip, []).append(i)
    flagged: set[int] = set()
    for i, inv in enumerate(invoices):
        if fmts[i] != dominant and any(fmts[j] == dominant for j in by_nip[inv.seller_nip] if j != i):
            flagged.add(i)
    return flagged


def flags_for(invoices: list[Invoice]) -> list[list[str]]:
    """Dla każdej faktury lista tagów anomalii (duplikat / kwota odstająca / inny format)."""
    dups = find_duplicates(invoices)
    outs = find_outliers(invoices)
    fmts = find_format_mismatches(invoices)
    out: list[list[str]] = []
    for i in range(len(invoices)):
        tags = []
        if i in dups:
            tags.append("duplikat")
        if i in outs:
            tags.append("kwota odstająca")
        if i in fmts:
            tags.append("inny format faktury — kontrola ręczna")
        out.append(tags)
    return out
