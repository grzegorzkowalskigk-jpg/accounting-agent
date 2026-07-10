"""Uruchamia pipeline na wygenerowanych fakturach (ground truth), drukuje raport,
eksportuje księgę i sprawdza, czy złapaliśmy wstrzyknięte anomalie.

    python scripts/run_pipeline.py --data data --out out
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from accounting_agent.external import OfflineProvider  # noqa: E402
from accounting_agent.ledger import export, summary, to_dataframe  # noqa: E402
from accounting_agent.pipeline import process  # noqa: E402
from accounting_agent.schema import Invoice  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    gt = json.loads((Path(args.data) / "ground_truth.json").read_text(encoding="utf-8"))
    invoices = [Invoice.model_validate(r["truth"]) for r in gt]
    # Provider offline (mock) — całe demo działa bez sieci; w produkcji: MFWhitelistProvider().
    rows = process(invoices, provider=OfflineProvider())

    # --- raport per faktura ---
    print(f"{'Numer':<20}{'Kategoria':<30}{'Status':<14}Uwagi")
    print("-" * 100)
    for r in rows:
        inv = r["invoice"]
        note = r["notes"][0] if r["notes"] else ""
        print(f"{inv.invoice_number:<20}{r['category'][:28]:<30}{r['status']:<14}{note[:44]}")

    # --- podsumowanie ---
    s = summary(rows)
    print("\nPODSUMOWANIE")
    print(f"  Faktur: {s['count']} · do przeglądu: {s['to_review']}")
    print(f"  Netto: {s['total_net']:.2f} · VAT: {s['total_vat']:.2f} · Brutto: {s['total_gross']:.2f} PLN")
    print("  Koszty wg kategorii (netto):")
    for cat, val in s["by_category"].items():
        print(f"    {cat:<32} {val:>12.2f}")

    # --- eksport księgi ---
    paths = export(to_dataframe(rows), args.out)
    print(f"\nKsięga: {paths['csv']}" + (f" · {paths['xlsx']}" if paths["xlsx"] else ""))

    # --- ewaluacja kategoryzacji (predykcja regułowa vs prawda) ---
    correct = sum(1 for r_gt, r in zip(gt, rows) if r["category"] == r_gt["truth"].get("category"))
    print(f"\nKATEGORYZACJA (baseline regułowy): {correct}/{len(rows)} zgodnych z prawdą ({100 * correct // len(rows)}%)")

    # --- ewaluacja: czy złapaliśmy wstrzyknięte anomalie? (nasz „klucz odpowiedzi") ---
    from collections import defaultdict
    print("\nEWALUACJA WYKRYWANIA ANOMALII (per rodzaj)")
    stat: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # typ -> [wykryte, wszystkie]
    misses: list[tuple[str, str]] = []
    for r_gt, r in zip(gt, rows):
        inj = r_gt["injected_anomaly"]
        if not inj:
            continue
        errs = any(i.severity == "error" for i in r["issues"])
        vat_warn = any("vat_rate" in i.field and i.severity == "warning" for i in r["issues"])
        caught = (
            (inj == "arithmetic" and errs)
            or (inj == "duplicate" and "duplikat" in r["flags"])
            or (inj == "outlier" and "kwota odstająca" in r["flags"])
            or (inj == "wrong_vat" and vat_warn)
            or (inj == "layout" and any("inny format" in f for f in r["flags"]))
            or (inj == "bad_nip" and any(i.field == "seller_nip" and i.severity == "error" for i in r["issues"]))
            or (inj == "vat_inactive" and bool(r["vat_note"]))
        )
        stat[inj][0] += int(caught)
        stat[inj][1] += 1
        if not caught:
            misses.append((r_gt["file"], inj))
    for inj in sorted(stat):
        c, t = stat[inj]
        print(f"  {inj:<14} {c}/{t} {'OK' if c == t else 'BRAKI'}")
    for f, inj in misses:
        print(f"  PRZEOCZONE: {f} ({inj})")
    ok = sum(v[0] for v in stat.values())
    total = sum(v[1] for v in stat.values())
    print(f"  RAZEM: {ok}/{total} anomalii wykrytych")


if __name__ == "__main__":
    main()
