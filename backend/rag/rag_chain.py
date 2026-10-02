import os
from typing import List, Dict, Any, AsyncIterator, Tuple
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from backend.rag.vectorstore import PersistentVectorStore
from backend.rag.hybrid import HybridRetriever

load_dotenv()

SYSTEM_PROMPT = """You are an Apple Specialist and smart shopping assistant for Apple India (apple.com/in).

Your job is to answer customer questions accurately, concisely, and helpfully using the provided Apple Store context.

GUIDELINES:
1. Grounding: Answer ONLY based on facts, specifications, and prices present in the context below. Never hallucinate or assume non-existent models.
2. Prices & Currency: Always quote prices in Indian Rupees (₹ INR) exactly as shown in the context (e.g., ₹1,34,900 or ₹79,900).
3. Directness: Answer what the user specifically asked first.
4. Structure: Use clean Markdown with bold model names, bullet points for key specs, and concise price breakdowns.
5. Comparisons: If the user asks for comparison or recommendations, provide clear side-by-side spec highlights (Chip, Display, Battery, Camera, Starting Price).
6. Missing Information: If the provided context does not contain the answer, politely state that the specific detail is not available on the official India product page yet.

CONTEXT INFORMATION:
---------------------
{context}
---------------------
"""


class AppleRAGService:
    def __init__(self, vector_store: PersistentVectorStore):
        self.vector_store = vector_store
        self.retriever = HybridRetriever(vector_store)
        
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY is not set.")

        self.llm = ChatMistralAI(
            model="open-mistral-7b",
            temperature=0.1,
            mistral_api_key=api_key
        )

        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "{question}")
        ])

        self.chain = self.prompt_template | self.llm

    def refresh_retriever(self):
        self.retriever.refresh()

    def _retrieve_and_format_context(self, question: str, top_k: int = 5) -> Tuple[str, List[Dict[str, str]]]:
        scored_docs = self.retriever.get_relevant_documents(question, k=top_k)
        
        context_parts = []
        sources: List[Dict[str, str]] = []
        seen_urls = set()

        for doc, score in scored_docs:
            context_parts.append(doc.page_content)
            url = doc.metadata.get("url", "")
            title = doc.metadata.get("title", "Apple India")
            category = doc.metadata.get("category", "General")
            
            if url and url not in seen_urls:
                seen_urls.add(url)
                sources.append({
                    "title": title,
                    "url": url,
                    "category": category,
                    "relevance": f"{score:.2f}"
                })

        combined_context = "\n\n---\n\n".join(context_parts)
        return combined_context, sources

    def answer_question(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Retrieves context, invokes Mistral LLM, and returns the response with source citations.
        """
        if self.vector_store.count() == 0:
            return {
                "answer": "No Apple product data has been indexed yet. Please run ingestion or add URLs first.",
                "sources": [],
                "context_used_chars": 0
            }

        context, sources = self._retrieve_and_format_context(question, top_k=top_k)

        response = self.chain.invoke({
            "context": context,
            "question": question
        })

        return {
            "answer": str(response.content),
            "sources": sources,
            "context_used_chars": len(context)
        }

    async def stream_answer(self, question: str, top_k: int = 5) -> AsyncIterator[str]:
        """
        Streams response tokens as they are generated.
        """
        if self.vector_store.count() == 0:
            yield "No product data has been indexed yet. Please ingest seed URLs first."
            return

        context, _ = self._retrieve_and_format_context(question, top_k=top_k)

        async for chunk in self.chain.astream({
            "context": context,
            "question": question
        }):
            if chunk.content:
                yield str(chunk.content)
