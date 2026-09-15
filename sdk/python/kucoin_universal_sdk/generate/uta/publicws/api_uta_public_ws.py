"""Direct UTA public WebSocket API."""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from kucoin_universal_sdk.internal.infra.uta_push_ws_service import UtaPushSubscription, UtaPushWsService
from kucoin_universal_sdk.model.push_trade_type import PushTradeType


UtaPublicEvent = Dict[str, Any]
UtaPublicEventCallback = Callable[[UtaPublicEvent], None]


class KlineInterval(str, Enum):
    MIN_1 = "1min"
    MIN_3 = "3min"
    MIN_5 = "5min"
    MIN_15 = "15min"
    MIN_30 = "30min"
    HOUR_1 = "1hour"
    HOUR_2 = "2hour"
    HOUR_4 = "4hour"
    HOUR_6 = "6hour"
    HOUR_8 = "8hour"
    HOUR_12 = "12hour"
    DAY_1 = "1day"
    WEEK_1 = "1week"
    MONTH_1 = "1month"


class OrderbookDepth(str, Enum):
    BEST_1 = "1"
    BEST_5 = "5"
    BEST_50 = "50"
    INCREMENT = "increment"
    INCREMENT_10MS = "increment@10ms"


class OrderbookRpiFilter(int, Enum):
    NONE_RPI_ONLY = 0
    INCLUDE_RPI = 1


class UtaPublicWS:
    """One direct public UTA WebSocket connection for SPOT or FUTURES."""

    def __init__(self, ws_service: UtaPushWsService, trade_type: PushTradeType):
        self._ws_service = ws_service
        self._trade_type = trade_type

    def start(self) -> None:
        self._ws_service.start()

    def stop(self) -> None:
        self._ws_service.stop()

    def unsubscribe(self, subscription_id: str) -> None:
        self._ws_service.unsubscribe(subscription_id)

    def ticker(self, symbols: Union[str, List[str]], callback: UtaPublicEventCallback) -> str:
        return self._subscribe("ticker", symbols, callback)

    def kline(self, symbol: str, interval: Union[KlineInterval, str], callback: UtaPublicEventCallback) -> str:
        interval_value = interval.value if isinstance(interval, KlineInterval) else str(interval)
        if self._trade_type is PushTradeType.FUTURES and interval_value == KlineInterval.HOUR_6.value:
            raise ValueError("6hour Kline is not supported for FUTURES")
        return self._subscribe("kline", symbol, callback, {"interval": interval_value})

    def trade(self, symbol: str, callback: UtaPublicEventCallback) -> str:
        return self._subscribe("trade", symbol, callback)

    def orderbook(
        self,
        symbol: str,
        depth: Union[OrderbookDepth, str],
        callback: UtaPublicEventCallback,
        rpi_filter: Union[OrderbookRpiFilter, int] = OrderbookRpiFilter.NONE_RPI_ONLY,
    ) -> str:
        depth_value = depth.value if isinstance(depth, OrderbookDepth) else str(depth)
        rpi_value = rpi_filter.value if isinstance(rpi_filter, OrderbookRpiFilter) else int(rpi_filter)
        if rpi_value == 1 and self._trade_type is not PushTradeType.FUTURES:
            raise ValueError("rpi_filter=1 is supported only for FUTURES")
        if rpi_value == 1 and depth_value not in {OrderbookDepth.BEST_5.value, OrderbookDepth.BEST_50.value}:
            raise ValueError("rpi_filter=1 supports only depth 5 or 50")
        return self._subscribe("obu", symbol, callback, {"depth": depth_value, "rpiFilter": rpi_value})

    def mark_price(self, symbol: str, callback: UtaPublicEventCallback) -> str:
        self._require_futures("mark-price")
        return self._subscribe("mark-price", symbol, callback, include_trade_type=False)

    def funding_fee(self, symbols: Union[str, List[str]], callback: UtaPublicEventCallback) -> str:
        self._require_futures("funding-fee")
        return self._subscribe("funding-fee", symbols, callback, include_trade_type=False)

    def funding_fee_all_symbols(self, callback: UtaPublicEventCallback) -> str:
        self._require_futures("funding-fee-all-symbols")
        return self._ws_service.subscribe(
            UtaPushSubscription(
                channel="funding-fee-all-symbols", callback=callback, include_trade_type=False
            )
        )

    def call_auction_info(self, symbol: str, callback: UtaPublicEventCallback) -> str:
        if self._trade_type is not PushTradeType.SPOT:
            raise ValueError("callAuctionInfo is available only from the SPOT public endpoint")
        return self._subscribe("callAuctionInfo", symbol, callback, include_trade_type=False)

    def _subscribe(
        self,
        channel: str,
        symbols: Union[str, List[str]],
        callback: UtaPublicEventCallback,
        parameters: Optional[Dict[str, Any]] = None,
        include_trade_type: bool = True,
    ) -> str:
        values = [symbols] if isinstance(symbols, str) else list(symbols)
        return self._ws_service.subscribe(
            UtaPushSubscription(
                channel=channel,
                symbols=values,
                trade_type=self._trade_type.value,
                callback=callback,
                parameters=parameters or {},
                include_trade_type=include_trade_type,
            )
        )

    def _require_futures(self, channel: str) -> None:
        if self._trade_type is not PushTradeType.FUTURES:
            raise ValueError(f"{channel} is available only from the FUTURES public endpoint")

    # Java API compatibility aliases.
    markPrice = mark_price
    fundingFee = funding_fee
    fundingFeeAllSymbols = funding_fee_all_symbols
    callAuctionInfo = call_auction_info
    unSubscribe = unsubscribe


UtaPublicWSImpl = UtaPublicWS
