"""UTA unified order REST APIs."""

from __future__ import annotations

from ..base_api import UtaApiBase, install_routes


class OrderAPI(UtaApiBase):
    pass


class OrderAPIImpl(OrderAPI):
    pass


_routes = {
    "batchCancelOrdersBySymbol": ("POST", "/api/ua/v2/unified/order/cancel-all"),
    "batchCancelOrdersById": ("POST", "/api/ua/v2/unified/order/cancel-batch"),
    "cancelOrder": ("POST", "/api/ua/v2/unified/order/cancel"),
    "getOrderDetails": ("GET", "/api/ua/v2/unified/order/detail"),
    "getTradeHistory": ("GET", "/api/ua/v2/unified/order/execution"),
    "getOrderHistory": ("GET", "/api/ua/v2/unified/order/history"),
    "getOpenOrderList": ("GET", "/api/ua/v2/unified/order/open-list"),
    "placeOrder": ("POST", "/api/ua/v2/unified/order/place"),
    "amendOrder": ("POST", "/api/ua/v2/unified/order/amend"),
}

install_routes(OrderAPI, _routes)
