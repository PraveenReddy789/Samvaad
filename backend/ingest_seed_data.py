import os
import json
import time
from backend.rag.vectorstore import PersistentVectorStore
from backend.rag.crawler import AppleCrawler

def main():
    print("==========================================")
    print("      Apple India RAG Ingestion Pipeline  ")
    print("==========================================")

    seed_path = os.path.join(os.path.dirname(__file__), "data", "seed_urls.json")
    if not os.path.exists(seed_path):
        print(f"Error: Seed file not found at {seed_path}")
        return

    with open(seed_path, "r", encoding="utf-8") as f:
        urls = json.load(f)

    print(f"Loaded {len(urls)} curated Apple India product pages to index.")
    
    vector_store = PersistentVectorStore()
    crawler = AppleCrawler(vector_store)

    start_time = time.time()
    result = crawler.crawl_and_ingest_urls(urls)
    duration = time.time() - start_time

    print("\n------------------------------------------")
    print(f"Ingestion Finished in {duration:.1f}s")
    print(f"Successfully processed: {result['successful']} / {result['total_requested']} pages")
    print(f"Total Chunks in Vector Store: {result['total_chunks_indexed']}")
    if result["failed_urls"]:
        print(f"Failed URLs ({len(result['failed_urls'])}):", result["failed_urls"])
    print("------------------------------------------\n")


if __name__ == "__main__":
    main()
