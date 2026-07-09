"""Dashboard demo agenta księgowego (Streamlit).

Uruchom:  streamlit run app.py

Działa BEZ klucza API: dane syntetyczne generują się deterministycznie, a weryfikacja
kontrahenta korzysta z mocka (OfflineProvider). Ekstrakcja wizją Claude jest pokazana na
próbkach zweryfikowanych wcześniej (samples/vision/) — w produkcji zastępuje ją
AnthropicVisionExtractor (patrz scripts/extract_data.py --live).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from accounting_agent.external import OfflineProvider  # noqa: E402
from accounting_agent.extract import ReplayExtractor, field_diff  # noqa: E402
from accounting_agent.ledger import summary, to_dataframe  # noqa: E402
from accounting_agent.pipeline import process  # noqa: E402
from accounting_agent.schema import Invoice  # noqa: E402
from accounting_agent.synth import generate  # noqa: E402

DATA = ROOT / "data"
SAMPLES = ROOT / "samples" / "vision"

st.set_page_config(page_title="Agent księgowy — demo", page_icon="🧾", layout="wide")


# ----------------------------------------------------------------- dane + pipeline
def load() -> tuple[list[dict], list[str], list[str | None]]:
    """Wczytuje (generuje przy pierwszym uruchomieniu) faktury i przepuszcza przez pipeline."""
    if not (DATA / "ground_truth.json").exists():
        with st.spinner("Generuję syntetyczne faktury…"):
            generate(18, DATA)
    gt = json.loads((DATA / "ground_truth.json").read_text(encoding="utf-8"))
    invoices = [Invoice.model_validate(r["truth"]) for r in gt]
    files = [r["file"].split("/")[-1] for r in gt]
    injected = [r["injected_anomaly"] for r in gt]
    rows = process(invoices, provider=OfflineProvider())
    return rows, files, injected


rows, files, injected = load()
s = summary(rows)

# ----------------------------------------------------------------- klasyfikacja detekcji
def _has_err(r: dict, *fields: str) -> bool:
    return any(i.severity == "error" and any(f in i.field for f in fields) for i in r["issues"])


# (ikona, nazwa, opis, źródło, predykat detekcji)
CONTROLS = [
    ("🧮", "Arytmetyka i zaokrąglenia", "netto×ilość, netto+VAT=brutto, sumy", "lokalne",
     lambda r: _has_err(r, "net", "vat", "gross", "total")),
    ("📊", "Właściwa stawka VAT", "np. 8% zamiast 23%", "lokalne",
     lambda r: any("vat_rate" in i.field for i in r["issues"])),
    ("🔢", "Suma kontrolna NIP (PL)", "błędna cyfra kontrolna NIP", "lokalne",
     lambda r: _has_err(r, "seller_nip", "buyer_nip")),
    ("📑", "Duplikat numeru", "ten sam numer faktury w paczce", "paczka",
     lambda r: "duplikat" in r["flags"]),
    ("📈", "Kwota odstająca", "rażąco wysoka wartość (IQR)", "paczka",
     lambda r: "kwota odstająca" in r["flags"]),
    ("🎭", "Zmiana layoutu kontrahenta", "znany NIP, inny format numeru", "paczka",
     lambda r: any("inny format" in f for f in r["flags"])),
    ("🏛️", "Biała lista VAT", "status podatnika VAT (rejestr MF)", "API zewn.",
     lambda r: bool(r["vat_note"])),
]

# ----------------------------------------------------------------- nagłówek + KPI
st.title("🧾 Agent księgowy")
st.caption("Od skanu faktury do zapisu w księdze: ekstrakcja (Claude vision) → walidacja → "
           "kategoryzacja → wykrywanie anomalii → weryfikacja w rejestrach. Człowiek kontroluje, nie przepisuje.")

k = st.columns(5)
k[0].metric("Faktury", s["count"])
k[1].metric("Do przeglądu", s["to_review"], help="Faktury z błędem, anomalią lub sygnałem z rejestru")
k[2].metric("Razem netto", f"{s['total_net']:,.0f} zł".replace(",", " "))
k[3].metric("Razem VAT", f"{s['total_vat']:,.0f} zł".replace(",", " "))
k[4].metric("Razem brutto", f"{s['total_gross']:,.0f} zł".replace(",", " "))

with st.sidebar:
    st.header("O demie")
    st.markdown(
        "- Dane **syntetyczne** (18 faktur, ziarno stałe)\n"
        "- Weryfikacja VAT: **mock offline** (bez sieci)\n"
        "- Ekstrakcja wizją: próbki `samples/vision/`\n"
        "- Produkcja: `AnthropicVisionExtractor` + `MFWhitelistProvider`"
    )
    caught = sum(1 for r, inj in zip(rows, injected) if inj)
    st.metric("Wstrzyknięte anomalie", caught)

tab_ledger, tab_inv, tab_ctrl, tab_extract = st.tabs(
    ["📒 Księga", "🔎 Faktura", "🛡️ Kontrole", "👁️ Ekstrakcja (vision)"])

# ----------------------------------------------------------------- 1. Księga
with tab_ledger:
    df = to_dataframe(rows)
    c1, c2 = st.columns([1, 2])
    flt = c1.radio("Pokaż", ["Wszystkie", "Tylko do przeglądu", "Tylko OK"], horizontal=False)
    cats = c2.multiselect("Kategorie", sorted(df["Kategoria"].unique()), default=[])
    view = df.copy()
    if flt == "Tylko do przeglądu":
        view = view[view["Status"] != "OK"]
    elif flt == "Tylko OK":
        view = view[view["Status"] == "OK"]
    if cats:
        view = view[view["Kategoria"].isin(cats)]

    sty = view.style.apply(
        lambda col: ["color:#b42318;font-weight:600" if v != "OK" else "color:#067647" for v in col],
        subset=["Status"])
    st.dataframe(sty, use_container_width=True, hide_index=True,
                 column_config={"Netto": st.column_config.NumberColumn(format="%.2f"),
                                "VAT": st.column_config.NumberColumn(format="%.2f"),
                                "Brutto": st.column_config.NumberColumn(format="%.2f")})
    st.download_button("⬇️ Pobierz księgę (CSV)", df.to_csv(index=False).encode("utf-8-sig"),
                       "ksiega.csv", "text/csv")

# ----------------------------------------------------------------- 2. Faktura (szczegóły)
with tab_inv:
    labels = [f"{files[i]} — {rows[i]['invoice'].invoice_number} [{rows[i]['status']}]" for i in range(len(rows))]
    idx = st.selectbox("Wybierz fakturę", range(len(rows)), format_func=lambda i: labels[i])
    r = rows[idx]
    inv = r["invoice"]
    left, right = st.columns([1, 1])
    img = DATA / "invoices" / files[idx]
    if img.exists():
        left.image(str(img), caption=files[idx], use_container_width=True)

    with right:
        badge = "🟢 OK" if r["status"] == "OK" else "🟠 DO PRZEGLĄDU"
        st.subheader(badge)
        st.write(f"**Sprzedawca:** {inv.seller_name}  \nNIP: {inv.seller_nip}")
        st.write(f"**Kategoria (agent):** {r['category']}  ·  pewność {r['category_conf']:.0%}")
        st.write(f"**Kwoty:** netto {inv.total_net:.2f} · VAT {inv.total_vat:.2f} · brutto {inv.total_gross:.2f} zł")

        items_df = pd.DataFrame([{
            "Nazwa": it.description, "Ilość": it.quantity, "Cena netto": it.unit_price_net,
            "VAT": f"{int(round(it.vat_rate * 100))}%", "Netto": it.net, "Brutto": it.gross,
        } for it in inv.items])
        st.dataframe(items_df, hide_index=True, use_container_width=True)

        if r["issues"] or r["flags"] or r["vat_note"]:
            st.markdown("**Sygnały agenta:**")
            for i in r["issues"]:
                (st.error if i.severity == "error" else st.warning)(f"[{i.field}] {i.message}")
            for f in r["flags"]:
                st.warning(f"🚩 {f}")
            if r["vat_note"]:
                st.error(f"🏛️ {r['vat_note']}")
        else:
            st.success("Brak zastrzeżeń — faktura spójna.")

# ----------------------------------------------------------------- 3. Kontrole
with tab_ctrl:
    st.markdown("Agent uruchamia **7 kontroli**. Poniżej: co sprawdza i które faktury zostały oznaczone.")
    for icon, name, desc, src, pred in CONTROLS:
        hit = [files[i] for i, r in enumerate(rows) if pred(r)]
        cols = st.columns([3, 1])
        cols[0].markdown(f"**{icon} {name}** — {desc}  \n<small>źródło: {src}</small>", unsafe_allow_html=True)
        cols[1].metric("Oznaczone", len(hit))
        if hit:
            cols[0].caption("· ".join(hit))
        st.divider()

# ----------------------------------------------------------------- 4. Ekstrakcja (vision)
with tab_extract:
    st.markdown("Ekstrakcja **obraz → struktura** przez Claude (vision). Poniżej próbki odczytane "
                "z obrazu i porównane z prawdą (ground truth) — pomiar wierności odczytu.")
    replay = ReplayExtractor(SAMPLES)
    gt_map = {files[i]: rows[i]["invoice"] for i in range(len(rows))}
    sample_files = sorted(p.stem + ".png" for p in SAMPLES.glob("*.json"))

    recs, tot_m, tot_t = [], 0, 0
    for fn in sample_files:
        pred = replay.extract(fn)
        truth = gt_map.get(fn)
        d = field_diff(pred, truth) if truth else None
        if d:
            tot_m += d.matched
            tot_t += d.total
        recs.append({"Plik": fn, "Pól poprawnych": f"{d.matched}/{d.total}" if d else "—",
                     "Dokładność": d.accuracy if d else None})

    st.metric("Dokładność ekstrakcji (pola)", f"{100 * tot_m / tot_t:.1f}%" if tot_t else "—",
              help=f"{tot_m}/{tot_t} pól na {len(sample_files)} próbkach")
    st.dataframe(pd.DataFrame(recs), hide_index=True, use_container_width=True,
                 column_config={"Dokładność": st.column_config.ProgressColumn(
                     format="%.0f%%", min_value=0, max_value=1)})

    pick = st.selectbox("Podgląd odczytu", sample_files)
    pred = replay.extract(pick)
    c1, c2 = st.columns([1, 1])
    p_img = DATA / "invoices" / pick
    if p_img.exists():
        c1.image(str(p_img), caption=f"Obraz: {pick}", use_container_width=True)
    c2.markdown("**Odczytane przez Claude (vision):**")
    c2.json(json.loads(pred.model_dump_json(exclude={"category"})))
