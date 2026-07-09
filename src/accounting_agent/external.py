"""Weryfikacja kontrahenta w zewnętrznych rejestrach — pluggable.

Provider = wspólny interfejs. Wymienny backend:
- OfflineProvider  — mock do dema/testów bez sieci (konfigurowalne listy).
- MFWhitelistProvider — realny klient Białej Listy VAT (Ministerstwo Finansów, wymaga sieci).

To samo miejsce podłączenia dla innych rejestrów (np. BIK / listy zaległości —
API komercyjne): wystarczy nowy Provider z metodą verify().
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Protocol

# NIP oznaczony jako niepodatnik VAT w mocku (poprawna suma kontrolna, spoza listy sprzedawców).
DEMO_INACTIVE_NIP = "1181934533"


@dataclass
class VatStatus:
    checked: bool                        # czy w ogóle udało się sprawdzić (sieć/API)
    active: bool | None                  # czynny podatnik VAT
    account_whitelisted: bool | None     # rachunek na białej liście (None = nie sprawdzano)
    status_text: str
    source: str


class Provider(Protocol):
    def verify(self, nip: str, account: str | None = None) -> VatStatus: ...


def _digits(s: str) -> str:
    return "".join(c for c in str(s) if c.isdigit())


class OfflineProvider:
    """Mock bez sieci — pozwala uruchomić i przetestować cały przepływ deterministycznie."""

    def __init__(self, inactive_nips: set[str] | None = None, bad_accounts: set[str] | None = None):
        self.inactive = {_digits(n) for n in (inactive_nips or {DEMO_INACTIVE_NIP})}
        self.bad_accounts = set(bad_accounts or ())

    def verify(self, nip: str, account: str | None = None) -> VatStatus:
        d = _digits(nip)
        active = d not in self.inactive
        acc_ok = None if account is None else (_digits(account) not in {_digits(a) for a in self.bad_accounts})
        return VatStatus(True, active, acc_ok, "Czynny" if active else "Niezarejestrowany", "offline-mock")


class MFWhitelistProvider:
    """Realny klient Białej Listy VAT (Ministerstwo Finansów). Wymaga dostępu do sieci.

    Błąd sieci/API → checked=False (agent nie blokuje faktury, tylko odnotowuje brak weryfikacji).
    """

    BASE = "https://wl-api.mf.gov.pl/api/search/nip/"

    def verify(self, nip: str, account: str | None = None) -> VatStatus:
        d = _digits(nip)
        url = f"{self.BASE}{d}?date={date.today().isoformat()}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            subject = ((data.get("result") or {}).get("subject")) or {}
            status = subject.get("statusVat", "") or "Niezarejestrowany"
            active = status.strip().lower().startswith("czynny")
            accounts = {_digits(a) for a in (subject.get("accountNumbers") or [])}
            acc_ok = None if account is None else (_digits(account) in accounts)
            return VatStatus(True, active, acc_ok, status, "MF-wl-api")
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
            return VatStatus(False, None, None, f"brak weryfikacji ({type(e).__name__})", "MF-wl-api")
