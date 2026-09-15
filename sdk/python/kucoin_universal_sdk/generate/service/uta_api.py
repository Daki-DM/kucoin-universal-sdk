
"""Aggregates all UTA REST API groups."""

from abc import ABC, abstractmethod

from kucoin_universal_sdk.generate.uta.account import AccountAPI, AccountAPIImpl
from kucoin_universal_sdk.generate.uta.affiliate import AffiliateAPI, AffiliateAPIImpl
from kucoin_universal_sdk.generate.uta.market import MarketAPI, MarketAPIImpl
from kucoin_universal_sdk.generate.uta.order import OrderAPI, OrderAPIImpl
from kucoin_universal_sdk.generate.uta.positions import PositionsAPI, PositionsAPIImpl
from kucoin_universal_sdk.generate.uta.viplending import VIPLendingAPI, VIPLendingAPIImpl
from kucoin_universal_sdk.internal.interfaces.transport import Transport


class UTAService(ABC):
    @abstractmethod
    def get_account_api(self) -> AccountAPI:
        pass

    @abstractmethod
    def get_market_api(self) -> MarketAPI:
        pass

    @abstractmethod
    def get_vip_lending_api(self) -> VIPLendingAPI:
        pass

    @abstractmethod
    def get_positions_api(self) -> PositionsAPI:
        pass

    @abstractmethod
    def get_order_api(self) -> OrderAPI:
        pass

    @abstractmethod
    def get_affiliate_api(self) -> AffiliateAPI:
        pass


class UTAServiceImpl(UTAService):
    def __init__(self, transport: Transport):
        self.account = AccountAPIImpl(transport)
        self.market = MarketAPIImpl(transport)
        self.vip_lending = VIPLendingAPIImpl(transport)
        self.positions = PositionsAPIImpl(transport)
        self.order = OrderAPIImpl(transport)
        self.affiliate = AffiliateAPIImpl(transport)

    def get_account_api(self) -> AccountAPI:
        return self.account

    def get_market_api(self) -> MarketAPI:
        return self.market

    def get_vip_lending_api(self) -> VIPLendingAPI:
        return self.vip_lending

    def get_positions_api(self) -> PositionsAPI:
        return self.positions

    def get_order_api(self) -> OrderAPI:
        return self.order

    def get_affiliate_api(self) -> AffiliateAPI:
        return self.affiliate
