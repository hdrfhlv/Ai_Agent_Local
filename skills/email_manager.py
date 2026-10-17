"""Gmail integration: read important emails and reply via AI assistant."""

import base64
from pathlib import Path
from email.mime.text import MIMEText
from typing import Any
from datetime import datetime, timedelta

# Gmail API
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = PROJECT_ROOT / "data" / "gmail_token.json"
CREDENTIALS_FILE = PROJECT_ROOT / "data" / "gmail_credentials.json"

# Scope untuk membaca dan kirim email
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

EMAIL_TOOL_SCHEMAS = [
    {
        "name": "cek_email_penting",
        "description": (
            "Cek email penting yang belum dibaca dari Gmail. Filter otomatis email "
            "verifikasi, dari klien, atau email penting lainnya. Mengembalikan daftar "
            "email dengan ID, pengirim, subjek, preview isi, dan tanggal."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "jumlah": {
                    "type": "integer",
                    "description": "Jumlah maksimal email yang ditampilkan (default 10).",
                },
                "hari_terakhir": {
                    "type": "integer",
                    "description": "Hanya tampilkan email dari N hari terakhir (default 7).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "baca_email",
        "description": (
            "Baca isi lengkap email berdasarkan ID yang didapat dari cek_email_penting. "
            "Mengembalikan pengirim, subjek, isi email lengkap, dan tanggal."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "string",
                    "description": "ID email yang mau dibaca (didapat dari cek_email_penting).",
                },
            },
            "required": ["email_id"],
        },
    },
    {
        "name": "balas_email",
        "description": (
            "Balas email berdasarkan ID. Otomatis mengirim balasan ke pengirim asli "
            "dengan subjek reply yang sesuai. HANYA gunakan kalau user EKSPLISIT minta "
            "balas email dengan isi balasan yang jelas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "string",
                    "description": "ID email yang mau dibalas.",
                },
                "isi_balasan": {
                    "type": "string",
                    "description": "Isi balasan email dalam bahasa yang sesuai konteks.",
                },
            },
            "required": ["email_id", "isi_balasan"],
        },
    },
    {
        "name": "kirim_email",
        "description": (
            "Kirim email baru ke alamat email tertentu. Gunakan hanya kalau user "
            "eksplisit minta kirim email dengan tujuan, subjek, dan isi yang jelas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kepada": {
                    "type": "string",
                    "description": "Alamat email tujuan.",
                },
                "subjek": {
                    "type": "string",
                    "description": "Subjek email.",
                },
                "isi": {
                    "type": "string",
                    "description": "Isi email.",
                },
            },
            "required": ["kepada", "subjek", "isi"],
        },
    },
]


def _get_gmail_service():
    """Authenticate dan return Gmail API service."""
    if not GMAIL_AVAILABLE:
        raise ImportError(
            "Library Gmail belum terinstall. Install dulu dengan: "
            "pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        )
    
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"File credentials Gmail tidak ditemukan di {CREDENTIALS_FILE}. "
            "Download credentials.json dari Google Cloud Console dan simpan di folder data/."
        )
    
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    
    # Kalau belum ada token atau token expired
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Simpan token untuk next time
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    
    return build("gmail", "v1", credentials=creds)


def _is_important_email(headers: dict, snippet: str) -> bool:
    """Filter email penting: verifikasi, klien, invoice, pembayaran, dll."""
    subject = headers.get("Subject", "").lower()
    sender = headers.get("From", "").lower()
    snippet_lower = snippet.lower()
    
    # Kata kunci penting
    important_keywords = [
        "verifikasi", "verify", "verification", "confirm", "konfirmasi",
        "invoice", "pembayaran", "payment", "tagihan", "bill",
        "urgent", "penting", "mendesak", "segera",
        "klien", "client", "customer", "pelanggan",
        "order", "pesanan", "transaksi", "transaction",
        "reset password", "security alert", "keamanan",
        "otp", "kode", "code",
    ]
    
    # Filter spam/newsletter/promo yang sering tidak penting
    spam_indicators = [
        "unsubscribe", "berhenti berlangganan",
        "newsletter", "promo", "diskon",
        "no-reply", "noreply", "do-not-reply",
    ]
    
    # Cek spam indicator dulu
    for spam in spam_indicators:
        if spam in sender or spam in subject:
            return False
    
    # Cek kata kunci penting
    for keyword in important_keywords:
        if keyword in subject or keyword in snippet_lower:
            return True
    
    return False


def _parse_email_headers(headers: list) -> dict:
    """Parse email headers jadi dict."""
    result = {}
    for header in headers:
        result[header["name"]] = header["value"]
    return result


def _decode_email_body(payload: dict) -> str:
    """Decode email body dari payload."""
    body = ""
    
    if "parts" in payload:
        # Multipart email
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                if "data" in part["body"]:
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                    break
            elif part["mimeType"] == "text/html" and not body:
                if "data" in part["body"]:
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
    else:
        # Single part email
        if "data" in payload["body"]:
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
    
    return body.strip()


def cek_email_penting(jumlah: int = 10, hari_terakhir: int = 7) -> dict[str, Any]:
    """Cek email penting yang belum dibaca."""
    try:
        service = _get_gmail_service()
        
        # Query: unread email dari N hari terakhir
        date_filter = datetime.now() - timedelta(days=hari_terakhir)
        query = f"is:unread after:{date_filter.strftime('%Y/%m/%d')}"
        
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=min(jumlah * 3, 100)  # Ambil lebih banyak untuk di-filter
        ).execute()
        
        messages = results.get("messages", [])
        
        if not messages:
            return {
                "ok": True,
                "jumlah": 0,
                "email": [],
                "pesan": "Tidak ada email penting yang belum dibaca.",
            }
        
        important_emails = []
        
        for msg in messages:
            message = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="full"
            ).execute()
            
            headers = _parse_email_headers(message["payload"]["headers"])
            snippet = message.get("snippet", "")
            
            # Filter email penting
            if _is_important_email(headers, snippet):
                # Parse tanggal
                timestamp = int(message["internalDate"]) / 1000
                date = datetime.fromtimestamp(timestamp).strftime("%d %b %Y, %H:%M")
                
                important_emails.append({
                    "id": message["id"],
                    "dari": headers.get("From", "Unknown"),
                    "subjek": headers.get("Subject", "(No Subject)"),
                    "preview": snippet[:200] + "..." if len(snippet) > 200 else snippet,
                    "tanggal": date,
                })
            
            if len(important_emails) >= jumlah:
                break
        
        return {
            "ok": True,
            "jumlah": len(important_emails),
            "email": important_emails,
        }
        
    except ImportError as e:
        return {"ok": False, "error": str(e)}
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"Gagal cek email: {e}"}


def baca_email(email_id: str) -> dict[str, Any]:
    """Baca isi lengkap email."""
    try:
        service = _get_gmail_service()
        
        message = service.users().messages().get(
            userId="me",
            id=email_id,
            format="full"
        ).execute()
        
        headers = _parse_email_headers(message["payload"]["headers"])
        body = _decode_email_body(message["payload"])
        
        # Parse tanggal
        timestamp = int(message["internalDate"]) / 1000
        date = datetime.fromtimestamp(timestamp).strftime("%d %b %Y, %H:%M")
        
        return {
            "ok": True,
            "id": email_id,
            "dari": headers.get("From", "Unknown"),
            "subjek": headers.get("Subject", "(No Subject)"),
            "isi": body,
            "tanggal": date,
        }
        
    except ImportError as e:
        return {"ok": False, "error": str(e)}
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"Gagal baca email: {e}"}


def balas_email(email_id: str, isi_balasan: str) -> dict[str, Any]:
    """Balas email."""
    try:
        service = _get_gmail_service()
        
        # Ambil email asli untuk data pengirim dan subjek
        original = service.users().messages().get(
            userId="me",
            id=email_id,
            format="full"
        ).execute()
        
        headers = _parse_email_headers(original["payload"]["headers"])
        
        # Buat message reply
        to = headers.get("From")
        subject = headers.get("Subject", "")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        
        # Get user's email address
        profile = service.users().getProfile(userId="me").execute()
        from_email = profile["emailAddress"]
        
        # Buat MIME message
        message = MIMEText(isi_balasan)
        message["to"] = to
        message["from"] = from_email
        message["subject"] = subject
        message["In-Reply-To"] = headers.get("Message-ID", "")
        message["References"] = headers.get("Message-ID", "")
        
        # Encode dan kirim
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        send_message = service.users().messages().send(
            userId="me",
            body={
                "raw": raw,
                "threadId": original["threadId"]
            }
        ).execute()
        
        # Mark original as read
        service.users().messages().modify(
            userId="me",
            id=email_id,
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()
        
        return {
            "ok": True,
            "kepada": to,
            "subjek": subject,
            "pesan": "Email berhasil dibalas dan ditandai sudah dibaca.",
        }
        
    except ImportError as e:
        return {"ok": False, "error": str(e)}
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"Gagal balas email: {e}"}


def kirim_email(kepada: str, subjek: str, isi: str) -> dict[str, Any]:
    """Kirim email baru."""
    try:
        service = _get_gmail_service()
        
        # Get user's email address
        profile = service.users().getProfile(userId="me").execute()
        from_email = profile["emailAddress"]
        
        # Buat MIME message
        message = MIMEText(isi)
        message["to"] = kepada
        message["from"] = from_email
        message["subject"] = subjek
        
        # Encode dan kirim
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        send_message = service.users().messages().send(
            userId="me",
            body={"raw": raw}
        ).execute()
        
        return {
            "ok": True,
            "kepada": kepada,
            "subjek": subjek,
            "pesan": "Email berhasil dikirim.",
        }
        
    except ImportError as e:
        return {"ok": False, "error": str(e)}
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"Gagal kirim email: {e}"}
