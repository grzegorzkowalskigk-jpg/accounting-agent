# Changelog — accounting-agent

Rejestr błędów i poprawek. Bug and fix log.

## v1.0.0 (2026-07) — pierwsze wydanie / initial release

Naprawione / Fixed:

1. **Wykrywanie obcego formatu numeru dawało fałszywe alarmy** — formaty
   porównywane w całej paczce oznaczały jako podejrzanych kontrahentów, którzy
   po prostu numerują faktury inaczej. Porównanie zawężono do faktur tego
   samego NIP-u (`detect.py: find_format_mismatches`).
   *Number-format detection compared across the whole batch and flagged vendors
   who simply number differently; comparison is now scoped to the same tax id.*

2. **Zagraniczne numery VAT oblewały walidację NIP-u** — polska suma kontrolna
   nie ma do nich zastosowania; są odnotowywane, a nie zgłaszane jako błąd
   (`validate.py: check_nip`).
   *Foreign VAT numbers failed the Polish checksum; they are now annotated
   rather than reported as errors (`validate.py: check_nip`).*

3. **Komunikaty walidacji były nieczytelne dla człowieka** — techniczne
   prefiksy pól (`item[2].vat`) trafiały do księgi i dashboardu; `human_note()`
   tłumaczy problem na zdanie (`validate.py`).
   *Validation messages exposed technical field prefixes to the ledger and
   dashboard; `human_note()` renders them as sentences (`validate.py`).*

4. **Demo wymagało klucza API** — bez niego nie dało się pokazać ekstrakcji.
   Dodano backend odtwarzania na zweryfikowanych próbkach, dzięki czemu
   dashboard działa offline (`extract.py`, `app.py`).
   *The demo required an API key; a replay backend over verified samples lets
   the dashboard run offline (`extract.py`, `app.py`).*

5. **Porównanie kwot po dosłownej wartości zgłaszało różnice groszowe** —
   `field_diff()` i `_close()` porównują kwoty z tolerancją (`extract.py`,
   `validate.py`).
   *Literal amount comparison reported sub-cent differences; `field_diff()` and
   `_close()` compare within a tolerance.*
