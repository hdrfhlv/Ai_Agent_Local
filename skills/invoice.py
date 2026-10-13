"""
Skill: Invoice Generator (PDF).

Kamu cukup kasih nama pembeli + daftar item (nama, harga, jumlah).
Subtotal, pajak, total, nomor invoice, dan tanggal dihitung otomatis,
lalu hasilnya disimpan sebagai PDF di folder `invoice/`.

Dependensi:  pip install reportlab

>>> GANTI DATA USAHA DI BAWAH (PENGATURAN) dengan data usaha kamu sendiri. <<<
"""

import json
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from PIL import Image, ImageChops
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

# ---------- PENGATURAN: edit sesuai usaha kamu ----------
PENGATURAN = {
    "nama_usaha": "KANTI",
    "tagline": "Karya Anugerah Tijarah | Partner Digital Anda",
    "nama_rekening": "KANTI",
    "no_rekening": "165433721 BCA An KANTI",         # contoh dari template, GANTI
    "penandatangan": "Priambodo Andi Assegaf",       # contoh dari template, GANTI
    "logo_path": "D:\\project_1\\logo\\logo kanti.jpeg",                        # opsional: path file logo (png/jpg)
    "tanda_tangan_path": "",                # opsional: path gambar tanda tangan (png transparan)
    "pajak_persen_default": 10,             # 10 = pajak 10%; isi 0 kalau tanpa pajak
    "pemisah_ribuan": ",",                  # "," -> RP 100,000   |   "." -> RP 100.000
    "folder_output": "invoice",
}

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
    "Agustus", "September", "Oktober", "November", "Desember",
]

# ---------- Ukuran layout (satuan poin, kertas A4) ----------
W, H = A4
LM, RM = 55, W - 55            # margin kiri / kanan teks
BAND_L, BAND_R = 40, W - 40    # lebar pita abu-abu baris
COL_HARGA_R = 335              # tepi kanan kolom HARGA
COL_JML_C = 400                # titik tengah kolom JML
ROW_H = 28
KET_MAX = 190                  # lebar maksimum teks keterangan
MAKS_ITEM = 200

ABU_BAND = 0.89
ABU_GARIS = 0.65


# ---------- Utilitas ----------
def _aman(teks) -> str:
    """Font bawaan PDF hanya mendukung Latin-1/cp1252; karakter lain diganti '?'."""
    return str(teks).encode("cp1252", "replace").decode("cp1252")


def _potong(teks, font: str, ukuran: float, lebar_maks: float) -> str:
    teks = _aman(teks)
    if stringWidth(teks, font, ukuran) <= lebar_maks:
        return teks
    while teks and stringWidth(teks + "...", font, ukuran) > lebar_maks:
        teks = teks[:-1]
    return teks.rstrip() + "..."


def _rupiah(n: int) -> str:
    s = f"{n:,}"
    sep = PENGATURAN["pemisah_ribuan"]
    if sep != ",":
        s = s.replace(",", sep)
    return f"RP {s}"


def _tanggal_panjang(d: date) -> str:
    return f"{HARI[d.weekday()]}, {d.day} {BULAN[d.month - 1]} {d.year}"


def parse_harga(teks) -> int:
    """
    Ubah teks harga jadi angka Rupiah utuh. Mendukung:
    '100000', '100.000', 'Rp 100.000', '100rb', '100k', '1,5jt', '2 juta'.
    """
    t = str(teks).lower().replace("rp", "").replace(" ", "")
    pengali = 1
    for akhiran, m in (("juta", 10**6), ("jt", 10**6), ("ribu", 1000), ("rb", 1000), ("k", 1000)):
        if t.endswith(akhiran):
            t, pengali = t[: -len(akhiran)], m
            break
    # Dengan akhiran (rb/jt) koma/titik dianggap desimal; tanpa akhiran dianggap pemisah ribuan
    t = t.replace(",", ".") if pengali > 1 else t.replace(".", "").replace(",", "")
    try:
        nilai = Decimal(t) * pengali
    except InvalidOperation:
        raise ValueError(f"Harga tidak valid: '{teks}'")
    if nilai < 0:
        raise ValueError("Harga tidak boleh negatif.")
    return int(nilai.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


_POLA_ITEM = re.compile(
    r"^(?P<nama>.+?)\s+(?P<harga>(?:rp\.?\s*)?\d[\d.,]*\s*(?:juta|jt|ribu|rb|k)?)"
    r"(?:\s*[x×]\s*(?P<jml>\d+))?$",
    re.IGNORECASE,
)


def parse_baris_item(teks: str) -> dict:
    """'kaos polo 120rb x2' -> {'keterangan': 'kaos polo', 'harga': 120000, 'jumlah': 2}"""
    m = _POLA_ITEM.match(teks.strip())
    if not m:
        raise ValueError("Formatnya: <nama> <harga> [x jumlah], contoh: kaos polo 120rb x2")
    return {
        "keterangan": m["nama"].strip(),
        "harga": parse_harga(m["harga"]),
        "jumlah": int(m["jml"]) if m["jml"] else 1,
    }


def _validasi_item(items) -> list[tuple[str, int, int]]:
    if not isinstance(items, list) or not items:
        raise ValueError("Daftar item kosong. Isi minimal 1 item.")
    if len(items) > MAKS_ITEM:
        raise ValueError(f"Maksimal {MAKS_ITEM} item per invoice.")
    hasil = []
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict):
            raise ValueError(f"Item #{i} formatnya salah.")
        ket = str(it.get("keterangan", "")).strip()
        if not ket:
            raise ValueError(f"Item #{i}: keterangan tidak boleh kosong.")
        if "harga" not in it or it["harga"] in (None, ""):
            raise ValueError(f"Item #{i} ('{ket}'): harga belum diisi.")
        harga = it["harga"]
        harga = parse_harga(harga) if isinstance(harga, str) else int(round(float(harga)))
        if harga < 0:
            raise ValueError(f"Item #{i} ('{ket}'): harga tidak boleh negatif.")
        jml_mentah = it.get("jumlah", 1)
        if jml_mentah in (None, ""):  # kosong -> default 1 (0 tetap ditolak di bawah)
            jml_mentah = 1
        try:
            jml_f = float(jml_mentah)
        except (TypeError, ValueError):
            raise ValueError(f"Item #{i} ('{ket}'): jumlah harus angka.")
        if jml_f < 1 or jml_f != int(jml_f):
            raise ValueError(f"Item #{i} ('{ket}'): jumlah harus bilangan bulat >= 1.")
        hasil.append((ket, harga, int(jml_f)))
    return hasil


def _hitung(items, persen) -> tuple[int, int, int]:
    subtotal = sum(h * j for _, h, j in items)
    pajak = int(
        (Decimal(subtotal) * Decimal(str(persen)) / 100).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    return subtotal, pajak, subtotal + pajak


def _baca_counter(folder: Path) -> int:
    try:
        return int(json.loads((folder / "counter.json").read_text())["terakhir"])
    except (OSError, ValueError, KeyError, TypeError):
        return 0


def _tulis_counter(folder: Path, n: int) -> None:
    (folder / "counter.json").write_text(json.dumps({"terakhir": n}))


# ---------- Menggambar PDF ----------
def _gambar_logo(c, cx: float, cy: float) -> None:
    path = PENGATURAN["logo_path"]
    if path and Path(path).exists():
        with Image.open(path) as source:
            image = source.convert("RGB")
        background = Image.new(image.mode, image.size, image.getpixel((0, 0)))
        batas = ImageChops.difference(image, background).getbbox()
        if batas is None:
            raise ValueError(f"Logo tidak memiliki area gambar yang terlihat: {path}")

        left, top, right, bottom = batas
        padding = int(max(right - left, bottom - top) * 0.04)
        batas = (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
        image = image.crop(batas)
        iw, ih = image.size
        ukuran = 46
        skala = ukuran / max(iw, ih)
        lebar, tinggi = iw * skala, ih * skala
        c.drawImage(ImageReader(image), cx - lebar / 2, cy - tinggi / 2,
                    lebar, tinggi, mask="auto")
        return
    # Logo bawaan: tiga persegi bertumpuk diputar 45 derajat
    c.saveState()
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    c.setLineWidth(2.2)
    c.translate(cx, cy)
    c.rotate(45)
    for s in (30, 20, 10):
        c.rect(-s / 2, -s / 2, s, s, stroke=1, fill=0)
    c.restoreState()


def _kepala_tabel(c, y: float) -> None:
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(LM, y, "KETERANGAN")
    c.drawRightString(COL_HARGA_R, y, "HARGA")
    c.drawCentredString(COL_JML_C, y, "JML")
    c.drawRightString(RM, y, "TOTAL")


def _halaman_pertama(c, nomor: str, tgl: date, kepada: str, email: str) -> float:
    cfg = PENGATURAN
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 38)
    c.drawString(LM, H - 95, "INVOICE")

    _gambar_logo(c, RM - 24, H - 82)
    c.setFont("Helvetica-Bold", 15)
    c.drawRightString(RM - 62, H - 80, _potong(cfg["nama_usaha"].upper(), "Helvetica-Bold", 15, 240))
    c.setFont("Helvetica", 10)
    c.drawRightString(RM - 62, H - 96, _potong(cfg["tagline"], "Helvetica", 10, 240))

    c.setLineWidth(0.8)
    c.line(LM, H - 125, RM, H - 125)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(LM, H - 160, "KEPADA :")
    c.drawRightString(RM, H - 160, "TANGGAL :")
    c.drawRightString(RM, H - 206, "NO INVOICE :")
    c.setFont("Helvetica", 10)
    c.drawString(LM, H - 176, _potong(kepada, "Helvetica", 10, 260))
    if email:
        c.drawString(LM, H - 190, _potong(email, "Helvetica", 10, 260))
    c.drawRightString(RM, H - 176, _tanggal_panjang(tgl))
    c.drawRightString(RM, H - 222, _aman(nomor))

    _kepala_tabel(c, H - 262)
    return H - 276  # y atas baris pertama


def _halaman_lanjutan(c, nomor: str) -> float:
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(LM, H - 60, f"INVOICE {_aman(nomor)} (lanjutan)")
    _kepala_tabel(c, H - 95)
    return H - 109


def _baris(c, y_top: float, ket, harga, jml, pakai_garis: bool) -> None:
    c.setFillColorRGB(ABU_BAND, ABU_BAND, ABU_BAND)
    c.rect(BAND_L, y_top - ROW_H, BAND_R - BAND_L, ROW_H, stroke=0, fill=1)
    if pakai_garis:
        c.setStrokeColorRGB(ABU_GARIS, ABU_GARIS, ABU_GARIS)
        c.setLineWidth(0.6)
        c.line(BAND_L, y_top, BAND_R, y_top)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont("Helvetica", 9)
    yt = y_top - ROW_H / 2 - 3
    c.drawString(LM, yt, _potong(ket.upper(), "Helvetica", 9, KET_MAX))
    c.drawRightString(COL_HARGA_R, yt, _rupiah(harga))
    c.drawCentredString(COL_JML_C, yt, str(jml))
    c.drawRightString(RM, yt, _rupiah(harga * jml))


def _ringkasan_pembayaran(c, y_top: float, subtotal, pajak, total) -> None:
    cfg = PENGATURAN
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(LM, y_top, "PEMBAYARAN :")
    c.setFont("Helvetica", 9)
    c.drawString(LM, y_top - 16, _potong(f"Nama : {cfg['nama_rekening']}", "Helvetica", 9, 220))
    c.drawString(LM, y_top - 30, _potong(f"No Rek : {cfg['no_rekening']}", "Helvetica", 9, 220))

    x_label = 440
    c.setFont("Helvetica", 9)
    c.drawRightString(x_label, y_top, "SUB TOTAL :")
    c.drawRightString(RM, y_top, _rupiah(subtotal))
    c.drawRightString(x_label, y_top - 17, "PAJAK :")
    c.drawRightString(RM, y_top - 17, _rupiah(pajak))
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(x_label, y_top - 36, "TOTAL :")
    c.drawRightString(RM, y_top - 36, _rupiah(total))


def _penutup(c) -> None:
    cfg = PENGATURAN
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(LM, 100, "TERIMAKASIH ATAS")
    c.drawString(LM, 87, "PEMBELIAN ANDA")

    xc = RM - 80
    ttd = cfg["tanda_tangan_path"]
    if ttd and Path(ttd).exists():
        img = ImageReader(ttd)
        iw, ih = img.getSize()
        skala = min(120 / iw, 50 / ih)
        c.drawImage(img, xc - iw * skala / 2, 100, iw * skala, ih * skala, mask="auto")
    else:
        c.setFont("Times-Italic", 24)
        c.drawCentredString(xc, 106, _potong(cfg["penandatangan"], "Times-Italic", 24, 170))
    c.setLineWidth(0.8)
    c.line(xc - 82, 98, xc + 82, 98)
    c.setFont("Helvetica", 10)
    c.drawCentredString(xc, 82, _potong(cfg["penandatangan"], "Helvetica", 10, 170))


def _bagi_halaman(n: int) -> list[int]:
    """
    Tentukan jumlah baris per halaman. Halaman terakhir harus muat blok pembayaran
    + tanda tangan (butuh sisa ruang ~230pt); kalau baris terakhir mepet, sebagian
    baris dipindah supaya total/tanda tangan tidak sendirian di halaman baru.
    """
    hasil, sisa, pertama = [], n, True
    while sisa > 0:
        y_awal = (H - 276) if pertama else (H - 109)
        muat_penuh = int((y_awal - 60) // ROW_H)
        muat_dgn_footer = int((y_awal - 28 - 55 - 145) // ROW_H)
        if sisa <= muat_dgn_footer:
            ambil = sisa
        elif sisa <= muat_penuh:
            ambil = sisa - 1  # sisakan 1 baris untuk halaman berikut agar footer ikut
        else:
            ambil = muat_penuh
        hasil.append(ambil)
        sisa -= ambil
        pertama = False
    return hasil


def _tulis_pdf(path: Path, nomor, tgl, kepada, email, items, subtotal, pajak, total) -> int:
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(f"Invoice {nomor}")
    c.setAuthor(_aman(PENGATURAN["nama_usaha"]))

    pembagian = _bagi_halaman(len(items))
    idx, y = 0, 0.0
    for nomor_hal, jumlah_baris in enumerate(pembagian):
        if nomor_hal == 0:
            y = _halaman_pertama(c, nomor, tgl, kepada, email)
        else:
            c.showPage()
            y = _halaman_lanjutan(c, nomor)
        for k in range(jumlah_baris):
            ket, harga, jml = items[idx]
            _baris(c, y, ket, harga, jml, pakai_garis=k > 0)
            y -= ROW_H
            idx += 1

    _ringkasan_pembayaran(c, y - 30, subtotal, pajak, total)
    _penutup(c)
    c.save()
    return len(pembagian)


# ---------- Fungsi publik (dipakai AI dan perintah manual) ----------
def buat_invoice(
    kepada: str,
    items: list,
    email: str = "",
    pajak_persen: float | None = None,
    tanggal: str = "",
) -> dict:
    try:
        if not str(kepada).strip():
            return {"ok": False, "error": "Nama pembeli (kepada) belum diisi."}
        daftar = _validasi_item(items)

        persen = PENGATURAN["pajak_persen_default"] if pajak_persen is None else pajak_persen
        try:
            if not 0 <= Decimal(str(persen)) <= 100:
                raise ValueError
        except (InvalidOperation, ValueError):
            return {"ok": False, "error": "Pajak harus angka antara 0 sampai 100 (persen)."}

        if tanggal:
            try:
                tgl = date.fromisoformat(str(tanggal).strip())
            except ValueError:
                return {"ok": False, "error": "Format tanggal harus YYYY-MM-DD, contoh 2026-10-13."}
        else:
            tgl = date.today()

        folder = Path(PENGATURAN["folder_output"])
        folder.mkdir(parents=True, exist_ok=True)
        urut = _baca_counter(folder) + 1
        nomor = f"{urut:03d}/{tgl:%d/%m/%Y}"
        slug = re.sub(r"[^A-Za-z0-9]+", "-", str(kepada)).strip("-")[:30] or "pelanggan"
        path = folder / f"invoice_{urut:03d}_{slug}.pdf"

        subtotal, pajak, total = _hitung(daftar, persen)
        halaman = _tulis_pdf(path, nomor, tgl, str(kepada).strip(), str(email or "").strip(),
                             daftar, subtotal, pajak, total)
        _tulis_counter(folder, urut)  # nomor baru terpakai hanya kalau PDF berhasil dibuat

        return {
            "ok": True,
            "nomor_invoice": nomor,
            "kepada": str(kepada).strip(),
            "jumlah_item": len(daftar),
            "halaman": halaman,
            "pajak_persen": float(persen),
            "subtotal": subtotal,
            "pajak": pajak,
            "total": total,
            "total_format": _rupiah(total),
            "file": str(path),
        }
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"Gagal membuat invoice: {e}"}


# ---------- Skema tool untuk AI (format sama dengan ACTIVE_TOOL_SCHEMAS di scrapper) ----------
INVOICE_TOOL_SCHEMAS = [
    {
        "name": "buat_invoice",
        "description": (
            "Membuat invoice PDF untuk satu pembeli. Subtotal, pajak, total, nomor invoice, "
            "dan tanggal dihitung otomatis oleh tool; JANGAN dihitung manual. Harga harus "
            "sudah berupa angka Rupiah utuh (contoh: 100rb -> 100000). Kalau user belum "
            "menyebut nama pembeli atau harga suatu item, tanyakan dulu; jangan mengarang."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kepada": {"type": "string", "description": "Nama pembeli."},
                "email": {
                    "type": ["string", "null"],
                    "description": "Email pembeli (opsional; boleh null atau dihilangkan).",
                },
                "items": {
                    "type": "array",
                    "description": "Daftar barang/jasa yang ditagihkan.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "keterangan": {"type": "string", "description": "Nama barang/jasa."},
                            "harga": {"type": "integer", "description": "Harga satuan dalam Rupiah, contoh 100000."},
                            "jumlah": {"type": "integer", "description": "Jumlah barang, default 1."},
                        },
                        "required": ["keterangan", "harga"],
                    },
                },
                "pajak_persen": {
                    "type": ["number", "null"],
                    "description": "Persentase pajak. null atau dihilangkan untuk pakai default; isi 0 kalau tanpa pajak.",
                },
                "tanggal": {
                    "type": ["string", "null"],
                    "description": "Tanggal invoice format YYYY-MM-DD. null atau dihilangkan untuk pakai hari ini.",
                },
            },
            "required": ["kepada", "items"],
        },
    }
]