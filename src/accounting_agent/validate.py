"""Walidacja faktury — kontrole poprawności, które łapią błędy zanim trafią do księgi.

Działa na obiekcie Invoice (skądkolwiek pochodzi: ground truth lub ekstrakcja).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .schema import VAT_RATES, Invoice

TOL = 0.02  # tolerancja groszowa dla zaokrągleń (błędy rzędu 0,01 zł NIE są flagowane)

# Oczekiwana stawka VAT wg rodzaju towaru/usługi (heurystyka).
# Domyślnie 23%; wyjątki dla stawek obniżonych. Łapie „8% zamiast 23%".
REDUCED_RATE_KEYWORDS: dict[float, list[str]] = {
    0.08: ["gastronom", "hotel", "nocleg", "przewóz os", "transport os", "roboty budowl"],
    0.05: ["książk", "e-book", "ebook", "czasopism", "żywnoś"],
    0.00: ["eksport", "wewnątrzwspólnot", "wnt "],
}


def expected_vat_rate(description: str) -> float:
    """Typowa stawka VAT dla danej pozycji (23% domyślnie, obniżone dla wyjątków)."""
    d = description.lower()
    for rate, keywords in REDUCED_RATE_KEYWORDS.items():
        if any(k in d for k in keywords):
            return rate
    return 0.23


@dataclass
class Issue:
    severity: str  # 'error' | 'warning'
    field: str
    message: str


def _close(a: float, b: float, tol: float = TOL) -> bool:
    return abs(a - b) <= tol


def _pdate(s: str) -> date | None:
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def validate_invoice(inv: Invoice) -> list[Issue]:
    """Zwraca listę problemów (pusta = faktura spójna)."""
    issues: list[Issue] = []

    # 1. Arytmetyka pozycji
    for n, it in enumerate(inv.items, 1):
        if not _close(it.net, it.quantity * it.unit_price_net):
            issues.append(Issue("error", f"item[{n}].net", f"netto {it.net} ≠ ilość×cena {round(it.quantity * it.unit_price_net, 2)}"))
        if not _close(it.vat, it.net * it.vat_rate):
            issues.append(Issue("error", f"item[{n}].vat", f"VAT {it.vat} ≠ netto×stawka {round(it.net * it.vat_rate, 2)}"))
        if not _close(it.gross, it.net + it.vat):
            issues.append(Issue("error", f"item[{n}].gross", f"brutto {it.gross} ≠ netto+VAT {round(it.net + it.vat, 2)}"))
        if it.vat_rate not in VAT_RATES:
            issues.append(Issue("warning", f"item[{n}].vat_rate", f"nietypowa stawka VAT: {it.vat_rate}"))
        exp = expected_vat_rate(it.description)
        if abs(it.vat_rate - exp) > 1e-9:
            issues.append(Issue("warning", f"item[{n}].vat_rate",
                                f"zastosowano {int(round(it.vat_rate * 100))}% VAT — dla „{it.description[:26]}” zwykle {int(round(exp * 100))}%"))

    # 2. Arytmetyka sum
    if not _close(inv.total_net, sum(i.net for i in inv.items)):
        issues.append(Issue("error", "total_net", f"razem netto {inv.total_net} ≠ suma pozycji {round(sum(i.net for i in inv.items), 2)}"))
    if not _close(inv.total_vat, sum(i.vat for i in inv.items)):
        issues.append(Issue("error", "total_vat", f"razem VAT {inv.total_vat} ≠ suma pozycji {round(sum(i.vat for i in inv.items), 2)}"))
    if not _close(inv.total_gross, inv.total_net + inv.total_vat):
        issues.append(Issue("error", "total_gross", f"do zapłaty {inv.total_gross} ≠ netto+VAT {round(inv.total_net + inv.total_vat, 2)}"))

    # 3. NIP — 10 cyfr
    for who, nip in (("seller", inv.seller_nip), ("buyer", inv.buyer_nip)):
        digits = "".join(c for c in str(nip) if c.isdigit())
        if len(digits) != 10:
            issues.append(Issue("warning", f"{who}_nip", f"NIP powinien mieć 10 cyfr, ma {len(digits)}"))

    # 4. Daty
    iss, sal, due = _pdate(inv.issue_date), _pdate(inv.sale_date), _pdate(inv.due_date)
    if iss and sal and sal > iss:
        issues.append(Issue("warning", "sale_date", "data sprzedaży po dacie wystawienia"))
    if iss and due and due < iss:
        issues.append(Issue("error", "due_date", "termin płatności przed datą wystawienia"))

    return issues


def is_valid(inv: Invoice) -> bool:
    return not any(i.severity == "error" for i in validate_invoice(inv))
