# ---------- Import dan konfigurasi ----------
import os
import json
import getpass
from dotenv import load_dotenv

load_dotenv()  # dipanggil sebelum import skills, kalau-kalau skills membaca .env

from groq import Groq
from skills.scrapper import (
    ACTIVE_TOOL_SCHEMAS,
    analyze_scraped_data,
    scrape_products,
)
from skills.invoice import (
    INVOICE_TOOL_SCHEMAS,
    buat_invoice,
    parse_baris_item,
)
from skills.password import (
    ambil_password,
    buat_password,
    buka_vault,
    daftar_layanan,
    hapus_password,
    kunci_vault,
    simpan_password,
    vault_ada,
    vault_terbuka,
)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "openai/gpt-oss-20b"


# ---------- Daftar fungsi dan skema tool untuk AI ----------
# CATATAN: skill password SENGAJA tidak didaftarkan di sini. Kalau didaftarkan,
# password dan isi vault ikut terkirim ke server model. Skill password hanya
# bisa dipakai lewat perintah manual di loop utama (pakai getpass, tidak masuk
# ke riwayat percakapan AI).
TOOL_FUNCS = {
    "scrape_products": scrape_products,
    "analyze_scraped_data": analyze_scraped_data,
    "buat_invoice": buat_invoice,
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": schema["name"],
            "description": schema["description"],
            "parameters": schema["input_schema"],
        },
    }
    for schema in [*ACTIVE_TOOL_SCHEMAS, *INVOICE_TOOL_SCHEMAS]
]

# ---------- Instruksi awal dan riwayat percakapan ----------
messages = [
    {
        "role": "system",
        "content": """
        Kamu adalah AI assistant yang ngobrol dengan gaya bahasa Indonesia
        yang gaul, santai, natural, dan friendly.

        Gunakan bahasa sehari-hari seperti gue, lu, wkwk, nah, oke, sip,
        jika memang cocok dengan konteks.

        Jangan terlalu formal seperti buku atau robot.
        Jawaban harus jelas, membantu, dan tidak berlebihan.

        Kamu punya tool scrape_products untuk mengambil nama, harga jika
        tersedia, dan tautan produk dari katalog publik, mengikuti halaman
        berikutnya sampai jumlah maksimum tercapai atau halaman habis, lalu
        menyimpannya ke Excel.
        Tool memerlukan URL lengkap; tool tidak menerima kata kunci pencarian.
        Setiap scrape otomatis menambahkan statistik dan diagram ke sheet
        Analisis dalam workbook yang sama. Jelaskan juga temuan dari ringkasan
        statistik yang dikembalikan tool.

        Kamu juga punya tool analyze_scraped_data untuk menganalisis file Excel
        hasil scrape, menambahkan statistik dan diagram ke sheet Analisis, dan
        mempertahankan sheet data sumber. Kalau user meminta analisis hasil
        scrape tanpa menyebut nama file, gunakan hasil_scraping.xlsx.

        Setelah tool selesai:
        - Kalau ok = true, kasih tau jumlah produk, jumlah halaman, dan lokasi file.
        - Untuk analisis, jelaskan ringkasan hasil dan nama sheet diagramnya.
        - Kalau ok = false, jelasin errornya apa adanya. JANGAN bilang
          berhasil kalau gagal atau jumlah produknya 0.

        Kamu juga punya tool buat_invoice untuk membuat invoice PDF. Cukup
        butuh nama pembeli dan daftar item (nama, harga, jumlah). Aturannya:
        - Ubah singkatan harga jadi angka Rupiah utuh sebelum memanggil tool
          (100rb atau 100k = 100000, 1,5jt = 1500000).
        - Jumlah default 1 kalau user tidak menyebutkan.
        - Pajak pakai default tool kalau user tidak menyebutnya; kalau user
          bilang tanpa pajak, kirim pajak_persen = 0.
        - Kalau nama pembeli atau harga salah satu item belum disebut, TANYA
          dulu. Jangan mengarang nama atau harga.
        - JANGAN menghitung subtotal, pajak, atau total sendiri; tool yang
          menghitung. Setelah ok = true, sebutkan nomor invoice, total, dan
          lokasi file PDF-nya.

        Soal password: kamu TIDAK punya akses ke brankas password user dan
        tidak boleh menyimpan atau mengingat password. Kalau user minta
        nyimpen/ngambil password, arahkan ke perintah manual: "simpan password",
        "lihat password <layanan>", "daftar password", "hapus password <layanan>",
        "generate password [panjang]", dan "kunci vault". Ingatkan juga untuk
        JANGAN mengetik password langsung di chat dengan kamu.
        """,
    }
]


# ---------- Menampilkan hasil scrape dan analisis ----------
def print_scrape_result(hasil: dict, label_jumlah: str = "Jumlah data"):
    if hasil.get("ok"):
        print("\nAI: Berhasil brok!")
        print(f"{label_jumlah:<14}:", hasil["jumlah"])
        if hasil.get("halaman") is not None:
            print("Halaman       :", hasil["halaman"])
        if hasil.get("lembar_analisis"):
            print("Sheet analisis:", hasil["lembar_analisis"])
            print("Diagram       :", hasil["diagram"])
            for item in hasil.get("ringkasan", []):
                if "rata_rata" in item:
                    print(
                        f"{item['kolom']}: rata-rata {item['rata_rata']:.2f}, "
                        f"median {item['median']:.2f}, rentang "
                        f"{item['minimum']:.2f}–{item['maksimum']:.2f}"
                    )
                elif item.get("kategori_teratas"):
                    teratas = item["kategori_teratas"][0]
                    print(
                        f"{item['kolom']}: kategori terbanyak "
                        f"{teratas['kategori']} ({teratas['jumlah']})"
                    )
        print("File Excel    :", hasil["file"])
        if hasil.get("catatan"):
            print("Catatan       :", hasil["catatan"])
    else:
        print("\nAI: Gagal scrape:", hasil.get("error", "alasan tidak diketahui"))


# ---------- Meringkas hasil tool untuk dikirim ke AI ----------
def ringkas_hasil(result: dict, batas: int = 3000) -> str:
    """
    Hasil tool dikirim balik ke model. Kalau terlalu besar (misal berisi
    ratusan produk), pangkas supaya tidak menghabiskan token / kena rate limit.
    Data lengkap tetap aman di file Excel.
    """
    teks = json.dumps(result, ensure_ascii=False)
    if len(teks) <= batas:
        return teks
    ringkas = {
        k: v for k, v in result.items()
        if isinstance(v, (str, int, float, bool, type(None)))
    }
    ringkas["catatan_sistem"] = "Detail lengkap sudah ada di file Excel; hasil dipangkas."
    return json.dumps(ringkas, ensure_ascii=False)[:batas]


# ---------- Menjalankan tool yang diminta AI ----------
def jalankan_tool(tc) -> dict:
    func = TOOL_FUNCS.get(tc.function.name)
    if func is None:
        return {"ok": False, "error": f"Tool tidak dikenal: {tc.function.name}"}
    try:
        args = json.loads(tc.function.arguments or "{}")
        print(f"\nAI: Lagi jalanin {tc.function.name}...")
        return func(**args)
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------- Mengelola percakapan AI dan pemanggilan tool ----------
def chat_with_tools():
    """Panggil model; kalau model minta tool, jalankan lalu lanjutkan."""
    for _ in range(5):  # batas putaran biar nggak loop terus
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        # Model tidak minta tool -> ini jawaban final
        if not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content or ""})
            return msg.content

        # Simpan permintaan tool dari model
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        # Jalankan tiap tool, kirim hasilnya balik ke model
        for tc in msg.tool_calls:
            result = jalankan_tool(tc)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": ringkas_hasil(result),
                }
            )

    return "Waduh, kebanyakan putaran nih, coba ulangi ya."


# ---------- Password vault (perintah manual, tidak lewat AI) ----------
PERINTAH_PASSWORD = (
    "simpan password",
    "lihat password",
    "daftar password",
    "hapus password",
    "generate password",
    "kunci vault",
)


def pastikan_vault_terbuka() -> bool:
    """Minta master password (lewat getpass) kalau vault masih terkunci."""
    if vault_terbuka():
        return True

    if not vault_ada():
        print("\nAI: Vault belum ada, kita bikin dulu ya.")
        print("    Master password TIDAK disimpan di mana pun dan nggak bisa")
        print("    dipulihkan, jadi jangan sampai lupa.")
        for _ in range(3):
            m1 = getpass.getpass("Buat master password: ")
            m2 = getpass.getpass("Ulangi master password: ")
            if m1 != m2:
                print("AI: Dua-duanya nggak sama, coba lagi.")
                continue
            hasil = buka_vault(m1)
            if hasil["ok"]:
                print("AI: Vault berhasil dibuat.")
                return True
            print("AI:", hasil["error"])
        return False

    for _ in range(3):
        hasil = buka_vault(getpass.getpass("Master password: "))
        if hasil["ok"]:
            print(f"AI: Vault kebuka ({hasil['jumlah']} password tersimpan).")
            return True
        print("AI:", hasil["error"])
    print("AI: Kebanyakan salah, coba lagi nanti.")
    return False


def tangani_perintah_password(pertanyaan: str) -> bool:
    """Return True kalau input adalah perintah password (sudah ditangani di sini)."""
    kecil = pertanyaan.lower()
    cmd = next(
        (c for c in PERINTAH_PASSWORD if kecil == c or kecil.startswith(c + " ")),
        None,
    )
    if cmd is None:
        return False
    arg = pertanyaan[len(cmd):].strip()

    # --- generate password: tidak butuh vault ---
    if cmd == "generate password":
        try:
            panjang = int(arg) if arg else 16
        except ValueError:
            print("AI: Formatnya: generate password [panjang], contoh: generate password 20")
            return True
        hasil = buat_password(panjang)
        if hasil["ok"]:
            print("\nPassword acak:", hasil["password"], "\n")
        else:
            print("AI:", hasil["error"])
        return True

    # --- kunci vault ---
    if cmd == "kunci vault":
        kunci_vault()
        print("AI: Vault dikunci. Nanti diminta master password lagi.")
        return True

    # Sisanya butuh vault terbuka
    if not pastikan_vault_terbuka():
        return True

    if cmd == "simpan password":
        layanan = arg or input("Nama layanan (misal: Gmail): ").strip()
        if not layanan:
            print("AI: Nama layanan nggak boleh kosong.")
            return True
        username = input("Username / email: ").strip()
        password = getpass.getpass("Password (kosongin = dibuatin otomatis): ")
        dibuat_otomatis = not password
        if dibuat_otomatis:
            password = buat_password(16)["password"]
        catatan = input("Catatan (opsional): ").strip()

        hasil = simpan_password(layanan, username, password, catatan)
        if hasil.get("sudah_ada"):
            if input(f"'{layanan}' sudah ada. Timpa? (y/n): ").strip().lower() == "y":
                hasil = simpan_password(layanan, username, password, catatan, timpa=True)
            else:
                print("AI: Oke, dibatalin.")
                return True
        if hasil["ok"]:
            print(f"\nAI: Password {hasil['layanan']} tersimpan.")
            if dibuat_otomatis:
                print("Password yang dibuat:", password)
        else:
            print("\nAI: Gagal nyimpen:", hasil["error"])

    elif cmd == "lihat password":
        layanan = arg or input("Nama layanan: ").strip()
        hasil = ambil_password(layanan)
        if hasil["ok"]:
            print(f"\nLayanan  : {hasil['layanan']}")
            print(f"Username : {hasil['username']}")
            print(f"Password : {hasil['password']}")
            if hasil.get("catatan"):
                print(f"Catatan  : {hasil['catatan']}")
            print()
        else:
            print("\nAI:", hasil["error"])

    elif cmd == "daftar password":
        hasil = daftar_layanan()
        if hasil["ok"] and hasil["jumlah"]:
            print(f"\nAda {hasil['jumlah']} password tersimpan:")
            for item in hasil["item"]:
                print(f"- {item['layanan']} ({item['username'] or 'tanpa username'})")
            print()
        elif hasil["ok"]:
            print("\nAI: Vault masih kosong.")
        else:
            print("\nAI:", hasil["error"])

    elif cmd == "hapus password":
        layanan = arg or input("Nama layanan yang mau dihapus: ").strip()
        if input(f"Yakin hapus '{layanan}'? (y/n): ").strip().lower() != "y":
            print("AI: Oke, dibatalin.")
            return True
        hasil = hapus_password(layanan)
        if hasil["ok"]:
            print(f"\nAI: Password {hasil['layanan']} sudah dihapus.")
        else:
            print("\nAI:", hasil["error"])

    return True


# ---------- Invoice (perintah manual interaktif) ----------
def print_invoice_result(hasil: dict):
    if hasil.get("ok"):
        print("\nAI: Invoice jadi!")
        print("No invoice    :", hasil["nomor_invoice"])
        print("Kepada        :", hasil["kepada"])
        print("Jumlah item   :", hasil["jumlah_item"])
        print("Subtotal      :", f"RP {hasil['subtotal']:,}")
        print(f"Pajak ({hasil['pajak_persen']:g}%)".ljust(14) + ":", f"RP {hasil['pajak']:,}")
        print("Total         :", f"RP {hasil['total']:,}")
        print("File PDF      :", hasil["file"])
    else:
        print("\nAI: Gagal bikin invoice:", hasil.get("error", "alasan tidak diketahui"))


def perintah_invoice():
    """Bikin invoice lewat tanya-jawab di terminal (alternatif kalau mau input manual)."""
    print("\nAI: Oke, bikin invoice. Kosongin 'Kepada' kalau mau batal.")
    kepada = input("Kepada (nama pembeli): ").strip()
    if not kepada:
        print("AI: Dibatalin.")
        return
    email = input("Email pembeli (opsional): ").strip()

    print("Masukin item satu per satu. Format: <nama> <harga> [x jumlah]")
    print("Contoh: kaos polo 120rb x2   (kosongin kalau sudah selesai)")
    items = []
    while True:
        baris = input(f"Item {len(items) + 1}: ").strip()
        if not baris:
            break
        try:
            items.append(parse_baris_item(baris))
        except ValueError as e:
            print("AI:", e)
    if not items:
        print("AI: Belum ada item, dibatalin.")
        return

    pajak = None
    pajak_in = input("Pajak % (kosongin = pakai default): ").strip().replace(",", ".")
    if pajak_in:
        try:
            pajak = float(pajak_in)
        except ValueError:
            print("AI: Pajak nggak valid, pakai default aja.")

    print_invoice_result(buat_invoice(kepada, items, email=email, pajak_persen=pajak))


# ---------- Loop utama: menerima perintah dari pengguna ----------
while True:

    pertanyaan = input("Kamu: ").strip()

    if not pertanyaan:  # input kosong bikin API error, lewati saja
        continue

    if pertanyaan.lower() == "exit":
        kunci_vault()
        print("AI: Yaela udahan mulu")
        break

    # Perintah manual untuk password vault (tidak diteruskan ke AI)
    if tangani_perintah_password(pertanyaan):
        continue

    # Perintah manual untuk bikin invoice (atau minta AI: "buatin invoice buat ...")
    if pertanyaan.lower() == "invoice":
        perintah_invoice()
        continue

    # Perintah manual untuk menganalisis file Excel
    if pertanyaan.lower() == "analisis" or pertanyaan.lower().startswith("analisis "):
        bagian = pertanyaan.split(maxsplit=1)
        filename = bagian[1].strip() if len(bagian) == 2 else "hasil_scraping.xlsx"
        print("\nAI: Lagi menganalisis file Excel...")
        hasil = analyze_scraped_data(filename)
        if hasil.get("ok"):
            print("\nAI: Analisis selesai!")
            print("Jumlah baris  :", hasil["jumlah_baris"])
            if hasil.get("kolom_numerik"):
                print("Kolom numerik :", ", ".join(hasil["kolom_numerik"]))
            print("Diagram       :", hasil["diagram"])
            print("Sheet analisis:", hasil["lembar_analisis"])
            print("File Excel    :", hasil["file"])
        else:
            print("\nAI: Gagal menganalisis:", hasil.get("error", "alasan tidak diketahui"))
        continue

    # Perintah manual untuk scrape katalog dan memilih nama file Excel
    if pertanyaan.lower().startswith(("scrape ", "produk ")):
        bagian = pertanyaan.split(maxsplit=3)
        if len(bagian) < 2:
            print("AI: Formatnya: scrape <URL> [jumlah] [nama file.xlsx]")
            continue
        url = bagian[1].strip()
        if not url.startswith(("http://", "https://")):
            print("AI: URL-nya harus lengkap, diawali http:// atau https://")
            continue
        max_items = 50
        filename = "hasil_scraping.xlsx"
        if len(bagian) >= 3:
            try:
                max_items = int(bagian[2])
                if len(bagian) == 4:
                    filename = bagian[3].strip()
            except ValueError:
                filename = " ".join(bagian[2:]).strip()
        if max_items < 1:
            print("AI: Jumlah produk harus lebih besar dari 0.")
            continue
        print("\nAI: Lagi scraping halaman...")
        hasil = scrape_products(url, max_items, filename)
        print_scrape_result(hasil)
        continue

    # Pesan lain diteruskan ke AI; AI dapat memanggil tool jika diperlukan
    panjang_awal = len(messages)
    messages.append({"role": "user", "content": pertanyaan})

    try:
        jawaban = chat_with_tools()
        print("AI:", jawaban)
    except Exception as e:
        # Buang pesan setengah jadi (misal tool_calls tanpa hasil) supaya
        # percakapan berikutnya tidak ikut error.
        del messages[panjang_awal:]
        print("AI: Error pas ngobrol:", e)