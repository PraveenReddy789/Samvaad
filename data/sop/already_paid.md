# Already Paid — Collection SOP

## Trigger
Customer says the EMI or outstanding amount has already been paid.

## Agent Actions
1. Acknowledge the customer's statement.
2. Ask for the approximate payment date, amount, and transaction reference if available.
3. Do not repeatedly demand payment while verification is pending.
4. Use the payment-status tool/API to verify the transaction.
5. If verified, record the payment and close or update the collection disposition.
6. If not found, explain that verification is still pending and route the case when required.

## Allowed Outcome
`ALREADY_PAID`, `PAYMENT_PENDING_VERIFICATION`, or `ESCALATE_PAYMENT_DISPUTE`.

## Prohibited
Never claim a payment is successful without verification.
