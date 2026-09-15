"""Direct UTA WebSocket trading API."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Union

from pydantic import BaseModel

from kucoin_universal_sdk.internal.infra.uta_private_trade_ws_service import UtaPrivateTradeWsService


UtaTradeWsResponse = Dict[str, Any]


class UtaPrivateTradeWS:
    """Places, cancels and amends real UTA orders over WebSocket."""

    def __init__(self, ws_service: UtaPrivateTradeWsService):
        self._ws_service = ws_service

    def start(self) -> None:
        self._ws_service.start()

    def stop(self) -> None:
        self._ws_service.stop()

    def place_order(self, request: Union[Mapping[str, Any], BaseModel]) -> UtaTradeWsResponse:
        return self._ws_service.place_order(request)

    def cancel_order(self, request: Union[Mapping[str, Any], BaseModel]) -> UtaTradeWsResponse:
        return self._ws_service.cancel_order(request)

    def amend_order(self, request: Union[Mapping[str, Any], BaseModel]) -> UtaTradeWsResponse:
        return self._ws_service.amend_order(request)

    # Java API compatibility aliases.
    placeOrder = place_order
    cancelOrder = cancel_order
    amendOrder = amend_order


UtaPrivateTradeWSImpl = UtaPrivateTradeWS
