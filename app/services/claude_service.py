from dataclasses import dataclass
from typing import Generic, TypeVar

from anthropic import AsyncAnthropic
from pydantic import BaseModel, ValidationError

from app.config import get_settings

# route -> service -> ClaudeService -> Anthropic SDK
# Only this module talks to the Anthropic SDK, so all Claude API access
# sits behind one clear boundary.


class ClaudeConfigurationError(RuntimeError):
    # A required setting (API key, model) is missing: a setup problem.
    pass


class ClaudeResponseError(RuntimeError):
    # Claude answered, but the answer could not be used as application data.
    pass


# Placeholder for "any Pydantic model class", so passing ClaimExtraction in
# gives a ClaimExtraction back.
StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


@dataclass(frozen=True)
class ClaudeStructuredResult(Generic[StructuredModel]):
    data: StructuredModel  # Already validated by Pydantic
    model: str
    input_tokens: int
    output_tokens: int


class ClaudeService:
    def __init__(self) -> None:
        # Read settings (loaded from environment / .env) once at construction.
        settings = get_settings()

        # Fail early with a clear message if the key was never provided.
        if settings.anthropic_api_key is None:
            raise ClaudeConfigurationError(
                "ANTHROPIC_API_KEY is not configured."
            )

        # The key is stored as a Pydantic SecretStr so it is hidden in logs
        # and reprs; get_secret_value() reveals it only here, where it is used.
        api_key = (
            settings.anthropic_api_key
            .get_secret_value()
            .strip()
        )

        # A key that is only whitespace passes the None check above, so
        # guard against it separately.
        if not api_key:
            raise ClaudeConfigurationError(
                "ANTHROPIC_API_KEY is empty."
            )

        if not settings.claude_model:
            raise ClaudeConfigurationError(
                "CLAUDE_MODEL is not configured."
            )

        self.model = settings.claude_model

        # Async client so FastAPI's event loop is not blocked while waiting
        # for Claude. Timeout and retry behaviour come from settings.
        self.client = AsyncAnthropic(
            api_key=api_key,
            timeout=settings.claude_timeout_seconds,
            max_retries=settings.claude_max_retries,
        )

    async def generate_structured(
        self,
        user_message: str,
        *,
        output_model: type[StructuredModel],
        max_tokens: int = 500,
        system: str | None = None,
    ) -> ClaudeStructuredResult[StructuredModel]:
        # Ask Claude for a reply and parse it into a Pydantic model.
        # output_model is the Pydantic model class the reply must match.
        # user_message / system / max_tokens work as in generate_text.

        # Same request shape as generate_text, plus output_format, which
        # tells the SDK which schema to request and parse the reply into.
        request = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": user_message,
                }
            ],
            "output_format": output_model,
        }

        if system:
            request["system"] = system

        try:
            # messages.parse sends the request and validates the reply
            # against output_model in one step.
            message = await self.client.messages.parse(
                **request
            )
        except ValidationError as exc:
            # The reply did not match the schema: never treat it as valid
            # application data. Re-raise as our own error type.
            raise ClaudeResponseError(
                "Claude structured output failed application validation"
            ) from exc

        # parsed_output is None when nothing could be parsed (for example,
        # the response was cut off or refused), so check before using it.
        if message.parsed_output is None:
            raise ClaudeResponseError(
                "Claude returned no structured output"
            )

        # Return only the validated data plus the usage numbers.
        return ClaudeStructuredResult[StructuredModel](
            data=message.parsed_output,
            model=message.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )

    async def close(self) -> None:
        # Release the HTTP connections held by the client.
        await self.client.close()
