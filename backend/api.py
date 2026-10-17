import json
import os
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from groq import Groq
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from skills.invoice import INVOICE_TOOL_SCHEMAS, buat_invoice  # noqa: E402
from skills.finance import (  # noqa: E402
    FINANCE_TOOL_SCHEMAS,
    catat_transaksi_keuangan,
    hapus_transaksi_keuangan,
    ringkasan_keuangan,
)
from skills.email_manager import (  # noqa: E402
    EMAIL_TOOL_SCHEMAS,
    baca_email,
    balas_email,
    cek_email_penting,
    kirim_email,
)
from skills.password import (  # noqa: E402
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
from skills.scrapper import (  # noqa: E402
    ACTIVE_TOOL_SCHEMAS,
    analyze_scraped_data,
    scrape_products,
)
from backend.auth import (  # noqa: E402
    authenticate_owner,
    clear_sessions,
    create_owner,
    create_session,
    initialize_auth_store,
    owner_exists,
    revoke_session,
    session_username,
)

MODEL = "openai/gpt-oss-20b"
API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=API_KEY) if API_KEY else None

TOOL_FUNCS = {
    "scrape_products": scrape_products,
    "analyze_scraped_data": analyze_scraped_data,
    "buat_invoice": buat_invoice,
    "catat_transaksi_keuangan": catat_transaksi_keuangan,
    "ringkasan_keuangan": ringkasan_keuangan,
    "cek_email_penting": cek_email_penting,
    "baca_email": baca_email,
    "balas_email": balas_email,
    "kirim_email": kirim_email,
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
    for schema in [
        *ACTIVE_TOOL_SCHEMAS,
        *INVOICE_TOOL_SCHEMAS,
        *FINANCE_TOOL_SCHEMAS,
        *EMAIL_TOOL_SCHEMAS,
    ]
]

SYSTEM_PROMPT = """
Kamu adalah AI assistant yang ngobrol dengan gaya bahasa Indonesia yang
santai, natural, dan friendly. Jawaban harus jelas, membantu, dan tidak
berlebihan.

Kamu punya tool scrape_products untuk mengambil produk dari katalog publik
melalui URL lengkap dan menyimpannya ke Excel, serta analyze_scraped_data untuk
menganalisis file Excel hasil scrape. Kalau file tidak disebut, gunakan
hasil_scraping.xlsx. Setelah tool selesai, jelaskan hasil dan lokasi filenya.

Kamu juga punya tool buat_invoice untuk membuat invoice PDF. Ubah harga
singkatan menjadi angka Rupiah utuh, jumlah default 1, pajak default tool
kecuali user meminta tanpa pajak (0%). Jangan mengarang nama pembeli atau
harga yang belum disebut dan jangan menghitung total sendiri.

Kamu punya tool catat_transaksi_keuangan untuk mencatat pemasukan dan
pengeluaran, serta ringkasan_keuangan untuk laporan periode. Catat transaksi
hanya jika pengguna jelas meminta pencatatan dan jumlah Rupiah disebutkan.
Jangan mengarang jumlah. Laporan menghitung pemasukan, pengeluaran,
laba/rugi periode, dan saldo kas bersih dari transaksi yang tercatat. Ini
pembukuan kas sederhana, BUKAN neraca formal aset, kewajiban, dan modal.
Jelaskan jika hasil hanya mencakup data yang sudah dicatat.

Kamu juga punya tool email Gmail:
- cek_email_penting untuk menampilkan email penting yang belum dibaca.
- baca_email untuk membaca email berdasarkan ID dari hasil pemeriksaan.
- balas_email dan kirim_email untuk mengirim email.
Untuk email:
- Jangan membalas atau mengirim email kecuali user meminta dengan jelas.
- Jika user hanya meminta draf balasan, jangan kirim; tampilkan draf untuk
  dikonfirmasi lebih dulu.
- Saat user meminta cek email, panggil cek_email_penting dan tampilkan hasil
  ringkas bernomor agar user dapat memilih email yang ingin dibaca.
- Jika hasil tool gagal, jelaskan error sebenarnya; jangan mengklaim inbox kosong.
- Jangan mengarang isi atau metadata email yang tidak dikembalikan tool.

Password vault hanya ditangani lewat fitur vault terpisah di aplikasi lokal.
Jangan meminta user memasukkan password ke chat dan jangan pernah meminta,
menyimpan, atau mengirim isi vault ke model.
"""

@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_auth_store()
    clear_sessions()
    yield
    kunci_vault()


app = FastAPI(title="KANTI Local AI", version="1.0.0", lifespan=lifespan)

_PUBLIC_AUTH_PATHS = {
    "/api/auth/status",
    "/api/auth/register",
    "/api/auth/login",
}


@app.middleware("http")
async def require_owner_session(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path not in _PUBLIC_AUTH_PATHS:
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token or not session_username(token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Sesi berakhir. Silakan masuk kembali."},
            )
    return await call_next(request)


_conversations: dict[str, list[dict[str, Any]]] = {}
_conversation_locks: dict[str, threading.Lock] = {}
_conversations_guard = threading.Lock()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=64)


class OwnerAuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=10, max_length=1024)


class VaultOpenRequest(BaseModel):
    master_password: str = Field(min_length=1, max_length=1024)
    confirmation: str | None = Field(default=None, max_length=1024)


class VaultSaveRequest(BaseModel):
    layanan: str = Field(min_length=1, max_length=200)
    username: str = Field(default="", max_length=500)
    password: str = Field(min_length=1, max_length=1024)
    catatan: str = Field(default="", max_length=2000)
    timpa: bool = False


class PasswordRequest(BaseModel):
    panjang: int = Field(default=16, ge=8, le=128)


class FinanceTransactionRequest(BaseModel):
    jenis: str = Field(pattern="^(pemasukan|pengeluaran)$")
    keterangan: str = Field(min_length=1, max_length=500)
    jumlah: int = Field(gt=0)
    tanggal: str | None = Field(default=None, max_length=10)
    kategori: str | None = Field(default=None, max_length=100)


def _history_for(conversation_id: str) -> tuple[list[dict[str, Any]], threading.Lock]:
    with _conversations_guard:
        if conversation_id not in _conversations:
            _conversations[conversation_id] = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
            _conversation_locks[conversation_id] = threading.Lock()
        return _conversations[conversation_id], _conversation_locks[conversation_id]


def _tool_result(tool_call: Any) -> dict[str, Any]:
    function = TOOL_FUNCS.get(tool_call.function.name)
    if function is None:
        return {"ok": False, "error": f"Tool tidak dikenal: {tool_call.function.name}"}

    arguments = json.loads(tool_call.function.arguments or "{}")
    if not isinstance(arguments, dict):
        return {"ok": False, "error": "Argumen tool harus berupa objek JSON."}
    return function(**arguments)


def _format_email_check_result(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        return f"Gagal cek email: {result.get('error', 'alasan tidak diketahui')}"

    emails = result.get("email", [])
    if not emails:
        return result.get("pesan", "Tidak ada email penting yang belum dibaca.")

    lines = [f"Ditemukan {len(emails)} email penting yang belum dibaca:"]
    for index, email in enumerate(emails, start=1):
        lines.extend(
            [
                f"{index}. ID: `{email.get('id', 'tidak tersedia')}`",
                f"   Dari: {email.get('dari', 'Tidak diketahui')}",
                f"   Subjek: {email.get('subjek', '(Tanpa subjek)')}",
                f"   Tanggal: {email.get('tanggal', 'Tidak diketahui')}",
                f"   Preview: {email.get('preview', '')}",
            ]
        )
    lines.extend(
        [
            "",
            "Untuk membaca email, kirim: baca email lalu salin ID yang diinginkan.",
        ]
    )
    return "\n".join(lines)


def _short_result(result: dict[str, Any], limit: int = 3000) -> str:
    encoded = json.dumps(result, ensure_ascii=False)
    if len(encoded) <= limit:
        return encoded
    reduced = {
        key: value
        for key, value in result.items()
        if isinstance(value, (str, int, float, bool, type(None)))
    }
    reduced["catatan_sistem"] = (
        "Detail lengkap tersimpan di file; hasil dikirim ke model dalam bentuk ringkas."
    )
    return json.dumps(reduced, ensure_ascii=False)[:limit]


def _make_artifact(path: Any) -> dict[str, str] | None:
    if not isinstance(path, str):
        return None
    file_path = Path(path).expanduser().resolve()
    root = PROJECT_ROOT.resolve()
    invoice_dir = (root / "invoice").resolve()
    if file_path.parent == root and file_path.suffix.lower() == ".xlsx":
        pass
    elif file_path.parent == invoice_dir and file_path.suffix.lower() == ".pdf":
        pass
    else:
        return None
    if not file_path.is_file():
        return None
    return {
        "name": file_path.name,
        "url": f"/api/files?path={quote(str(file_path), safe='')}",
    }


def _run_chat(history: list[dict[str, Any]]) -> tuple[str, list[dict[str, str]]]:
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY belum diatur. Isi file .env lalu mulai ulang server.",
        )

    artifacts: list[dict[str, str]] = []
    email_check_result: dict[str, Any] | None = None
    for _ in range(5):
        response = client.chat.completions.create(
            model=MODEL,
            messages=history,
            tools=TOOLS,
            tool_choice="auto",
        )
        message = response.choices[0].message

        if not message.tool_calls:
            answer = message.content or ""
            history.append({"role": "assistant", "content": answer})
            return answer, artifacts

        history.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in message.tool_calls
                ],
            }
        )
        for call in message.tool_calls:
            try:
                result = _tool_result(call)
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                result = {"ok": False, "error": str(exc)}
            except Exception as exc:
                result = {"ok": False, "error": f"Tool gagal dijalankan: {exc}"}
            if call.function.name == "cek_email_penting":
                email_check_result = result
            artifact = _make_artifact(result.get("file"))
            if artifact and artifact not in artifacts:
                artifacts.append(artifact)
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": _short_result(result),
                }
            )
        if email_check_result is not None:
            answer = _format_email_check_result(email_check_result)
            history.append({"role": "assistant", "content": answer})
            return answer, artifacts

    raise HTTPException(
        status_code=502,
        detail="Model meminta terlalu banyak putaran tool. Coba ulangi pesan.",
    )


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "assistant_ready": client is not None,
        "vault_exists": vault_ada(),
        "vault_unlocked": vault_terbuka(),
    }


@app.get("/api/auth/status")
def auth_status() -> dict[str, bool]:
    return {"owner_exists": owner_exists()}


@app.post("/api/auth/register")
def auth_register(request: OwnerAuthRequest) -> dict[str, str]:
    username = request.username.strip()
    if len(username) < 3:
        raise HTTPException(
            status_code=422,
            detail="Nama pengguna harus memiliki minimal 3 karakter.",
        )
    try:
        create_owner(username, request.password)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"token": create_session(username.casefold()), "username": username}


@app.post("/api/auth/login")
def auth_login(request: OwnerAuthRequest) -> dict[str, str]:
    username = authenticate_owner(request.username, request.password)
    if username is None:
        raise HTTPException(status_code=401, detail="Nama pengguna atau kata sandi salah.")
    return {"token": create_session(username), "username": username}


@app.get("/api/auth/session")
def auth_session(request: Request) -> dict[str, str]:
    token = request.headers.get("Authorization", "").partition(" ")[2]
    username = session_username(token)
    if username is None:
        raise HTTPException(status_code=401, detail="Sesi berakhir. Silakan masuk kembali.")
    return {"username": username}


@app.post("/api/auth/logout")
def auth_logout(request: Request) -> dict[str, bool]:
    token = request.headers.get("Authorization", "").partition(" ")[2]
    revoke_session(token)
    kunci_vault()
    with _conversations_guard:
        _conversations.clear()
        _conversation_locks.clear()
    return {"ok": True}


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Pesan tidak boleh kosong.")
    conversation_id = request.conversation_id or str(uuid.uuid4())
    history, lock = _history_for(conversation_id)

    with lock:
        history_start = len(history)
        history.append({"role": "user", "content": message})
        try:
            answer, artifacts = _run_chat(history)
        except Exception:
            del history[history_start:]
            raise
    return {
        "conversation_id": conversation_id,
        "reply": answer,
        "artifacts": artifacts,
    }


@app.get("/api/finance/summary")
def finance_summary(
    tanggal_mulai: str | None = None,
    tanggal_akhir: str | None = None,
) -> dict[str, Any]:
    result = ringkasan_keuangan(tanggal_mulai, tanggal_akhir)
    if not result["ok"]:
        raise HTTPException(status_code=422, detail=result["error"])
    return result


@app.post("/api/finance/transactions")
def finance_add_transaction(request: FinanceTransactionRequest) -> dict[str, Any]:
    result = catat_transaksi_keuangan(
        request.jenis,
        request.keterangan,
        request.jumlah,
        request.tanggal,
        request.kategori,
    )
    if not result["ok"]:
        raise HTTPException(status_code=422, detail=result["error"])
    return result


@app.delete("/api/finance/transactions/{transaksi_id}")
def finance_delete_transaction(transaksi_id: int) -> dict[str, Any]:
    result = hapus_transaksi_keuangan(transaksi_id)
    if not result["ok"]:
        status = 404 if result["error"] == "Transaksi tidak ditemukan." else 422
        raise HTTPException(status_code=status, detail=result["error"])
    return result


@app.get("/api/vault/status")
def vault_status() -> dict[str, bool]:
    return {"exists": vault_ada(), "unlocked": vault_terbuka()}


@app.post("/api/vault/open")
def vault_open(request: VaultOpenRequest) -> dict[str, Any]:
    if not vault_ada():
        if request.confirmation is None or request.master_password != request.confirmation:
            raise HTTPException(
                status_code=422,
                detail="Konfirmasi master password harus sama untuk membuat vault baru.",
            )
    result = buka_vault(request.master_password)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ok": True, "baru": result["baru"], "jumlah": result["jumlah"]}


@app.post("/api/vault/lock")
def vault_lock() -> dict[str, bool]:
    kunci_vault()
    return {"ok": True}


@app.get("/api/vault/entries")
def vault_entries() -> dict[str, Any]:
    result = daftar_layanan()
    if not result["ok"]:
        raise HTTPException(status_code=423, detail=result["error"])
    return result


@app.get("/api/vault/entries/{layanan}")
def vault_entry(layanan: str) -> dict[str, Any]:
    result = ambil_password(layanan)
    if not result["ok"]:
        status = 423 if "terkunci" in result["error"].lower() else 404
        raise HTTPException(status_code=status, detail=result["error"])
    return result


@app.post("/api/vault/entries")
def vault_save(request: VaultSaveRequest) -> dict[str, Any]:
    result = simpan_password(
        request.layanan,
        request.username,
        request.password,
        request.catatan,
        timpa=request.timpa,
    )
    if not result["ok"]:
        status = 423 if "terkunci" in result["error"].lower() else 409
        raise HTTPException(status_code=status, detail=result["error"])
    return result


@app.delete("/api/vault/entries/{layanan}")
def vault_delete(layanan: str) -> dict[str, Any]:
    result = hapus_password(layanan)
    if not result["ok"]:
        status = 423 if "terkunci" in result["error"].lower() else 404
        raise HTTPException(status_code=status, detail=result["error"])
    return result


@app.post("/api/vault/generate")
def vault_generate(request: PasswordRequest) -> dict[str, Any]:
    return buat_password(request.panjang)


@app.get("/api/files")
def download_file(path: str) -> FileResponse:
    file_path = Path(path).expanduser().resolve()
    root = PROJECT_ROOT.resolve()
    invoice_dir = (root / "invoice").resolve()
    allowed_excel = (
        file_path.parent == root and file_path.suffix.lower() == ".xlsx"
    )
    allowed_invoice = (
        file_path.parent == invoice_dir and file_path.suffix.lower() == ".pdf"
    )
    if not (allowed_excel or allowed_invoice) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File hasil tidak ditemukan.")
    return FileResponse(file_path, filename=file_path.name)
