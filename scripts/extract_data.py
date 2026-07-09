"""Ekstrakcja faktur (obraz → struktura) + pomiar dokładności względem ground truth.

Domyślnie (bez klucza) działa w trybie REPLAY na próbkach zweryfikowanych wizją Claude
(samples/vision/) — pokazuje dokładność odczytu bez sieci:

    python scripts/extract_data.py

Tryb produkcyjny (Claude vision na wszystkich obrazach, wymaga ANTHROPIC_API_KEY):

    python scripts/extract_data.py --live --out data/extracted
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
