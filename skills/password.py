"""
Skill: Password Vault (brankas password lokal, terenkripsi).

Cara kerja:
- Semua password disimpan di SATU file terenkripsi (default: password_vault.enc).
- Kamu cukup hafal SATU master password. Master password TIDAK disimpan di mana pun;
  dia dipakai buat menurunkan kunci enkripsi (scrypt) lalu data dienkripsi
  dengan Fernet (AES-128-CBC + HMAC-SHA256, dari library `cryptography`).
- Kalau master password lupa, isi vault TIDAK bisa dipulihkan. Itu memang desainnya.

Dependensi:  pip install cryptography

PENTING: fungsi di file ini sengaja TIDAK didaftarkan sebagai tool AI.
Kalau didaftarkan, password kamu akan ikut terkirim ke server model (Groq).
Pakai lewat perintah manual di main.py saja.
"""

import base64
import difflib
import json
import os
import secrets
import string
import tempfile
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VAULT_FILE = Path(
    os.environ.get("PASSWORD_VAULT_FILE", str(PROJECT_ROOT / "password_vault.enc"))
).expanduser()
if not VAULT_FILE.is_absolute():
    VAULT_FILE = PROJECT_ROOT / VAULT_FILE
MIN_MASTER = 8

# Parameter scrypt (disimpan di header file, jadi bisa dinaikkan nanti tanpa merusak vault lama)
_KDF_PARAMS = {"n": 2**15, "r": 8, "p": 1}

# Status sesi di memori: kunci hanya hidup selama program jalan
_sesi = {"fernet": None, "salt": None, "kdf": None, "data": None}


# ---------- Fungsi internal ----------
def _turunkan_kunci(master: str, salt: bytes, kdf_params: dict) -> bytes:
    kdf = Scrypt(
        salt=salt,
        length=32,
        n=kdf_params["n"],
        r=kdf_params["r"],
        p=kdf_params["p"],
    )
    return base64.urlsafe_b64encode(kdf.derive(master.encode("utf-8")))


def _normalisasi(layanan: str) -> str:
    return " ".join(layanan.casefold().split())


def _simpan_ke_disk() -> None:
    """Tulis vault secara atomik: tulis ke file sementara dulu, baru timpa file asli."""
    token = _sesi["fernet"].encrypt(
        json.dumps(_sesi["data"], ensure_ascii=False).encode("utf-8")
    )
    isi = {
        "version": 1,
        "kdf": _sesi["kdf"],
        "salt": base64.b64encode(_sesi["salt"]).decode("ascii"),
        "token": token.decode("ascii"),
    }
    folder = VAULT_FILE.resolve().parent
    folder.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".vault_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(isi, f)
        os.replace(tmp, VAULT_FILE)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _butuh_terbuka() -> dict | None:
    if _sesi["fernet"] is None:
        return {"ok": False, "error": "Vault masih terkunci. Buka dulu pakai master password."}
    return None


# ---------- Fungsi publik ----------
def vault_ada() -> bool:
    return VAULT_FILE.exists()


def vault_terbuka() -> bool:
    return _sesi["fernet"] is not None


def buka_vault(master_password: str) -> dict:
    """
    Buka vault yang sudah ada, atau bikin vault baru kalau belum ada file-nya.
    """
    try:
        if vault_ada():
            try:
                isi = json.loads(VAULT_FILE.read_text(encoding="utf-8"))
                salt = base64.b64decode(isi["salt"])
                kdf = isi["kdf"]
                token = isi["token"].encode("ascii")
            except (ValueError, KeyError, TypeError):
                return {"ok": False, "error": "File vault rusak atau formatnya tidak dikenal."}

            fernet = Fernet(_turunkan_kunci(master_password, salt, kdf))
            try:
                data = json.loads(fernet.decrypt(token).decode("utf-8"))
            except InvalidToken:
                return {"ok": False, "error": "Master password salah."}

            _sesi.update(fernet=fernet, salt=salt, kdf=kdf, data=data)
            return {"ok": True, "baru": False, "jumlah": len(data["entries"])}

        # Vault belum ada -> bikin baru
        if len(master_password) < MIN_MASTER:
            return {
                "ok": False,
                "error": f"Master password minimal {MIN_MASTER} karakter.",
            }
        salt = secrets.token_bytes(16)
        kdf = dict(_KDF_PARAMS)
        _sesi.update(
            fernet=Fernet(_turunkan_kunci(master_password, salt, kdf)),
            salt=salt,
            kdf=kdf,
            data={"entries": {}},
        )
        _simpan_ke_disk()
        return {"ok": True, "baru": True, "jumlah": 0}
    except Exception as e:
        kunci_vault()
        return {"ok": False, "error": f"Gagal membuka vault: {e}"}


def kunci_vault() -> None:
    """Hapus kunci dan data dari memori."""
    _sesi.update(fernet=None, salt=None, kdf=None, data=None)


def simpan_password(
    layanan: str,
    username: str,
    password: str,
    catatan: str = "",
    timpa: bool = False,
) -> dict:
    if (err := _butuh_terbuka()):
        return err
    if not layanan.strip() or not password:
        return {"ok": False, "error": "Nama layanan dan password tidak boleh kosong."}

    kunci = _normalisasi(layanan)
    entries = _sesi["data"]["entries"]
    if kunci in entries and not timpa:
        return {
            "ok": False,
            "sudah_ada": True,
            "error": f"'{layanan}' sudah tersimpan. Konfirmasi dulu kalau mau ditimpa.",
        }

    entries[kunci] = {
        "layanan": layanan.strip(),
        "username": username.strip(),
        "password": password,
        "catatan": catatan.strip(),
        "diubah": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        _simpan_ke_disk()
    except Exception as e:
        return {"ok": False, "error": f"Gagal menulis vault ke disk: {e}"}
    return {"ok": True, "layanan": layanan.strip()}


def ambil_password(layanan: str) -> dict:
    if (err := _butuh_terbuka()):
        return err
    entries = _sesi["data"]["entries"]
    kunci = _normalisasi(layanan)
    entri = entries.get(kunci)
    if entri is None:
        kandidat = difflib.get_close_matches(kunci, entries.keys(), n=3, cutoff=0.4)
        saran = [entries[nama]["layanan"] for nama in kandidat]
        return {
            "ok": False,
            "error": f"Layanan '{layanan}' tidak ditemukan.",
            "saran": saran,
        }
    return {"ok": True, **entri}


def daftar_layanan() -> dict:
    """Daftar nama layanan + username saja (password TIDAK ikut)."""
    if (err := _butuh_terbuka()):
        return err
    item = [
        {"layanan": e["layanan"], "username": e["username"], "diubah": e["diubah"]}
        for e in sorted(
            _sesi["data"]["entries"].values(), key=lambda e: e["layanan"].lower()
        )
    ]
    return {"ok": True, "jumlah": len(item), "item": item}


def hapus_password(layanan: str) -> dict:
    if (err := _butuh_terbuka()):
        return err
    kunci = _normalisasi(layanan)
    if kunci not in _sesi["data"]["entries"]:
        return {"ok": False, "error": f"Layanan '{layanan}' tidak ditemukan."}
    del _sesi["data"]["entries"][kunci]
    try:
        _simpan_ke_disk()
    except Exception as e:
        return {"ok": False, "error": f"Gagal menulis vault ke disk: {e}"}
    return {"ok": True, "layanan": layanan.strip()}


def buat_password(panjang: int = 16, simbol: bool = True) -> dict:
    """Generate password acak yang kuat (pakai modul `secrets`, bukan `random`)."""
    if not 8 <= panjang <= 128:
        return {"ok": False, "error": "Panjang password harus antara 8 dan 128."}

    kelompok = [string.ascii_lowercase, string.ascii_uppercase, string.digits]
    if simbol:
        kelompok.append("!@#$%^&*()-_=+[]{}?")
    semua = "".join(kelompok)

    while True:
        pw = "".join(secrets.choice(semua) for _ in range(panjang))
        # pastikan setiap jenis karakter muncul minimal sekali
        if all(any(c in k for c in pw) for k in kelompok):
            return {"ok": True, "password": pw}