# AI Agent Learning

Proyek ini adalah AI agent berbahasa Indonesia dengan Python dan Groq. Program
ini juga bisa mengelola password secara lokal dengan vault terenkripsi,
mengambil data katalog publik, menganalisis hasil scrape di Excel, dan membuat
invoice PDF.

## Fitur

- Chat berbahasa Indonesia lewat Groq.
- Simpan, lihat, daftar, dan hapus password melalui vault lokal terenkripsi.
- Buat password acak dengan generator kriptografis.
- Ambil nama produk, harga jika tersedia, dan tautannya dari katalog publik.
- Ikuti halaman katalog berikutnya sampai jumlah produk yang diminta tercapai
  atau katalog habis.
- Simpan data sebagai tabel Excel yang sudah punya header, filter, dan tautan
  yang bisa diklik.
- Buat sheet **Analisis** beserta statistik dan diagram batang secara otomatis
  setelah scrape.
- Analisis ulang file Excel yang sudah ada tanpa menghapus sheet data sumber.
- Buat invoice PDF dengan identitas usaha KANTI.
- Catat pemasukan dan pengeluaran serta lihat saldo kas dan laporan laba-rugi.
- **Email Manager (BARU!)**: Cek email penting otomatis, baca, balas, dan kirim
  email langsung lewat Gmail API tanpa buka browser.

Scraping paling cocok untuk halaman publik yang menyediakan konten produk di
HTML dan tautan halaman berikutnya yang bisa dikenali. Situs yang bergantung
pada JavaScript, login, CAPTCHA, atau proteksi anti-bot mungkin tidak bisa
dibaca dengan scraper ini.

## Persiapan

Pastikan Python sudah terpasang. Jalankan perintah berikut dari PowerShell di
folder proyek untuk membuat environment dan memasang dependensi backend:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Website memerlukan Node.js versi 18 atau lebih baru. Pasang dependensi React
satu kali dari folder proyek:

```powershell
npm install --prefix frontend
```

Program chat memerlukan API key Groq. Buat file `.env` di folder proyek:

```dotenv
GROQ_API_KEY=isi_api_key_groq_di_sini
```

Ganti nilai contoh dengan API key Groq milikmu.
Jangan bagikan file `.env` karena berisi kredensial rahasia.

### Setup Gmail API (untuk fitur email)

Untuk menggunakan fitur email manager, ikuti panduan lengkap di
**[SETUP_GMAIL.md](SETUP_GMAIL.md)**.

Ringkasannya:
1. Install dependencies: `pip install -r requirements.txt`
2. Buat Google Cloud Project dan enable Gmail API
3. Download OAuth credentials
4. Rename jadi `gmail_credentials.json` dan taruh di folder `data/`
5. First-time auth akan buka browser otomatis

Password vault menggunakan file `password_vault.enc` di folder proyek secara
default. File dibuat saat pertama kali memakai perintah password. Buat master
password minimal 8 karakter dan simpan dengan aman: master password tidak
disimpan, dan isi vault tidak dapat dipulihkan jika master password terlupa.
Password vault hanya diproses secara lokal dan tidak dikirim ke model AI.

## Menjalankan website lokal

Jalankan dari folder proyek:

```powershell
.\run-web.bat
```

Launcher membuka server API lokal dan website React, lalu membuka browser ke
`http://127.0.0.1:5173`. Jendela server harus tetap berjalan selama website
digunakan. API hanya menerima koneksi dari komputer ini dan diakses website
melalui proxy lokal; ini adalah versi localhost, bukan hosting publik.

Saat pertama kali membuka website, buat akun pemilik dengan nama pengguna dan
kata sandi minimal 10 karakter. Hanya satu akun yang dapat didaftarkan.
Sesi berakhir saat tab ditutup atau server dimulai ulang; masuk kembali saat
berikutnya membuka website. Data hash akun disimpan lokal di
`data/owner_auth.sqlite3` dan file tersebut tidak diunggah ke Git.
Jika kata sandi terlupa, hentikan server lalu hapus `data/owner_auth.sqlite3`
untuk mengulang pendaftaran. Tindakan ini hanya mereset akun pemilik, bukan
data keuangan atau isi vault.

Setelah website terbuka, gunakan halaman **Asisten AI** untuk chat, membuat
invoice PDF, scrape katalog, menganalisis Excel, atau **mengelola email**.
Tautan unduhan hasil invoice dan Excel akan muncul di percakapan. Halaman
**Keuangan** berisi pencatatan dan laporan kas. Halaman **Password vault**
mengelola brankas terenkripsi secara lokal. Master password dan isi vault tidak
dikirim ke Groq.

Untuk menghentikan aplikasi, tutup jendela server KANTI AI API dan jendela
website. Vault otomatis dikunci ketika server berhenti.

### Mode terminal lama

Jika masih ingin menggunakan antarmuka terminal, jalankan:

```powershell
.\run.bat
```

atau:

```powershell
.\.venv\Scripts\python.exe main.py
```

Perintah terminal lama tetap tersedia secara terpisah dari website.

## Menggunakan website

### Email Manager (BARU!)

Di halaman **Asisten AI**, gunakan perintah email untuk mengelola inbox Gmail
tanpa buka browser:

**Cek email penting:**
```text
cek email
ada email penting gak?
cek 5 email terakhir
```

AI otomatis filter email penting saja (verifikasi, klien, invoice, urgent).
Tidak tampilkan newsletter, promo, atau spam.

**Baca email lengkap:**
```text
baca email 1
buka email pertama
```

**Balas email:**
```text
balas email 1, bilang terima kasih sudah konfirmasi
reply email kedua, kasih tau invoice sudah dikirim
```

AI akan generate balasan, kirim lewat Gmail API, dan mark email as read.

**Kirim email baru:**
```text
kirim email ke client@example.com subjek "Update Project" isi "Project sudah selesai"
```

Setup Gmail API wajib dilakukan dulu, lihat **[SETUP_GMAIL.md](SETUP_GMAIL.md)**.

### Pembukuan keuangan

Buka halaman **Keuangan** untuk mencatat pemasukan atau pengeluaran dengan
keterangan, jumlah Rupiah, tanggal, dan kategori opsional. Laporan dapat
difilter berdasarkan tanggal dan menampilkan saldo kas bersih, total pemasukan,
total pengeluaran, serta laba/rugi untuk periode yang dipilih. Grafik
**Pengeluaran per kategori** merangkum seluruh pengeluaran dalam periode yang
dipilih, diurutkan dari kategori dengan pengeluaran terbesar. Pengeluaran
tanpa kategori ditampilkan sebagai **Tanpa kategori**. Transaksi juga bisa
dicatat melalui chat, contohnya:

```text
Catat pemasukan jasa pembuatan website Rp2.500.000 hari ini, kategori proyek.
Berapa total pengeluaran bulan ini?
```

AI akan mencatat transaksi hanya jika jenis, keterangan, dan jumlahnya jelas.
Data pembukuan disimpan lokal dalam `data/finance.sqlite3` dan file basis data
tersebut dikecualikan dari Git. Saldo kas dihitung dari transaksi yang pernah
dicatat, tanpa saldo awal. Ini pembukuan kas sederhana, bukan neraca formal
aset, kewajiban, dan modal atau laporan pajak. Pastikan catatan transaksi
lengkap sebelum memakai angkanya untuk keputusan bisnis.

### Buat invoice PDF

Di halaman **Asisten AI**, minta invoice dengan bahasa biasa. Sebutkan nama
pembeli dan nama jasa/barang beserta harga satuannya; jumlah otomatis menjadi
1 jika tidak disebutkan. Contoh:

```text
Buat invoice untuk PT Maju Jaya: Pembuatan website, harga Rp2.500.000.
```

Pajak default invoice adalah 10%. Sebutkan **tanpa pajak** untuk menggunakan
pajak 0%, atau sebutkan persentase pajak yang diinginkan. Tanggal otomatis
menggunakan tanggal saat invoice dibuat, dan email pembeli bersifat opsional.
Jika nama pembeli atau harga belum disebut, AI akan meminta informasi itu
sebelum membuat invoice.

Invoice juga bisa dibuat dengan mengetik `invoice` pada mode terminal lama,
lalu mengisi pertanyaan yang muncul satu per satu. PDF tersimpan di folder `invoice/`.
Identitas pada header PDF menggunakan nama **KANTI** dan tagline **Karya
Anugerah Tijarah | Partner Digital Anda**. Logo, nama rekening, nomor rekening,
penandatangan, dan pengaturan invoice lainnya dikonfigurasi di
`skills/invoice.py` pada bagian `PENGATURAN`. Pastikan `logo_path` mengarah ke
file logo yang tersedia di komputer; area putih di sekeliling logo akan
dipangkas saat PDF dibuat.

### Scrape katalog produk

```text
scrape https://books.toscrape.com/ 60 koleksi_buku.xlsx
```

Angka setelah URL adalah batas jumlah produk. Kalau jumlahnya tidak
dicantumkan, program memakai batas 50. Nama file juga opsional:

```text
scrape https://books.toscrape.com/
scrape https://books.toscrape.com/ koleksi_buku
```

Program mengikuti tautan halaman berikutnya secara otomatis. Hasilnya
disimpan sebagai `hasil_scraping.xlsx` di folder tempat program dijalankan
kalau nama file tidak diberikan. Ekstensi `.xlsx` boleh ditulis atau akan
ditambahkan otomatis. Contoh di atas membuat `koleksi_buku.xlsx`.
Setelah scrape, buka file tersebut dan pilih sheet **Produk** atau
**Analisis**.

### Analisis file yang sudah ada

Scrape baru langsung menyertakan analisis. Dari website, minta analisis file
Excel lewat chat. Pada mode terminal lama, untuk menganalisis ulang file lama,
tutup dulu file tersebut di Excel, lalu ketik:

```text
analisis
```

Perintah terminal tersebut memakai `hasil_scraping.xlsx`. Untuk file lain,
masukkan nama atau path-nya:

```text
analisis data_produk.xlsx
```

Sheet **Analisis** akan dibuat ulang, sementara sheet data sumber tetap ada.
Untuk kolom numerik seperti harga, program menghitung jumlah data, rata-rata,
median, nilai minimum, dan maksimum, lalu membuat diagram 10 nilai tertinggi.
Kalau tidak ada kolom numerik yang dikenali, program membuat diagram frekuensi
kategori teratas.

### Password vault

Password vault dikelola melalui halaman **Password vault** di website atau
lewat perintah lokal pada mode terminal. Password tidak dikirim ke AI. Saat
pertama kali membuat vault, tentukan master password minimal 8 karakter dan
simpan baik-baik. Pesan di halaman chat dikirim ke layanan Groq memakai API key
di `.env`; jangan masukkan password atau master password ke chat.

```text
simpan password Gmail
lihat password Gmail
daftar password
hapus password Gmail
generate password
generate password 24
kunci vault
```

Di website, masukkan username, password, dan catatan melalui form vault. Pada
mode terminal, password diminta lewat prompt tersembunyi. Jangan mengetik
password atau master password sebagai pesan chat. `daftar password` hanya
menampilkan nama layanan dan username. Untuk melihat entri, gunakan **nama
layanan** yang tercantum di daftar, bukan username. Misalnya, jika daftar
menunjukkan `Gmail (nama@example.com)`, perintahnya `lihat password Gmail`.
Nama yang dimasukkan saat menyimpan menjadi nama layanan; jika memasukkan teks
placeholder seperti `<layanan>`, teks itu akan tersimpan sebagai nama literal.

Perintah `hapus password` meminta konfirmasi. `kunci vault` menghapus kunci
dari memori; vault akan meminta master password lagi pada perintah berikutnya.

### Perintah lainnya

```text
exit
```

`exit` menutup program dan mengunci vault.

## Isi workbook

- **Produk** — data hasil scrape dengan header `Nama Produk`, `Harga`, dan
  `Tautan Produk`.
- **Analisis** — ringkasan statistik, data pendukung diagram, dan diagram
  batang.

Analisis hanya bisa menggunakan data yang berhasil diambil. Kalau harga
kosong atau tidak terbaca dari situs, program tidak bisa menghitung statistik
harga untuk produk tersebut.
