"""Shared request and response types for the UTA REST APIs.

UTA response schemas have historically differed between the documented schema and the
wire response (notably, several endpoints can return either an object or an array).
These types deliberately keep ``data`` untyped so callers always receive the exact
server payload instead of failing during response deserialization.
"""

from __future__ import annotations

import json
import pprint
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from kucoin_universal_sdk.internal.interfaces.response import Response
from kucoin_universal_sdk.model.common import RestResponse


class UtaRequest(BaseModel):
    """Flexible UTA request model.

    The UTA API has a large set of endpoint-specific parameters.  Accepting extra
    fields keeps the SDK forward-compatible while still using the common transport
    signing and query serialization path.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True, protected_namespaces=())

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True, exclude_none=True)

    @classmethod
    def from_dict(cls, value: Optional[Dict[str, Any]]) -> Optional["UtaRequest"]:
        if value is None:
            return None
        return cls.model_validate(value)


class UtaResponse(BaseModel, Response):
    """UTA REST response whose ``data`` value may be an object, array, scalar or null."""

    data: Any = Field(default=None)
    common_response: Optional[RestResponse] = Field(default=None, exclude=True)

    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    def to_str(self) -> str:
        return pprint.pformat(self.to_dict())

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True, exclude_none=True)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)

    @classmethod
    def from_json(cls, value: str) -> "UtaResponse":
        return cls.from_dict(json.loads(value))

    @classmethod
    def from_dict(cls, value: Any) -> "UtaResponse":
        return cls(data=value)

    def set_common_response(self, response: RestResponse):
        self.common_response = response
