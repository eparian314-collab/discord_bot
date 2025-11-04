import asyncio
from typing import Optional


class SuccessStub:
    def __init__(self, label: str = "success") -> None:
        self.label = label

    async def translate(self, text: str, src: Optional[str], tgt: Optional[str]) -> str:
        return f"[{self.label}] {text}->{tgt or 'auto'}"


class SlowStub:
    def __init__(self, delay: float = 2.0, label: str = "slow") -> None:
        self.delay = delay
        self.label = label

    async def translate(self, text: str, src: Optional[str], tgt: Optional[str]) -> str:
        await asyncio.sleep(self.delay)
        return f"[{self.label}] {text}->{tgt or 'auto'}"


class FailingStub:
    def __init__(self, label: str = "fail") -> None:
        self.label = label

    async def translate(self, text: str, src: Optional[str], tgt: Optional[str]) -> str:
        raise RuntimeError(f"{self.label}: boom")



