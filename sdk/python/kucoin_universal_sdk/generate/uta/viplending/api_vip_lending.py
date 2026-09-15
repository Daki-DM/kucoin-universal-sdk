"""UTA VIP lending REST APIs."""

from __future__ import annotations

from ..base_api import UtaApiBase, install_routes


class VIPLendingAPI(UtaApiBase):
    pass


class VIPLendingAPIImpl(VIPLendingAPI):
    pass


_routes = {
    "getAccounts": ("GET", "/api/ua/v2/otc-loan/account"),
    "getDiscountRateConfigs": ("GET", "/api/ua/v2/otc-loan/discount-rate"),
    "getLoanInfo": ("GET", "/api/ua/v2/otc-loan/loan"),
}

install_routes(VIPLendingAPI, _routes)
