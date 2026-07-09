"""Orkiestracja: faktury → walidacja + kategoryzacja + wykrywanie anomalii → wynik.

Wejściem jest lista Invoice (na razie z ground truth; docelowo z ekstrakcji Claude).
"""
from __future__ import annotations

from .categorize import categorize
from .detect import flags_for
from .external import Provider
from .schema import Invoice
from .validate import validate_invoice


def process(invoices: list[Invoice], provider: Provider | None = None) -> list[dict]:
    """Zwraca listę rekordów: {invoice, category, category_conf, issues, flags, vat_note, status, notes}.

    status: 'OK' | 'DO PRZEGLĄDU' — faktura idzie do człowieka, gdy ma błąd, złą stawkę,
    anomalię (duplikat/outlier/format) lub gdy zewnętrzny rejestr (provider) zgłasza problem.
    provider (opcjonalny): weryfikacja w rejestrze zewnętrznym, np. biała lista VAT.
    """
    batch_flags = flags_for(invoices)
    results: list[dict] = []
    for inv, flags in zip(invoices, batch_flags):
        issues = validate_invoice(inv)
        category, conf = categorize(inv)
        errors = [i for i in issues if i.severity == "error"]
        vat_warn = any("vat_rate" in i.field for i in issues)  # zła/nietypowa stawka VAT

        # Weryfikacja zewnętrzna (biała lista VAT itp.) — tylko gdy podłączony provider
        vat_note: str | None = None
        if provider is not None:
            st = provider.verify(inv.seller_nip)
            if st.checked and st.active is False:
                vat_note = f"sprzedawca NIEZAREJESTROWANY jako podatnik VAT — VAT nie do odliczenia ({st.source})"
            elif st.checked and st.account_whitelisted is False:
                vat_note = f"rachunek spoza białej listy VAT ({st.source})"

        notes = [f"{i.field}: {i.message}" for i in issues] + list(flags)
        if vat_note:
            notes.append(vat_note)
        if conf == 0.0:
            notes.append("kategoria niepewna — do przeglądu")
        status = "OK" if not errors and not flags and not vat_warn and not vat_note and conf > 0 else "DO PRZEGLĄDU"

        results.append({
            "invoice": inv,
            "category": category,
            "category_conf": conf,
            "issues": issues,
            "flags": flags,
            "vat_note": vat_note,
            "status": status,
            "notes": notes,
        })
    return results
