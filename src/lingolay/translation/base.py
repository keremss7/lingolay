from dataclasses import dataclass


@dataclass
class TranslationResult:
    text: str
    from_cache: bool = False
    latency_ms: int = 0
    error: str | None = None
