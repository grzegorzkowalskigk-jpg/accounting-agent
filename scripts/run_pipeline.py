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
    rows = process(invoices)

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

    # --- ewaluacja: czy złapaliśmy wstrzyknięte anomalie? ---
    print("\nEWALUACJA WYKRYWANIA ANOMALII")
    ok = total = 0
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
        )
        ok += caught
        total += 1
        print(f"  {r_gt['file']:<22} wstrzyknięto={inj:<12} -> {'ZŁAPANE' if caught else 'PRZEOCZONE'}")
    print(f"  Wynik: {ok}/{total} anomalii wykrytych")


if __name__ == "__main__":
    main()
