from anthropic import APIError
from fastapi import APIRouter, HTTPException
from pymongo.errors import PyMongoError

from app.database import get_database
from app.repositories.claim_repository import ClaimRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.policy_repository import PolicyRepository
from app.schemas.claim import (
    ClaimAnalyseRequest,
    ClaimAnalyseResponse,
    ClaimResult,
    ClaimSubmitRequest,
)
from app.services.claim_service import (
    ClaimService,
    EmployeeNotAllowedError,
    EmployeeNotFoundError,
)
from app.services.claude_service import (
    ClaudeConfigurationError,
    ClaudeResponseError,
    ClaudeService,
)

# Routes only accept the request and shape the response. Pydantic validates
# the body before this code runs; the Claude work happens in the services.
router = APIRouter(prefix="/claims", tags=["claims"])


# POST /claims/analyse: extract structured data from a description.
# Nothing is saved; this is a "preview" of what Claude understood.
@router.post("/analyse", response_model=ClaimAnalyseResponse)
async def analyse_claim(request: ClaimAnalyseRequest) -> ClaimAnalyseResponse:
    try:
        claude_service = ClaudeService()
    except ClaudeConfigurationError:
        raise HTTPException(status_code=503, detail="AI service is not configured.")

    try:
        result = await ClaimService(claude_service).analyse(request.description)
    except ClaudeResponseError:
        # Claude answered but the answer broke our schema rules.
        raise HTTPException(status_code=502, detail="AI returned an invalid analysis.")
    except APIError:
        # Network error, timeout, rate limit or other Anthropic API failure.
        raise HTTPException(status_code=503, detail="AI service is unavailable.")
    finally:
        await claude_service.close()

    return ClaimAnalyseResponse(
        analysis=result.data,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


# POST /claims/submit: the full multi-step workflow (see ClaimService.submit).
@router.post("/submit", response_model=ClaimResult, status_code=201)
async def submit_claim(request: ClaimSubmitRequest) -> ClaimResult:
    try:
        claude_service = ClaudeService()
    except ClaudeConfigurationError:
        raise HTTPException(status_code=503, detail="AI service is not configured.")

    database = get_database()
    try:
        return await ClaimService(claude_service).submit(
            request,
            employees=EmployeeRepository(database),
            policies=PolicyRepository(database),
            claims=ClaimRepository(database),
        )
    except EmployeeNotFoundError:
        raise HTTPException(status_code=404, detail="Employee not found.")
    except EmployeeNotAllowedError:
        raise HTTPException(status_code=403, detail="Employee is not allowed to submit claims.")
    except ClaudeResponseError:
        raise HTTPException(status_code=502, detail="AI returned an invalid analysis.")
    except APIError:
        raise HTTPException(status_code=503, detail="AI service is unavailable.")
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database is unavailable.")
    finally:
        await claude_service.close()
