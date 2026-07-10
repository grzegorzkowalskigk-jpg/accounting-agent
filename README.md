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
— mierzymy dokładność pól, zanim zaufamy modelowi. Więcej niżej: *Jak agent uczy się
poprawnie sprawdzać faktury?*

## Jak agent „uczy się" poprawnie sprawdzać faktury?

Krótka, uczciwa odpowiedź: **nie ma tu jednego „silnika AI, który sam się uczy na tysiącach
faktur"**. Inteligencja agenta pochodzi z dwóch różnych źródeł i warto je rozdzielić.

**1. Czytanie faktury — gotowy model, którego nie trenujemy.**
Odczytanie danych z obrazu robi Claude — duży model, który „widzi" i rozumie dokumenty już
z fabryki. Nie uczymy go od zera na naszych fakturach; dajemy mu instrukcję (co odczytać i
w jakim formacie) i sprawdzamy, czy się nie myli. To jak zatrudnienie doświadczonego
księgowego: nie uczysz go czytać — dajesz wytyczne i kontrolujesz jakość.

**2. Ocena faktury — jawne reguły, nie „czarna skrzynka".**
Czy 23% VAT policzono dobrze, czy NIP ma poprawną sumę kontrolną, czy numer się nie powtarza
— to nie „przeczucie modelu", tylko konkretne, zapisane reguły księgowe. Są przejrzyste i da
się je uzasadnić jednym zdaniem („brutto ≠ netto + VAT, różnica 10 zł"). Dla firmy to zaleta:
księgowość musi umieć wytłumaczyć, dlaczego coś odrzuciła.

**Skąd więc wiemy, że działa? Z klucza odpowiedzi.**
Skoro modelu nie trenujemy, „nauka" polega na czymś innym — na ciągłym **mierzeniu**.
Generujemy własne faktury, do których znamy prawidłową odpowiedź (bo sami je tworzymy — to
nasz *ground truth*, czyli klucz odpowiedzi), i **celowo podrzucamy do nich znane błędy** —
jak nauczyciel, który wsuwa do stosu prac kilka z zaplanowanymi pomyłkami, żeby sprawdzić, czy
egzaminator je wyłapie. Potem liczymy trzy rzeczy:
- czy agent odczytał każde pole zgodnie z obrazem (**dokładność ekstrakcji**),
- czy złapał każdy podrzucony błąd (**skuteczność kontroli**),
- czy trafił z kategorią kosztu (**dokładność klasyfikacji**).

Każda nowa reguła trafia do repozytorium **razem z nowym podrzuconym błędem** w zbiorze
testowym. Dzięki temu od razu widać, czy reguła działa — i czy przypadkiem nie zepsuła
czegoś, co wcześniej było poprawne.

**Zbiór testowy — i kiedy potrzebny byłby treningowy i walidacyjny.**
Dziś nasz zbiór syntetyczny pełni rolę **zbioru testowego**: dane z gotowym kluczem
odpowiedzi, na których egzaminujemy agenta. Klasycznego **zbioru treningowego** i
**walidacyjnego** (typowy podział 70% / 15% / 15%) nie ma, bo nie ma tu uczenia „od danych"
— reguły piszemy ręcznie, a model do czytania jest wytrenowany fabrycznie.
Trzy zbiory staną się potrzebne dopiero, gdy któryś element zamienimy na komponent **uczony
na danych** — np. gdy dzisiejszą kategoryzację po słowach kluczowych zastąpimy klasyfikatorem
uczonym na przykładach. Wtedy:
- **treningowy** — na nim model uczy się wzorców,
- **walidacyjny** — na nim stroimy ustawienia i pilnujemy, żeby nie „wykuł się na pamięć" (przeuczenie),
- **testowy** — odłożony do samego końca, ostateczny sprawdzian na danych, których model nie widział.

**Dlaczego faktury syntetyczne, a nie prawdziwe?** Po pierwsze prywatność — nie ryzykujemy
danymi realnych kontrahentów. Po drugie, nie da się zmierzyć wykrywacza błędów bez błędów do
wykrycia — a te musimy znać z góry. Po trzecie, próbę możemy dowolnie powiększać i dokładać
nowe scenariusze. W produkcji ten sam agent działa na prawdziwych fakturach — zmienia się
tylko źródło obrazów, nie logika.

**Aktualny wynik (próba 60 faktur, po 2 z każdego z 7 rodzajów anomalii):**
- **266/266** pól ekstrakcji odczytanych poprawnie (100%) — na próbkach zweryfikowanych wizją,
- **14/14** podrzuconych anomalii wykrytych,
- **60/60** trafionych kategorii kosztu.

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
python scripts/generate_data.py --n 60              # generuje syntetyczne faktury do data/
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
- [x] Generator syntetycznych faktur (obraz + ground truth, 7 rodzajów anomalii, skalowalna próba)
- [x] Walidacja: arytmetyka + zaokrąglenia, właściwa stawka VAT, suma kontrolna NIP (PL), daty
- [x] Wykrywanie anomalii: duplikaty, kwoty odstające (IQR), zmiana layoutu u znanego kontrahenta
- [x] Weryfikacja zewnętrzna (pluggable): biała lista VAT — realny klient MF + mock offline
- [x] Kategoryzacja kosztu (baseline regułowy) + eksport do księgi (CSV/Excel)
- [x] Ekstrakcja (Claude vision → struktura) + tryb replay bez klucza; próbki w samples/vision/
- [x] Dashboard Streamlit (księga, szczegóły faktury, przegląd kontroli, dokładność ekstrakcji)
- [x] Ewaluacja (próba 60 faktur): 14/14 anomalii, 60/60 kategoryzacji, 266/266 pól ekstrakcji (100%)
