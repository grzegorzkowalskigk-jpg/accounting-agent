"""EN: Invoice extraction (image to structure) with accuracy measured against the
ground truth; runs in replay mode when no API key is present.
PL: Ekstrakcja faktur (obraz na strukture) z pomiarem dokladnosci wobec danych
wzorcowych; bez klucza API dziala w trybie odtwarzania.

Usage / Uruchomienie: python scripts/extract_data.py --data data
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from accounting_agent.extract import (  # noqa: E402
    AnthropicVisionExtractor,
    ReplayExtractor,
    field_diff,
)
from accounting_agent.schema import Invoice  # noqa: E402


def main() -> None:
    """EN: Extracts every invoice and prints per-field accuracy.
    PL: Wyciaga dane z kazdej faktury i wypisuje dokladnosc per pole.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data", help="katalog z ground_truth.json i invoices/")
    ap.add_argument("--samples", default="samples/vision", help="katalog z ekstrakcjami (tryb replay)")
    ap.add_argument("--live", action="store_true", help="prawdziwa ekstrakcja Claude vision (wymaga klucza)")
    ap.add_argument("--out", default="data/extracted", help="dokąd zapisać ekstrakcje w trybie --live")
    args = ap.parse_args()

    data = Path(args.data)
    gt = {r["file"].split("/")[-1]: Invoice.model_validate(r["truth"])
          for r in json.loads((data / "ground_truth.json").read_text(encoding="utf-8"))}

    if args.live:
        extractor = AnthropicVisionExtractor()
        out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
        images = sorted((data / "invoices").glob("*.png"))
        print(f"Ekstrakcja LIVE (Claude vision) — {len(images)} faktur → {out}")
    else:
        extractor = ReplayExtractor(args.samples)
        images = [data / "invoices" / (p.stem + ".png") for p in sorted(Path(args.samples).glob("*.json"))]
        print(f"Ekstrakcja REPLAY — {len(images)} próbek zweryfikowanych wizją ({args.samples})")

    print(f"{'Plik':<16}{'Dokładność':<14}Rozbieżności")
    print("-" * 80)
    tot_matched = tot_fields = 0
    for img in images:
        pred = extractor.extract(img)
        if args.live:
            (Path(args.out) / (img.stem + ".json")).write_text(
                pred.model_dump_json(indent=2), encoding="utf-8")
        truth = gt.get(img.name)
        if truth is None:
            print(f"{img.name:<16}{'—':<14}(brak ground truth)")
            continue
        d = field_diff(pred, truth)
        tot_matched += d.matched
        tot_fields += d.total
        detail = "OK" if not d.mismatches else "; ".join(d.mismatches[:2])
        print(f"{img.name:<16}{d.matched}/{d.total} ({100 * d.accuracy:.0f}%){'':<3}{detail[:52]}")

    if tot_fields:
        print("-" * 80)
        print(f"RAZEM: {tot_matched}/{tot_fields} pól poprawnych "
              f"({100 * tot_matched / tot_fields:.1f}% dokładności pól)")


if __name__ == "__main__":
    main()
