"""Orkiestracja: faktury → walidacja + kategoryzacja + wykrywanie anomalii → wynik.

Wejściem jest lista Invoice (na razie z ground truth; docelowo z ekstrakcji Claude).
"""
from __future__ import annotations

from .categorize import categorize
from .detect import flags_for
from .schema import Invoice
from .validate import validate_invoice


def process(invoices: list[Invoice]) -> list[dict]:
    """Zwraca listę rekordów: {invoice, category, category_conf, issues, flags, status, notes}.

    status: 'OK' | 'DO PRZEGLĄDU' — faktura idzie do człowieka, gdy ma błąd, duplikat lub jest odstająca.
    """
    batch_flags = flags_for(invoices)
    results: list[dict] = []
    for inv, flags in zip(invoices, batch_flags):
        issues = validate_invoice(inv)
        category, conf = categorize(inv)
        errors = [i for i in issues if i.severity == "error"]

        notes = [f"{i.field}: {i.message}" for i in issues] + list(flags)
        if conf == 0.0:
            notes.append("kategoria niepewna — do przeglądu")
        status = "OK" if not errors and not flags and conf > 0 else "DO PRZEGLĄDU"

        results.append({
            "invoice": inv,
            "category": category,
            "category_conf": conf,
            "issues": issues,
            "flags": flags,
            "status": status,
            "notes": notes,
        })
    return results
