import time
import json
from typing import Dict, Any, List, Optional
from backend.config import LLM_PROVIDER, MISTRAL_API_KEY, MISTRAL_MODEL, OLLAMA_BASE_URL, OLLAMA_MODEL
from backend.db.tools import (
    get_customer_account,
    get_payment_history,
    verify_payment_transaction,
    record_promise_to_pay,
    register_hardship_request,
    create_escalation_ticket,
    record_call_disposition,
    record_call_turn,
)
from backend.agent.memory import get_memory_manager
from backend.agent.router import get_query_router
from backend.agent.policy_engine import get_policy_engine
from backend.agent.prompts import SYSTEM_COLLECTION_AGENT_PROMPT, GROUNDED_RESPONSE_TEMPLATE
from backend.rag.hybrid_retriever import get_hybrid_retriever
from backend.services.tts_service import generate_speech_audio, get_voice_for_customer
from backend.services.metrics import (
    QUERY_TOTAL,
    RETRIEVAL_LATENCY,
    LLM_LATENCY,
    TOOL_EXECUTION_TOTAL,
    CALL_DISPOSITIONS_TOTAL,
)


class RAGCollectionAgentOrchestrator:
    """
    Main Agent Orchestrator. Coordinates Query Routing, Memory, Authoritative
    Database Tools, Hybrid Search, Compliance Policy Engine, and Voice TTS.
    """

    def __init__(self):
        self.router = get_query_router()
        self.memory = get_memory_manager()
        self.retriever = get_hybrid_retriever()
        self.policy_engine = get_policy_engine()
        self._init_llm()

    def _init_llm(self):
        """Initializes the LLM with low latency settings."""
        self.llm = None
        self.chain = None
        if LLM_PROVIDER == "mistral" and MISTRAL_API_KEY and "mstrl_" in MISTRAL_API_KEY:
            try:
                from langchain_mistralai import ChatMistralAI
                from langchain_core.prompts import PromptTemplate

                self.llm = ChatMistralAI(
                    model=MISTRAL_MODEL,
                    mistral_api_key=MISTRAL_API_KEY,
                    temperature=0.2,
                    max_tokens=250,
                    timeout=8.0
                )
                self.prompt_template = PromptTemplate.from_template(GROUNDED_RESPONSE_TEMPLATE)
                # LangChain Expression Language (LCEL) chain
                self.chain = self.prompt_template | self.llm
            except Exception as e:
                print(f"[Warning] Failed to initialize LangChain ChatMistralAI chain: {e}")

    async def process_turn(
        self,
        customer_id: str,
        message: str,
        session_id: Optional[str] = None,
        voice: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes an end-to-end agent turn:
        Routing -> Tool Execution -> Hybrid RAG -> LLM Synthesis -> Policy Checks -> TTS
        """
        start_time = time.time()
        session_id = session_id or f"sess_{customer_id}"

        # 1. Fetch Authoritative Customer Profile (Golden Rule: DB fact, not RAG)
        customer = get_customer_account(customer_id)
        if not customer:
            return {
                "error": f"Customer ID '{customer_id}' not found in core database.",
                "response": "I could not locate your customer account. Please confirm your customer ID.",
                "intent": "UNKNOWN",
                "citations": [],
                "tool_executions": []
            }

        # 2. Fetch Historical Context & Short-Term Memory
        past_context = self.memory.get_customer_historical_context(customer_id)
        past_summary = (
            f"Previous Call Intent: {past_context.get('last_intent')} | "
            f"Outcome: {past_context.get('last_outcome')} | "
            f"Summary: {past_context.get('last_summary')}"
            if past_context else "No prior recorded calls."
        )
        recent_turns = self.memory.get_conversation_history(session_id)

        # 3. Query Routing & Entity Extraction
        routed = self.router.route_query(message)
        intent = routed["intent"]
        txn_ref = routed["transaction_reference"]
        promised_date = routed["promised_date"]
        if language:
            lang_low = language.lower()
            for l_code in ["te", "hi", "ta", "ml", "en"]:
                if lang_low.startswith(l_code):
                    detected_lang = l_code
                    break
            else:
                detected_lang = routed.get("language", "en")
        else:
            detected_lang = routed.get("language", "en")

        # Fast-Path for Conversational Non-Financial Queries (CALL_CLOSING, GREETING, CHITCHAT)
        # Bypasses RAG vector search, core DB operations, and policy prompts for sub-200ms real-time latency
        if intent in ["GREETING", "CHITCHAT", "CALL_CLOSING"]:
            fast_response = self._generate_conversational_response(customer["name"], intent, detected_lang)
            disposition_outcome = (
                "CALL_COMPLETED" if intent == "CALL_CLOSING" else
                "GREETING" if intent == "GREETING" else
                "CHITCHAT"
            )
            selected_voice = voice if (voice and voice != "auto") else get_voice_for_customer(customer["name"], language=detected_lang)
            tts_result = await generate_speech_audio(fast_response, voice=selected_voice)
            
            self.memory.add_message(session_id, "user", message)
            self.memory.add_message(session_id, "assistant", fast_response)
            
            record_call_turn(
                customer_id=customer_id,
                session_id=session_id,
                user_message=message,
                agent_response=fast_response,
                intent=intent,
                outcome=disposition_outcome,
                sentiment="positive" if intent in ["GREETING", "CHITCHAT"] else "neutral"
            )
            
            QUERY_TOTAL.labels(intent=intent, status="success").inc()
            CALL_DISPOSITIONS_TOTAL.labels(outcome=disposition_outcome).inc()
            
            return {
                "customer_id": customer_id,
                "session_id": session_id,
                "intent": intent,
                "outcome": disposition_outcome,
                "is_escalated": False,
                "response": fast_response,
                "audio": tts_result,
                "tool_executions": [],
                "citations": [],
                "compliance_warnings": [],
                "turn_latency_ms": round((time.time() - start_time) * 1000, 2)
            }

        # 4. Tool Execution (Authoritative Database Actions)
        tool_results: Dict[str, Any] = {}
        tool_executions_log: List[Dict[str, Any]] = []

        if intent == "ALREADY_PAID" and txn_ref:
            res = verify_payment_transaction(txn_ref, customer_id=customer_id)

            if res.get("status") == "ACCOUNT_MISMATCH":
                res["is_account_mismatch"] = True
                res["verification_verdict"] = (
                    f"ACCOUNT MISMATCH (UNAUTHORIZED TRANSACTION): Transaction reference '{txn_ref}' is NOT registered under {customer['name']}'s loan account ({customer_id}). "
                    f"It belongs to a completely different customer. You MUST NOT accept this payment or clear their EMI balance! "
                    f"Explicitly inform {customer['name']} that this transaction reference is not associated with their account, "
                    f"and ask them to check their bank statement/receipt and provide their own valid UTR or payment reference."
                )
            elif res.get("verified"):
                v_amt = float(res.get("amount", 0.0))
                emi_amt = float(customer["emi_amount"])
                is_partial = v_amt < emi_amt
                remaining = max(0.0, emi_amt - v_amt)
                res["verified_amount"] = v_amt
                res["scheduled_emi"] = emi_amt
                res["is_partial_payment"] = is_partial
                res["remaining_emi_balance"] = remaining
                res["matched_reference"] = txn_ref
                if is_partial:
                    res["verification_verdict"] = (
                        f"PARTIAL PAYMENT VERIFIED: Customer paid ₹{v_amt:,.2f} under transaction reference '{txn_ref}'. "
                        f"Remaining EMI balance is ₹{remaining:,.2f}. Confirm that {txn_ref} is verified and ask for remaining balance."
                    )
                else:
                    customer["status"] = "PAYMENT_CLEARED"
                    res["verification_verdict"] = (
                        f"FULL PAYMENT VERIFIED: Full payment of ₹{v_amt:,.2f} under transaction reference '{txn_ref}' is CONFIRMED in records. "
                        f"Customer EMI is completely paid off. You MUST confirm that reference '{txn_ref}' was verified and their balance is fully cleared."
                    )
            else:
                missing_ref = txn_ref or "the provided reference"
                res["verification_verdict"] = (
                    f"NOT FOUND: Transaction reference '{missing_ref}' was not found in core banking records. "
                    f"Inform {customer['name']} that it was not found and ask them to double-check their bank receipt or UTR."
                )
            tool_results["verify_payment"] = res
            tool_executions_log.append({"tool": "verify_payment_transaction", "params": {"ref": txn_ref, "customer_id": customer_id}, "result": res})
            TOOL_EXECUTION_TOTAL.labels(tool_name="verify_payment_transaction", status="success" if res.get("verified") else "failed").inc()


        elif intent == "PROMISE_TO_PAY" and promised_date:
            res = record_promise_to_pay(customer_id, promised_date, customer["emi_amount"])
            tool_results["promise_to_pay"] = res
            tool_executions_log.append({"tool": "record_promise_to_pay", "params": {"date": promised_date}, "result": res})
            TOOL_EXECUTION_TOTAL.labels(tool_name="record_promise_to_pay", status="success").inc()

        elif intent == "HARDSHIP":
            res = register_hardship_request(customer_id, reason=message)
            tool_results["hardship"] = res
            tool_executions_log.append({"tool": "register_hardship_request", "params": {"reason": message}, "result": res})
            TOOL_EXECUTION_TOTAL.labels(tool_name="register_hardship_request", status="success").inc()

        elif intent == "DISPUTE":
            res = create_escalation_ticket(customer_id, category="PAYMENT_DISPUTE", reason=message)
            tool_results["dispute_ticket"] = res
            tool_executions_log.append({"tool": "create_escalation_ticket", "params": {"category": "PAYMENT_DISPUTE"}, "result": res})
            TOOL_EXECUTION_TOTAL.labels(tool_name="create_escalation_ticket", status="success").inc()

        elif intent == "ESCALATE":
            res = create_escalation_ticket(customer_id, category="HUMAN_AGENT_REQUEST", reason=message)
            tool_results["escalation_ticket"] = res
            tool_executions_log.append({"tool": "create_escalation_ticket", "params": {"category": "HUMAN_AGENT_REQUEST"}, "result": res})
            TOOL_EXECUTION_TOTAL.labels(tool_name="create_escalation_ticket", status="success").inc()

        # 5. Hybrid Retrieval (Gated for low latency: only when policy knowledge is needed)
        retrieval_start = time.time()
        citations = []
        retrieved_text = "Authoritative core banking database action applied directly."

        if intent in ["POLICY_INQUIRY", "DISPUTE", "REFUSAL_TO_PAY"] or (intent == "HARDSHIP" and not tool_results.get("hardship")):
            chunks = self.retriever.search(query=message, top_k=2, filter_status="Active")
            RETRIEVAL_LATENCY.observe(time.time() - retrieval_start)
            
            snippets = []
            for c in chunks:
                meta = c.get("metadata", {})
                snippets.append(c["text"])
                citations.append({
                    "title": meta.get("title", "Policy Document"),
                    "source": meta.get("source", "Knowledge Base"),
                    "version": meta.get("version"),
                    "score": c.get("rerank_score", 0.0),
                    "snippet": c["text"][:180] + "..."
                })
            if snippets:
                retrieved_text = "\n\n".join(snippets)

        # 6. Construct LLM Grounded Prompt
        conv_text = "\n".join([f"{t['role'].capitalize()}: {t['content']}" for t in recent_turns]) or "None."
        
        if tool_results.get("verify_payment"):
            vp = tool_results["verify_payment"]
            if vp.get("status") == "ACCOUNT_MISMATCH":
                mismatched_ref = vp.get("transaction_reference") or txn_ref or "the provided reference"
                tool_results_text = (
                    f"PAYMENT VERIFICATION REPORT:\n"
                    f"- VERIFICATION STATUS: REJECTED (ACCOUNT MISMATCH / SECURITY ALERT)\n"
                    f"- Searched Reference: {mismatched_ref}\n"
                    f"- Verdict: {vp.get('verification_verdict')}\n"
                    f"- CRITICAL DIRECTIVE: The transaction reference '{mismatched_ref}' does NOT belong to {customer['name']} ({customer_id}). "
                    f"Under NO circumstances should you credit this payment or say their EMI is cleared! "
                    f"You MUST explicitly inform {customer['name']} that this transaction reference is not registered to their loan account, and politely ask them to check their bank receipt and provide their own valid UTR/reference number."
                )
            elif vp.get("verified"):
                matched_ref = vp.get("transaction_reference") or txn_ref or "TXN"
                v_amt = vp.get("amount", 0.0)
                tool_results_text = (
                    f"PAYMENT VERIFICATION REPORT:\n"
                    f"- VERIFICATION STATUS: SUCCESS (CONFIRMED IN CORE BANKING RECORDS)\n"
                    f"- Matched Transaction Reference: {matched_ref}\n"
                    f"- Payment Amount Received: ₹{v_amt:,.2f}\n"
                    f"- Scheduled EMI Amount: ₹{customer['emi_amount']:,.2f}\n"
                    f"- Verdict: {vp.get('verification_verdict')}\n"
                    f"- CRITICAL DIRECTIVE: You MUST inform {customer['name']} that their payment under transaction '{matched_ref}' has been verified successfully. Under NO circumstances should you state that this transaction was not found."
                )
            else:
                missing_ref = txn_ref or "the provided reference"
                tool_results_text = (
                    f"PAYMENT VERIFICATION REPORT:\n"
                    f"- VERIFICATION STATUS: NOT FOUND IN DATABASE\n"
                    f"- Searched Reference: {missing_ref}\n"
                    f"- CRITICAL DIRECTIVE: Inform {customer['name']} that transaction reference '{missing_ref}' was not found in records and politely ask them to re-check their UTR number or bank receipt."
                )
        else:
            tool_results_text = str(tool_results) if tool_results else "No external tools executed in this turn."


        language_instructions_map = {
            "te": (
                "MANDATORY LANGUAGE: The customer communicated in Telugu. "
                "You MUST respond ONLY in polite, natural Telugu script (తెలుగు లిపి). Do NOT reply in English. "
                "Address customer respectfully with 'గారూ'. "
                "For refusal to pay, convince the customer by explaining that non-payment leads to late payment penalties (ఆలస్య రుసుము), "
                "damages their CIBIL credit score, and reduces future loan eligibility (భవిష్యత్తులో కొత్త రుణాలు పొందే అర్హత తగ్గుతుంది). "
                "Urge them to pay today to protect their credit standing."
            ),
            "hi": (
                "MANDATORY LANGUAGE: The customer communicated in Hindi. "
                "You MUST respond ONLY in polite, natural Hindi in Devanagari script (हिन्दी / देवनागरी लिपि). Do NOT reply in English. "
                "Address customer respectfully with 'जी' or 'आप'. "
                "For refusal to pay, convince the customer by explaining that non-payment incurs late fees (विलंब शुल्क), "
                "damages their CIBIL score, and harms future loan approvals across all financial institutions. "
                "Urge them to clear the EMI today to safeguard their credit profile."
            ),
            "ta": (
                "MANDATORY LANGUAGE: The customer communicated in Tamil. "
                "You MUST respond ONLY in polite, natural Tamil script (தமிழ் எழுத்துரு). Do NOT reply in English. "
                "Address customer respectfully with 'அவர்கள்' or 'சார்' / 'மேடம்'. "
                "For refusal to pay, explain that non-payment leads to late penalties (தாமதக் கட்டணம்), damages CIBIL score, "
                "and severely affects future bank loan approvals. Urge them to make the payment today to protect their credit standing."
            ),
            "ml": (
                "MANDATORY LANGUAGE: The customer communicated in Malayalam. "
                "You MUST respond ONLY in polite, natural Malayalam script (മലയാള ലിപി). Do NOT reply in English. "
                "Address customer respectfully with 'സാർ' or 'മാഡം'. "
                "For refusal to pay, explain that non-payment incurs late charges (ലെയ്റ്റ് ഫീസ്), severely damages CIBIL credit score, "
                "and restricts future loan access from all banks. Urge them to clear the EMI today to preserve their credit rating."
            ),
            "en": "MANDATORY LANGUAGE: Respond in clear, professional English. Be empathetic, concise, and direct."
        }
        language_instruction = language_instructions_map.get(detected_lang, language_instructions_map["en"])


        prompt = GROUNDED_RESPONSE_TEMPLATE.format(
            system_prompt=SYSTEM_COLLECTION_AGENT_PROMPT,
            customer_id=customer["customer_id"],
            name=customer["name"],
            salutation=customer.get("salutation", "Mr."),
            loan_id=customer["loan_id"],
            product_id=customer["product_id"],
            emi_amount=customer["emi_amount"],
            emi_due_date=customer["emi_due_date"],
            status=customer["status"],
            promise_to_pay_date=customer.get("promise_to_pay_date") or "None",
            hardship_flag="Yes" if customer.get("hardship_flag") else "No",
            language_instruction=language_instruction,
            past_call_summary=past_summary,
            retrieved_context=retrieved_text,
            tool_results_text=tool_results_text,
            conversation_history=conv_text,
            customer_message=message
        )

        # 7. Generate Response via LangChain LCEL Chain (PromptTemplate | ChatMistralAI)
        llm_start = time.time()
        raw_response = ""
        if self.chain:
            try:
                res = self.chain.invoke({
                    "system_prompt": SYSTEM_COLLECTION_AGENT_PROMPT,
                    "customer_id": customer["customer_id"],
                    "name": customer["name"],
                    "salutation": customer.get("salutation", "Mr."),
                    "loan_id": customer["loan_id"],
                    "product_id": customer["product_id"],
                    "emi_amount": customer["emi_amount"],
                    "emi_due_date": customer["emi_due_date"],
                    "status": customer["status"],
                    "promise_to_pay_date": customer.get("promise_to_pay_date") or "None",
                    "hardship_flag": "Yes" if customer.get("hardship_flag") else "No",
                    "language_instruction": language_instruction,
                    "past_call_summary": past_summary,
                    "retrieved_context": retrieved_text,
                    "tool_results_text": tool_results_text,
                    "conversation_history": conv_text,
                    "customer_message": message
                })
                raw_response = res.content.strip()
                LLM_LATENCY.observe(time.time() - llm_start)
            except Exception as e:
                print(f"[LangChain Chain Error] {e}. Trying direct LLM fallback.")

        if not raw_response and self.llm:
            try:
                res = self.llm.invoke(prompt)
                raw_response = res.content.strip()
                LLM_LATENCY.observe(time.time() - llm_start)
            except Exception as e:
                print(f"[LLM Error] {e}. Using deterministic grounded generator.")

        if not raw_response:
            raw_response = self._generate_deterministic_response(customer, intent, tool_results, message, detected_lang)

        # 8. Policy & Regulatory Compliance Validation
        compliance_check = self.policy_engine.validate_and_sanitize(
            response_text=raw_response,
            intent=intent,
            tool_results=tool_results
        )
        final_response = compliance_check["sanitized_response"]

        # 9. Tri-Modal Output Classification (Answer / Tool Call / Escalate)
        is_escalated = intent in ["ESCALATE", "DISPUTE"] or "escalation_ticket" in tool_results or "dispute_ticket" in tool_results
        disposition_outcome = (
            "ESCALATED" if is_escalated else
            "ALREADY_PAID" if intent == "ALREADY_PAID" and tool_results.get("verify_payment", {}).get("verified") else
            "PAYMENT_PENDING_VERIFICATION" if intent == "ALREADY_PAID" else
            "HARDSHIP" if intent == "HARDSHIP" else
            "WILL_PAY" if intent == "PROMISE_TO_PAY" else
            "REFUSAL_TO_PAY" if intent == "REFUSAL_TO_PAY" else
            "INFORMATION_PROVIDED"
        )

        # 10. Voice Synthesis with Selected or Gender Inverted Voice Tone & Language
        selected_voice = voice if (voice and voice != "auto") else get_voice_for_customer(customer["name"], language=detected_lang)
        tts_result = await generate_speech_audio(final_response, voice=selected_voice)

        # 11. Update Memory & Records
        self.memory.add_message(session_id, "user", message)
        self.memory.add_message(session_id, "assistant", final_response)
        
        # Maintain a SINGLE call history record for this entire call session
        record_call_turn(
            customer_id=customer_id,
            session_id=session_id,
            user_message=message,
            agent_response=final_response,
            intent=intent,
            outcome=disposition_outcome,
            sentiment="negative" if intent in ["DISPUTE", "REFUSAL_TO_PAY"] else "neutral"
        )

        # Prometheus metrics
        QUERY_TOTAL.labels(intent=intent, status="success").inc()
        CALL_DISPOSITIONS_TOTAL.labels(outcome=disposition_outcome).inc()

        return {
            "customer_id": customer_id,
            "session_id": session_id,
            "intent": intent,
            "outcome": disposition_outcome,
            "is_escalated": is_escalated,
            "response": final_response,
            "audio": tts_result,
            "tool_executions": tool_executions_log,
            "citations": citations,
            "compliance_warnings": compliance_check["warnings"],
            "turn_latency_ms": round((time.time() - start_time) * 1000, 2)
        }

    def _generate_deterministic_response(
        self,
        customer: Dict[str, Any],
        intent: str,
        tool_results: Dict[str, Any],
        user_message: str,
        detected_lang: str = "en"
    ) -> str:
        """Robust deterministic grounded response generator if LLM is unavailable."""
        name = customer["name"]
        emi = f"₹{customer['emi_amount']:,.2f}"
        due_date = customer["emi_due_date"]
        lang = detected_lang if detected_lang in ["te", "hi", "ta", "ml"] else "en"

        if intent == "CHECK_BALANCE":
            if lang == "te":
                return f"నమస్కారం {name} గారూ, మీ నెలవారీ EMI బకాయి {emi}, ఇది {due_date} నాటికి చెల్లించాల్సి ఉంది."
            if lang == "hi":
                return f"नमस्ते {name} जी, आपका मासिक ईएमआई (EMI) बकाया {emi} है, जो {due_date} तक देय था।"
            if lang == "ta":
                return f"வணக்கம் {name} அவர்களே, உங்கள் மாதாந்திர தவணைத் தொகை (EMI) {emi}, இது {due_date} தேதிக்குள் செலுத்த வேண்டியிருந்தது."
            if lang == "ml":
                return f"നമസ്കാരം {name} സാർ, നിങ്ങളുടെ പ്രതിമാസ ഇ.എം.ഐ കുടിശ്ശിക {emi} ആണ്, ഇത് {due_date}-ന് അടക്കേണ്ടതായിരുന്നു."
            return f"Hello {name}, your scheduled EMI amount is {emi}, which was due on {due_date}. Your account is currently marked as {customer['status']}."

        if intent == "ALREADY_PAID":
            verify = tool_results.get("verify_payment")
            if verify and verify.get("status") == "ACCOUNT_MISMATCH":
                m_ref = verify.get("transaction_reference") or "the provided reference"
                if lang == "te":
                    return f"{name} గారూ, మీరు తెలిపిన లావాదేవీ సంఖ్య {m_ref} మీ లోన్ ఖాతాతో సరిపోలడం లేదు. దయచేసి మీ స్వంత చెల్లింపు రశీదు లేదా UTR నంబర్‌ను సరిచూసి తెలపండి."
                if lang == "hi":
                    return f"{name} जी, आपने जो ट्रांजेक्शन नंबर {m_ref} साझा किया है वह आपके लोन खाते में दर्ज नहीं है। कृपया अपनी बैंक रसीद से सही UTR या रेफरेंस नंबर प्रदान करें।"
                if lang == "ta":
                    return f"{name} அவர்களே, நீங்கள் குறிப்பிட்ட பரிவர்த்தனை எண் {m_ref} உங்கள் கடன் கணக்கில் பதிவு செய்யப்படவில்லை. தயவுசெய்து உங்கள் சொந்த கட்டண ரசீது அல்லது UTR எண்ணைப் பகிரவும்."
                if lang == "ml":
                    return f"{name} സാർ, നിങ്ങൾ നൽകിയ ട്രാൻസാക്ഷൻ നമ്പർ {m_ref} നിങ്ങളുടെ ലോൺ അക്കൗണ്ടുമായി പൊരുത്തപ്പെടുന്നില്ല. ദയവായി നിങ്ങളുടെ ബാങ്ക് രസീത് പരിശോധിച്ച് ശരിയായ UTR നമ്പർ നൽകുക."
                return f"{customer.get('salutation', 'Mr.')} {name}, transaction reference {m_ref} is not registered under your loan account. Please verify your payment receipt and provide the UTR issued for your own account."

            elif verify and verify.get("verified"):
                v_amt = verify.get("amount", customer["emi_amount"])
                if v_amt >= customer["emi_amount"]:
                    if lang == "te":
                        return f"ధన్యవాదాలు {name} గారూ. మీ లావాదేవీని ధృవీకరించాము. మీ చెల్లింపు ₹{v_amt:,.2f} పూర్తయింది. మీ EMI పూర్తిగా క్లియర్ చేయబడింది."
                    if lang == "hi":
                        return f"धन्यवाद {name} जी। हमने आपके लेनदेन का सत्यापन कर लिया है। आपका ₹{v_amt:,.2f} का भुगतान सफल रहा है और ईएमआई पूर्ण रूप से चुकता हो चुकी है।"
                    if lang == "ta":
                        return f"நன்றி {name} அவர்களே. உங்கள் பரிவர்த்தனை வெற்றிகரமாக சரிபார்க்கப்பட்டது. உங்கள் ₹{v_amt:,.2f} கட்டணம் பெறப்பட்டு EMI முழுமையாக செலுத்தப்பட்டுள்ளது."
                    if lang == "ml":
                        return f"നന്ദി {name} സാർ. നിങ്ങളുടെ ഇടപാട് പരിശോധിച്ചു ഉറപ്പുവരുത്തി. ₹{v_amt:,.2f} അടവ് വിജയകരമായി പൂർത്തിയായി, ഇ.എം.ഐ ക്ലിയർ ചെയ്തിട്ടുണ്ട്."
                    return f"Thank you for confirming, {name}. I have checked our system and verified your transaction. Your payment of ₹{v_amt:,.2f} was successful. Your EMI is fully cleared, and you have no payment due at this time."
                else:
                    rem = customer['emi_amount'] - v_amt
                    if lang == "te":
                        return f"ధన్యవాదాలు {name} గారూ. మీ పాక్షిక చెల్లింపు ₹{v_amt:,.2f} ధృవీకరించబడింది. మీ EMI బకాయి ఇంకా ₹{rem:,.2f} మిగిలి ఉంది."
                    if lang == "hi":
                        return f"धन्यवाद {name} जी। आपका ₹{v_amt:,.2f} का आंशिक भुगतान सत्यापित हो गया है। आपकी ईएमआई का शेष बकाया ₹{rem:,.2f} है।"
                    if lang == "ta":
                        return f"நன்றி {name} அவர்களே. உங்கள் பகுதி கட்டணம் ₹{v_amt:,.2f} பெறப்பட்டது. மீதமுள்ள தவணைத் தொகை ₹{rem:,.2f} ஆகும்."
                    if lang == "ml":
                        return f"നന്ദി {name} സാർ. നിങ്ങളുടെ ഭാഗിക അടവ് ₹{v_amt:,.2f} സ്ഥിരീകരിച്ചു. ബാക്കി കുടിശ്ശിക ₹{rem:,.2f} ആണ്."
                    return f"Thank you for confirming, {name}. I have verified your partial payment of ₹{v_amt:,.2f}. The remaining balance on your scheduled EMI is ₹{(customer['emi_amount'] - v_amt):,.2f}."
            else:
                if lang == "te":
                    return f"ధన్యవాదాలు {name} గారూ. మీరు చెల్లింపు చేసి ఉంటే, దయచేసి ట్రాన్సాక్షన్ నంబర్ లేదా UTR తెలపండి, మేము వెంటనే సరిచూస్తాము."
                if lang == "hi":
                    return f"धन्यवाद {name} जी। यदि आपने भुगतान कर दिया है, तो कृपया अपना ट्रांजेक्शन नंबर या UTR बताएं, हम तुरंत जांच कर लेंगे।"
                if lang == "ta":
                    return f"நன்றி {name} அவர்களே. நீங்கள் ஏற்கனவே கட்டணம் செலுத்தியிருந்தால், தயவுசெய்து உங்கள் பரிவர்த்தனை எண் அல்லது UTR-ஐ தெரிவிக்கவும், நாங்கள் உடனே சரிபார்க்கிறோம்."
                if lang == "ml":
                    return f"നന്ദി {name} സാർ. നിങ്ങൾ പണം അടച്ചിട്ടുണ്ടെങ്കിൽ, ദയവായി ട്രാൻസാക്ഷൻ നമ്പർ അല്ലെങ്കിൽ UTR നൽകുക, ഞങ്ങൾ ഉടൻ പരിശോധിക്കാം."
                return f"Thank you, {name}. If you have already made the payment, could you please provide your transaction reference number or UTR so our system can immediately verify it?"

        if intent == "PROMISE_TO_PAY":
            p_date = customer.get("promise_to_pay_date", "the agreed date")
            if lang == "te":
                return f"ధన్యవాదాలు {name} గారూ. మీరు {p_date} తేదీన EMI {emi} చెల్లిస్తానని తెలిపిన వివరాలను నమోదు చేసుకున్నాము."
            if lang == "hi":
                return f"धन्यवाद {name} जी। हमने {p_date} को आपका ईएमआई {emi} भुगतान करने का वादा दर्ज कर लिया है।"
            if lang == "ta":
                return f"நன்றி {name} அவர்களே. {p_date} தேதியில் உங்கள் EMI {emi} செலுத்துவதாக நீங்கள் கூறியதை பதிவு செய்துள்ளோம்."
            if lang == "ml":
                return f"നന്ദി {name} സാർ. {p_date}-ൽ നിങ്ങളുടെ ഇ.എം.ഐ {emi} അടക്കാമെന്ന വാഗ്ദാനം ഞങ്ങൾ രേഖപ്പെടുത്തിയിട്ടുണ്ട്."
            return f"Thank you for confirming, {name}. We have noted your commitment to pay your EMI of {emi} on {p_date}. We will send you a confirmation reminder."

        if intent == "HARDSHIP":
            if lang == "te":
                return f"మీ సమస్యను మేము అర్థం చేసుకున్నాము {name} గారూ. మీ అభ్యర్థనను సహాయక సమీక్ష కొరకు నమోదు చేశాము, మా బృందం మిమ్మల్ని సంప్రదిస్తుంది."
            if lang == "hi":
                return f"हम आपकी समस्या समझते हैं {name} जी। हमने आपकी वित्तीय कठिनाई समीक्षा का अनुरोध दर्ज कर लिया है, हमारी सहायता टीम आपसे संपर्क करेगी।"
            if lang == "ta":
                return f"உங்கள் சூழ்நிலையை நாங்கள் புரிந்துகொள்கிறோம் {name} அவர்களே. உங்கள் நிதிச் சிரமத்திற்கான மறுஆய்வு கோரிக்கையை பதிவு செய்துள்ளோம், எங்கள் குழு தொடர்பு கொள்ளும்."
            if lang == "ml":
                return f"നിങ്ങളുടെ ബുദ്ധിമുട്ട് ഞങ്ങൾ മനസ്സിലാക്കുന്നു {name} സാർ. നിങ്ങളുടെ ധനകാര്യ സഹായ അവലോകന അഭ്യർത്ഥന ഞങ്ങൾ രജിസ്റ്റർ ചെയ്തിട്ടുണ്ട്, ഞങ്ങളുടെ സംഘം ബന്ധപ്പെടും."
            return f"I understand your difficult situation, {name}, and we truly appreciate you letting us know. I have registered a financial hardship review request for your account, and our hardship team will follow up to evaluate available assistance options."

        if intent == "DISPUTE":
            ticket = tool_results.get("dispute_ticket", {}).get("escalation_id", "DISPUTE-CASE")
            if lang == "te":
                return f"మీ సమస్యను నమోదు చేసుకున్నాము {name} గారూ. టికెట్ నంబర్ ({ticket}) రూపొందించబడింది, మా బృందం దీనిపై విచారణ చేస్తుంది."
            if lang == "hi":
                return f"आपकी शिकायत दर्ज कर ली गई है {name} जी। टिकट संख्या ({ticket}) जारी की गई है, हमारी जांच टीम इसका समाधान करेगी।"
            if lang == "ta":
                return f"உங்கள் கோரிக்கை பதிவு செய்யப்பட்டது {name} அவர்களே. புகார் எண் ({ticket}) உருவாக்கப்பட்டுள்ளது, எங்கள் குழு ஆய்வு செய்யும்."
            if lang == "ml":
                return f"നിങ്ങളുടെ പരാതി രജിസ്റ്റർ ചെയ്തിട്ടുണ്ട് {name} സാർ. പരാതി നമ്പർ ({ticket}) നൽകിയിട്ടുണ്ട്, ഞങ്ങളുടെ സംഘം ഉടൻ പരിശോധിക്കും."
            return f"We acknowledge your concern regarding your account details, {name}. A dispute ticket ({ticket}) has been opened for our accounts team to review the discrepancy."

        if intent == "REFUSAL_TO_PAY":
            if lang == "te":
                return (
                    f"{name} గారూ, మీరు EMI చెల్లించకపోతే ఆలస్య రుసుము (penal charges) పడుతుంది మరియు మీ CIBIL స్కోర్ తీవ్రంగా దెబ్బతింటుంది. "
                    f"దీనివల్ల భవిష్యత్తులో మీకు బ్యాంకుల నుండి ఎలాంటి కొత్త రుణాలు లభించే అర్హత తగ్గుతుంది. "
                    f"దయచేసి మీ క్రెడిట్ స్కోర్ కాపాడుకోవడానికి వీలైనంత త్వరగా బకాయిని చెల్లించండి."
                )
            if lang == "hi":
                return (
                    f"{name} जी, कृपया समझें कि ईएमआई न चुकाने पर विलंब शुल्क लगता है और आपका CIBIL स्कोर खराब होता है। "
                    f"इससे भविष्य में किसी भी बैंक से नया ऋण मिलना मुश्किल हो जाएगा। अपना क्रेडिट स्कोर सुरक्षित रखने के लिए आज ही भुगतान करें।"
                )
            if lang == "ta":
                return (
                    f"{name} அவர்களே, தவணைத் தொகை செலுத்தத் தவறினால் தாமத அபராதக் கட்டணம் விதிக்கப்படும் மற்றும் உங்கள் சிபில் (CIBIL) மதிப்பெண் பாதிக்கப்படும். "
                    f"இது எதிர்காலத்தில் புதிய கடன்கள் பெறுவதைத் தடுக்கும். உங்கள் கடன் தகுதியைப் பாதுகாக்க இன்றே செலுத்தவும்."
                )
            if lang == "ml":
                return (
                    f"{name} സാർ, ഇ.എം.ഐ കൃത്യസമയത്ത് അടക്കാതിരുന്നാൽ പിഴ ഈടാക്കുകയും നിങ്ങളുടെ സിബിൽ (CIBIL) സ്കോർ താഴുകയും ചെയ്യും. "
                    f"ഇത് ഭാവിയിൽ ലോണുകൾ ലഭിക്കുന്നതിന് തടസ്സമാകും. നിങ്ങളുടെ ക്രെഡിറ്റ് സ്കോർ സംരക്ഷിക്കാൻ ദയവായി ഉടൻ പണമടക്കുക."
                )
            return (
                f"{name}, please understand that non-payment incurs late payment penalties and lowers your CIBIL credit score. "
                f"A reduced credit score will severely impact your future loan eligibility across all banks. "
                f"We strongly urge you to make a payment to protect your credit profile."
            )

        if intent == "ESCALATE":
            ticket = tool_results.get("escalation_ticket", {}).get("escalation_id", "ESC-CARE")
            if lang == "te":
                return f"ఖచ్చితంగా {name} గారూ. మీ కోసం టికెట్ ({ticket}) రూపొందించాము, మా సీనియర్ అధికారి మిమ్మల్ని త్వరలో సంప్రదిస్తారు."
            if lang == "hi":
                return f"निश्चिंत रहें {name} जी। आपके लिए टिकट ({ticket}) बना दिया गया है, हमारे वरिष्ठ अधिकारी शीघ्र ही आपसे संपर्क करेंगे।"
            if lang == "ta":
                return f"நிச்சயமாக {name} அவர்களே. டிக்கெட் ({ticket}) உருவாக்கப்பட்டுள்ளது, எங்கள் உயர் அதிகாரி விரைவில் உங்களைத் தொடர்புகொள்வார்."
            if lang == "ml":
                return f"തീർച്ചയായും {name} സാർ. നിങ്ങൾക്കായി ടിക്കറ്റ് ({ticket}) തയ്യാറാക്കിയിട്ടുണ്ട്, ഞങ്ങളുടെ സീനിയർ ഓഫീസർ ഉടൻ ബന്ധപ്പെടും."
            return f"I understand, {name}. I have created an escalation ticket ({ticket}) and routed your case to a senior representative who will assist you shortly."

        # Policy inquiry default
        if lang == "te":
            return f"{name} గారూ, మా పాలసీ ప్రకారం గడువు ముగిసిన తర్వాత ఆలస్య రుసుము వర్తిస్తుంది. మీ ప్రస్తుత EMI బకాయి {emi}."
        if lang == "hi":
            return f"{name} जी, बैंक नीति के अनुसार देय तिथि के बाद विलंब शुल्क लागू होता है। आपकी वर्तमान ईएमआई बकाया {emi} है।"
        if lang == "ta":
            return f"{name} அவர்களே, கொள்கைப்படி தவணைத் தேதி கடந்த பின் தாமதக் கட்டணம் விதிக்கப்படும். உங்கள் தற்போதைய நிலுவைத் தொகை {emi}."
        if lang == "ml":
            return f"{name} സാർ, ബാങ്ക് പോളിസി പ്രകാരം നിശ്ചിത തീയതി കഴിഞ്ഞാൽ ലെയ്റ്റ് ഫീസ് ബാധകമാണ്. നിങ്ങളുടെ നിലവിലെ ഇ.എം.ഐ കുടിശ്ശിക {emi} ആണ്."
        return f"Regarding your inquiry, {name}: under our active policy, an eligible grace period applies and late fees are governed by the contractual terms of your loan. Your current due EMI is {emi}."

    def _generate_conversational_response(self, name: str, intent: str, lang: str) -> str:
        """Generates natural, instant conversational responses across 5 Pan-Indian languages."""
        l = lang if lang in ["te", "hi", "ta", "ml"] else "en"

        if intent == "GREETING":
            if l == "te":
                return f"నమస్కారం {name} గారూ, ఈ రోజు నేను మీకు ఎలా సహాయపడగలను?"
            if l == "hi":
                return f"नमस्ते {name} जी, आज मैं आपकी क्या सहायता कर सकता हूँ?"
            if l == "ta":
                return f"வணக்கம் {name} அவர்களே, இன்று நான் உங்களுக்கு எவ்வாறு உதவ முடியும்?"
            if l == "ml":
                return f"നമസ്കാരം {name} സാർ, ഇന്ന് ഞാൻ അങ്ങയെ എങ്ങനെ സഹായിക്കണം?"
            return f"Hello {name}, how may I assist you today?"

        if intent == "CHITCHAT":
            if l == "te":
                return f"నేను బాగున్నాను, మీరు కూడా బాగున్నారని ఆశిస్తున్నాను {name} గారూ! చెప్పండి, నేను మీకు ఎలా సహాయపడగలను?"
            if l == "hi":
                return f"मैं बहुत अच्छा हूँ, आशा है आप भी सकुशल होंगे {name} जी! बताइए, मैं आपकी क्या सहायता कर सकता हूँ?"
            if l == "ta":
                return f"நான் நலமாக உள்ளேன், நீங்களும் நலமாக இருக்கிறீர்கள் என நம்புகிறேன் {name} அவர்களே! சொல்லுங்கள், நான் உங்களுக்கு எவ்வாறு உதவலாம்?"
            if l == "ml":
                return f"സുഖമായിരിക്കുന്നു, അങ്ങേയ്ക്കും സുഖമെന്ന് കരുതുന്നു {name} സാർ! പറയൂ, ഞാൻ എങ്ങനെ സഹായിക്കണം?"
            return f"I'm doing good, hope you're doing great {name}! Tell me, how can I help you today?"

        # CALL_CLOSING (e.g. "no thanks", "nothing else", "bye", "all good")
        if l == "te":
            return f"మాతో బ్యాంకింగ్ చేసినందుకు ధన్యవాదాలు {name} గారూ. భవిష్యత్తులో ఏదైనా సహాయం కావాలంటే దయచేసి మమ్మల్ని సంప్రదించడానికి సంకోచించకండి. ధన్యవాదాలు, మీకు శుభదినం!"
        if l == "hi":
            return f"हमारे साथ बैंकिंग करने के लिए धन्यवाद {name} जी। यदि भविष्य में किसी अन्य सहायता की आवश्यकता हो, तो कृपया बेझिझक दोबारा कॉल करें। धन्यवाद, आपका दिन शुभ हो!"
        if l == "ta":
            return f"எங்களுடன் வங்கி சேவை பெற்றதற்கு நன்றி {name} அவர்களே. மேலும் உதவி தேவைப்பட்டால் தயங்காமல் எங்களை மீண்டும் அழைக்கவும். நன்றி, இனிய நாளாக அமையட்டும்!"
        if l == "ml":
            return f"ഞങ്ങളുമായി ബാങ്കിംഗ് സേവനം തുടരുന്നതിന് നന്ദി {name} സാർ. കൂടുതൽ സഹായം ആവശ്യമുണ്ടെങ്കിൽ ദയവായി വീണ്ടും വിളിക്കാൻ മടിക്കരുത്. നന്ദി, നല്ലൊരു ദിവസം ആശംസിക്കുന്നു!"
        return f"Thank you for banking with us, {name}. If further assistance is required, please do not hesitate to call back. Thank you, have a nice day!"




_orchestrator_instance = None


def get_orchestrator() -> RAGCollectionAgentOrchestrator:
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = RAGCollectionAgentOrchestrator()
    return _orchestrator_instance
