from pathlib import Path
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import fitz
import re

ROOT = Path(__file__).resolve().parent.parent
KIFRS_PDF_DIR = ROOT / "cache" / "kifrs"
PERSIST_DIR = ROOT / "cache" / "kifrs_chroma"

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", " "],
)

PARAGRAPH_PATTERN = re.compile(
    r"^\s*(SP\d+\.\d+|BC\d+\.\d+|IG\d+\.\d+|IG\d+|IE\d+(?:\.\d+)?|\d+\.\d+|\d+|[가-힣]\d+)\s"
)


def parse_paragraph_chunks(text, standard, standard_name, source_file):
    docs = []
    current_para = None
    current_text = []
    
    for line in text.split("\n"):
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
    
    # Commit last paragraph
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
    
    # Sub-split oversized chunks
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
    return final_docs