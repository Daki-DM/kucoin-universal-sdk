from abc import ABC, abstractmethod

from kucoin_universal_sdk.generate.futures.futures_private.ws_futures_private import FuturesPrivateWS
from kucoin_universal_sdk.generate.futures.futures_public.ws_futures_public import FuturesPublicWS
from kucoin_universal_sdk.generate.margin.margin_private.ws_margin_private import MarginPrivateWS
from kucoin_universal_sdk.generate.margin.margin_public.ws_margin_public import MarginPublicWS
from kucoin_universal_sdk.generate.spot.spot_private.ws_spot_private import SpotPrivateWS
from kucoin_universal_sdk.generate.spot.spot_public.ws_spot_public import SpotPublicWS
from kucoin_universal_sdk.generate.uta.privatews import UtaPrivateTradeWS, UtaPrivateWS
from kucoin_universal_sdk.generate.uta.publicws import UtaPublicWS
from kucoin_universal_sdk.model.push_trade_type import PushTradeType


class KucoinWSService(ABC):

    @abstractmethod
    def new_spot_public_ws(self) -> SpotPublicWS:
        """
        new_spot_public_ws returns the interface to interact with
        the Spot Trading websocket (public channel) API of Kucoin.
        """
        pass

    @abstractmethod
    def new_spot_private_ws(self) -> SpotPrivateWS:
        """
        new_spot_private_ws returns the interface to interact with
        the Spot Trading websocket (private channel) API of Kucoin.
        """
        pass

    @abstractmethod
    def new_margin_public_ws(self) -> MarginPublicWS:
        """
        new_margin_public_ws returns the interface to interact with
        the Margin Trading websocket (public channel) API of Kucoin.
        """
        pass

    @abstractmethod
    def new_margin_private_ws(self) -> MarginPrivateWS:
        """
        new_margin_private_ws returns the interface to interact with
        the Margin Trading websocket (private channel) API of Kucoin.
        """
        pass

    @abstractmethod
    def new_futures_public_ws(self) -> FuturesPublicWS:
        """new_futures_public_ws returns the interface to interact with
        the Futures Trading websocket (public channel) API of Kucoin."""
        pass

    @abstractmethod
    def new_futures_private_ws(self) -> FuturesPrivateWS:
        """new_futures_private_ws returns the interface to interact with
        the Futures Trading websocket (private channel) API of Kucoin."""
        pass

    @abstractmethod
    def new_uta_public_ws(self, trade_type: PushTradeType) -> UtaPublicWS:
        """Creates a direct UTA public push WebSocket for SPOT or FUTURES."""
        pass

    @abstractmethod
    def new_uta_private_ws(self) -> UtaPrivateWS:
        """Creates a direct authenticated UTA private push WebSocket."""
        pass

    @abstractmethod
    def new_uta_private_trade_ws(self) -> UtaPrivateTradeWS:
        """Creates a direct authenticated UTA WebSocket trading connection."""
        pass
