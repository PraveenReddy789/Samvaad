# RAG Voice Collection Project — Synthetic Dataset

This dataset is synthetic and is intended for learning and portfolio development.

## Retrieval responsibilities
- policies/: policy and version/effective-date knowledge
- sop/: operational procedures
- products/: general product knowledge
- calls/: conversation history for customer-aware retrieval
- customers/customers.csv: structured customer/account facts
- customers/payments.csv: structured payment facts

## Important architecture rule
Do NOT use RAG to answer customer-specific facts such as current EMI, outstanding balance, or payment status when an authoritative database/API is available.

Use:
- RAG → policies, SOPs, product knowledge, historical conversation context
- SQL/API/tool → current customer and payment facts
- LLM → grounded response generation
