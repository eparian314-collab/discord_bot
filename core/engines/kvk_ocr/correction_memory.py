from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Dict, Optional


class CorrectionMemory:
    """Persist name/score corrections per guild to storage/ocr_corrections.json."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or Path("storage/ocr_corrections.json")
        self._lock = asyncio.Lock()
        self._cache: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None

    async def get_name_correction(self, guild_id: str, raw_value: str) -> Optional[str]:
        """Return the remembered name correction for this guild, if any."""
        data = await self._load()
        normalized = self._normalize(raw_value)
        return data.get(guild_id, {}).get("names", {}).get(normalized)

    async def get_score_correction(self, guild_id: str, raw_value: str) -> Optional[int]:
        """Return the remembered score correction for this guild, if any."""
        data = await self._load()
        normalized = self._normalize(raw_value)
        score_map = data.get(guild_id, {}).get("scores", {})
        value = score_map.get(normalized)
        return int(value) if value is not None else None

    async def record_name_correction(self, guild_id: str, raw_value: str, corrected_value: str) -> None:
        """Store a name correction for future matches."""
        await self._record(guild_id, "names", raw_value, corrected_value)

    async def record_score_correction(self, guild_id: str, raw_value: str, corrected_value: int) -> None:
        """Store a score correction for future matches."""
        await self._record(guild_id, "scores", raw_value, str(corrected_value))

    async def _record(self, guild_id: str, field: str, raw_value: str, corrected_value: str) -> None:
        async with self._lock:
            data = await self._load()
            guild_map = data.setdefault(guild_id, {"names": {}, "scores": {}})
            guild_map.setdefault(field, {})
            guild_map[field][self._normalize(raw_value)] = corrected_value
            self._cache = data
            await self._persist()

    async def _load(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            self._cache = {}
            return self._cache
        text = await asyncio.to_thread(self.path.read_text, encoding="utf-8")
        self._cache = json.loads(text) if text else {}
        return self._cache

    async def _persist(self) -> None:
        parent = self.path.parent
        parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self._cache or {}, indent=2)
        await asyncio.to_thread(self.path.write_text, text, encoding="utf-8")

    def _normalize(self, value: str) -> str:
        return value.strip().lower()
