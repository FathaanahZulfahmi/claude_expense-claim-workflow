import logging
from datetime import datetime, timezone
from uuid import uuid4

from anthropic import APIError

from app.prompts.claim_extraction import CLAIM_EXTRACTION_SYSTEM_PROMPT
from app.prompts.claim_reply import CLAIM_REPLY_SYSTEM_PROMPT
from app.repositories.claim_repository import ClaimRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.policy_repository import PolicyRepository
from app.schemas.claim import (
    ClaimExtraction,
    ClaimReply,
    ClaimResult,
    ClaimStatus,
    ClaimSubmitRequest,
)
from app.services.claude_service import (
    ClaudeResponseError,
    ClaudeService,
    ClaudeStructuredResult,
)

# route -> ClaimService -> ClaudeService / repositories
# This service holds the expense-claim use cases. Claude extracts data and
# writes text; the business decision is made by decide_claim() below.

logger = logging.getLogger(__name__)


class EmployeeNotFoundError(Exception):
    pass


class EmployeeNotAllowedError(Exception):
    pass


def decide_claim(
    extraction: ClaimExtraction,
    claimed_amount: float,
    policy: dict | None,
) -> tuple[ClaimStatus, list[str]]:
    # Plain Python business rules: no AI involved. Every rule that fails
    # adds a reason; any reason at all sends the claim to a human reviewer.
    reasons: list[str] = []

    if policy is None:
        reasons.append(f"No expense policy is configured for category '{extraction.category.value}'.")
    else:
        if claimed_amount > policy["max_amount"]:
            reasons.append(
                f"Claimed amount {claimed_amount:.2f} exceeds the {extraction.category.value} "
                f"limit of {policy['max_amount']:.2f} {policy['currency']}."
            )
        if extraction.currency != policy["currency"]:
            reasons.append(f"Currency must be {policy['currency']} (found: {extraction.currency or 'none'}).")

    # Cross-check: never trust either the user's number or Claude's alone.
    if extraction.amount is None:
        reasons.append("No amount was found in the description.")
    elif abs(extraction.amount - claimed_amount) > 0.01:
        reasons.append(
            f"Claimed amount {claimed_amount:.2f} does not match the amount in the "
            f"description ({extraction.amount:.2f})."
        )

    if extraction.missing_info:
        reasons.append("Missing information: " + ", ".join(extraction.missing_info) + ".")

    status = ClaimStatus.NEEDS_REVIEW if reasons else ClaimStatus.AUTO_APPROVED
    return status, reasons


def fallback_reply(name: str, status: ClaimStatus, reasons: list[str]) -> str:
    # Used when Claude cannot write the reply, so the workflow still finishes.
    first_name = name.split()[0]
    if status == ClaimStatus.AUTO_APPROVED:
        return f"Hi {first_name}, your expense claim has been approved."
    return f"Hi {first_name}, your claim needs review by finance. Reasons: " + " ".join(reasons)


class ClaimService:
    def __init__(self, claude_service: ClaudeService) -> None:
        # Passed in (not created here) so the route controls its lifecycle.
        self.claude_service = claude_service

    async def analyse(self, description: str) -> ClaudeStructuredResult[ClaimExtraction]:
        # The untrusted description is wrapped in tags so the system prompt
        # can tell Claude exactly which part is data, not instructions.
        user_prompt = f"<claim_description>\n{description}\n</claim_description>"

        return await self.claude_service.generate_structured(
            user_prompt,
            output_model=ClaimExtraction,
            system=CLAIM_EXTRACTION_SYSTEM_PROMPT,
            max_tokens=500,
        )

    async def submit(
        self,
        request: ClaimSubmitRequest,
        *,
        employees: EmployeeRepository,
        policies: PolicyRepository,
        claims: ClaimRepository,
    ) -> ClaimResult:
        # Step 1: the APP checks who may submit (before spending on Claude).
        employee = await employees.get_by_id(request.employee_id)
        if employee is None:
            raise EmployeeNotFoundError(request.employee_id)
        if not employee["active"]:
            raise EmployeeNotAllowedError(request.employee_id)

        # Step 2: Claude extracts structured data (validated by Pydantic).
        extraction = (await self.analyse(request.description)).data

        # Step 3: load the policy for the category Claude chose.
        policy = await policies.get_by_category(extraction.category.value)

        # Step 4: the APP decides, using plain rules.
        status, reasons = decide_claim(extraction, request.claimed_amount, policy)

        # Step 5: Claude explains the decision. A failure here should not
        # lose the claim, so fall back to a template message instead.
        reply_message = await self._draft_reply(employee["name"], status, reasons, extraction)

        # Step 6: store the result, then return it.
        result = ClaimResult(
            claim_id=f"CLM-{uuid4().hex[:8].upper()}",
            employee_id=request.employee_id,
            claimed_amount=request.claimed_amount,
            status=status,
            reasons=reasons,
            policy_limit=policy["max_amount"] if policy else None,
            extraction=extraction,
            reply_message=reply_message,
            created_at=datetime.now(timezone.utc),
        )
        await claims.insert(result)
        return result

    async def _draft_reply(
        self,
        name: str,
        status: ClaimStatus,
        reasons: list[str],
        extraction: ClaimExtraction,
    ) -> str:
        reasons_text = "\n".join(f"- {r}" for r in reasons) or "- none"
        user_prompt = (
            "<decision>\n"
            f"employee_name: {name}\n"
            f"expense: {extraction.summary}\n"
            f"status: {status.value}\n"
            f"reasons:\n{reasons_text}\n"
            "</decision>"
        )
        try:
            result = await self.claude_service.generate_structured(
                user_prompt,
                output_model=ClaimReply,
                system=CLAIM_REPLY_SYSTEM_PROMPT,
                max_tokens=300,
            )
            return result.data.message
        except (ClaudeResponseError, APIError):
            logger.warning("Claude reply generation failed; using fallback message.")
            return fallback_reply(name, status, reasons)
