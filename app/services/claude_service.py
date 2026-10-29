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
        settings = get_settings()

        # The key is optional in Settings, so check it here, right before use.
        if settings.anthropic_api_key is None:
            raise ClaudeConfigurationError("ANTHROPIC_API_KEY is not configured.")

        api_key = settings.anthropic_api_key.get_secret_value().strip()
        if not api_key:
            raise ClaudeConfigurationError("ANTHROPIC_API_KEY is empty.")

        if not settings.claude_model:
            raise ClaudeConfigurationError("CLAUDE_MODEL is not configured.")

        self.model = settings.claude_model
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
        system: str,
        max_tokens: int = 500,
    ) -> ClaudeStructuredResult[StructuredModel]:
        # system = the application's instructions; user_message = untrusted
        # input. Sending them in separate fields keeps them apart.
        try:
            # messages.parse requests output matching output_model's schema
            # and validates the reply against it in one step.
            message = await self.client.messages.parse(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_message}],
                output_format=output_model,
            )
        except ValidationError as exc:
            # The reply broke our rules: never treat it as application data.
            raise ClaudeResponseError("Claude output failed validation.") from exc

        # None when nothing could be parsed (e.g. cut off or refused).
        if message.parsed_output is None:
            raise ClaudeResponseError("Claude returned no structured output.")

        return ClaudeStructuredResult[StructuredModel](
            data=message.parsed_output,
            model=message.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )

    async def close(self) -> None:
        # Release the HTTP connections held by the client.
        await self.client.close()
