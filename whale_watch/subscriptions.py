"""Subscription rules shared by transfer scanning and alert delivery."""

from dataclasses import dataclass

from .model import Transfer


@dataclass(frozen=True)
class Subscription:
    chat_id: int
    address: str
    token: str = "*"

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", self.address.strip().lower())
        token = self.token.strip()
        normalized = token.lower() if token.startswith(("0x", "0X")) else token.upper()
        object.__setattr__(self, "token", normalized or "*")


@dataclass(frozen=True)
class WatchPlan:
    rules: tuple[Subscription, ...]

    def __bool__(self) -> bool:
        return bool(self.rules)

    def matches(self, transfer: Transfer) -> bool:
        return any(self._matches(rule, transfer) for rule in self.rules)

    def chats_for(self, transfer: Transfer) -> frozenset[int]:
        return frozenset(rule.chat_id for rule in self.rules if self._matches(rule, transfer))

    @staticmethod
    def _matches(rule: Subscription, transfer: Transfer) -> bool:
        if rule.address not in (transfer.from_addr.lower(), transfer.to_addr.lower()):
            return False
        if rule.token == "*":
            return True
        return rule.token in (transfer.token.strip().upper(), transfer.token_address.lower())
