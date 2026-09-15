"""Direct UTA private push WebSocket API."""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from kucoin_universal_sdk.internal.infra.uta_push_ws_service import UtaPushSubscription, UtaPushWsService


UtaPrivateEvent = Dict[str, Any]
UtaPrivateEventCallback = Callable[[UtaPrivateEvent], None]


class ExecutionLiteTradeType(str, Enum):
    SPOT = "SPOT"
    ISOLATED = "ISOLATED"
    CROSS = "CROSS"
    FUTURES = "FUTURES"
    UNIFIED = "UNIFIED"


class BalanceAccountType(str, Enum):
    UNIFIED = "UNIFIED"
    FUNDING = "FUNDING"
    ISOLATED = "ISOLATED"


class UtaPrivateWS:
    def __init__(self, ws_service: UtaPushWsService):
        self._ws_service = ws_service

    def start(self) -> None:
        self._ws_service.start()

    def stop(self) -> None:
        self._ws_service.stop()

    def unsubscribe(self, subscription_id: str) -> None:
        self._ws_service.unsubscribe(subscription_id)

    def execution(self, callback: UtaPrivateEventCallback) -> str:
        return self._subscribe("execution", callback, trade_type="UNIFIED")

    def execution_lite(
        self, trade_type: Union[ExecutionLiteTradeType, str], callback: UtaPrivateEventCallback
    ) -> str:
        value = trade_type.value if isinstance(trade_type, ExecutionLiteTradeType) else str(trade_type).upper()
        if value not in {entry.value for entry in ExecutionLiteTradeType}:
            raise ValueError("execution_lite trade_type must be SPOT, ISOLATED, CROSS, FUTURES or UNIFIED")
        return self._subscribe("execution.lite", callback, trade_type=value)

    def order_all(self, callback: UtaPrivateEventCallback) -> str:
        return self._subscribe("orderAll", callback, trade_type="UNIFIED")

    def order(self, symbol: str, callback: UtaPrivateEventCallback) -> str:
        return self._subscribe("order", callback, trade_type="UNIFIED", symbols=[symbol])

    def balance(self, account_type: Union[BalanceAccountType, str], callback: UtaPrivateEventCallback) -> str:
        value = account_type.value if isinstance(account_type, BalanceAccountType) else str(account_type).upper()
        if value not in {entry.value for entry in BalanceAccountType}:
            raise ValueError("balance account_type must be UNIFIED, FUNDING or ISOLATED")
        return self._subscribe("balance", callback, account_type=value, include_trade_type=False)

    def position_all(self, callback: UtaPrivateEventCallback) -> str:
        return self._subscribe("positionAll", callback, trade_type="UNIFIED")

    def position(self, symbol: str, callback: UtaPrivateEventCallback) -> str:
        return self._subscribe("position", callback, trade_type="UNIFIED", symbols=[symbol])

    def leverage(self, callback: UtaPrivateEventCallback) -> str:
        return self._subscribe("leverage", callback, trade_type="UNIFIED")

    def liquidation_warning(self, callback: UtaPrivateEventCallback) -> str:
        return self._subscribe("lw", callback, trade_type="UNIFIED")

    def _subscribe(
        self,
        channel: str,
        callback: UtaPrivateEventCallback,
        *,
        trade_type: Optional[str] = None,
        account_type: Optional[str] = None,
        symbols: Optional[List[str]] = None,
        include_trade_type: bool = True,
    ) -> str:
        return self._ws_service.subscribe(
            UtaPushSubscription(
                channel=channel,
                callback=callback,
                symbols=symbols or [],
                trade_type=trade_type,
                account_type=account_type,
                include_trade_type=include_trade_type,
            )
        )

    # Java API compatibility aliases.
    executionLite = execution_lite
    orderAll = order_all
    positionAll = position_all
    liquidationWarning = liquidation_warning
    unSubscribe = unsubscribe


UtaPrivateWSImpl = UtaPrivateWS
