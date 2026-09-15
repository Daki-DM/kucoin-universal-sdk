"""UTA affiliate REST APIs."""

from __future__ import annotations

from ..base_api import UtaApiBase, install_routes


class AffiliateAPI(UtaApiBase):
    pass


class AffiliateAPIImpl(AffiliateAPI):
    pass


_routes = {
    "getInvited": ("GET", "/api/ua/v2/affiliate/queryInvitees"),
    "getKumining": ("GET", "/api/ua/v2/affiliate/queryKumining"),
    "getCommission": ("GET", "/api/ua/v2/affiliate/queryMyCommission"),
    "getTransaction": ("GET", "/api/ua/v2/affiliate/queryTransactionByTime"),
    "getTradeHistory": ("GET", "/api/ua/v2/affiliate/queryTransactionByUid"),
}

install_routes(AffiliateAPI, _routes)
