# Expense Claim Workflow API

A small FastAPI backend that uses the **Claude API** to process employee expense claims.


### `POST /claims/analyse`

```json
{ "description": "Grab ride from KLIA to the office on 20 Oct 2026, RM 85.50" }
```

Returns the validated `ClaimExtraction` plus token usage:

```json
{
  "analysis": {
    "category": "travel",
    "amount": 85.5,
    "currency": "MYR",
    "expense_date": "2026-10-20",
    "summary": "Grab ride from KLIA to Petronas office for client meeting.",
    "missing_info": []
  },
  "model": "claude-sonnet-4-6",
  "input_tokens": 965,
  "output_tokens": 56
}
```

### `POST /claims/submit`

```json
{
  "claim_id": "CLM-89C732C4",
  "employee_id": "E001",
  "claimed_amount": 85.5,
  "status": "auto_approved",
  "reasons": [],
  "policy_limit": 500.0,
  "extraction": {
    "category": "travel",
    "amount": 85.5,
    "currency": "MYR",
    "expense_date": "2026-10-20",
    "summary": "Grab ride from KLIA to Petronas office for a client meeting.",
    "missing_info": []
  },
  "reply_message": "Hi Aisyah, great news! Your expense claim for the Grab ride from KLIA to the Petronas office for your client meeting has been automatically approved. No further action is needed from your side. Thank you for submitting your claim promptly!",
  "created_at": "2026-10-29T08:10:33.861460Z"
}
```
