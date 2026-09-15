import json
from enum import Enum
from io import BytesIO
from typing import Any
from urllib.parse import urlencode

import requests
from pydantic import BaseModel
from requests.adapters import HTTPAdapter

from kucoin_universal_sdk.model.client_option import ClientOption
from kucoin_universal_sdk.model.common import RestRateLimit, RestError
from kucoin_universal_sdk.model.common import RestResponse
from kucoin_universal_sdk.model.constants import DomainType
from kucoin_universal_sdk.model.transport_option import TransportOption
from .default_signer import KcSigner
from ..interfaces.response import Response
from ..interfaces.transport import Transport

class DefaultTransport(Transport):
    def __init__(self, client_option: ClientOption, sdk_version: str):
        transport_option = client_option.transport_option
        if transport_option is None:
            transport_option = TransportOption()
            client_option.transport_option = transport_option
        self.client_option = client_option
        self.sdk_version = sdk_version

        self.transport_option = transport_option
        self.signer = KcSigner(client_option.key, client_option.secret, client_option.passphrase,
                               client_option.broker_name, client_option.broker_partner, client_option.broker_key)

        self.http_client = self.create_http_client(transport_option)

    def create_http_client(self, option: TransportOption) -> requests.Session:
        session = requests.Session()
        session = self.apply_option(session, option)
        return session

    def apply_option(self, session: requests.Session, option: TransportOption) -> requests.Session:
        adapter = HTTPAdapter(
            max_retries=option.max_retries,
            pool_connections=option.max_connection_per_pool,
            pool_maxsize=option.max_pool_size,
            pool_block=True
        )
        session.mount('https://', adapter)
        session.mount('http://', adapter)

        session.headers.update({
            'Connection': 'keep-alive' if option.keep_alive else 'close'
        })

        if option.proxy:
            session.proxies = option.proxy
        return session

    def process_headers(self, body: bytes, raw_url: str, request: requests.PreparedRequest, method: str, broker: bool):
        request.headers["Content-Type"] = "application/json"
        request.headers["User-Agent"] = f"Kucoin-Universal-Python-SDK/{self.sdk_version}"

        b = BytesIO()
        b.write(method.encode())
        b.write(raw_url.encode())
        b.write(body)
        payload = b.getvalue().decode()

        if broker:
            headers = self.signer.broker_headers(payload)
        else:
            headers = self.signer.headers(payload)

        for key, value in headers.items():
            request.headers[key] = value

    def process_path_variable(self, path: str, request_obj: Any) -> str:
        if request_obj is None:
            return path

        path_variables = {
            field_info.alias or field_name: getattr(request_obj, field_name)
            for field_name, field_info in request_obj.model_fields.items()
            if field_info.json_schema_extra and field_info.json_schema_extra.get("path_variable", False)
        }

        missing_placeholders = [key for key, value in path_variables.items() if value is None]
        if missing_placeholders:
            raise ValueError(f"Missing path variable value(s) for {', '.join(missing_placeholders)}")

        return path.format(**path_variables)

    @staticmethod
    def _query_value(value: Any) -> str:
        if isinstance(value, Enum):
            value = value.value
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def query_items(self, query_dict):
        if not query_dict:
            return []

        result = []
        for key, values in query_dict.items():
            if not isinstance(values, (list, tuple, set)):
                values = [values]
            for value in values:
                if value is not None:
                    result.append((key, self._query_value(value)))
        return result

    @staticmethod
    def raw_query(query_items):
        if not query_items:
            return ""
        return "&".join(f"{key}={value}" for key, value in query_items)

    def process_request(self, request_obj: Any, broker: bool, path: str, endpoint: str, method: str,
                        request_as_json: bool, **kwargs: Any) -> requests.Request:
        path = self.process_path_variable(path, request_obj)
        raw_url = path
        req_body = None
        full_path = f"{endpoint}{path}"

        if request_as_json:
            if request_obj:
                req_body = request_obj.to_json()
        else:
            if method in ["GET", "DELETE"]:
                if request_obj:
                    query_items = self.query_items(request_obj.to_dict())
                    query_params = urlencode(query_items)
                    raw_query_params = self.raw_query(query_items)
                    if query_params:
                        full_path += f"?{query_params}"
                        raw_url += f"?{raw_query_params}"
            elif method == "POST":
                if request_obj:
                    req_body = request_obj.to_json()
            else:
                raise ValueError(f"Invalid method: {method}")

        req = requests.Request(
            method=method,
            url=full_path,
            data=req_body,
        )
        prepared_req = req.prepare()
        self.process_headers(req_body.encode() if req_body is not None else b"", raw_url, prepared_req, method, broker)

        return prepared_req

    def do_with_retry(self, req: requests.Request) -> requests.Response:
        resp = None
        err = None
        try:
            for interceptor in self.transport_option.interceptors:
                try:
                    req = interceptor.before(req)
                except Exception as e:
                    raise Exception(f"Interceptor before failed: {e}") from e

            try:
                resp = self.http_client.send(req, timeout=(
                    self.transport_option.connect_timeout, self.transport_option.read_timeout))
                err = None
            except Exception as e:
                err = e
                raise e
        finally:
            for interceptor in self.transport_option.interceptors:
                try:
                    resp = interceptor.after(req, resp, err)
                except Exception as e:
                    raise Exception(f"Interceptor after failed: {e}") from e

        return resp

    def process_limit(self, resp: requests.Response) -> RestRateLimit:
        limit = int(resp.headers.get("gw-ratelimit-limit", -1))
        remaining = int(resp.headers.get("gw-ratelimit-remaining", -1))
        reset = int(resp.headers.get("gw-ratelimit-reset", -1))

        return RestRateLimit(
            limit=limit,
            remaining=remaining,
            reset=reset
        )

    def process_response(self, resp: requests.Response, response_obj: Response) -> Any:
        resp_body = resp.content
        if resp.status_code != requests.codes.ok:
            raise RestError(None, f"Invalid status code: {resp.status_code}, msg: {resp_body.decode('utf-8')}")

        try:
            common_response = RestResponse.from_json(resp_body.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise RestError(None, f"Failed to parse common response JSON: {str(e)}")

        resp_body = None
        common_response.rate_limit = self.process_limit(resp)

        if common_response.error():
            raise RestError(common_response, "")

        if common_response.data is None:
            response_obj.set_common_response(common_response)
            return response_obj

        try:
            response_obj = response_obj.from_dict(common_response.data)
        except json.JSONDecodeError as e:
            raise RestError(common_response, f"Failed to parse response JSON data: {str(e)}")
        finally:
            response_obj.set_common_response(common_response)
            return response_obj

    def call(self, domain: str, broker: bool, method: str, path: str, request_obj: Any, response_obj: Response,
             request_as_json: bool, **kwargs: Any) -> Any:
        domain = domain.lower()
        method = method.upper()
        if domain == DomainType.SPOT.value:
            endpoint = self.client_option.spot_endpoint
        elif domain == DomainType.FUTURES.value:
            endpoint = self.client_option.futures_endpoint
        elif domain == DomainType.BROKER.value:
            endpoint = self.client_option.broker_endpoint
        else:
            raise ValueError(f"Invalid domain: {domain}")

        if request_obj is not None and not isinstance(request_obj, BaseModel):
            raise TypeError(f"The request object must inherit from BaseModel, got {type(request_obj)}.")

        try:
            path = self.process_path_variable(path, request_obj)
            req = self.process_request(request_obj, path=path, endpoint=endpoint, method=method, broker=broker,
                                       request_as_json=request_as_json, **kwargs)
            response_body = self.do_with_retry(req)
        except Exception as err:
            raise RestError(None, f"Request failed: {err}")
        return self.process_response(response_body, response_obj)

    def close(self):
        self.http_client.close()
