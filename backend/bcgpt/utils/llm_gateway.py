"""LiteLLM Gateway — unified multi-model routing with fallbacks and cost tracking.

Wraps LiteLLM's Router for:
- Automatic fallback when primary model fails
- Retry with exponential backoff
- Cost tracking per request
- Load balancing across providers

LiteLLM is an *optional* dependency. When not installed the gateway simply
refuses to initialise and callers fall back to the existing direct OpenAI
HTTP path — zero breakage.
"""

import logging
from typing import Optional

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

_gateway_instance: Optional["LLMGateway"] = None


class LLMGateway:
    """LiteLLM Router wrapper for multi-model routing."""

    def __init__(
        self,
        primary_model: str,
        fallback_model: str = "",
        api_base: str = "",
        api_key: str = "",
        num_retries: int = 3,
        timeout: int = 60,
        fallbacks: list[dict] = None,
    ):
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.api_base = api_base
        self.api_key = api_key
        self.num_retries = num_retries
        self.timeout = timeout
        self._router = None
        self._cost_tracker: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Lazy router init (deferred until first request)
    # ------------------------------------------------------------------

    @property
    def router(self):
        if self._router is None:
            self._init_router()
        return self._router

    def _init_router(self):
        """Initialize LiteLLM Router with model list and fallbacks."""
        try:
            import litellm  # noqa: F401 — ensure available
            from litellm import Router

            model_list = [
                {
                    "model_name": self.primary_model,
                    "litellm_params": {
                        "model": f"openai/{self.primary_model}",
                        "api_base": self.api_base,
                        "api_key": self.api_key,
                        "timeout": self.timeout,
                        "num_retries": self.num_retries,
                    },
                }
            ]

            fallback_list: list[dict] = []
            if self.fallback_model:
                model_list.append(
                    {
                        "model_name": self.fallback_model,
                        "litellm_params": {
                            "model": f"openai/{self.fallback_model}",
                            "api_base": self.api_base,
                            "api_key": self.api_key,
                            "timeout": self.timeout,
                            "num_retries": self.num_retries,
                        },
                    }
                )
                fallback_list = [
                    {"from": [self.primary_model], "to": [self.fallback_model]}
                ]

            self._router = Router(
                model_list=model_list,
                fallbacks=fallback_list,
                retry_after=0,
                allowed_fails=3,
                cooldown_time=60,
            )

            log.info(
                f"LiteLLM Router initialized: primary={self.primary_model}, "
                f"fallback={self.fallback_model or 'none'}"
            )
        except ImportError:
            log.warning(
                "litellm not installed — gateway disabled. "
                "Install with: pip install litellm"
            )
            self._router = None
        except Exception as e:
            log.error(f"Failed to initialize LiteLLM Router: {e}")
            self._router = None

    # ------------------------------------------------------------------
    # Completion proxy
    # ------------------------------------------------------------------

    async def completion(self, **kwargs):
        """Route a completion request through LiteLLM."""
        if self.router is None:
            raise RuntimeError("LiteLLM Router not initialized")

        model = kwargs.pop("model", self.primary_model)
        kwargs["model"] = model

        response = await self.router.acompletion(**kwargs)

        self._track_cost(response)
        return response

    # ------------------------------------------------------------------
    # Cost tracking
    # ------------------------------------------------------------------

    def _track_cost(self, response):
        """Track cost per request using LiteLLM's cost calculation."""
        try:
            import litellm

            cost = litellm.completion_cost(completion_response=response)
            model = getattr(response, "model", "unknown")
            self._cost_tracker[model] = self._cost_tracker.get(model, 0.0) + cost
        except Exception:
            pass

    def get_cost_report(self) -> dict:
        """Return cost breakdown by model."""
        return dict(self._cost_tracker)

    def reset_costs(self):
        """Reset cost tracker."""
        self._cost_tracker.clear()


# ======================================================================
# Singleton accessor
# ======================================================================


def get_gateway(
    primary_model: str = "",
    fallback_model: str = "",
    api_base: str = "",
    api_key: str = "",
    num_retries: int = 3,
    timeout: int = 60,
) -> Optional[LLMGateway]:
    """Get or create the singleton LLMGateway instance."""
    global _gateway_instance
    if _gateway_instance is None:
        if not primary_model:
            return None
        _gateway_instance = LLMGateway(
            primary_model=primary_model,
            fallback_model=fallback_model,
            api_base=api_base,
            api_key=api_key,
            num_retries=num_retries,
            timeout=timeout,
        )
    return _gateway_instance


def reset_gateway():
    """Reset the singleton — mainly for testing / config changes."""
    global _gateway_instance
    _gateway_instance = None
