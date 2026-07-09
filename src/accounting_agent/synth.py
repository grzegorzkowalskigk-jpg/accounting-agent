"""Generator syntetycznych faktur VAT: realistyczny obraz PNG + prawda (ground truth).

Wstrzykuje kontrolowane anomalie (duplikat numeru, błąd arytmetyczny, wartość odstająca),
żeby później było na czym testować walidację i wykrywanie anomalii agenta.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .schema import CATEGORIES, Invoice, LineItem

# ---------------------------------------------------------------- dane źródłowe
# (nazwa, NIP — stały na kontrahenta, adres)
SELLERS = [
    ("SoftForge Sp. z o.o.", "6772345198", "ul. Krzemowa 12, 30-001 Kraków"),
    ("BiuroMax S.A.", "5252248481", "al. Handlowa 88, 00-950 Warszawa"),
    ("PetroTrans Sp. z o.o.", "5832917640", "ul. Paliwowa 3, 80-200 Gdańsk"),
    ("NetCom Polska Sp. z o.o.", "8981726354", "ul. Światłowodowa 21, 50-100 Wrocław"),
    ("Kreatywni Sp. z o.o.", "7792483015", "ul. Reklamowa 7, 61-001 Poznań"),
    ("Nieruchomości Centrum Sp. z o.o.", "6762938471", "ul. Rynek 1, 31-042 Kraków"),
    ("Kancelaria Nowak i Wspólnicy", "5261048822", "ul. Prawna 15, 00-020 Warszawa"),
    ("TechSprzęt S.A.", "6342815907", "ul. Serwerowa 44, 40-001 Katowice"),
]
BUYER = ("GK Analytics Sp. z o.o.", "ul. Danych 10, 30-500 Kraków")

# katalog pozycji wg kategorii: (nazwa, jednostka, (min, max) ceny netto, stawka VAT)
CATALOG = {
    "Usługi IT i oprogramowanie": [
        ("Licencja oprogramowania (mies.)", "mies.", (80, 600), 0.23),
        ("Usługa wdrożeniowa", "godz.", (120, 320), 0.23),
        ("Hosting serwera VPS", "mies.", (40, 250), 0.23),
    ],
    "Materiały biurowe": [
        ("Papier ksero A4 (ryza)", "szt.", (18, 30), 0.23),
        ("Toner do drukarki", "szt.", (120, 380), 0.23),
        ("Zestaw długopisów", "opak.", (8, 25), 0.23),
    ],
    "Paliwo i transport": [
        ("Paliwo Diesel", "l", (5.8, 6.9), 0.23),
        ("Przewóz przesyłki", "szt.", (15, 60), 0.23),
    ],
    "Telekomunikacja": [
        ("Abonament telefoniczny", "mies.", (40, 120), 0.23),
        ("Internet światłowodowy", "mies.", (60, 180), 0.23),
    ],
    "Marketing i reklama": [
        ("Kampania reklamowa online", "usł.", (500, 3000), 0.23),
        ("Projekt graficzny", "godz.", (90, 200), 0.23),
    ],
    "Wynajem i media": [
        ("Wynajem powierzchni biurowej", "mies.", (1500, 6000), 0.23),
        ("Energia elektryczna", "usł.", (200, 900), 0.23),
    ],
    "Usługi księgowe i prawne": [
        ("Obsługa księgowa (mies.)", "mies.", (400, 1500), 0.23),
        ("Porada prawna", "godz.", (200, 500), 0.23),
    ],
    "Sprzęt i wyposażenie": [
        ("Laptop biznesowy", "szt.", (2800, 6500), 0.23),
        ("Monitor 27\"", "szt.", (700, 1600), 0.23),
        ("Krzesło biurowe", "szt.", (300, 1200), 0.23),
    ],
}


@dataclass
class Record:
    """Wpis w zbiorze: nazwa pliku, prawda i ewentualna wstrzyknięta anomalia."""
    file: str
    truth: Invoice
    injected_anomaly: str | None  # 'duplicate' | 'arithmetic' | 'outlier' | None


def _nip(rng: random.Random) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(10))


def _r2(x: float) -> float:
    return round(x + 1e-9, 2)


def _make_invoice(rng: random.Random, idx: int) -> tuple[Invoice, str]:
    seller_name, seller_nip, seller_addr = rng.choice(SELLERS)
    category = rng.choice(CATEGORIES)
    products = CATALOG[category]

    issue = date(2026, rng.randint(1, 6), rng.randint(1, 28))
    sale = issue - timedelta(days=rng.randint(0, 3))
    due = issue + timedelta(days=rng.choice([7, 14, 21, 30]))
    number = f"FV/{issue.year}/{issue.month:02d}/{idx + 1:04d}"

    items: list[LineItem] = []
    for _ in range(rng.randint(1, 4)):
        name, unit, (lo, hi), vr = rng.choice(products)
        qty = rng.choice([1, 1, 1, 2, 3]) if unit != "l" else rng.randint(20, 60)
        price = _r2(rng.uniform(lo, hi))
        net = _r2(price * qty)
        vat = _r2(net * vr)
        items.append(LineItem(description=name, quantity=qty, unit=unit, unit_price_net=price,
                              vat_rate=vr, net=net, vat=vat, gross=_r2(net + vat)))

    tnet = _r2(sum(i.net for i in items))
    tvat = _r2(sum(i.vat for i in items))
    inv = Invoice(
        invoice_number=number,
        issue_date=issue.isoformat(), sale_date=sale.isoformat(), due_date=due.isoformat(),
        seller_name=seller_name, seller_nip=seller_nip, seller_address=seller_addr,
        buyer_name=BUYER[0], buyer_nip="1234567890", buyer_address=BUYER[1],
        currency="PLN", items=items,
        total_net=tnet, total_vat=tvat, total_gross=_r2(tnet + tvat),
        payment_method=rng.choice(["Przelew", "Przelew", "Gotówka", "Karta"]),
        category=category,
    )
    return inv, category


# ------------------------------------------------------------------- rendering
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = "C:/Windows/Fonts/arial" + ("bd" if bold else "") + ".ttf"
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def _money(x: float) -> str:
    return f"{x:,.2f}".replace(",", " ").replace(".", ",")


def render(inv: Invoice, path: Path) -> None:
    W, H = 1000, 1400
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    fh, fb, fs, fss = _font(30, True), _font(15, True), _font(14), _font(12)
    ink, gray = (20, 20, 20), (110, 110, 110)
    M = 50

    d.text((M, 40), f"Faktura VAT {inv.invoice_number}", font=fh, fill=ink)
    d.text((M, 82), f"Data wystawienia: {inv.issue_date}", font=fss, fill=gray)
    d.text((M, 100), f"Data sprzedaży: {inv.sale_date}", font=fss, fill=gray)
    d.text((W - M - 230, 82), f"Termin płatności: {inv.due_date}", font=fss, fill=gray)
    d.text((W - M - 230, 100), f"Płatność: {inv.payment_method}", font=fss, fill=gray)
    d.line((M, 128, W - M, 128), fill=(200, 200, 200), width=1)

    # Sprzedawca / Nabywca
    def party(x: int, title: str, name: str, nip: str, addr: str) -> None:
        d.text((x, 150), title, font=fss, fill=gray)
        d.text((x, 170), name, font=fb, fill=ink)
        d.text((x, 192), f"NIP: {nip}", font=fs, fill=ink)
        d.text((x, 212), addr, font=fs, fill=ink)
    party(M, "SPRZEDAWCA", inv.seller_name, inv.seller_nip, inv.seller_address)
    party(W // 2 + 20, "NABYWCA", inv.buyer_name, inv.buyer_nip, inv.buyer_address)

    # Tabela pozycji
    cols = [(M, "Lp"), (M + 40, "Nazwa"), (500, "Ilość"), (575, "j.m."),
            (640, "Cena netto"), (745, "VAT"), (800, "Netto"), (900, "Brutto")]
    y = 270
    d.rectangle((M, y, W - M, y + 26), fill=(238, 238, 238))
    for x, label in cols:
        d.text((x + 4, y + 6), label, font=fss, fill=ink)
    y += 26
    for n, it in enumerate(inv.items, 1):
        row = [str(n), it.description[:38], _money(it.quantity), it.unit,
               _money(it.unit_price_net), f"{int(it.vat_rate * 100)}%", _money(it.net), _money(it.gross)]
        for (x, _), val in zip(cols, row):
            d.text((x + 4, y + 6), val, font=fs, fill=ink)
        y += 26
        d.line((M, y, W - M, y), fill=(225, 225, 225), width=1)

    # Podsumowanie
    y += 24
    xs = W - M - 260
    d.text((xs, y), "Razem netto:", font=fs, fill=ink); d.text((W - M - 130, y), f"{_money(inv.total_net)} zł", font=fs, fill=ink)
    d.text((xs, y + 24), "Razem VAT:", font=fs, fill=ink); d.text((W - M - 130, y + 24), f"{_money(inv.total_vat)} zł", font=fs, fill=ink)
    d.line((xs, y + 48, W - M, y + 48), fill=(180, 180, 180), width=1)
    d.text((xs, y + 56), "Do zapłaty:", font=fb, fill=ink); d.text((W - M - 150, y + 54), f"{_money(inv.total_gross)} zł", font=_font(18, True), fill=ink)

    d.text((M, H - 60), "Dokument wygenerowany syntetycznie do celów demonstracyjnych.", font=fss, fill=(170, 170, 170))
    img.save(path, "PNG")


# --------------------------------------------------------------------- publiczne
def generate(n: int, out_dir: str | Path, seed: int = 42) -> list[Record]:
    """Generuje n faktur (obrazy) + zwraca listę rekordów z ground truth.

    Gwarantuje po jednej z anomalii: duplikat numeru, błąd arytmetyczny brutto, wartość odstająca.
    """
    rng = random.Random(seed)
    out = Path(out_dir); (out / "invoices").mkdir(parents=True, exist_ok=True)

    base = [_make_invoice(rng, i)[0] for i in range(n)]

    # wybór, w które wstrzyknąć anomalie
    anomaly_of: dict[int, str] = {}
    picks = rng.sample(range(1, n), 5)
    anomaly_of[picks[0]] = "duplicate"
    anomaly_of[picks[1]] = "arithmetic"
    anomaly_of[picks[2]] = "outlier"
    anomaly_of[picks[3]] = "wrong_vat"
    anomaly_of[picks[4]] = "layout"

    records: list[Record] = []
    for i, inv in enumerate(base):
        anomaly = anomaly_of.get(i)
        if anomaly == "duplicate":
            # ten sam numer co inna, POPRAWNA faktura (klasyczny duplikat w obiegu)
            src = next(j for j in range(n) if j not in anomaly_of)
            inv.invoice_number = base[src].invoice_number
        elif anomaly == "arithmetic":
            # brutto nie zgadza się z netto+VAT (literówka / błąd w systemie) — reszta spójna
            inv.total_gross = _r2(inv.total_gross + rng.choice([10, 100, -50, 90]))
        elif anomaly == "outlier":
            # nienaturalnie wysoka, ale arytmetycznie SPÓJNA kwota (zawyżona cena jednostkowa)
            it = inv.items[0]
            it.unit_price_net = _r2(it.unit_price_net * 20)
            it.net = _r2(it.unit_price_net * it.quantity)
            it.vat = _r2(it.net * it.vat_rate)
            it.gross = _r2(it.net + it.vat)
            inv.total_net = _r2(sum(x.net for x in inv.items))
            inv.total_vat = _r2(sum(x.vat for x in inv.items))
            inv.total_gross = _r2(inv.total_net + inv.total_vat)
        elif anomaly == "wrong_vat":
            # zaniżona stawka VAT (8% zamiast 23%) — arytmetycznie spójna, ale błędna stawka
            it = inv.items[0]
            it.vat_rate = 0.08
            it.vat = _r2(it.net * it.vat_rate)
            it.gross = _r2(it.net + it.vat)
            inv.total_vat = _r2(sum(x.vat for x in inv.items))
            inv.total_gross = _r2(inv.total_net + inv.total_vat)
        elif anomaly == "layout":
            # ten sam kontrahent co inna, poprawna faktura, ale INNY format numeru (inny system)
            src = next(j for j in range(n) if j not in anomaly_of)
            inv.seller_name = base[src].seller_name
            inv.seller_nip = base[src].seller_nip
            inv.seller_address = base[src].seller_address
            inv.invoice_number = f"{inv.issue_date[:4]}-{rng.randint(10000, 99999)}"

        fname = f"inv_{i + 1:03d}.png"
        render(inv, out / "invoices" / fname)
        records.append(Record(file=f"invoices/{fname}", truth=inv, injected_anomaly=anomaly))

    return records
