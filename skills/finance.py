"""Local income, expense, cash balance, and profit/loss bookkeeping."""

import sqlite3
from datetime import date
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Literal

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FINANCE_DB = PROJECT_ROOT / "data" / "finance.sqlite3"

FINANCE_TOOL_SCHEMAS = [
    {
        "name": "catat_transaksi_keuangan",
        "description": (
            "Catat pemasukan atau pengeluaran ke pembukuan lokal. Panggil hanya "
            "ketika pengguna meminta transaksi dicatat dan jumlah rupiahnya jelas. "
            "Jangan pernah mengarang nilai transaksi."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "jenis": {
                    "type": "string",
                    "enum": ["pemasukan", "pengeluaran"],
                    "description": "Jenis transaksi.",
                },
                "keterangan": {
                    "type": "string",
                    "description": "Keterangan transaksi.",
                },
                "jumlah": {
                    "type": "integer",
                    "description": "Nilai transaksi dalam Rupiah utuh.",
                },
                "tanggal": {
                    "type": ["string", "null"],
                    "description": "Tanggal YYYY-MM-DD; null untuk hari ini.",
                },
                "kategori": {
                    "type": ["string", "null"],
                    "description": "Kategori transaksi, opsional.",
                },
            },
            "required": ["jenis", "keterangan", "jumlah"],
        },
    },
    {
        "name": "ringkasan_keuangan",
        "description": (
            "Tampilkan total pemasukan, pengeluaran, laba/rugi, saldo kas bersih "
            "sepanjang riwayat pembukuan, dan transaksi dalam periode. Jika tanggal "
            "tidak diberikan, gunakan bulan berjalan. Ini pembukuan kas sederhana, "
            "bukan neraca aset, kewajiban, dan modal."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tanggal_mulai": {
                    "type": ["string", "null"],
                    "description": "Tanggal awal YYYY-MM-DD.",
                },
                "tanggal_akhir": {
                    "type": ["string", "null"],
                    "description": "Tanggal akhir YYYY-MM-DD.",
                },
            },
            "required": [],
        },
    },
]


def _connect() -> sqlite3.Connection:
    FINANCE_DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(FINANCE_DB, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL CHECK (kind IN ('pemasukan', 'pengeluaran')),
            description TEXT NOT NULL,
            amount INTEGER NOT NULL CHECK (amount > 0),
            transaction_date TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date, id)"
    )
    return connection


@contextmanager
def _database() -> Generator[sqlite3.Connection, None, None]:
    connection = _connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _parse_date(value: str | None, field: str, fallback: date) -> date:
    if value is None or value == "":
        return fallback
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} harus berformat YYYY-MM-DD.") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field} harus berformat YYYY-MM-DD.")
    return parsed


def _serialize(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "jenis": row["kind"],
        "keterangan": row["description"],
        "jumlah": row["amount"],
        "tanggal": row["transaction_date"],
        "kategori": row["category"],
    }


def catat_transaksi_keuangan(
    jenis: Literal["pemasukan", "pengeluaran"],
    keterangan: str,
    jumlah: int,
    tanggal: str | None = None,
    kategori: str | None = None,
) -> dict[str, Any]:
    if jenis not in ("pemasukan", "pengeluaran"):
        return {"ok": False, "error": "Jenis transaksi harus pemasukan atau pengeluaran."}
    description = str(keterangan).strip()
    if not description:
        return {"ok": False, "error": "Keterangan transaksi tidak boleh kosong."}
    if isinstance(jumlah, bool) or not isinstance(jumlah, int) or jumlah <= 0:
        return {"ok": False, "error": "Jumlah transaksi harus bilangan Rupiah bulat positif."}
    try:
        transaction_date = _parse_date(tanggal, "Tanggal transaksi", date.today())
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        with _database() as connection:
            cursor = connection.execute(
                """
                INSERT INTO transactions (kind, description, amount, transaction_date, category)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    jenis,
                    description,
                    jumlah,
                    transaction_date.isoformat(),
                    str(kategori or "").strip(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM transactions WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"Gagal menyimpan transaksi keuangan: {exc}"}

    return {"ok": True, "transaksi": _serialize(row)}


def ringkasan_keuangan(
    tanggal_mulai: str | None = None,
    tanggal_akhir: str | None = None,
) -> dict[str, Any]:
    today = date.today()
    default_start = today.replace(day=1)
    try:
        start = _parse_date(tanggal_mulai, "Tanggal mulai", default_start)
        end = _parse_date(tanggal_akhir, "Tanggal akhir", today)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if start > end:
        return {"ok": False, "error": "Tanggal mulai tidak boleh setelah tanggal akhir."}

    try:
        with _database() as connection:
            totals = connection.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN kind = 'pemasukan' THEN amount ELSE 0 END), 0) AS pemasukan,
                    COALESCE(SUM(CASE WHEN kind = 'pengeluaran' THEN amount ELSE 0 END), 0) AS pengeluaran,
                    COUNT(*) AS jumlah_transaksi
                FROM transactions
                WHERE transaction_date BETWEEN ? AND ?
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchone()
            cash = connection.execute(
                """
                SELECT COALESCE(SUM(
                    CASE WHEN kind = 'pemasukan' THEN amount ELSE -amount END
                ), 0) AS saldo
                FROM transactions
                WHERE transaction_date <= ?
                """,
                (end.isoformat(),),
            ).fetchone()
            rows = connection.execute(
                """
                SELECT * FROM transactions
                WHERE transaction_date BETWEEN ? AND ?
                ORDER BY transaction_date DESC, id DESC
                LIMIT 500
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()
            expenses_by_category = connection.execute(
                """
                SELECT
                    COALESCE(NULLIF(TRIM(category), ''), 'Tanpa kategori') AS kategori,
                    SUM(amount) AS jumlah
                FROM transactions
                WHERE kind = 'pengeluaran' AND transaction_date BETWEEN ? AND ?
                GROUP BY COALESCE(NULLIF(TRIM(category), ''), 'Tanpa kategori')
                ORDER BY jumlah DESC, kategori COLLATE NOCASE ASC
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"Gagal membaca pembukuan keuangan: {exc}"}

    income = totals["pemasukan"]
    expense = totals["pengeluaran"]
    return {
        "ok": True,
        "tanggal_mulai": start.isoformat(),
        "tanggal_akhir": end.isoformat(),
        "pemasukan": income,
        "pengeluaran": expense,
        "laba_rugi": income - expense,
        "saldo_kas": cash["saldo"],
        "jumlah_transaksi": totals["jumlah_transaksi"],
        "transaksi": [_serialize(row) for row in rows],
        "transaksi_dibatasi": totals["jumlah_transaksi"] > len(rows),
        "pengeluaran_per_kategori": [
            {"kategori": row["kategori"], "jumlah": row["jumlah"]}
            for row in expenses_by_category
        ],
    }


def hapus_transaksi_keuangan(transaksi_id: int) -> dict[str, Any]:
    if isinstance(transaksi_id, bool) or transaksi_id <= 0:
        return {"ok": False, "error": "ID transaksi tidak valid."}
    try:
        with _database() as connection:
            cursor = connection.execute(
                "DELETE FROM transactions WHERE id = ?", (transaksi_id,)
            )
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"Gagal menghapus transaksi keuangan: {exc}"}

    if cursor.rowcount == 0:
        return {"ok": False, "error": "Transaksi tidak ditemukan."}
    return {"ok": True, "id": transaksi_id}
