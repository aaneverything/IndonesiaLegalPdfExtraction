#!/usr/bin/env python3
"""
PDF -> final_corpus.jsonl (full pipeline)
- Extract text (pypdf, fallback pdfminer)
- Detect structure (BUKU/BAB/BAGIAN/Pasal)
- Minimal cleaning (preserve separators and (1),(2) markers)
- Build per-Pasal records
- Explode Pasal -> Ayat rows (regex)
- Drop "Penjelasan" blocks (title contains "penjelasan" or text startswith "cukup jelas")
- Write final JSONL corpus

Dependencies:
  pip install pypdf pdfminer.six pandas
"""
import json
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd

# ---------------- CONFIG: sesuaikan path PDF dan nama output ----------------
PDF_FILES = [
    {"pdf": "pdf/UU Nomor 1 Tahun 2023.pdf", "uu_code": "UU_CIPTA_KERJA_2023", "uu_name": "Undang-Undang Cipta Kerja", "uu_number": "UU No. 1 Tahun 2023", "year": 2023, "valid_from": None, "valid_to": None},
    {"pdf": "pdf/UU Nomor 1 Tahun 2024.pdf", "uu_code": "UU_ITE_2024", "uu_name": "Undang-Undang Informasi dan Transaksi Elektronik (Perubahan 2024)", "uu_number": "UU No. 1 Tahun 2024", "year": 2024, "valid_from": None, "valid_to": None},
    {"pdf": "pdf/UU Nomor 1 Tahun 1946.pdf", "uu_code": "KUHP_1946", "uu_name": "Kitab Undang-Undang Hukum Pidana Lama (KUHP)", "uu_number": "UU No. 1 Tahun 1946", "year": 1946, "valid_from": None, "valid_to": "2026-01-02"},
    {"pdf": "pdf/UU Nomor 6 Tahun 2023.pdf", "uu_code": "KUHP_2023", "uu_name": "Kitab Undang-Undang Hukum Pidana (KUHP)", "uu_number": "UU No. 6 Tahun 2023", "year": 2023, "valid_from": "2023-03-31", "valid_to": None},
    {"pdf": "pdf/UU Nomor 8 Tahun 1999.pdf", "uu_code": "UU_PERLINDUNGAN_KONSUMEN_1999", "uu_name": "Undang-Undang Perlindungan Konsumen", "uu_number": "UU No. 8 Tahun 1999", "year": 1999, "valid_from": None, "valid_to": None},
    {"pdf": "pdf/UU Nomor 16 Tahun 2019.pdf", "uu_code": "UU_PERKAWINAN_2019", "uu_name": "Undang-Undang Perkawinan", "uu_number": "UU No. 16 Tahun 2019", "year": 2019, "valid_from": None, "valid_to": None},
    {"pdf": "pdf/UU Nomor 27 Tahun 2022.pdf", "uu_code": "UU_PDP_2022", "uu_name": "Undang-Undang Perlindungan Data Pribadi", "uu_number": "UU No. 27 Tahun 2022", "year": 2022, "valid_from": None, "valid_to": None},
    {"pdf": "pdf/UU Nomor 35 Tahun 2009.pdf", "uu_code": "UU_NARKOTIKA_2009", "uu_name": "Undang-Undang Narkotika", "uu_number": "UU No. 35 Tahun 2009", "year": 2009, "valid_from": None, "valid_to": None},
    {"pdf": "pdf/UU Nomor 35 Tahun 2014.pdf", "uu_code": "UU_PERLINDUNGAN_ANAK_2014", "uu_name": "Undang-Undang Perlindungan Anak", "uu_number": "UU No. 35 Tahun 2014", "year": 2014, "valid_from": None, "valid_to": None}
]

OUTPUT_FILE = "final_corpus.jsonl"

# ---------------- [STEP 1] PDF extraction (pypdf, fallback pdfminer) ----------------
def _extract_with_pypdf(pdf_path: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    pages = []
    for p in reader.pages:
        txt = p.extract_text() or ""
        pages.append(txt.replace("\r", ""))
    return "\n".join(pages)

def _extract_with_pdfminer(pdf_path: str) -> str:
    from pdfminer.high_level import extract_text
    txt = extract_text(pdf_path) or ""
    return txt.replace("\r", "")

def read_pdf_text(pdf_path: str) -> str:
    # Attempt pypdf first, fallback to pdfminer if text too short or pypdf fails
    try:
        txt = _extract_with_pypdf(pdf_path)
    except Exception:
        txt = ""
    if len(txt) < 500:
        try:
            alt = _extract_with_pdfminer(pdf_path)
            if len(alt) > len(txt):
                return alt
        except Exception:
            pass
    return txt

# ---------------- [STEP 2] Detect structure (BUKU/BAB/BAGIAN/PASAL) ----------------
PASAL_ANY_RE = re.compile(r'(?im)^\s*Pasal\s+((\d+[A-Za-z]?)|([IVXLCM]+))\s*$', re.MULTILINE)
BUKU_RE   = re.compile(r'(?im)^\s*BUKU\s+([IVXLC]+)\s*(.*)$')
BAB_RE    = re.compile(r'(?im)^\s*BAB\s+([IVXLC]+)\s*(.*)$')
BAGIAN_RE = re.compile(r'(?im)^\s*Bagian\s+([0-9IVXLC]+)\s*(.*)$')

def detect_structure(full_text: str) -> List[Dict]:
    lines = full_text.splitlines()
    # map line index to absolute char offset (for nearest-tag lookup)
    line_starts = []
    pos = 0
    for ln in lines:
        line_starts.append(pos)
        pos += len(ln) + 1

    buku_marks, bab_marks, bagian_marks = [], [], []
    for i, ln in enumerate(lines):
        m = BUKU_RE.match(ln)
        if m:
            buku_marks.append((line_starts[i], ("BUKU", m.group(1).strip(), (m.group(2) or "").strip())))
        m = BAB_RE.match(ln)
        if m:
            bab_marks.append((line_starts[i], ("BAB", m.group(1).strip(), (m.group(2) or "").strip())))
        m = BAGIAN_RE.match(ln)
        if m:
            bagian_marks.append((line_starts[i], ("BAGIAN", m.group(1).strip(), (m.group(2) or "").strip())))

    def nearest_tag(idx, marks):
        prev = None
        for (p, tag) in marks:
            if p <= idx:
                prev = tag
            else:
                break
        return prev

    matches = list(PASAL_ANY_RE.finditer(full_text))
    out = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(full_text)
        pasal_label = m.group(1).strip()
        body = full_text[start:end].strip()
        body = re.sub(r'(?im)^\s*Pasal\s+' + re.escape(pasal_label) + r'\s*$', '', body).strip()
        body = re.sub(r'[ \t]+', ' ', body)
        out.append({
            "pasal_number": pasal_label,
            "text": body,
            "buku": nearest_tag(start, buku_marks),
            "bab": nearest_tag(start, bab_marks),
            "bagian": nearest_tag(start, bagian_marks)
        })
    return out

# ---------------- [STEP 3] Minimal cleaning / normalization ----------------
def minimal_clean(t: str) -> str:
    if t is None:
        return t
    t = t.replace('\x00', '')
    t = unicodedata.normalize('NFKC', t)
    t = re.sub(r'-\n\s*', '', t)               # join hyphenation
    t = re.sub(r'\s*\.\s*\.\s*\.\s*', '…', t) # ". . ." -> …
    # preserve long separators and (1)/(2) markers — do not remove them
    lines = [ln.rstrip() for ln in t.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r'\n{4,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()

# ---------------- Build per-pasal records (STEP 4: mapping to structured records) ----------
def build_records_per_pdf(cfg: Dict) -> List[Dict]:
    pdf_path = Path(cfg["pdf"])
    raw_text = read_pdf_text(pdf_path)
    if not raw_text or not raw_text.strip():
        return []
    blocks = detect_structure(raw_text)
    records = []
    for blk in blocks:
        pasal = blk.get("pasal_number")
        body = blk.get("text", "")
        cleaned = minimal_clean(body)
        buku_obj = blk.get("buku")
        bab_obj = blk.get("bab")
        bagian_obj = blk.get("bagian")
        rec = {
            "uu_code": cfg.get("uu_code"),
            "uu_name": cfg.get("uu_name"),
            "uu_number": cfg.get("uu_number"),
            "year": cfg.get("year"),
            "section_type": "PASAL",
            "title": f"Pasal {pasal}",
            "pasal_number": pasal,
            "ayat_number": None,   # keep per-pasal at this stage
            "buku": (buku_obj[1] if buku_obj else None),
            "bab": (bab_obj[1] if bab_obj else None),
            "bagian": (bagian_obj[1] if bagian_obj else None),
            "valid_from": cfg.get("valid_from"),
            "valid_to": cfg.get("valid_to"),
            "source_file": pdf_path.name,
            "text": cleaned
        }
        records.append(rec)
    return records

# ---------------- [STEP 5] Explode Pasal -> Ayat (explode_ayat_rows) ----------------
AYAT_SPLIT_RE = re.compile(r"\(\s*(\d+)\s*\)")

def explode_ayat_rows_df(df: pd.DataFrame) -> pd.DataFrame:
    # Expect df to have columns including "text", "section_type", "ayat_number", and metadata
    rows = []
    for _, r in df.iterrows():
        text = str(r.get("text", "") or "").strip()
        sect = (r.get("section_type") or "").upper()
        # only attempt explosion when row is PASAL and ayat_number is empty/null
        if sect == "PASAL" and (pd.isna(r.get("ayat_number")) or str(r.get("ayat_number")) in ("", "nan")):
            parts = AYAT_SPLIT_RE.split(text)
            if len(parts) > 1:
                # split result example: ['', '1', 'first ayat body', '2', 'second ayat body', ...]
                for i in range(1, len(parts), 2):
                    ay = str(parts[i]).strip()
                    body = (parts[i+1] or "").strip()
                    if not body:
                        continue
                    rr = r.copy()
                    rr["section_type"] = "AYAT"
                    rr["ayat_number"] = ay
                    rr["text"] = body
                    rows.append(rr)
                continue
        rows.append(r)
    return pd.DataFrame(rows)

# ---------------- [STEP 6] Drop Penjelasan (filter out explanation blocks) ----------------
def drop_penjelasan_df(df: pd.DataFrame) -> pd.DataFrame:
    def is_penjelasan(row):
        text = str(row.get("text","") or "").strip().lower()
        title = str(row.get("title","") or "").lower()
        if text.startswith("cukup jelas"):
            return True
        if "penjelasan" in title:
            return True
        return False
    mask = df.apply(is_penjelasan, axis=1)
    keep_df = df[~mask].reset_index(drop=True)
    return keep_df

# ---------------- [STEP 7] Final write JSONL (corpus assembly) ----------------
def write_jsonl_from_df(df: pd.DataFrame, out_path: str):
    with open(out_path, "a", encoding="utf-8") as fh:
        for _, row in df.iterrows():
            rec = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

# ---------------- MAIN flow ----------------
def main():
    outp = Path(OUTPUT_FILE)
    # clear output
    outp.write_text("", encoding="utf-8")
    total_records = 0

    all_records = []
    for cfg in PDF_FILES:
        p = Path(cfg["pdf"])
        if not p.exists():
            print(f"Missing: {p}  (skipping)")
            continue
        try:
            recs = build_records_per_pdf(cfg)  # STEP 1..3..4
        except Exception as e:
            print(f"Error processing {p}: {e}")
            continue
        all_records.extend(recs)
        print(f" Extracted {len(recs)} pasal-records from {p.name}")

    if not all_records:
        print("No records extracted. Exiting.")
        return

    # convert to DataFrame for further steps
    df = pd.DataFrame(all_records)

    # STEP 5: explode pasal -> ayat rows (if (1),(2) markers exist)
    df = explode_ayat_rows_df(df)
    print(f"After explode_ayat_rows: {len(df)} rows")

    # normalize pasal_number and ayat_number to string no trailing .0
    if "pasal_number" in df.columns:
        df["pasal_number"] = df["pasal_number"].astype(str).str.replace(r"\.0$","", regex=True)
    if "ayat_number" in df.columns:
        df["ayat_number"] = df["ayat_number"].astype(str).str.replace(r"\.0$","", regex=True)

    # STEP 6: drop penjelasan blocks
    df = drop_penjelasan_df(df)
    print(f"After drop_penjelasan: {len(df)} rows remain")

    # STEP 7: write final JSONL (merge corpus)
    write_jsonl_from_df(df, outp)
    total_records = len(df)
    print(f"\n WROTE TOTAL: {total_records} records → {outp}")

if __name__ == "__main__":
    main()
