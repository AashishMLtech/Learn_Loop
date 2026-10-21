"""LLM Client Interface and Provider Implementation.

Purpose:
    Defines a clean, swappable LLMClient interface and provides the official
    Groq SDK implementation with exponential backoff infrastructure retries
    and token budget enforcement.

Inputs/Outputs:
    Inputs: Chat messages, model identifier, temperature, JSON formatting mode.
    Outputs: LLMResponse containing completion text and real token metrics.

What it must NOT do:
    - Must NOT count infrastructure retries (429/5xx/timeouts) as pedagogical lesson retries.
    - Must NOT fabricate token metrics; real provider usage numbers only.
    - Must NOT import agent, UI, or evaluation logic.
"""
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from groq import APIConnectionError, APITimeoutError, Groq, InternalServerError, RateLimitError

from shared.enums import CallType

logger = logging.getLogger("lesson_generator.llm_client")


class InfrastructureExhaustedError(Exception):
    """Raised when provider infrastructure retries (429/5xx/timeout) are exhausted."""
    pass


class BudgetExhaustedError(Exception):
    """Raised when the configured token budget is insufficient to proceed."""
    pass


@dataclass
class LLMResponse:
    """Standardized response container across all LLM providers."""
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str


@dataclass
class TokenCallRecord:
    """Historical record of an individual LLM invocation."""
    attempt: int
    call_type: CallType
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    is_estimated: bool = False


@dataclass
class TokenBudgetTracker:
    """Tracks token consumption against a strict run budget."""
    max_budget: int = 30000
    records: List[TokenCallRecord] = field(default_factory=list)

    @property
    def total_tokens_used(self) -> int:
        """Returns the aggregate token count consumed so far."""
        return sum(r.total_tokens for r in self.records)

    @property
    def remaining_budget(self) -> int:
        """Returns remaining available tokens."""
        return max(0, self.max_budget - self.total_tokens_used)

    def can_afford(self, min_tokens: int = 1000) -> bool:
        """Checks whether remaining budget satisfies minimum call threshold."""
        return self.remaining_budget >= min_tokens

    def assert_budget_available(self, min_tokens: int = 1000) -> None:
        """Raises BudgetExhaustedError if remaining budget is below threshold.

        Args:
            min_tokens: Minimum tokens required for an invocation.

        Raises:
            BudgetExhaustedError: If insufficient budget remains.
        """
        if not self.can_afford(min_tokens):
            raise BudgetExhaustedError(
                f"Token budget exhausted: used {self.total_tokens_used}/{self.max_budget}. "
                f"Remaining {self.remaining_budget} < required {min_tokens}."
            )

    def record_usage(
        self,
        attempt: int,
        call_type: CallType,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        is_estimated: bool = False,
    ) -> TokenCallRecord:
        """Appends a verified usage record to the budget history.

        Args:
            attempt: Current lesson attempt counter.
            call_type: Call category (generate, revise, judge, repair).
            model: Model identifier.
            prompt_tokens: Input tokens consumed.
            completion_tokens: Output tokens consumed.
            total_tokens: Total tokens consumed.
            is_estimated: True only if estimated rather than measured.

        Returns:
            The recorded TokenCallRecord.
        """
        record = TokenCallRecord(
            attempt=attempt,
            call_type=call_type,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            is_estimated=is_estimated,
        )
        self.records.append(record)
        return record


class LLMClientInterface(ABC):
    """Abstract interface defining the swappable model provider contract."""

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        json_mode: bool = True,
    ) -> LLMResponse:
        """Dispatches chat completion call to the underlying provider.

        Args:
            messages: List of chat messages with role and content.
            model: Model identifier.
            temperature: Sampling temperature.
            json_mode: Whether to enforce JSON object output formatting.

        Returns:
            Standardized LLMResponse with text and usage.

        Raises:
            InfrastructureExhaustedError: If provider infrastructure fails.
        """
        pass

    @abstractmethod
    def list_models(self) -> List[str]:
        """Lists available models from the provider API.

        Returns:
            List of string model IDs.
        """
        pass


class GroqLLMClient(LLMClientInterface):
    """Official Groq SDK implementation of LLMClientInterface with infrastructure backoff."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initializes Groq client with optional explicit API key and default model.

        Args:
            api_key: Groq API key (defaults to GROQ_API_KEY env var if None).
            model: Groq model identifier (defaults to GROQ_MODEL env var or openai/gpt-oss-120b).
        """
        resolved_key = api_key or os.getenv("GROQ_API_KEY")
        self.client = Groq(api_key=resolved_key) if resolved_key else None
        self.model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        json_mode: bool = True,
    ) -> LLMResponse:
        """Executes a completion call on Groq with exponential backoff on 429/5xx/timeout.

        Args:
            messages: Formatted prompt messages.
            model: Groq model identifier.
            temperature: Sampling temperature.
            json_mode: Whether to instruct JSON formatting.

        Returns:
            Standardized LLMResponse.

        Raises:
            InfrastructureExhaustedError: On 3 exhausted infrastructure attempts.
            RuntimeError: If client is not initialized.
        """
        if not self.client:
            raise RuntimeError("GroqLLMClient client is not initialized with an API key.")

        max_attempts = 3
        backoff_base = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                kwargs: Dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}

                response = self.client.chat.completions.create(**kwargs)

                content = response.choices[0].message.content or ""
                usage = getattr(response, "usage", None)
                pt = getattr(usage, "prompt_tokens", 0) if usage else 0
                ct = getattr(usage, "completion_tokens", 0) if usage else 0
                tt = getattr(usage, "total_tokens", pt + ct) if usage else (pt + ct)

                return LLMResponse(
                    content=content,
                    prompt_tokens=pt,
                    completion_tokens=ct,
                    total_tokens=tt,
                    model=model,
                )

            except (RateLimitError, InternalServerError, APIConnectionError, APITimeoutError) as exc:
                logger.warning(
                    "Groq infrastructure error on attempt %d/%d: %s",
                    attempt,
                    max_attempts,
                    exc,
                )
                if attempt == max_attempts:
                    raise InfrastructureExhaustedError(
                        f"Groq infrastructure exhausted after {max_attempts} attempts: {exc}"
                    ) from exc

                sleep_time = backoff_base * (2 ** (attempt - 1))
                if isinstance(exc, RateLimitError) and hasattr(exc, "response") and exc.response is not None:
                    header_val = exc.response.headers.get("retry-after")
                    if header_val:
                        try:
                            sleep_time = max(float(header_val), sleep_time)
                        except ValueError:
                            pass
                time.sleep(min(sleep_time, 10.0))

            except Exception as non_retryable:
                raise non_retryable

        raise InfrastructureExhaustedError("Groq call failed unexpectedly without completion.")

    def list_models(self) -> List[str]:
        """Queries Groq API for available model identifiers.

        Returns:
            List of model IDs.
        """
        if not self.client:
            return []
        try:
            return [m.id for m in self.client.models.list().data]
        except Exception as exc:
            logger.warning("Could not list Groq models: %s", exc)
            return []
