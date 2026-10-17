# Quick Start: Email Manager

Panduan cepat untuk mulai pakai fitur email manager.

## 1. Install Dependencies (5 menit)

```bash
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

Atau install semua sekaligus:
```bash
pip install -r requirements.txt
```

## 2. Setup Gmail API (10 menit)

### A. Google Cloud Console
1. Buka https://console.cloud.google.com/
2. Buat project baru: **New Project** → nama `AI Agent Email`
3. Enable **Gmail API**: **APIs & Services** → **Library** → search "Gmail API" → **Enable**

### B. OAuth Credentials
1. **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth client ID**
2. Configure consent screen:
   - User Type: **External**
   - App name: `AI Agent Email`
   - Test users: **Add Users** → masukkan email Gmail kamu
3. Buat OAuth client:
   - Application type: **Desktop app**
   - Name: `AI Agent Desktop`
4. **Download JSON** (icon download) → rename jadi `gmail_credentials.json`
5. Pindahkan ke folder `d:\project_1\data\gmail_credentials.json`

## 3. First Login (2 menit)

Pastikan library di `requirements.txt` sudah terpasang, lalu jalankan AI agent:
```bash
pip install -r requirements.txt
python main.py
```

Ketik perintah ini. Perintah tersebut langsung menjalankan pemeriksaan email:
```
cek email
```

Browser akan otomatis kebuka untuk login Gmail dan kasih izin. Setelah approve, token disimpan dan next time tidak perlu login lagi.

## 4. Mulai Pakai! 🎉

### Cek Email Penting
```
cek email
ada email penting?
cek 10 email terakhir
```

AI akan tampilkan email dengan nomor urut:
```
1. [Dari: support@stripe.com] Verify your account
2. [Dari: client@company.com] Invoice #1234
3. [Dari: github@notifications.com] Security alert
```

### Baca Email
```
baca email 1
buka email pertama
```

### Balas Email
```
balas email 1, bilang "Terima kasih, sudah saya konfirmasi"
```

AI akan:
1. Baca email asli
2. Generate balasan
3. Kirim lewat Gmail
4. Mark email as read ✅

### Kirim Email Baru
```
kirim email ke client@example.com subjek "Invoice Ready" isi "Halo, invoice sudah siap"
```

## Filter Email Penting

AI otomatis filter berdasarkan kata kunci:

✅ **Ditampilkan:**
- Verifikasi, OTP, konfirmasi
- Invoice, payment, tagihan
- Urgent, penting, mendesak
- Email dari klien/customer
- Security alert
- Order, transaksi

❌ **Tidak ditampilkan:**
- Newsletter
- Promo, diskon
- No-reply emails
- Unsubscribe emails

## Tips

1. **Test users wajib** - Email kamu harus ditambahkan sebagai test user di OAuth consent screen, kalau tidak akan error "Access blocked"

2. **Credentials aman** - File `gmail_credentials.json` dan `gmail_token.json` sudah masuk `.gitignore`, jangan di-push ke GitHub

3. **Revoke akses** - Kalau mau revoke, buka https://myaccount.google.com/permissions → pilih "AI Agent Email" → **Remove Access**

4. **Custom filter** - Edit fungsi `_is_important_email()` di `skills/email_manager.py` untuk adjust filter

## Troubleshooting

**Browser tidak kebuka saat auth:**
→ Copy URL dari terminal, paste di browser manual

**"Access blocked":**
→ Tambahkan email kamu sebagai test user di OAuth consent screen

**"Credentials not found":**
→ File `gmail_credentials.json` harus ada di `data/` folder

**Token expired:**
→ Akan auto-refresh, kalau gagal hapus `data/gmail_token.json` dan login ulang

---

Udah siap pakai! Cek email tanpa buka Gmail lagi 🚀
