import re
from typing import Dict, Any, List


class PolicyComplianceEngine:
    """
    Enforces Fair Debt Collection Practices, regulatory compliance,
    and SOP prohibitions across all agent responses.
    """

    PROHIBITED_PHRASES = [
        (r"we will send the police", "Threatening legal force is strictly prohibited."),
        (r"we will seize your property immediately", "Threat of immediate seizure without court order is prohibited."),
        (r"i guarantee (a )?(waiver|discount|settlement|reduction)", "Agents cannot guarantee debt waivers or discounts."),
        (r"i can reduce your emi to", "EMI reductions require formal credit committee approval."),
        (r"system prompt|api_key|token|internal instruction", "Internal instructions or secrets must never be leaked."),
    ]

    def validate_and_sanitize(
        self,
        response_text: str,
        intent: str,
        tool_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validates the generated response against compliance rules.
        Returns sanitized text and any compliance warnings or flags.
        """
        warnings = []
        is_compliant = True
        sanitized = response_text

        # 1. Prohibited phrases check
        for pattern, reason in self.PROHIBITED_PHRASES:
            if re.search(pattern, response_text, re.IGNORECASE):
                warnings.append(reason)
                is_compliant = False
                # Redact or sanitize
                sanitized = re.sub(pattern, "[Policy Compliant Action]", sanitized, flags=re.IGNORECASE)

        # 2. SOP Guardrail: Already Paid
        if intent == "ALREADY_PAID":
            verify_res = tool_results.get("verify_payment")
            if not verify_res or not verify_res.get("verified"):
                # Prohibit claiming payment is received without verification
                if re.search(r"payment (is|has been) (received|verified|cleared|credited)", response_text, re.IGNORECASE):
                    warnings.append("Payment cannot be confirmed as received without verified transaction reference.")
                    sanitized += " Please note that payment confirmation is still pending verification in our core records."
            elif verify_res.get("status") == "SUCCESS":
                amt = float(verify_res.get("amount", 0.0))
                p_date = verify_res.get("payment_date", "")
                is_partial = verify_res.get("is_partial_payment", False)
                rem_bal = float(verify_res.get("remaining_emi_balance", 0.0))

                if is_partial:
                    # Strictly intercept and sanitize hallucinated claims of "fully cleared" or "no payment due"
                    if re.search(r"(fully cleared|no payment (is )?due|zero balance|all cleared|cleared your emi|no payment due now|payment of ₹?12,?500)", sanitized, re.IGNORECASE):
                        warnings.append("Corrected hallucination: agent claimed full clearance for a partial payment.")
                        sanitized = f"I have verified your partial payment of ₹{amt:,.2f} on {p_date}. The remaining balance on your scheduled EMI is ₹{rem_bal:,.2f}."
                else:
                    # If full payment, ensure agent confirms clearance and doesn't tell customer to hold
                    if re.search(r"(please hold|hold for a moment|update you as soon as|wait a moment|will verify|will check)", sanitized, re.IGNORECASE):
                        sanitized = f"I have checked our system and verified your transaction. Your payment of ₹{amt:,.2f} on {p_date} was successful. Your EMI is marked as fully cleared, and you have no payment due at this time."

        # 3. SOP Guardrail: Financial Hardship
        if intent == "HARDSHIP":
            if re.search(r"i (have approved|will waive|approved) your hardship", response_text, re.IGNORECASE):
                warnings.append("Hardship requests are subject to approval; cannot be promised outright.")
                sanitized = re.sub(
                    r"i (have approved|will waive|approved) your hardship",
                    "I have registered your hardship request for formal review",
                    sanitized,
                    flags=re.IGNORECASE
                )

        return {
            "is_compliant": is_compliant,
            "warnings": warnings,
            "sanitized_response": sanitized
        }


_policy_engine_instance = None


def get_policy_engine() -> PolicyComplianceEngine:
    global _policy_engine_instance
    if _policy_engine_instance is None:
        _policy_engine_instance = PolicyComplianceEngine()
    return _policy_engine_instance
