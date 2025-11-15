from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .game_storage_engine import GameStorageEngine


COOKIE_NAMESPACE = "cookies"
COOKIE_BALANCE_KEY = "balance"


@dataclass(slots=True)
class CookieBalance:
    amount: int = 0


class CookieManager:
    """High-level helper for tracking helper cookies per user.

    All state is persisted via :class:`GameStorageEngine`, using the
    ``cookies`` namespace so that the underlying schema can remain
    generic and future-proof.
    """

    def __init__(self, storage: GameStorageEngine) -> None:
        self._storage = storage

    async def get_balance(self, user_id: int) -> CookieBalance:
        raw = await self._storage.get_user_value(
            user_id=user_id,
            namespace=COOKIE_NAMESPACE,
            key=COOKIE_BALANCE_KEY,
            default={"amount": 0},
        )
        try:
            amount = int(raw.get("amount", 0))  # type: ignore[call-arg]
        except Exception:
            amount = 0
        return CookieBalance(amount=max(amount, 0))

    async def set_balance(self, user_id: int, amount: int) -> CookieBalance:
        amount = max(int(amount), 0)
        payload = {"amount": amount}
        await self._storage.set_user_value(
            user_id=user_id,
            namespace=COOKIE_NAMESPACE,
            key=COOKIE_BALANCE_KEY,
            value=payload,
        )
        return CookieBalance(amount=amount)

    async def add_cookies(self, user_id: int, delta: int) -> CookieBalance:
        """Increment a user's cookie balance by ``delta`` (can be negative)."""

        current = await self.get_balance(user_id)
        new_amount = max(current.amount + int(delta), 0)
        return await self.set_balance(user_id, new_amount)

    async def transfer_cookies(
        self,
        sender_id: int,
        recipient_id: int,
        amount: int,
        allow_negative_sender: bool = False,
    ) -> tuple[CookieBalance, CookieBalance]:
        """Transfer cookies between users.

        If ``allow_negative_sender`` is False, the sender's balance will not
        be allowed to go below zero and the actual transfer amount will be
        clipped accordingly.
        """

        amount = max(int(amount), 0)
        if amount == 0:
            sender_balance = await self.get_balance(sender_id)
            recipient_balance = await self.get_balance(recipient_id)
            return sender_balance, recipient_balance

        sender_balance = await self.get_balance(sender_id)
        if not allow_negative_sender and sender_balance.amount < amount:
            amount = sender_balance.amount

        sender_balance = await self.add_cookies(sender_id, -amount)
        recipient_balance = await self.add_cookies(recipient_id, amount)
        return sender_balance, recipient_balance


__all__ = ["CookieManager", "CookieBalance"]
