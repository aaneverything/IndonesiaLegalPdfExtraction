# LawExtraction

Ringkasan

LawExtraction adalah skrip Python kecil untuk mengekstrak teks terstruktur dari PDF undang-undang (Undang‑Undang) Indonesia dan menghasilkan satu file JSONL (`final_corpus.jsonl`) berisi record per‑Pasal. Skrip ini menggunakan `pypdf` dengan fallback ke `pdfminer.six` untuk ekstraksi teks, lalu melakukan deteksi struktur sederhana (Pasal / BUKU / BAB / Bagian) dan pembersihan minimal.

Konten repository

- `main.py`  — skrip utama untuk mengekstrak dan menulis `final_corpus.jsonl`.
- `requirements.txt` — daftar dependensi (pypdf, pdfminer.six, tqdm).
- `pdf/` — folder yang berisi PDF undang‑undang yang dikonfigurasi.
- `final_corpus.jsonl` — keluaran (dibuat setelah menjalankan skrip).

Persyaratan

- Python 3.8+ direkomendasikan.
- Sistem operasi: cross‑platform (Windows/Linux/macOS). Panduan perintah di README menggunakan Windows `cmd.exe`.

Instalasi (Windows)

1. Buat virtual environment (opsional tapi direkomendasikan):

```cmd
python -m venv venv
venv\Scripts\activate
```

2. Install dependensi:

```cmd
pip install -r requirements.txt
```

Menjalankan

Jalankan skrip utama dari root proyek:

```cmd
python main.py
```

Setelah selesai, file `final_corpus.jsonl` akan berisi satu record JSON per baris untuk setiap Pasal yang terdeteksi dari semua PDF yang dikonfigurasi.

Konfigurasi

`main.py` memiliki konstanta `PDF_FILES` di bagian atas — daftar objek konfigurasi untuk setiap PDF yang akan diproses. Contoh entri:

{
  "pdf": "pdf/UU Nomor 1 Tahun 2023.pdf",
  "uu_code": "UU_CIPTA_KERJA_2023",
  "uu_name": "Undang-Undang Cipta Kerja",
  "uu_number": "UU No. 1 Tahun 2023",
  "year": 2023,
  "valid_from": null,
  "valid_to": null
}

Anda bisa menambah, menghapus, atau mengubah entri di `PDF_FILES` untuk menyesuaikan file yang diproses dan metadata yang ingin disertakan pada tiap record.

Output (skema record JSONL)

Setiap baris di `final_corpus.jsonl` adalah objek JSON dengan field berikut (ringkasan):

- `uu_code`, `uu_name`, `uu_number`, `year`: metadata UU dari konfigurasi.
- `section_type`: selalu "PASAL" untuk keluaran saat ini.
- `title`: mis. "Pasal 1".
- `pasal_number`: label pasal seperti "1", "2a", atau romawi bila ada.
- `ayat_number`: `null` (skrip saat ini tidak memecah ayat ke record terpisah).
- `buku`, `bab`, `bagian`: jika terdeteksi, berisi nomor/label terkait.
- `valid_from`, `valid_to`: metadata tanggal bila diisi dalam konfigurasi.
- `source_file`: nama file PDF asal.
- `text`: teks pasal setelah pembersihan minimal (penyambungan pemenggalan kata, normalisasi unicode, penghilangan null bytes, dsb.).

Contoh satu baris JSON (dipersingkat):

{"uu_code": "UU_CIPTA_KERJA_2023", "title": "Pasal 1", "pasal_number": "1", "text": "..."}

Bagaimana ekstraksi bekerja (catatan teknis)

- Pertama, skrip mencoba mengekstrak teks dengan `pypdf` (lebih cepat dan sering cukup untuk PDF berbasis teks).
- Jika teks yang diperoleh terlalu pendek atau `pypdf` gagal, skrip mencoba fallback ke `pdfminer.six`.
- Deteksi struktur Pasal dilakukan dengan regex yang mencari baris yang diawali "Pasal <nomor>". Selain itu ada pencarian header seperti `BUKU`, `BAB`, dan `Bagian` untuk menambahkan konteks ke setiap pasal.
- Pembersihan minimal menjaga penanda ayat seperti `(1)`/`(2)` tetap utuh, sambil memperbaiki pemenggalan kata akibat linebreak.

Contributing

Silakan buka issue atau buat pull request dengan perbaikan/fitur baru. Sertakan contoh PDF (atau potongan teks) bila mengajukan perbaikan pada deteksi struktur.

License

Tidak ada file lisensi di repo; tambahkan `LICENSE` bila ingin menerapkan lisensi tertentu.

---

