"""Base implementation used by the generated UTA REST API groups."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Callable, Dict, Optional, Tuple, Type

from pydantic import BaseModel

from kucoin_universal_sdk.internal.interfaces.transport import Transport

from .common import UtaRequest, UtaResponse


Route = Tuple[str, str]


class UtaApiBase:
    """Dispatches UTA calls through the normal signed Spot transport."""

    def __init__(self, transport: Transport):
        self.transport = transport

    def _call(
        self,
        method: str,
        path: str,
        request: Optional[Any] = None,
        **kwargs: Any,
    ) -> UtaResponse:
        request_object = self._request_object(request, kwargs)
        return self.transport.call(
            "spot", False, method, path, request_object, UtaResponse(), False
        )

    @staticmethod
    def _request_object(request: Optional[Any], values: Dict[str, Any]) -> Optional[BaseModel]:
        if request is None:
            return UtaRequest(**values) if values else None

        if isinstance(request, Mapping):
            merged = dict(request)
            merged.update(values)
            return UtaRequest(**merged)

        if not isinstance(request, BaseModel):
            raise TypeError(
                "UTA request must be a mapping or pydantic BaseModel, "
                f"got {type(request).__name__}"
            )

        if not values:
            return request

        if hasattr(request, "to_dict"):
            merged = request.to_dict()
        else:
            merged = request.model_dump(by_alias=True, exclude_none=True)
        merged.update(values)
        return UtaRequest(**merged)


def camel_to_snake(name: str) -> str:
    """Convert Java-style UTA method names to the Python SDK naming convention."""

    first_pass = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", first_pass).lower()


def install_routes(api_class: Type[UtaApiBase], routes: Dict[str, Route]) -> None:
    """Install Python snake_case methods plus Java-compatible aliases for routes."""

    for java_name, (http_method, path) in routes.items():
        python_name = camel_to_snake(java_name)

        def make_method(method: str, route: str, name: str) -> Callable[..., UtaResponse]:
            def endpoint(
                self: UtaApiBase, request: Optional[Any] = None, **kwargs: Any
            ) -> UtaResponse:
                return self._call(method, route, request, **kwargs)

            endpoint.__name__ = name
            endpoint.__qualname__ = f"{api_class.__name__}.{name}"
            endpoint.__doc__ = f"Calls {method} {route}."
            return endpoint

        endpoint = make_method(http_method, path, python_name)
        setattr(api_class, python_name, endpoint)
        setattr(api_class, java_name, endpoint)
