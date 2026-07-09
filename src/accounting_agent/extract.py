"""Ekstrakcja: obraz faktury (PNG) → struktura Invoice.

Dwa backendy o wspólnym interfejsie (Extractor):
- AnthropicVisionExtractor — produkcja: Claude (vision) czyta obraz i zwraca JSON. Wymaga klucza.
- ReplayExtractor        — demo bez klucza: czyta wcześniej wyekstrahowane JSON-y z dysku.

Ekstrakcja NIE poprawia faktury (nie liczy od nowa, nie zmienia stawek) — przepisuje to, co
widać. Wykrywanie błędów to zadanie walidacji (validate.py) — dzięki temu mierzymy osobno
wierność odczytu (accuracy) i skuteczność kontroli.
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .schema import Invoice

MODEL = "claude-opus-4-8"

# Skeleton przekazywany modelowi — nazwy pól są kontraktem (schema.py).
_SKELETON = """{
  "invoice_number": "string",
  "issue_date": "YYYY-MM-DD", "sale_date": "YYYY-MM-DD", "due_date": "YYYY-MM-DD",
  "seller_name": "string", "seller_nip": "10 cyfr", "seller_address": "string",
  "buyer_name": "string", "buyer_nip": "10 cyfr", "buyer_address": "string",
  "currency": "PLN",
  "items": [
    {"description": "string", "quantity": 0, "unit": "string",
     "unit_price_net": 0.0, "vat_rate": 0.23, "net": 0.0, "vat": 0.0, "gross": 0.0}
  ],
  "total_net": 0.0, "total_vat": 0.0, "total_gross": 0.0,
  "payment_method": "string"
}"""

EXTRACTION_PROMPT = f"""Jesteś systemem ekstrakcji danych z faktur. Odczytaj fakturę z obrazu
i zwróć WYŁĄCZNIE obiekt JSON zgodny ze schematem — bez komentarzy, bez bloków ``` .

Zasady:
- Przepisz wartości DOKŁADNIE tak, jak są na fakturze. NIE poprawiaj błędów rachunkowych
  ani stawek VAT — od kontroli poprawności jest osobny moduł.
- Liczby jako liczby (kropka dziesiętna), bez spacji i symbolu waluty: „1 234,56 zł" → 1234.56.
- Stawka VAT jako ułamek: „23%" → 0.23, „8%" → 0.08.
- Daty w formacie YYYY-MM-DD.

Schemat:
{_SKELETON}
"""

_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


class Extractor(Protocol):
    def extract(self, image_path: str | Path) -> Invoice: ...


def _strip_json(text: str) -> str:
    """Wyłuskuje surowy JSON z odpowiedzi modelu (usuwa ewentualne ```json ... ```)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end != -1 else text


def _encode(path: Path) -> tuple[str, str]:
    media = _MEDIA.get(path.suffix.lower(), "image/png")
    return media, base64.standard_b64encode(path.read_bytes()).decode("ascii")


class AnthropicVisionExtractor:
    """Produkcyjna ekstrakcja przez Claude (vision). Wymaga ANTHROPIC_API_KEY.

    Klienta można wstrzyknąć (testy); domyślnie tworzy anthropic.Anthropic() z env.
    """

    def __init__(self, client=None, model: str = MODEL, max_tokens: int = 2000):
        self.model = model
        self.max_tokens = max_tokens
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import anthropic  # import leniwy — moduł działa bez SDK/klucza (ReplayExtractor)
            self._client = anthropic.Anthropic()
        return self._client

    def extract(self, image_path: str | Path) -> Invoice:
        path = Path(image_path)
        media, data = _encode(path)
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }],
        )
        raw = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        return Invoice.model_validate_json(_strip_json(raw))


class ReplayExtractor:
    """Demo bez klucza: zwraca wcześniej zapisaną ekstrakcję (samples/vision/<stem>.json)."""

    def __init__(self, directory: str | Path):
        self.dir = Path(directory)

    def has(self, image_path: str | Path) -> bool:
        return (self.dir / (Path(image_path).stem + ".json")).exists()

    def extract(self, image_path: str | Path) -> Invoice:
        p = self.dir / (Path(image_path).stem + ".json")
        return Invoice.model_validate_json(p.read_text(encoding="utf-8"))


# ------------------------------------------------------- ewaluacja dokładności
_SCALAR = [
    "invoice_number", "issue_date", "sale_date", "due_date",
    "seller_name", "seller_nip", "seller_address",
    "buyer_name", "buyer_nip", "buyer_address", "currency",
    "total_net", "total_vat", "total_gross", "payment_method",
]
_MONEY = {"total_net", "total_vat", "total_gross"}
_ITEM_SCALAR = ["description", "unit"]
_ITEM_NUM = ["quantity", "unit_price_net", "vat_rate", "net", "vat", "gross"]


@dataclass
class FieldDiff:
    """Wynik porównania ekstrakcji z prawdą: ile pól trafionych i lista rozbieżności."""
    matched: int = 0
    total: int = 0
    mismatches: list[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.matched / self.total if self.total else 1.0


def _eq_num(a: float, b: float, tol: float) -> bool:
    return abs(float(a) - float(b)) <= tol


def field_diff(pred: Invoice, truth: Invoice, money_tol: float = 0.01) -> FieldDiff:
    """Porównuje pola faktury odczytanej (pred) z prawdą (truth). Pole 'category' pomijamy
    (uzupełnia je agent, nie ma go na fakturze)."""
    d = FieldDiff()

    def check(name: str, a, b, num: bool = False, tol: float = 0.0) -> None:
        d.total += 1
        ok = _eq_num(a, b, tol) if num else (str(a).strip() == str(b).strip())
        if ok:
            d.matched += 1
        else:
            d.mismatches.append(f"{name}: '{a}' ≠ '{b}'")

    for f_ in _SCALAR:
        check(f_, getattr(pred, f_), getattr(truth, f_), num=f_ in _MONEY, tol=money_tol)

    if len(pred.items) != len(truth.items):
        d.total += 1
        d.mismatches.append(f"items: liczba pozycji {len(pred.items)} ≠ {len(truth.items)}")
    for i, (pi, ti) in enumerate(zip(pred.items, truth.items), 1):
        for f_ in _ITEM_SCALAR:
            check(f"item[{i}].{f_}", getattr(pi, f_), getattr(ti, f_))
        for f_ in _ITEM_NUM:
            check(f"item[{i}].{f_}", getattr(pi, f_), getattr(ti, f_), num=True, tol=money_tol)
    return d
