# Setup Gmail API untuk Email Manager

Skill email manager butuh akses ke Gmail API. Ikutin langkah berikut:

## 1. Install Dependencies Baru

```bash
pip install -r requirements.txt
```

Library baru yang ditambahkan:
- `google-auth-oauthlib` - OAuth untuk Gmail
- `google-auth-httplib2` - HTTP client
- `google-api-python-client` - Gmail API client

## 2. Setup Google Cloud Project & Gmail API

### A. Buat Project di Google Cloud Console

1. Buka [Google Cloud Console](https://console.cloud.google.com/)
2. Klik **Select a Project** → **New Project**
3. Nama project: `AI Agent Email` (atau terserah)
4. Klik **Create**

### B. Enable Gmail API

1. Di dashboard project, klik **APIs & Services** → **Library**
2. Search "Gmail API"
3. Klik **Gmail API** → **Enable**

### C. Buat OAuth Credentials

1. Klik **APIs & Services** → **Credentials**
2. Klik **Create Credentials** → **OAuth client ID**
3. Kalau diminta configure consent screen:
   - User Type: **External**
   - App name: `AI Agent Email`
   - User support email: email kamu
   - Developer contact: email kamu
   - Klik **Save and Continue**
   - Scopes: skip (klik **Save and Continue**)
   - Test users: klik **Add Users**, masukkan email Gmail kamu
   - Klik **Save and Continue**
4. Balik ke **Credentials**, klik **Create Credentials** → **OAuth client ID**
5. Application type: **Desktop app**
6. Name: `AI Agent Desktop`
7. Klik **Create**

### D. Download Credentials

1. Setelah OAuth client dibuat, klik tombol **Download JSON** (icon download)
2. File yang di-download namanya kayak `client_secret_xxx.json`
3. **Rename jadi `gmail_credentials.json`**
4. **Pindahkan ke folder `d:\project_1\data\`**

Struktur file:
```
d:\project_1\
├── data\
│   └── gmail_credentials.json  ← taruh di sini
├── skills\
│   └── email_manager.py
└── ...
```

## 3. First-Time Authentication

Pertama kali jalanin AI agent dan pakai perintah email (misal `cek email`), browser akan otomatis kebuka untuk login Gmail dan kasih izin akses.

Setelah login dan approve:
- Token otomatis disimpan di `data/gmail_token.json`
- Next time tidak perlu login lagi (kecuali token expired, nanti auto-refresh)

## 4. Cara Pakai

### Cek Email Penting
```
Kamu: cek email
Kamu: ada email penting gak?
Kamu: cek 5 email terakhir
```

AI akan filter otomatis email penting aja (verifikasi, klien, invoice, urgent, dll). Tidak tampilkan newsletter/promo/spam.

### Baca Email Lengkap
```
Kamu: baca email 1
Kamu: buka email pertama
```

### Balas Email
```
Kamu: balas email 1, bilang terima kasih sudah konfirmasi
Kamu: reply email kedua, kasih tau kalau invoice sudah dikirim
```

AI akan:
1. Baca email asli
2. Generate draf balasan (atau pakai isi yang kamu minta)
3. Kirim balasan lewat Gmail API
4. Mark email as read

### Kirim Email Baru
```
Kamu: kirim email ke client@example.com subjek "Update Project" isi "Halo, project sudah selesai"
```

## 5. Security & Privacy

✅ **AMAN:**
- Credentials dan token disimpan LOKAL di folder `data/`
- Tidak ada yang di-upload ke server manapun
- AI tidak bisa akses email tanpa setup credentials dulu
- File `gmail_credentials.json` dan `gmail_token.json` sudah masuk `.gitignore`

⚠️ **PERHATIAN:**
- Jangan share file `gmail_credentials.json` atau `gmail_token.json`
- Kalau credentials bocor, revoke di Google Cloud Console
- AI agent cuma bisa akses email akun yang kamu authorize

## 6. Filter Email Penting

AI otomatis filter email berdasarkan kata kunci:
- ✅ **Ditampilkan:** verifikasi, invoice, payment, klien, urgent, OTP, security alert, order, konfirmasi
- ❌ **Tidak ditampilkan:** newsletter, promo, unsubscribe, no-reply

Kalau mau adjust filter, edit fungsi `_is_important_email()` di `skills/email_manager.py`.

## Troubleshooting

### Error: "File credentials Gmail tidak ditemukan"
→ File `gmail_credentials.json` belum ada di `data/`. Download dari Google Cloud Console.

### Error: "Library Gmail belum terinstall"
→ Jalankan `pip install -r requirements.txt`

### Browser tidak kebuka saat first-time auth
→ Copy URL yang muncul di terminal, buka manual di browser.

### "Access blocked: AI Agent Email has not completed the Google verification process"
→ Pastikan email kamu sudah ditambahkan sebagai **Test user** di OAuth consent screen.

## Update Requirements

Jangan lupa install dependencies baru:
```bash
pip install -r requirements.txt
```

atau langsung:
```bash
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

Udah siap pakai! 🚀
