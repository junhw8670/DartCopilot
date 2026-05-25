from __future__ import annotations

import re
from pathlib import Path

import fitz
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
KIFRS_PDF_DIR = BASE_DIR / "cache" / "kifrs"
PERSIST_DIR = BASE_DIR / "cache" / "kifrs_chroma"

EMBEDDING_MODEL = "text-embedding-3-large"
COLLECTION_NAME = "kifrs"

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", " "],
)

MIN_KOREAN_RATIO = 0.3
MIN_CHUNK_CHARS = 50
PAGE_NUMBER_LINE = re.compile(r"^\s*-\s*\d+\s*-\s*$")
PARAGRAPH_PATTERN = re.compile(
    r"^\s*("
    r"한?\d+(?:\.\d+)?"           # 본문 문단 (1, 23, 한4.1, 한117.1)
    r"|한?B\d+[A-Z]?(?:\.\d+)?"   # 부록 B 적용지침 (B1, B107, B119A)
    r")(?:\s|$)"
)

NUMBERED_STANDARD = re.compile(r"K-IFRS_제(\d+)호_([^(]+?)(?:_?\(|$)")
PRACTICE_STATEMENT = re.compile(r"국제회계기준_실무서_(\d+)_([^(]+?)(?:_?\(|$)")
MANAGEMENT_COMMENTARY = re.compile(r"경영진설명서_([^(]+?)(?:_?\(|$)")
NAMED_STANDARD = re.compile(r"K-IFRS_([^(]+?)(?:_?\(|$)")


def _clean(name: str) -> str:
    """Trim trailing underscores and convert remaining underscores to spaces."""
    return name.rstrip("_").replace("_", " ").strip()


def _is_mostly_korean(text: str) -> bool:
    """Reject chunks that are not predominantly Korean (filters English copyright pages)."""
    if len(text) < 20:
        return True
    korean = sum(1 for c in text if "\uac00" <= c <= "\ud7af")
    return korean / len(text) >= MIN_KOREAN_RATIO


def parse_filename_metadata(filename: str) -> tuple[str, str]:
    """Return (standard_id, standard_name) parsed from a K-IFRS PDF filename."""
    stem = filename.replace(".pdf", "")

    m = NUMBERED_STANDARD.search(stem)
    if m:
        return f"K-IFRS {m.group(1)}", _clean(m.group(2))

    m = PRACTICE_STATEMENT.search(stem)
    if m:
        return f"K-IFRS Practice Statement {m.group(1)}", _clean(m.group(2))

    m = MANAGEMENT_COMMENTARY.search(stem)
    if m:
        return "Management Commentary", _clean(m.group(1))

    m = NAMED_STANDARD.search(stem)
    if m:
        return "K-IFRS Framework", _clean(m.group(1))

    return "Unknown", _clean(stem.split("(")[0])


def extract_pdf_text(pdf_path: Path) -> str:
    """Return the concatenated text of all pages in a PDF."""
    doc = fitz.open(pdf_path)
    try:
        return "\n".join(_page_text_excluding_tables(page) for page in doc)
    finally:
        doc.close()


def _page_text_excluding_tables(page) -> str:
    """Page text minus any block whose bbox overlaps a detected table."""
    try:
        table_bboxes = [t.bbox for t in page.find_tables()]
    except Exception:
        table_bboxes = []

    kept = []
    for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
        if not any(_bbox_overlaps((x0, y0, x1, y1), tbb) for tbb in table_bboxes):
            kept.append(text)
    return "".join(kept)


def _bbox_overlaps(a, b) -> bool:
    """True if two (x0, y0, x1, y1) rectangles intersect."""
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def parse_paragraph_chunks(text, standard, standard_name, source_file):
    docs = []
    current_para = None
    current_text = []
    
    for line in text.split("\n"):
        if PAGE_NUMBER_LINE.match(line):
            continue
        m = PARAGRAPH_PATTERN.match(line)
        if m:
            if current_para and current_text:
                docs.append(Document(
                    page_content=" ".join(current_text).strip(),
                    metadata={
                        "standard": standard,
                        "standard_name": standard_name,
                        "paragraph": current_para,
                        "source_file": source_file,
                    }
                ))
            current_para = m.group(1)
            current_text = [line[m.end():].strip()]
        else:
            current_text.append(line.strip())
    
    if current_para and current_text:
        docs.append(Document(
            page_content=" ".join(current_text).strip(),
            metadata={
                "standard": standard,
                "standard_name": standard_name,
                "paragraph": current_para,
                "source_file": source_file,
            }
        ))
    
    final_docs = []
    for d in docs:
        if len(d.page_content) > 1500:
            sub_chunks = splitter.split_text(d.page_content)
            for i, sub in enumerate(sub_chunks):
                final_docs.append(Document(
                    page_content=sub,
                    metadata={**d.metadata, "sub_chunk": i}
                ))
        else:
            final_docs.append(d)

    final_docs = [
        d for d in final_docs
        if len(d.page_content) >= MIN_CHUNK_CHARS and _is_mostly_korean(d.page_content)
    ]
    return final_docs


def build_index() -> None:
    """Read every PDF under KIFRS_PDF_DIR, chunk it, persist to PERSIST_DIR."""
    if PERSIST_DIR.exists() and any(PERSIST_DIR.iterdir()):
        print(f"index already exists at {PERSIST_DIR}. Delete the directory to rebuild.")
        return

    pdf_files = sorted(KIFRS_PDF_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDFs")

    all_docs: list[Document] = []

    for pdf_path in pdf_files:
        try:
            text = extract_pdf_text(pdf_path)
            standard, standard_name = parse_filename_metadata(pdf_path.name)
            chunks = parse_paragraph_chunks(text, standard, standard_name, pdf_path.name)
            all_docs.extend(chunks)
            print(f" {pdf_path.name}: {len(chunks)} chunks")
        except Exception as e:
            print(f" {pdf_path.name}: FAILED - {e!r}")

    print(f"Total chunks: {len(all_docs)}")

    embeddings = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        chunk_size=200,
        max_retries=10,
    )
    Chroma.from_documents(
        documents=all_docs,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(PERSIST_DIR),
    )
    print(f"Index built and persisted at {PERSIST_DIR}")

if __name__ == "__main__":
    build_index()
