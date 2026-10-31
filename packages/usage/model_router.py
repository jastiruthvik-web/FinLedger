import os
from dataclasses import dataclass

from usage.kill_switch import KillSwitch
from usage.live_gemini import transport_is_explicit_live
from usage.provider import MockProvider
from usage.providers.gemini import GeminiProvider, GeminiSettings
from usage.providers.openrouter import (
    OPENROUTER_DEFAULT_MODEL,
    OpenRouterProvider,
    OpenRouterSettings,
    build_openrouter_transport,
    require_openrouter_api_key,
)
from usage.providers.transport import GeminiTransport, OpenRouterTransport

_HOSTED_BLOCKED_PROVIDERS = frozenset({"mock", "gemini"})
_GEMINI_DEFAULT_MODEL = "gemini-3.5-flash-lite"
_PURPOSE_ENV = (
    ("model_extract", "FINLEDGER_MODEL_EXTRACT", _GEMINI_DEFAULT_MODEL),
    ("model_extract_vision", "FINLEDGER_MODEL_EXTRACT_VISION", _GEMINI_DEFAULT_MODEL),
    ("model_risk_llm", "FINLEDGER_MODEL_RISK", _GEMINI_DEFAULT_MODEL),
    ("model_map", "FINLEDGER_MODEL_MAP", _GEMINI_DEFAULT_MODEL),
    ("model_summary", "FINLEDGER_MODEL_SUMMARY", _GEMINI_DEFAULT_MODEL),
)


def _models_from_env(provider: str) -> dict[str, str]:
    """OpenRouter defaults every purpose to Qwen. A set per-purpose variable still wins."""
    shared = os.getenv("FINLEDGER_OPENROUTER_MODEL", "").strip()
    models: dict[str, str] = {}
    for field, env_name, gemini_default in _PURPOSE_ENV:
        if provider == "openrouter":
            explicit = os.getenv(env_name)
            if isinstance(explicit, str) and explicit.strip():
                models[field] = explicit.strip()
            else:
                models[field] = shared or OPENROUTER_DEFAULT_MODEL
        else:
            models[field] = os.getenv(env_name, gemini_default)
    return models


@dataclass(frozen=True)
class Settings:
    provider: str = "mock"
    per_bill_token_cap: int = 20000
    kill_switch_enabled: bool = True
    model_extract: str = _GEMINI_DEFAULT_MODEL
    model_extract_vision: str = _GEMINI_DEFAULT_MODEL
    model_risk_llm: str = _GEMINI_DEFAULT_MODEL
    model_map: str = _GEMINI_DEFAULT_MODEL
    model_summary: str = _GEMINI_DEFAULT_MODEL
    gemini_location: str = ""

    @classmethod
    def from_env(cls):
        provider = os.getenv("FINLEDGER_LLM_PROVIDER", "mock").strip().lower()
        return cls(
            provider=provider,
            per_bill_token_cap=int(os.getenv("FINLEDGER_PER_BILL_TOKEN_CAP", "20000")),
            kill_switch_enabled=os.getenv("FINLEDGER_LLM_KILL_SWITCH", "true").lower() not in {"0", "false", "off"},
            gemini_location=os.getenv("FINLEDGER_GEMINI_LOCATION", "").strip(),
            **_models_from_env(provider),
        )


_PROVIDERS = {}

class ModelRouter:
    def __init__(
        self,
        settings: Settings | None = None,
        gemini_transport: GeminiTransport | None = None,
        kill_switch: KillSwitch | None = None,
        openrouter_transport: OpenRouterTransport | None = None,
    ):
        self.settings = settings or Settings.from_env()
        env = os.getenv("FINLEDGER_ENV", "development").strip().lower()
        if env in {"staging", "production"} and self.settings.provider in _HOSTED_BLOCKED_PROVIDERS:
            # Hosted gemini stays refused until this process was given the real HTTP client.
            if not (self.settings.provider == "gemini" and transport_is_explicit_live(gemini_transport)):
                raise RuntimeError(f"{self.settings.provider} LLM provider cannot run in a hosted environment")
        self.routes = {
            "extract": self.settings.model_extract,
            "extract_vision": self.settings.model_extract_vision,
            "risk_llm": self.settings.model_risk_llm,
            "map": self.settings.model_map,
            "summary": self.settings.model_summary,
        }
        # Injected switch is the worker's durable adapter. Gemini never builds a socket
        # client here. OpenRouter builds its client object only in that branch; the
        # constructor does not open a socket.
        if kill_switch is None:
            kill = KillSwitch(self.settings.per_bill_token_cap, self.settings.kill_switch_enabled)
        else:
            kill = kill_switch
        if self.settings.provider == "mock":
            if kill_switch is None:
                key = (self.settings.provider, self.settings.per_bill_token_cap, self.settings.kill_switch_enabled)
                self.provider = _PROVIDERS.setdefault(key, MockProvider(kill))
            else:
                self.provider = MockProvider(kill)
        elif self.settings.provider == "gemini":
            if not self.settings.gemini_location:
                raise ValueError("FINLEDGER_GEMINI_LOCATION is required when FINLEDGER_LLM_PROVIDER=gemini")
            if gemini_transport is None:
                raise ValueError("gemini provider requires an explicit transport (no network fallback)")
            self.provider = GeminiProvider(
                GeminiSettings(
                    model=self.settings.model_extract,
                    location=self.settings.gemini_location,
                ),
                gemini_transport,
                kill,
            )
        elif self.settings.provider == "openrouter":
            api_key = require_openrouter_api_key()
            if openrouter_transport is None:
                transport = build_openrouter_transport(api_key)
            else:
                transport = openrouter_transport
            self.provider = OpenRouterProvider(
                OpenRouterSettings(model=self.settings.model_extract or OPENROUTER_DEFAULT_MODEL),
                transport,
                kill,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.settings.provider}")

    def resolve_model(self, purpose: str) -> str:
        if purpose not in self.routes:
            raise ValueError(f"Unknown purpose: {purpose}")
        return self.routes[purpose]
