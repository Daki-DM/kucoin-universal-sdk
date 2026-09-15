from kucoin_universal_sdk.api.api_ws import KucoinWSService
from kucoin_universal_sdk.generate.futures.futures_private.ws_futures_private import FuturesPrivateWS, \
    FuturesPrivateWSImpl
from kucoin_universal_sdk.generate.futures.futures_public.ws_futures_public import FuturesPublicWS, FuturesPublicWSImpl
from kucoin_universal_sdk.generate.margin.margin_private.ws_margin_private import MarginPrivateWS, MarginPrivateWSImpl
from kucoin_universal_sdk.generate.margin.margin_public.ws_margin_public import MarginPublicWS, MarginPublicWSImpl
from kucoin_universal_sdk.generate.spot.spot_private.ws_spot_private import SpotPrivateWS, SpotPrivateWSImpl
from kucoin_universal_sdk.generate.spot.spot_public.ws_spot_public import SpotPublicWS, SpotPublicWSImpl
from kucoin_universal_sdk.generate.uta.privatews import UtaPrivateTradeWS, UtaPrivateTradeWSImpl, UtaPrivateWS, UtaPrivateWSImpl
from kucoin_universal_sdk.generate.uta.publicws import UtaPublicWS, UtaPublicWSImpl
from kucoin_universal_sdk.generate.version import sdk_version
from kucoin_universal_sdk.internal.infra.default_ws_service import DefaultWsService
from kucoin_universal_sdk.internal.infra.uta_private_trade_ws_service import UtaPrivateTradeWsService
from kucoin_universal_sdk.internal.infra.uta_push_ws_service import UtaPushWsService
from kucoin_universal_sdk.model.client_option import ClientOption
from kucoin_universal_sdk.model.constants import DomainType
from kucoin_universal_sdk.model.push_trade_type import PushTradeType
from typing import Union


class DefaultKucoinWSAPIImpl(KucoinWSService):
    def __init__(self, options: ClientOption):
        self.options = options
        pass

    def new_spot_public_ws(self) -> SpotPublicWS:
        ws_service = DefaultWsService(self.options, DomainType.SPOT, False, sdk_version)
        return SpotPublicWSImpl(ws_service)

    def new_spot_private_ws(self) -> SpotPrivateWS:
        ws_service = DefaultWsService(self.options, DomainType.SPOT, True, sdk_version)
        return SpotPrivateWSImpl(ws_service)

    def new_margin_public_ws(self) -> MarginPublicWS:
        ws_service = DefaultWsService(self.options, DomainType.SPOT, False, sdk_version)
        return MarginPublicWSImpl(ws_service)

    def new_margin_private_ws(self) -> MarginPrivateWS:
        ws_service = DefaultWsService(self.options, DomainType.SPOT, True, sdk_version)
        return MarginPrivateWSImpl(ws_service)

    def new_futures_public_ws(self) -> FuturesPublicWS:
        ws_service = DefaultWsService(self.options, DomainType.FUTURES, False, sdk_version)
        return FuturesPublicWSImpl(ws_service)

    def new_futures_private_ws(self) -> FuturesPrivateWS:
        ws_service = DefaultWsService(self.options, DomainType.FUTURES, True, sdk_version)
        return FuturesPrivateWSImpl(ws_service)

    def new_uta_public_ws(self, trade_type: Union[PushTradeType, str]) -> UtaPublicWS:
        normalized = trade_type if isinstance(trade_type, PushTradeType) else PushTradeType(str(trade_type).upper())
        ws_service = UtaPushWsService(self.options, private_channel=False, trade_type=normalized)
        return UtaPublicWSImpl(ws_service, normalized)

    def new_uta_private_ws(self) -> UtaPrivateWS:
        return UtaPrivateWSImpl(UtaPushWsService(self.options, private_channel=True))

    def new_uta_private_trade_ws(self) -> UtaPrivateTradeWS:
        return UtaPrivateTradeWSImpl(UtaPrivateTradeWsService(self.options))
