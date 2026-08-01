"""EN: Invoice data models (Pydantic) - the shared contract for the generator,
extraction and validation.
PL: Modele danych faktury (Pydantic) - wspolny kontrakt dla generatora,
ekstrakcji i walidacji.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

# Stawki VAT w Polsce
VAT_RATES = [0.23, 0.08, 0.05, 0.00]

# Kategorie kosztów (klasyfikacja)
CATEGORIES = [
    "Usługi IT i oprogramowanie",
    "Materiały biurowe",
    "Paliwo i transport",
    "Telekomunikacja",
    "Marketing i reklama",
    "Wynajem i media",
    "Usługi księgowe i prawne",
    "Sprzęt i wyposażenie",
]


class LineItem(BaseModel):
    """Pojedyncza pozycja na fakturze."""
    description: str = Field(description="Nazwa towaru lub usługi")
    quantity: float = Field(description="Ilość")
    unit: str = Field(description="Jednostka miary, np. szt., godz., mies.")
    unit_price_net: float = Field(description="Cena jednostkowa netto")
    vat_rate: float = Field(description="Stawka VAT jako ułamek, np. 0.23")
    net: float = Field(description="Wartość netto pozycji")
    vat: float = Field(description="Kwota VAT pozycji")
    gross: float = Field(description="Wartość brutto pozycji")


class Invoice(BaseModel):
    """Faktura VAT — struktura wyciągana z obrazu i porównywana z ground truth."""
    invoice_number: str = Field(description="Numer faktury")
    issue_date: str = Field(description="Data wystawienia (YYYY-MM-DD)")
    sale_date: str = Field(description="Data sprzedaży (YYYY-MM-DD)")
    due_date: str = Field(description="Termin płatności (YYYY-MM-DD)")
    seller_name: str = Field(description="Nazwa sprzedawcy")
    seller_nip: str = Field(description="NIP sprzedawcy (10 cyfr)")
    seller_address: str = Field(description="Adres sprzedawcy")
    buyer_name: str = Field(description="Nazwa nabywcy")
    buyer_nip: str = Field(description="NIP nabywcy (10 cyfr)")
    buyer_address: str = Field(description="Adres nabywcy")
    currency: str = Field(default="PLN", description="Waluta")
    items: list[LineItem] = Field(description="Pozycje faktury")
    total_net: float = Field(description="Razem netto")
    total_vat: float = Field(description="Razem VAT")
    total_gross: float = Field(description="Razem brutto (do zapłaty)")
    payment_method: str = Field(description="Sposób płatności")
    # Uzupełniane przez agenta (nie ma na fakturze):
    category: str | None = Field(default=None, description="Kategoria kosztu (klasyfikacja)")
