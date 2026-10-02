import glob
import json
import uuid
import sys
from pathlib import Path
from typing import List, Dict, Any
from pypdf import PdfReader

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# Ensure project root in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.config import POLICIES_DIR, SOP_DIR, PRODUCTS_DIR, CALLS_DIR
from backend.rag.vectorstore import get_vector_store
from backend.rag.bm25_retriever import get_bm25_retriever


def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 80) -> List[str]:
    """
    Splits policy, SOP, and product text using LangChain's RecursiveCharacterTextSplitter
    for optimal contextual semantic boundaries and configurable chunk overlap.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    docs = splitter.create_documents([text])
    return [d.page_content for d in docs]


def load_and_index_all() -> int:
    """Loads all PDFs, SOPs, and Products, chunks them, and indexes into Qdrant & BM25."""
    print("Starting knowledge ingestion pipeline...")
    all_chunks: List[Dict[str, Any]] = []

    # 1. Ingest Policies (PDFs)
    pdf_files = glob.glob(str(POLICIES_DIR / "*.pdf"))
    for pdf_path in pdf_files:
        path_obj = Path(pdf_path)
        filename = path_obj.name.lower()
        reader = PdfReader(pdf_path)
        full_text = "\n".join([page.extract_text() or "" for page in reader.pages])

        # Metadata inference
        version = 2.0 if "v2" in filename else 1.0
        status = "Retired" if "v1" in filename else "Active"
        title = path_obj.stem.replace("_", " ").title()

        chunks = chunk_text(full_text, chunk_size=500, chunk_overlap=80)
        for i, c_text in enumerate(chunks):
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{path_obj.name}_{i}"))
            all_chunks.append({
                "id": chunk_id,
                "text": f"[{title} - {status}]\n{c_text}",
                "metadata": {
                    "source": path_obj.name,
                    "title": title,
                    "doc_type": "policy",
                    "version": version,
                    "status": status,
                    "chunk_index": i
                }
            })
    print(f"Loaded {len(pdf_files)} policy PDFs.")

    # 2. Ingest SOPs (Markdown)
    sop_files = glob.glob(str(SOP_DIR / "*.md"))
    for sop_path in sop_files:
        path_obj = Path(sop_path)
        with open(sop_path, "r", encoding="utf-8") as f:
            content = f.read()

        title = path_obj.stem.replace("_", " ").title() + " SOP"
        chunks = chunk_text(content, chunk_size=400, chunk_overlap=50)
        for i, c_text in enumerate(chunks):
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{path_obj.name}_{i}"))
            all_chunks.append({
                "id": chunk_id,
                "text": f"[Standard Operating Procedure: {title}]\n{c_text}",
                "metadata": {
                    "source": path_obj.name,
                    "title": title,
                    "doc_type": "sop",
                    "status": "Active",
                    "sop_key": path_obj.stem,
                    "chunk_index": i
                }
            })
    print(f"Loaded {len(sop_files)} SOP documents.")

    # 3. Ingest Products (Markdown)
    prod_files = glob.glob(str(PRODUCTS_DIR / "*.md"))
    for prod_path in prod_files:
        path_obj = Path(prod_path)
        with open(prod_path, "r", encoding="utf-8") as f:
            content = f.read()

        title = path_obj.stem.replace("_", " ").title()
        chunks = chunk_text(content, chunk_size=400, chunk_overlap=50)
        for i, c_text in enumerate(chunks):
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{path_obj.name}_{i}"))
            all_chunks.append({
                "id": chunk_id,
                "text": f"[Loan Product Specification: {title}]\n{c_text}",
                "metadata": {
                    "source": path_obj.name,
                    "title": title,
                    "doc_type": "product",
                    "status": "Active",
                    "product_key": path_obj.stem,
                    "chunk_index": i
                }
            })
    print(f"Loaded {len(prod_files)} product documents.")

    # 4. Ingest Historical Calls (JSON)
    call_files = glob.glob(str(CALLS_DIR / "*.json"))
    for call_path in call_files:
        path_obj = Path(call_path)
        with open(call_path, "r", encoding="utf-8") as f:
            call_data = json.load(f)

        call_text = (
            f"Call History for Customer {call_data.get('customer_id')}:\n"
            f"Intent: {call_data.get('intent')}\n"
            f"Outcome: {call_data.get('outcome')}\n"
            f"Summary: {call_data.get('summary')}\n"
            f"Transcript: {call_data.get('transcript')}"
        )
        chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{path_obj.name}_0"))
        all_chunks.append({
            "id": chunk_id,
            "text": call_text,
            "metadata": {
                "source": path_obj.name,
                "title": f"Previous Call - {call_data.get('customer_id')}",
                "doc_type": "call",
                "customer_id": call_data.get("customer_id"),
                "status": "Active",
                "outcome": call_data.get("outcome")
            }
        })
    print(f"Loaded {len(call_files)} past call histories.")

    # 5. Index into Vector Store (Qdrant)
    vector_store = get_vector_store()
    vector_store.upsert_chunks(all_chunks)
    print("Upserted dense vectors into Qdrant collection.")

    # 6. Index into BM25
    bm25 = get_bm25_retriever()
    bm25.index_chunks(all_chunks)
    print(f"Indexed {len(all_chunks)} chunks into BM25 keyword store.")

    return len(all_chunks)


if __name__ == "__main__":
    count = load_and_index_all()
    print(f"Knowledge ingestion complete! Total chunks indexed: {count}")
