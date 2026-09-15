from enum import Enum


class PushTradeType(str, Enum):
    """Trading domain used by the direct UTA public push WebSocket."""

    SPOT = "SPOT"
    FUTURES = "FUTURES"

    @property
    def endpoint(self) -> str:
        if self is PushTradeType.SPOT:
            return "wss://x-push-spot.kucoin.com"
        return "wss://x-push-futures.kucoin.com"
