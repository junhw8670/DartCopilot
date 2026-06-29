from dotenv import load_dotenv; load_dotenv()
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

db = Chroma(
    collection_name="kifrs",
    persist_directory="cache/kifrs_chroma",
    embedding_function=OpenAIEmbeddings(model="text-embedding-3-large"),
)
got = db.get(where={"standard": "K-IFRS 1109"})
paras = sorted({m.get("paragraph") for m in got["metadatas"] if m.get("paragraph")})

print("1109 총 청크:", len(got["ids"]))
print("4.1.x 문단:", [p for p in paras if p.startswith("4.1")])
print("4.x 문단:", [p for p in paras if p.startswith("4.")][:40])