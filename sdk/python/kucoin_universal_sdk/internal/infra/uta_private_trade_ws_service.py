"""Direct authenticated UTA WebSocket trading transport."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import threading
import urllib.parse
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Union

import websocket
from pydantic import BaseModel

from kucoin_universal_sdk.internal.infra.default_signer import KcSigner
from kucoin_universal_sdk.model.client_option import ClientOption
from kucoin_universal_sdk.model.websocket_option import WebSocketClientOption


@dataclass
class _PendingResponse:
    event: threading.Event = field(default_factory=threading.Event)
    response: Optional[Dict[str, Any]] = None
    error: Optional[BaseException] = None


class UtaPrivateTradeWsService:
    """Implements ``uta.order``, ``uta.cancel`` and ``uta.amend``."""

    ENDPOINT = "wss://wsapi.kucoin.com/v1/private"

    def __init__(self, client_option: ClientOption):
        if not all([client_option.key, client_option.secret, client_option.passphrase]):
            raise ValueError("UTA private trade WebSocket requires key, secret, and passphrase")
        self.client_option = client_option
        self.option: WebSocketClientOption = client_option.websocket_client_option or WebSocketClientOption()
        self._signer = KcSigner(
            client_option.key,
            client_option.secret,
            client_option.passphrase,
            client_option.broker_name,
            client_option.broker_partner,
            client_option.broker_key,
        )
        self._lock = threading.RLock()
        self._send_lock = threading.Lock()
        self._socket: Optional[websocket.WebSocketApp] = None
        self._socket_thread: Optional[threading.Thread] = None
        self._welcome = threading.Event()
        self._pending: Dict[str, _PendingResponse] = {}
        self._connected = False
        self._started = False
        self._shutting_down = False
        self._reconnecting = False
        self._reconnect_attempts = 0
        self._dial_error: Optional[BaseException] = None

    def start(self) -> None:
        with self._lock:
            if self._connected:
                return
            self._started = True
            self._shutting_down = False
        self._connect()

    def stop(self) -> None:
        with self._lock:
            self._started = False
            self._shutting_down = True
            self._connected = False
        self._close_socket("shutdown")
        self._fail_pending(RuntimeError("UTA private trade WebSocket stopped"))

    def place_order(self, request: Union[Mapping[str, Any], BaseModel]) -> Dict[str, Any]:
        return self._request("uta.order", self._order_args(request))

    def cancel_order(self, request: Union[Mapping[str, Any], BaseModel]) -> Dict[str, Any]:
        arguments = self._compact(request)
        self._require_order_reference(arguments)
        return self._request("uta.cancel", arguments)

    def amend_order(self, request: Union[Mapping[str, Any], BaseModel]) -> Dict[str, Any]:
        arguments = self._compact(request)
        self._require_order_reference(arguments)
        return self._request("uta.amend", arguments)

    def _request(self, operation: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if not self._connected:
            raise RuntimeError("UTA private trade WebSocket is not connected; call start() first")
        request_id = str(uuid.uuid4())
        pending = _PendingResponse()
        with self._lock:
            self._pending[request_id] = pending
        try:
            self._send_json({"id": request_id, "op": operation, "args": args})
            if not pending.event.wait(timeout=self.option.write_timeout):
                raise TimeoutError(f"{operation} response timed out")
            if pending.error is not None:
                raise RuntimeError(f"{operation} failed") from pending.error
            assert pending.response is not None
            return pending.response
        finally:
            with self._lock:
                self._pending.pop(request_id, None)

    def _connect(self) -> None:
        headers = self._signer.headers("")
        timestamp = headers["KC-API-TIMESTAMP"]
        query = urllib.parse.urlencode(
            {
                "apikey": self.client_option.key,
                "timestamp": timestamp,
                "sign": self._hmac(f"{self.client_option.key}{timestamp}"),
                "passphrase": headers["KC-API-PASSPHRASE"],
            }
        )
        self._welcome.clear()
        self._dial_error = None
        app = websocket.WebSocketApp(
            f"{self.ENDPOINT}?{query}",
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        with self._lock:
            self._socket = app
            self._socket_thread = threading.Thread(
                target=app.run_forever,
                kwargs={"ping_interval": 0},
                name="kucoin-uta-trade-ws",
                daemon=True,
            )
            self._socket_thread.start()
        if not self._welcome.wait(timeout=self.option.dial_timeout):
            self._close_socket("welcome timeout")
            raise RuntimeError("welcome not received before dial timeout")
        if self._dial_error is not None:
            self._close_socket("dial error")
            raise RuntimeError("WebSocket connection failed") from self._dial_error
        with self._lock:
            self._connected = True
            self._reconnect_attempts = 0

    def _on_open(self, _: websocket.WebSocketApp) -> None:
        logging.debug("UTA private trade WebSocket opened")

    def _on_message(self, _: websocket.WebSocketApp, raw: str) -> None:
        try:
            message = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            logging.warning("Ignoring invalid UTA private trade WebSocket JSON")
            return
        if not isinstance(message, dict):
            return
        if self._is_auth_challenge(message):
            try:
                self._send_text(self._hmac(raw))
            except BaseException as error:
                self._dial_error = error
                self._welcome.set()
            return
        if self._is_welcome(message):
            self._welcome.set()
            return
        request_id = message.get("id")
        if request_id is None:
            return
        with self._lock:
            pending = self._pending.get(str(request_id))
        if pending is None:
            return
        if str(message.get("code")) == "200000":
            pending.response = message
        else:
            pending.error = RuntimeError(json.dumps(message, ensure_ascii=False))
        pending.event.set()

    def _on_error(self, _: websocket.WebSocketApp, error: BaseException) -> None:
        logging.warning("UTA private trade WebSocket error: %s", error)
        if not self._connected:
            self._dial_error = error
            self._welcome.set()

    def _on_close(
        self, _: websocket.WebSocketApp, status_code: Optional[int], message: Optional[str]
    ) -> None:
        error = RuntimeError(f"closed {status_code}: {message or ''}")
        with self._lock:
            was_connected = self._connected
            self._connected = False
        self._fail_pending(error)
        if not was_connected:
            self._dial_error = error
            self._welcome.set()
            return
        if self._started and not self._shutting_down and self.option.reconnect:
            self._start_reconnect()

    def _start_reconnect(self) -> None:
        with self._lock:
            if self._reconnecting:
                return
            self._reconnecting = True
        threading.Thread(target=self._reconnect_loop, name="kucoin-uta-trade-reconnect", daemon=True).start()

    def _reconnect_loop(self) -> None:
        try:
            while self._started and not self._shutting_down:
                if self.option.reconnect_attempts >= 0 and self._reconnect_attempts >= self.option.reconnect_attempts:
                    return
                self._reconnect_attempts += 1
                threading.Event().wait(self.option.reconnect_interval)
                try:
                    self._connect()
                    return
                except BaseException as error:
                    logging.warning("UTA private trade WebSocket reconnect failed: %s", error)
        finally:
            with self._lock:
                self._reconnecting = False

    def _send_json(self, message: Dict[str, Any]) -> None:
        self._send_text(json.dumps(message, separators=(",", ":"), ensure_ascii=False))

    def _send_text(self, payload: str) -> None:
        with self._send_lock:
            socket = self._socket
            if socket is None or socket.sock is None or not socket.sock.connected:
                raise RuntimeError("UTA private trade WebSocket is not open")
            socket.send(payload)

    def _close_socket(self, reason: str) -> None:
        with self._lock:
            socket = self._socket
            self._socket = None
        if socket is not None:
            try:
                socket.close(status=1000, reason=reason)
            except BaseException:
                logging.debug("UTA private trade close failed", exc_info=True)

    def _fail_pending(self, error: BaseException) -> None:
        with self._lock:
            pending = list(self._pending.values())
            self._pending.clear()
        for value in pending:
            value.error = error
            value.event.set()

    def _order_args(self, request: Union[Mapping[str, Any], BaseModel]) -> Dict[str, Any]:
        arguments = self._compact(request)
        if self._blank(arguments.get("tpTriggerPrice")):
            arguments.pop("tpTriggerPrice", None)
            arguments.pop("tpTriggerPriceType", None)
        if self._blank(arguments.get("slTriggerPrice")):
            arguments.pop("slTriggerPrice", None)
            arguments.pop("slTriggerPriceType", None)
        return arguments

    @staticmethod
    def _compact(request: Union[Mapping[str, Any], BaseModel]) -> Dict[str, Any]:
        if isinstance(request, BaseModel):
            if hasattr(request, "to_dict"):
                values = request.to_dict()
            else:
                values = request.model_dump(by_alias=True, exclude_none=True)
        elif isinstance(request, Mapping):
            values = dict(request)
        else:
            raise TypeError("UTA trade request must be a mapping or pydantic BaseModel")
        return {key: value for key, value in values.items() if value is not None}

    @staticmethod
    def _require_order_reference(arguments: Dict[str, Any]) -> None:
        if UtaPrivateTradeWsService._blank(arguments.get("orderId")) and UtaPrivateTradeWsService._blank(arguments.get("clientOid")):
            raise ValueError("either orderId or clientOid must be provided")

    @staticmethod
    def _blank(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    def _hmac(self, value: str) -> str:
        digest = hmac.new(
            self.client_option.secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256
        ).digest()
        return base64.b64encode(digest).decode("utf-8")

    @staticmethod
    def _is_welcome(message: Dict[str, Any]) -> bool:
        return any(
            str(message.get(key, "")).lower() == "welcome"
            for key in ("data", "message", "op", "type")
        )

    @staticmethod
    def _is_auth_challenge(message: Dict[str, Any]) -> bool:
        return message.get("sessionId") is not None and message.get("timestamp") is not None and "data" not in message
