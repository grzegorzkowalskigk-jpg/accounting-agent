"""Walidacja faktury — kontrole poprawności, które łapią błędy zanim trafią do księgi.

Działa na obiekcie Invoice (skądkolwiek pochodzi: ground truth lub ekstrakcja).
"""
from __future__ import annotations

import re
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
    field: str     # techniczna nazwa pola (dla ewaluacji/logiki) — do ludzi mówi human_note()
    message: str


_ITEM_RE = re.compile(r"^item\[(\d+)\]")


def human_note(issue: Issue) -> str:
    """Komunikat gotowy do pokazania człowiekowi (księga, dashboard).

    Zamiast technicznego prefiksu pola („item[1].vat_rate: …") daje „poz. 1: …";
    pozostałe komunikaty są samowystarczalne, więc idą bez prefiksu.
    """
    m = _ITEM_RE.match(issue.field)
    return f"poz. {m.group(1)}: {issue.message}" if m else issue.message


def _m(x: float) -> str:
    """Kwota po ludzku: 478.7 → „478,70"."""
    return f"{x:.2f}".replace(".", ",")


def _close(a: float, b: float, tol: float = TOL) -> bool:
    return abs(a - b) <= tol


def _pdate(s: str) -> date | None:
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


# --- NIP: suma kontrolna. UWAGA: skonfigurowane WYŁĄCZNIE dla polskiego NIP.
#     Zagraniczne numery VAT (prefiks kraju ≠ PL) mają inne reguły → pomijamy checksum.
_NIP_WEIGHTS = [6, 5, 7, 2, 3, 4, 5, 6, 7]


def pl_nip_checksum_ok(digits10: str) -> bool:
    """True, gdy 10-cyfrowy polski NIP ma poprawną cyfrę kontrolną."""
    if len(digits10) != 10 or not digits10.isdigit():
        return False
    c = sum(int(digits10[i]) * _NIP_WEIGHTS[i] for i in range(9)) % 11
    return c != 10 and c == int(digits10[9])  # c==10 nie odpowiada żadnej cyfrze → NIP nieprawidłowy


def check_nip(who: str, raw: str) -> Issue | None:
    """Walidacja NIP: polski → suma kontrolna; zagraniczny → tylko adnotacja (poza zakresem)."""
    who_pl = "sprzedawcy" if who == "seller" else "nabywcy"
    norm = str(raw).strip().upper().replace(" ", "").replace("-", "")
    cc = norm[:2]
    if cc.isalpha() and cc != "PL":  # np. DE, FR — inny kraj, inne reguły
        return Issue("warning", f"{who}_nip", f"NIP {who_pl} zagraniczny ({cc}) — suma kontrolna sprawdzana tylko dla PL")
    digits = "".join(c for c in norm if c.isdigit())
    if len(digits) != 10:
        return Issue("warning", f"{who}_nip", f"NIP {who_pl} powinien mieć 10 cyfr, ma {len(digits)}")
    if not pl_nip_checksum_ok(digits):
        return Issue("error", f"{who}_nip", f"NIP {who_pl} {digits} — błędna suma kontrolna (nieprawidłowy)")
    return None


def validate_invoice(inv: Invoice) -> list[Issue]:
    """Zwraca listę problemów (pusta = faktura spójna)."""
    issues: list[Issue] = []

    # 1. Arytmetyka pozycji
    for n, it in enumerate(inv.items, 1):
        if not _close(it.net, it.quantity * it.unit_price_net):
            issues.append(Issue("error", f"item[{n}].net", f"netto {_m(it.net)} ≠ ilość × cena {_m(it.quantity * it.unit_price_net)}"))
        if not _close(it.vat, it.net * it.vat_rate):
            issues.append(Issue("error", f"item[{n}].vat", f"VAT {_m(it.vat)} ≠ netto × stawka {_m(it.net * it.vat_rate)}"))
        if not _close(it.gross, it.net + it.vat):
            issues.append(Issue("error", f"item[{n}].gross", f"brutto {_m(it.gross)} ≠ netto + VAT {_m(it.net + it.vat)}"))
        if it.vat_rate not in VAT_RATES:
            issues.append(Issue("warning", f"item[{n}].vat_rate", f"nietypowa stawka VAT: {it.vat_rate}"))
        exp = expected_vat_rate(it.description)
        if abs(it.vat_rate - exp) > 1e-9:
            issues.append(Issue("warning", f"item[{n}].vat_rate",
                                f"stawka VAT {int(round(it.vat_rate * 100))}% zamiast typowych {int(round(exp * 100))}% — „{it.description[:26]}”, do wyjaśnienia"))

    # 2. Arytmetyka sum
    if not _close(inv.total_net, sum(i.net for i in inv.items)):
        issues.append(Issue("error", "total_net", f"razem netto {_m(inv.total_net)} ≠ suma pozycji {_m(sum(i.net for i in inv.items))}"))
    if not _close(inv.total_vat, sum(i.vat for i in inv.items)):
        issues.append(Issue("error", "total_vat", f"razem VAT {_m(inv.total_vat)} ≠ suma pozycji {_m(sum(i.vat for i in inv.items))}"))
    if not _close(inv.total_gross, inv.total_net + inv.total_vat):
        issues.append(Issue("error", "total_gross", f"do zapłaty {_m(inv.total_gross)} ≠ netto + VAT {_m(inv.total_net + inv.total_vat)}"))

    # 3. NIP — suma kontrolna (tylko PL) lub adnotacja dla zagranicznych
    for who, nip in (("seller", inv.seller_nip), ("buyer", inv.buyer_nip)):
        problem = check_nip(who, nip)
        if problem:
            issues.append(problem)

    # 4. Daty
    iss, sal, due = _pdate(inv.issue_date), _pdate(inv.sale_date), _pdate(inv.due_date)
    if iss and sal and sal > iss:
        issues.append(Issue("warning", "sale_date", "data sprzedaży po dacie wystawienia"))
    if iss and due and due < iss:
        issues.append(Issue("error", "due_date", "termin płatności przed datą wystawienia"))

    return issues


def is_valid(inv: Invoice) -> bool:
    return not any(i.severity == "error" for i in validate_invoice(inv))
