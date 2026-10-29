from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# Shared base: reject unknown fields and strip surrounding whitespace.
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# The only categories the application accepts. Claude must pick one of
# these; it cannot invent a new category.
class ExpenseCategory(str, Enum):
    TRAVEL = "travel"
    MEALS = "meals"
    ACCOMMODATION = "accommodation"
    OFFICE_SUPPLIES = "office_supplies"
    OTHER = "other"


# Body of POST /claims/analyse: the employee's free-text expense description.
# Length limits reject empty input and cap large input (which raises cost).
class ClaimAnalyseRequest(StrictModel):
    description: str = Field(min_length=10, max_length=1000)


# The structured data Claude must return. Claude output is untrusted, so
# every field is checked here before the application uses it.
class ClaimExtraction(StrictModel):
    category: ExpenseCategory
    # None when the description does not state an amount.
    amount: float | None = Field(default=None, ge=0, le=100000)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    expense_date: date | None = None
    summary: str = Field(min_length=5, max_length=200)
    # Things a reviewer would need but the description did not include.
    missing_info: list[str] = Field(default_factory=list, max_length=5)


# Reply of POST /claims/analyse: the validated extraction plus token usage.
class ClaimAnalyseResponse(StrictModel):
    analysis: ClaimExtraction
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


# Body of POST /claims/submit. claimed_amount is what the employee says they
# spent; the app cross-checks it against the amount Claude finds in the text.
class ClaimSubmitRequest(StrictModel):
    employee_id: str = Field(pattern=r"^E\d{3}$")
    description: str = Field(min_length=10, max_length=1000)
    claimed_amount: float = Field(gt=0, le=100000)


# Decided by the APPLICATION's rules, never by Claude.
class ClaimStatus(str, Enum):
    AUTO_APPROVED = "auto_approved"
    NEEDS_REVIEW = "needs_review"


# What Claude must return when drafting the reply to the employee.
class ClaimReply(StrictModel):
    message: str = Field(min_length=10, max_length=800)


# Reply of POST /claims/submit; also the shape stored in MongoDB.
class ClaimResult(StrictModel):
    claim_id: str
    employee_id: str
    claimed_amount: float
    status: ClaimStatus
    # Why the app chose this status (empty when auto-approved).
    reasons: list[str]
    policy_limit: float | None
    extraction: ClaimExtraction
    reply_message: str
    created_at: datetime
