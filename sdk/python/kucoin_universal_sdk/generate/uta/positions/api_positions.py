"""UTA position REST APIs."""

from __future__ import annotations

from ..base_api import UtaApiBase, install_routes


class PositionsAPI(UtaApiBase):
    pass


class PositionsAPIImpl(PositionsAPI):
    pass


_routes = {
    "getPrivateFundingFeeHistory": ("GET", "/api/ua/v2/position/funding-history"),
    "getPositionsHistory": ("GET", "/api/ua/v2/position/history"),
    "getMarginMode": ("GET", "/api/ua/v2/unified/position/margin-mode"),
    "getPositionList": ("GET", "/api/ua/v2/unified/position/open-list"),
    "modifyMarginMode": ("POST", "/api/ua/v2/unified/position/margin-mode"),
    "modifyIsolatedFuturesMargin": ("POST", "/api/ua/v2/unified/position/modify-margin"),
}

install_routes(PositionsAPI, _routes)
