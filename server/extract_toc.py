import re
import json
import pdfplumber
from difflib import get_close_matches
from PyPDF2 import PdfReader


def normalize(text):
    text = re.sub(r'\s+', ' ', text.lower())
    return re.sub(r'[^\w\s]', '', text).strip()


def is_toc_like_page(text: str, min_entry_lines=3, min_total_lines=5) -> bool:
    if not text:
        return False
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < min_total_lines:
        return False
    toc_pat = re.compile(r"(?:\.{2,}\s*\d+$|\s{2,}\d+$)")
    return sum(bool(toc_pat.search(ln)) for ln in lines) >= min_entry_lines


def find_toc_page_range(pdf_path, max_scan_pages=50, min_toc_len=2):
    toc_start = toc_end = None
    with pdfplumber.open(pdf_path) as pdf:
        for i in range(min(len(pdf.pages), max_scan_pages)):
            txt = pdf.pages[i].extract_text() or ""
            low = [ln.strip().lower() for ln in txt.splitlines() if ln.strip()]
            if toc_start is None:
                print("the content:",low)
                if any(re.match(r"^(table of )?contents$", ln) for ln in low):
                    toc_start = toc_end = i + 1
                elif is_toc_like_page(txt):
                    toc_start = toc_end = i + 1
            else:
                if is_toc_like_page(txt):
                    toc_end = i + 1
                else:
                    break

    if toc_start and toc_end and (toc_end - toc_start + 1) >= min_toc_len:
        return toc_start, toc_end
    return None, None


def extract_toc_entries(pdf_path, start_page, end_page):
    pat = re.compile(
        r"""
        ^\s*
        (.*?)                 # group1: title text
        (?:\.{2,}\s*|\s{2,})   # dots-leader or ≥2 spaces
        (\d{1,4})\s*$         # group2: page number
        """,
        re.VERBOSE
    )

    entries = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in range(start_page - 1, end_page):
            txt = pdf.pages[p].extract_text() or ""
            for ln in txt.splitlines():
                m = pat.match(ln.strip())
                if m:
                    title = m.group(1).strip()
                    page  = int(m.group(2))
                    entries.append((title, page))
    return entries


def build_topic_map(entries):
    topic_map = {}
    for idx, (title, start) in enumerate(entries):
        nxt = entries[idx + 1][1] if idx + 1 < len(entries) else None
        end = (nxt) if (nxt and nxt >= start) else None
        topic_map[title] = [start, end]
    return topic_map


def extract_content(pdf_path, start, end):
    reader = PdfReader(pdf_path)
    last = end or start
    pages = []
    for i in range(start - 1, last):
        pages.append(reader.pages[i].extract_text() or "")
    return "\n".join(pages).strip()

def topic_search():
    query = input("🔎 Enter topic to extract: ").strip()
    match = get_close_matches(query, list(topic_map.keys()), n=1, cutoff=0.3)
    if not match:
        print("❌ No close match found.")
        exit(1)
    title = match[0]
    s, e  = topic_map[title]
    print(f"\n📘 Extracting '{title}' → pages {s}" + (f"–{e}" if e else "") + "\n")
    print(extract_content(pdf_path, s, e))

def parse_page_input(input_str):
    """
    Parses input like "page 1", "page 2-4", "page 1, 3, 5-7"
    Returns a list of (start, end) tuples.
    """
    input_str = input_str.lower().replace("pages", "").replace("page", "").strip()
    parts = [p.strip() for p in input_str.split(",")]
    ranges = []

    for part in parts:
        if "-" in part:
            start, end = map(int, part.split("-"))
            ranges.append((start, end))
        elif part.isdigit():
            val = int(part)
            ranges.append((val, val))
    return ranges

def extract_from_page_query(pdf_path, page_input):
    page_ranges = parse_page_input(page_input)
    all_content = []
    for start, end in page_ranges:
        content = extract_content(pdf_path, start, end)
        if content:
            all_content.append(f"\n--- Page {start} to {end} ---\n{content}")
    return "\n".join(all_content).strip()


if __name__ == "__main__":
    pdf_path = r"c:\Users\Akil\Downloads\lnotes_book.pdf"

    # 1) detect ToC pages
    start, end = find_toc_page_range(pdf_path)
    if not start:
        print("TOC not detected.")
        exit(1)
    print(f"✅ TOC pages: {start}–{end}")

    # 2) extract TOC entries
    raw_entries = extract_toc_entries(pdf_path, start, end)
    if not raw_entries:
        print("❌ No ToC entries found.")
        exit(1)

    # 3) build raw topic_map
    topic_map = build_topic_map(raw_entries)

    # 6) save JSON
    with open("topic_map.json", "w", encoding="utf-8") as f:
        json.dump(topic_map, f, indent=2, ensure_ascii=False)

    # 7) query & extract
    choice=input("1. search by topic\n2.seach by page\nenter:")
    if choice==1:
        topic_search()
    else:
        pg_range=input("enter the pages u want:")
        print(extract_from_page_query(pdf_path,pg_range))
