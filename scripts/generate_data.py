"""EN: Generates a synthetic invoice set: PNG images plus ground_truth.json.
PL: Generuje zbior syntetycznych faktur: obrazy PNG oraz ground_truth.json.

Usage / Uruchomienie: python scripts/generate_data.py --n 12 --out data
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from accounting_agent.synth import generate  # noqa: E402


def main() -> None:
    """EN: Writes images and the ground truth file.
    PL: Zapisuje obrazy i plik danych wzorcowych.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60, help="liczba faktur")
    ap.add_argument("--out", type=str, default="data", help="katalog wyjściowy")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--per-type", type=int, default=None,
                    help="ile anomalii każdego rodzaju (domyślnie ~1 na 30 faktur)")
    args = ap.parse_args()

    records = generate(args.n, args.out, seed=args.seed, per_type=args.per_type)

    truth = [{"file": r.file, "injected_anomaly": r.injected_anomaly, "truth": r.truth.model_dump()}
             for r in records]
    gt_path = Path(args.out) / "ground_truth.json"
    gt_path.write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")

    anomalies = [(r.file, r.injected_anomaly) for r in records if r.injected_anomaly]
    print(f"Wygenerowano {len(records)} faktur -> {Path(args.out) / 'invoices'}")
    print(f"Ground truth -> {gt_path}")
    print("Wstrzyknięte anomalie:")
    for f, a in anomalies:
        print(f"  {f}: {a}")


if __name__ == "__main__":
    main()
