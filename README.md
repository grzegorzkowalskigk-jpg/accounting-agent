# accounting-agent — agent księgowy (AI)

Agent, który przetwarza **faktury** (skany/zdjęcia) od surowego obrazu do gotowego
zapisu w księdze: wyciąga dane, weryfikuje poprawność, kategoryzuje koszt i wykrywa
anomalie oraz duplikaty. Cel: zamienić godziny ręcznego przepisywania faktur w minuty,
z człowiekiem w roli kontrolera, nie przepisywacza.

> Projekt demonstracyjny (portfolio). Faktury są **syntetyczne** — generowane
> lokalnie, żeby pokazać działanie bez ujawniania realnych danych.

## Jak to działa (pipeline)

```
skan faktury (PNG)
   │
   ├─ 1. Ekstrakcja   → Claude (vision) czyta obraz i zwraca strukturę (JSON wg schematu)
   ├─ 2. Walidacja    → kontrola arytmetyki (netto+VAT=brutto), stawek VAT, NIP, dat
   ├─ 3. Kategoryzacja→ przypisanie kosztu do kategorii (np. IT, paliwo, biuro)
   ├─ 4. Anomalie     → duplikaty (ten sam numer), błędy kwot, wartości odstające
   └─ 5. Księga       → eksport do CSV/Excel + podsumowanie
```

Ewaluacja: wynik ekstrakcji porównywany z „ground truth" wygenerowanym razem z fakturą
— mierzymy dokładność pól, zanim zaufamy modelowi.

## Struktura

```
src/accounting_agent/
  schema.py    # modele danych (Pydantic): Invoice, LineItem
  synth.py     # generator syntetycznych faktur (obraz PNG + ground truth)
  extract.py   # ekstrakcja: obraz → struktura (Claude vision)      [w budowie]
  validate.py  # kontrole poprawności                                [w budowie]
  categorize.py# klasyfikacja kosztu                                 [w budowie]
  ledger.py    # eksport do księgi + podsumowanie                    [w budowie]
scripts/
  generate_data.py  # tworzy zestaw faktur w data/
app.py         # dashboard demo (Streamlit)                          [w budowie]
```

## Szybki start

```bash
python -m venv .venv && .venv\Scripts\activate      # (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
python scripts/generate_data.py --n 12              # generuje syntetyczne faktury do data/
```

Ekstrakcja (gdy gotowa) wymaga klucza Anthropic w `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

## Stan prac

- [x] Schemat danych (Pydantic)
- [x] Generator syntetycznych faktur (obraz + ground truth, z wstrzykiwanymi anomaliami)
- [ ] Ekstrakcja (Claude vision → struktura)
- [ ] Walidacja i kategoryzacja
- [ ] Wykrywanie anomalii i duplikatów
- [ ] Eksport do księgi + dashboard Streamlit
- [ ] Ewaluacja dokładności
