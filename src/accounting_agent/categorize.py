"""Kategoryzacja kosztu — przypisanie faktury do kategoryzacji księgowej.

Baseline regułowy (bez klucza API): dopasowanie słów kluczowych w nazwach pozycji.
Docelowo do podmiany/uzupełnienia klasyfikacją LLM (dla trudnych przypadków).
"""
from __future__ import annotations

from .schema import Invoice

# słowa kluczowe → kategoria (kolejność ma znaczenie: pierwsze trafienie wygrywa)
RULES: list[tuple[str, list[str]]] = [
    ("Usługi IT i oprogramowanie", ["hosting", "licencj", "oprogram", "wdroż", "serwer", "vps", "saas", "chmur"]),
    ("Paliwo i transport", ["paliwo", "diesel", "benzyn", "przewóz", "przesył", "transport", "kurier"]),
    ("Telekomunikacja", ["abonament", "telefon", "internet", "światłowod", "gsm"]),
    ("Marketing i reklama", ["reklam", "kampani", "marketing", "graficz", "projekt graf"]),
    ("Wynajem i media", ["wynajem", "czynsz", "energia", "prąd", "media", "powierzchni"]),
    ("Usługi księgowe i prawne", ["księgow", "prawn", "porada", "kancelari", "audyt"]),
    ("Sprzęt i wyposażenie", ["laptop", "monitor", "krzesło", "biurko", "komputer"]),
    ("Materiały biurowe", ["papier", "toner", "tusz", "długopis", "materiał", "artykuł"]),
]


def categorize(inv: Invoice) -> tuple[str, float]:
    """Zwraca (kategoria, pewność 0..1). Pewność = udział pozycji trafionych regułą."""
    text = " ".join(it.description.lower() for it in inv.items)
    for category, keywords in RULES:
        if any(kw in text for kw in keywords):
            hits = sum(1 for it in inv.items if any(kw in it.description.lower() for kw in keywords))
            return category, round(hits / max(1, len(inv.items)), 2)
    return "Nieznana / do przeglądu", 0.0
