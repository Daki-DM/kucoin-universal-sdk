"""Direct UTA public/private push WebSocket transport.

The UTA push gateways do not use the legacy Bullet token/topic protocol.  This
transport intentionally owns its connection lifecycle, welcome handshake,
acknowledgements, authentication and heartbeat handling.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

import websocket

from kucoin_universal_sdk.internal.infra.default_signer import KcSigner
from kucoin_universal_sdk.model.client_option import ClientOption
from kucoin_universal_sdk.model.push_trade_type import PushTradeType
from kucoin_universal_sdk.model.websocket_option import WebSocketClientOption, WebSocketEvent


UtaPushCallback = Callable[[Dict[str, Any]], None]


@dataclass(frozen=True)
class UtaPushSubscription:
    channel: str
    callback: UtaPushCallback
    symbols: List[str] = field(default_factory=list)
    trade_type: Optional[str] = None
    account_type: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    include_trade_type: bool = True


@dataclass
class _PendingAck:
    event: threading.Event = field(default_factory=threading.Event)
    error: Optional[BaseException] = None


class UtaPushWsService:
    """Implements the direct UTA push wire protocol for public and private channels."""

    PRIVATE_ENDPOINT = "wss://wsapi-push.kucoin.com"
    AUTH_PLAINTEXT = "POST/api/websocket/users/verify"
    DEFAULT_PING_INTERVAL = 18.0
    DEFAULT_PING_TIMEOUT = 10.0

    def __init__(
        self,
        client_option: ClientOption,
        *,
        private_channel: bool,
        trade_type: Optional[Union[PushTradeType, str]] = None,
    ):
        self.client_option = client_option
        self.option = client_option.websocket_client_option or WebSocketClientOption()
        self.private_channel = private_channel
        self.trade_type = self._as_trade_type(trade_type) if not private_channel else None
        if not private_channel and self.trade_type is None:
            raise ValueError("UTA public WebSocket trade_type must be SPOT or FUTURES")
        if private_channel and not all(
            [client_option.key, client_option.secret, client_option.passphrase]
        ):
            raise ValueError("UTA private WebSocket requires key, secret, and passphrase")

        self._signer = (
            KcSigner(
                client_option.key,
                client_option.secret,
                client_option.passphrase,
                client_option.broker_name,
                client_option.broker_partner,
                client_option.broker_key,
            )
            if private_channel
            else None
        )
        self._endpoint = self.PRIVATE_ENDPOINT if private_channel else self.trade_type.endpoint
        self._lock = threading.RLock()
        self._send_lock = threading.Lock()
        self._socket: Optional[websocket.WebSocketApp] = None
        self._socket_thread: Optional[threading.Thread] = None
        self._welcome = threading.Event()
        self._pong = threading.Event()
        self._ping_stop = threading.Event()
        self._ping_thread: Optional[threading.Thread] = None
        self._pending: Dict[str, _PendingAck] = {}
        self._subscriptions: Dict[str, UtaPushSubscription] = {}
        self._started = False
        self._connected = False
        self._shutting_down = False
        self._reconnecting = False
        self._reconnect_attempts = 0
        self._dial_error: Optional[BaseException] = None
        self._ping_interval = self.DEFAULT_PING_INTERVAL
        self._ping_timeout = self.DEFAULT_PING_TIMEOUT

    @property
    def connected(self) -> bool:
        return self._connected

    def start(self) -> None:
        with self._lock:
            if self._connected:
                return
            self._started = True
            self._shutting_down = False
        self._connect()

    def stop(self) -> None:
        with self._lock:
            if not self._started and not self._connected:
                return
            self._started = False
            self._shutting_down = True
            self._connected = False
        self._stop_ping()
        self._fail_pending(RuntimeError("UTA WebSocket stopped"))
        self._close_socket("shutdown")
        self._notify(WebSocketEvent.EVENT_CLIENT_SHUTDOWN, self._channel_name(), "")

    def subscribe(self, subscription: UtaPushSubscription) -> str:
        if not self._connected:
            raise RuntimeError("UTA WebSocket is not connected; call start() first")
        self._validate_subscription(subscription)
        subscription_id = str(uuid.uuid4())
        with self._lock:
            self._subscriptions[subscription_id] = subscription
        try:
            self._send_subscription(subscription_id, subscription, "SUBSCRIBE")
            return subscription_id
        except BaseException:
            with self._lock:
                self._subscriptions.pop(subscription_id, None)
            raise

    def unsubscribe(self, subscription_id: str) -> None:
        with self._lock:
            subscription = self._subscriptions.get(subscription_id)
        if subscription is None:
            return
        if self._connected:
            self._send_subscription(subscription_id, subscription, "UNSUBSCRIBE")
        with self._lock:
            self._subscriptions.pop(subscription_id, None)

    def _connect(self) -> None:
        self._welcome.clear()
        self._dial_error = None
        app = websocket.WebSocketApp(
            self._endpoint,
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
                name="kucoin-uta-push-ws",
                daemon=True,
            )
            self._socket_thread.start()

        if not self._welcome.wait(timeout=self.option.dial_timeout):
            self._close_socket("welcome timeout")
            raise RuntimeError("welcome not received before dial timeout")
        if self._dial_error is not None:
            self._close_socket("dial error")
            raise RuntimeError("WebSocket connection failed") from self._dial_error

        if self.private_channel:
            self._authenticate()

        with self._lock:
            self._connected = True
            self._reconnect_attempts = 0
        self._start_ping()
        self._notify(WebSocketEvent.EVENT_CONNECTED, self._channel_name(), "")

    def _authenticate(self) -> None:
        assert self._signer is not None
        headers = self._signer.headers(self.AUTH_PLAINTEXT)
        self._send_and_await_ack(
            str(uuid.uuid4()),
            {
                "op": "auth",
                "kc-api-key": headers["KC-API-KEY"],
                "kc-api-sign": headers["KC-API-SIGN"],
                "kc-api-timestamp": headers["KC-API-TIMESTAMP"],
                "kc-api-passphrase": headers["KC-API-PASSPHRASE"],
            },
            operation="authentication",
        )

    def _send_subscription(
        self, subscription_id: str, subscription: UtaPushSubscription, action: str
    ) -> None:
        message: Dict[str, Any] = {"action": action, "channel": subscription.channel}
        if subscription.include_trade_type and subscription.trade_type:
            message["tradeType"] = str(subscription.trade_type).upper()
        if subscription.account_type:
            message["accountType"] = str(subscription.account_type).upper()
        if len(subscription.symbols) == 1:
            message["symbol"] = subscription.symbols[0]
        elif subscription.symbols:
            message["symbols"] = subscription.symbols
        message.update(subscription.parameters)
        self._send_and_await_ack(subscription_id, message, operation=action.lower())

    def _send_and_await_ack(self, message_id: str, message: Dict[str, Any], *, operation: str) -> None:
        pending = _PendingAck()
        with self._lock:
            self._pending[message_id] = pending
        try:
            payload = {"id": message_id, **message}
            self._send_json(payload)
            if not pending.event.wait(timeout=self.option.write_timeout):
                raise TimeoutError(f"UTA WebSocket {operation} acknowledgement timed out")
            if pending.error is not None:
                raise RuntimeError(f"UTA WebSocket {operation} failed") from pending.error
        finally:
            with self._lock:
                self._pending.pop(message_id, None)

    def _send_json(self, message: Dict[str, Any]) -> None:
        self._send_text(json.dumps(message, separators=(",", ":"), ensure_ascii=False))

    def _send_text(self, payload: str) -> None:
        with self._send_lock:
            socket = self._socket
            if socket is None or socket.sock is None or not socket.sock.connected:
                raise RuntimeError("UTA WebSocket is not open")
            socket.send(payload)

    def _on_open(self, _: websocket.WebSocketApp) -> None:
        logging.debug("UTA push WebSocket opened: %s", self._endpoint)

    def _on_message(self, _: websocket.WebSocketApp, raw: str) -> None:
        try:
            message = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            self._notify(WebSocketEvent.EVENT_ERROR_RECEIVED, "", "Invalid UTA WebSocket JSON")
            return
        if not isinstance(message, dict):
            return

        if self._is_welcome(message):
            self._ping_interval = self._positive_seconds(message.get("pingInterval"), self.DEFAULT_PING_INTERVAL)
            self._ping_timeout = self._positive_seconds(message.get("pingTimeout"), self.DEFAULT_PING_TIMEOUT)
            self._welcome.set()
            return

        if str(message.get("op", message.get("type", ""))).lower() == "pong":
            self._pong.set()
            self._notify(WebSocketEvent.EVENT_PONG_RECEIVED, raw, "")
            return

        message_id = message.get("id")
        if message_id is not None and "result" in message:
            self._resolve_ack(str(message_id), message)
            return

        if "T" in message and "d" in message:
            self._notify(WebSocketEvent.EVENT_MESSAGE_RECEIVED, raw, "")
            self._dispatch(message)

    def _on_error(self, _: websocket.WebSocketApp, error: BaseException) -> None:
        logging.warning("UTA push WebSocket error: %s", error)
        if not self._connected:
            self._dial_error = error
            self._welcome.set()

    def _on_close(
        self, _: websocket.WebSocketApp, status_code: Optional[int], message: Optional[str]
    ) -> None:
        reason = f"closed {status_code}: {message or ''}"
        self._handle_disconnect(reason)

    def _resolve_ack(self, message_id: str, message: Dict[str, Any]) -> None:
        with self._lock:
            pending = self._pending.get(message_id)
        if pending is None:
            return
        result = message.get("result")
        if result is True or str(result).lower() == "true":
            pending.event.set()
            return
        pending.error = RuntimeError(json.dumps(message, ensure_ascii=False))
        pending.event.set()

    def _dispatch(self, event: Dict[str, Any]) -> None:
        topic = str(event.get("T", ""))
        channel = "execution.lite" if topic.startswith("execution.lite.") else topic.split(".", 1)[0]
        data = event.get("d")
        symbol = data.get("s") if isinstance(data, dict) else None
        with self._lock:
            subscriptions = list(self._subscriptions.values())
        for subscription in subscriptions:
            if not self._matches(subscription, channel, topic, symbol):
                continue
            try:
                subscription.callback(event)
            except BaseException as error:
                logging.exception("UTA WebSocket callback failed")
                self._notify(WebSocketEvent.EVENT_CALLBACK_ERROR, "", str(error))

    @staticmethod
    def _matches(
        subscription: UtaPushSubscription, channel: str, topic: str, symbol: Optional[str]
    ) -> bool:
        expected = subscription.channel
        if expected != channel and not (
            (expected == "orderAll" and channel == "order")
            or (expected == "positionAll" and channel == "position")
        ):
            return False
        if subscription.account_type and topic != f"balance.{str(subscription.account_type).upper()}":
            return False
        return not subscription.symbols or symbol in subscription.symbols

    def _handle_disconnect(self, reason: str) -> None:
        with self._lock:
            was_connected = self._connected
            self._connected = False
        self._stop_ping()
        self._fail_pending(RuntimeError(reason))
        if not was_connected:
            self._dial_error = RuntimeError(reason)
            self._welcome.set()
            return
        self._notify(WebSocketEvent.EVENT_DISCONNECTED, self._channel_name(), reason)
        if self._started and not self._shutting_down and self.option.reconnect:
            self._start_reconnect()

    def _start_reconnect(self) -> None:
        with self._lock:
            if self._reconnecting:
                return
            self._reconnecting = True
        threading.Thread(target=self._reconnect_loop, name="kucoin-uta-push-reconnect", daemon=True).start()

    def _reconnect_loop(self) -> None:
        try:
            while self._started and not self._shutting_down:
                if self.option.reconnect_attempts >= 0 and self._reconnect_attempts >= self.option.reconnect_attempts:
                    self._notify(WebSocketEvent.EVENT_CLIENT_FAIL, self._channel_name(), "maximum reconnect attempts exceeded")
                    return
                self._reconnect_attempts += 1
                self._notify(WebSocketEvent.EVENT_TRY_RECONNECT, self._channel_name(), str(self._reconnect_attempts))
                # ``_ping_stop`` is set by _handle_disconnect(), so it cannot be
                # used as the reconnect delay signal.  Doing so made every
                # reconnect return immediately after the first disconnect.
                time.sleep(self.option.reconnect_interval)
                if not self._started or self._shutting_down:
                    return
                try:
                    self._connect()
                    with self._lock:
                        subscriptions = list(self._subscriptions.items())
                    for subscription_id, subscription in subscriptions:
                        self._send_subscription(subscription_id, subscription, "SUBSCRIBE")
                    self._notify(WebSocketEvent.EVENT_RE_SUBSCRIBE_OK, self._channel_name(), "")
                    return
                except BaseException as error:
                    logging.warning("UTA WebSocket reconnect failed: %s", error)
                    self._notify(WebSocketEvent.EVENT_RE_SUBSCRIBE_ERROR, self._channel_name(), str(error))
        finally:
            with self._lock:
                self._reconnecting = False

    def _start_ping(self) -> None:
        self._stop_ping()
        self._ping_stop = threading.Event()
        self._ping_thread = threading.Thread(target=self._ping_loop, name="kucoin-uta-push-ping", daemon=True)
        self._ping_thread.start()

    def _stop_ping(self) -> None:
        self._ping_stop.set()

    def _ping_loop(self) -> None:
        while self._connected and not self._ping_stop.wait(timeout=self._ping_interval):
            self._pong.clear()
            try:
                self._send_json({"id": str(uuid.uuid4()), "op": "ping", "timestamp": int(time.time() * 1000)})
            except BaseException as error:
                self._handle_disconnect(f"ping send failed: {error}")
                return
            if not self._pong.wait(timeout=self._ping_timeout):
                self._close_socket("pong timeout")
                return

    def _close_socket(self, reason: str) -> None:
        with self._lock:
            socket = self._socket
            self._socket = None
        if socket is not None:
            try:
                socket.close(status=1000, reason=reason)
            except BaseException:
                logging.debug("UTA WebSocket close failed", exc_info=True)

    def _fail_pending(self, error: BaseException) -> None:
        with self._lock:
            pending = list(self._pending.values())
            self._pending.clear()
        for value in pending:
            value.error = error
            value.event.set()

    def _validate_subscription(self, subscription: UtaPushSubscription) -> None:
        if not subscription.channel or not callable(subscription.callback):
            raise ValueError("channel and callback are required")
        normalized = self._normalise_symbols(subscription.symbols)
        if normalized != subscription.symbols:
            raise ValueError("symbols must be unique, non-empty strings")
        if subscription.channel not in {"funding-fee-all-symbols", "leverage", "lw", "execution", "execution.lite", "orderAll", "positionAll", "balance"} and not normalized:
            raise ValueError(f"{subscription.channel} requires a symbol or symbols")

    @staticmethod
    def _normalise_symbols(symbols: Iterable[str]) -> List[str]:
        result: List[str] = []
        for symbol in symbols:
            if not isinstance(symbol, str) or not symbol.strip():
                return []
            value = symbol.strip()
            if value not in result:
                result.append(value)
        return result

    @staticmethod
    def _as_trade_type(value: Optional[Union[PushTradeType, str]]) -> Optional[PushTradeType]:
        if value is None:
            return None
        if isinstance(value, PushTradeType):
            return value
        try:
            return PushTradeType(str(value).upper())
        except ValueError as error:
            raise ValueError("UTA public WebSocket trade_type must be SPOT or FUTURES") from error

    @staticmethod
    def _is_welcome(message: Dict[str, Any]) -> bool:
        return any(
            str(message.get(key, "")).lower() == "welcome"
            for key in ("data", "message", "op", "type")
        )

    @staticmethod
    def _positive_seconds(value: Any, default: float) -> float:
        try:
            numeric = float(value)
            if numeric <= 0:
                return default
            # Gateways announce milliseconds, while the SDK option uses seconds.
            return numeric / 1000.0 if numeric >= 1000 else numeric
        except (TypeError, ValueError):
            return default

    def _notify(self, event: WebSocketEvent, message: str, error: str) -> None:
        callback = self.option.event_callback
        if callback is None:
            return
        try:
            callback(event, message, error)
        except BaseException:
            logging.exception("UTA WebSocket event callback failed")

    def _channel_name(self) -> str:
        return "UTA_PRIVATE" if self.private_channel else f"UTA_PUBLIC_{self.trade_type.value}"
