import os
import re
import json
import urllib.request
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from backend.rag.vectorstore import PersistentVectorStore


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def clean_html_content(html: str) -> str:
    """Extracts high-signal readable text from HTML, discarding scripts, navbars, footers, and styling."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove unwanted tags
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "nav", "footer", "header"]):
        tag.decompose()

    # Get clean text
    text = soup.get_text(separator="\n")

    # Clean whitespace and repetitive blank lines
    lines = [line.strip() for line in text.splitlines()]
    clean_lines = []
    prev_blank = False
    for line in lines:
        if line:
            clean_lines.append(line)
            prev_blank = False
        elif not prev_blank:
            clean_lines.append("")
            prev_blank = True

    return "\n".join(clean_lines).strip()


def extract_page_title(html: str, fallback_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text().strip():
        title = title_tag.get_text().strip()
        # Clean title suffix e.g. " - Apple (IN)"
        return re.sub(r"\s*-\s*Apple\s*(\(IN\)|\(India\))?$", "", title, flags=re.IGNORECASE)
    return fallback_url


import requests
import certifi

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def fetch_url(url: str, timeout: int = 15) -> Optional[str]:
    """Fetches HTML content using requests with certifi SSL certificate bundle."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9"
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout, verify=certifi.where())
        if response.status_code == 200:
            return response.text
    except Exception as e:
        # Fallback with unverified context if local macOS CA chain is broken
        try:
            response = requests.get(url, headers=headers, timeout=timeout, verify=False)
            if response.status_code == 200:
                return response.text
        except Exception as e2:
            print(f"[Crawler] Error fetching {url}: {e2}")
    return None


class AppleCrawler:
    """
    Crawler & Processor for Apple India product information.
    Loads, cleans, categorizes, and indexes pages into the vector database.
    """

    def __init__(self, vector_store: PersistentVectorStore):
        self.vector_store = vector_store

    def crawl_and_ingest_urls(self, url_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Crawls a list of URL dictionaries: [{"url": "...", "title": "...", "category": "..."}]
        Cleans, creates Document chunks, and adds them to VectorStore.
        """
        documents: List[Document] = []
        crawled_count = 0
        failed_urls = []

        seen_urls = set()
        for item in url_entries:
            url = item.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            print(f"[Crawler] Crawling {url} ...")
            html = fetch_url(url)
            if not html:
                failed_urls.append(url)
                continue

            cleaned_text = clean_html_content(html)
            if len(cleaned_text) < 100:
                failed_urls.append(url)
                continue

            page_title = item.get("title") or extract_page_title(html, url)
            category = item.get("category") or self._detect_category(url, page_title)

            doc = Document(
                page_content=cleaned_text,
                metadata={
                    "url": url,
                    "title": page_title,
                    "category": category,
                    "source": "apple.com/in"
                }
            )
            documents.append(doc)
            crawled_count += 1

        if documents:
            self.vector_store.add_documents(documents)

        return {
            "total_requested": len(url_entries),
            "successful": crawled_count,
            "failed_urls": failed_urls,
            "total_chunks_indexed": self.vector_store.count()
        }

    def _detect_category(self, url: str, title: str) -> str:
        text = f"{url} {title}".lower()
        if "iphone" in text:
            return "iPhone"
        elif "mac" in text or "macbook" in text:
            return "Mac"
        elif "ipad" in text:
            return "iPad"
        elif "watch" in text:
            return "Watch"
        elif "airpod" in text or "audio" in text:
            return "AirPods"
        elif "trade-in" in text or "applecare" in text or "support" in text:
            return "Services"
        return "General"
