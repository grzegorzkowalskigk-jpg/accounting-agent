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
  extract.py   # ekstrakcja: obraz → struktura (Claude vision + replay bez klucza)
  validate.py  # kontrole poprawności (arytmetyka, VAT, NIP, daty)
  detect.py    # anomalie w paczce (duplikaty, outliery, zmiana layoutu)
  categorize.py# klasyfikacja kosztu
  external.py  # weryfikacja w rejestrach (biała lista VAT — pluggable)
  ledger.py    # eksport do księgi + podsumowanie
  pipeline.py  # orkiestracja: faktury → walidacja/kategoryzacja/anomalie → wynik
scripts/
  generate_data.py  # tworzy zestaw faktur w data/
  extract_data.py   # ekstrakcja obraz→JSON + pomiar dokładności (replay / --live)
  run_pipeline.py   # przepuszcza paczkę przez agenta + ewaluacja
samples/vision/  # 6 faktur odczytanych wizją Claude (demo bez klucza)
app.py           # dashboard demo (Streamlit)
```

## Szybki start

```bash
python -m venv .venv && .venv\Scripts\activate      # (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
python scripts/generate_data.py --n 18              # generuje syntetyczne faktury do data/
python scripts/run_pipeline.py                      # agent: walidacja + anomalie + księga + ewaluacja
python scripts/extract_data.py                      # dokładność ekstrakcji (replay, bez klucza)
streamlit run app.py                                # dashboard demo (bez klucza)
```

Ekstrakcja **produkcyjna** (Claude vision na wszystkich obrazach) wymaga klucza w `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```
```bash
python scripts/extract_data.py --live --out data/extracted
```
Bez klucza demo działa w pełni: dane generują się deterministycznie, weryfikacja VAT używa
mocka offline, a ekstrakcję wizją pokazują próbki w `samples/vision/` (100% dokładności pól).

## Stan prac

- [x] Schemat danych (Pydantic)
- [x] Generator syntetycznych faktur (obraz + ground truth, 7 wstrzykiwanych anomalii)
- [x] Walidacja: arytmetyka + zaokrąglenia, właściwa stawka VAT, suma kontrolna NIP (PL), daty
- [x] Wykrywanie anomalii: duplikaty, kwoty odstające (IQR), zmiana layoutu u znanego kontrahenta
- [x] Weryfikacja zewnętrzna (pluggable): biała lista VAT — realny klient MF + mock offline
- [x] Kategoryzacja kosztu (baseline regułowy) + eksport do księgi (CSV/Excel)
- [x] Ekstrakcja (Claude vision → struktura) + tryb replay bez klucza; próbki w samples/vision/
- [x] Dashboard Streamlit (księga, szczegóły faktury, przegląd kontroli, dokładność ekstrakcji)
- [x] Ewaluacja: 7/7 anomalii, 18/18 kategoryzacji, 242/242 pól ekstrakcji (100%)
