"""Budowa księgi z przetworzonych faktur + eksport i podsumowanie."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .schema import Invoice


def to_dataframe(rows: list[dict]) -> pd.DataFrame:
    """rows: lista dictów z pipeline.process() (invoice + category + status + flags)."""
    recs = []
    for r in rows:
        inv: Invoice = r["invoice"]
        recs.append({
            "Numer": inv.invoice_number,
            "Data": inv.issue_date,
            "Sprzedawca": inv.seller_name,
            "NIP": inv.seller_nip,
            "Netto": inv.total_net,
            "VAT": inv.total_vat,
            "Brutto": inv.total_gross,
            "Kategoria": r["category"],
            "Status": r["status"],
            "Uwagi": "; ".join(r["notes"]) if r["notes"] else "",
        })
    return pd.DataFrame(recs)


def export(df: pd.DataFrame, out_dir: str | Path) -> dict[str, str]:
    """Zapisuje księgę do CSV i XLSX. Zwraca ścieżki."""
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    csv_p, xlsx_p = out / "ksiega.csv", out / "ksiega.xlsx"
    df.to_csv(csv_p, index=False, encoding="utf-8-sig")
    try:
        df.to_excel(xlsx_p, index=False)
    except Exception:  # openpyxl brak — CSV wystarcza
        xlsx_p = None
    return {"csv": str(csv_p), "xlsx": str(xlsx_p) if xlsx_p else ""}


def summary(rows: list[dict]) -> dict:
    """Zagregowane liczby: sumy, podział wg kategorii, liczba faktur do przeglądu."""
    total_net = sum(r["invoice"].total_net for r in rows)
    total_vat = sum(r["invoice"].total_vat for r in rows)
    total_gross = sum(r["invoice"].total_gross for r in rows)
    by_cat: dict[str, float] = {}
    for r in rows:
        by_cat[r["category"]] = round(by_cat.get(r["category"], 0.0) + r["invoice"].total_net, 2)
    review = sum(1 for r in rows if r["status"] != "OK")
    return {
        "count": len(rows),
        "total_net": round(total_net, 2),
        "total_vat": round(total_vat, 2),
        "total_gross": round(total_gross, 2),
        "to_review": review,
        "by_category": dict(sorted(by_cat.items(), key=lambda kv: -kv[1])),
    }
