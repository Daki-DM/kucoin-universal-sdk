# Python SDK Documentation
![License Badge](https://img.shields.io/badge/license-MIT-green)  
![Language](https://img.shields.io/badge/Python-blue)

Welcome to the **Python** implementation of the KuCoin Universal SDK. This SDK is built based on KuCoin API specifications to provide a comprehensive and optimized interface for interacting with the KuCoin platform.

For an overview of the project and SDKs in other languages, refer to the [Main README](https://github.com/kucoin/kucoin-universal-sdk).

## 📦 Installation

### Latest Version: `1.3.2`
Install the Python SDK using `pip`:

```bash
pip install kucoin-universal-sdk
```

## 📖 UTA Quick Start

The SDK provides UTA REST groups for Account, Market, Order, Positions,
Affiliate and VIP Lending. Private UTA REST calls require an API key with the
corresponding UTA permission. Store credentials in environment variables rather
than source code:

```bash
export API_KEY='your-api-key'
export API_SECRET='your-api-secret'
export API_PASSPHRASE='your-api-passphrase'
```

### UTA REST: Get Account Overview

```python
import os

from kucoin_universal_sdk.api import DefaultClient
from kucoin_universal_sdk.model import (
    ClientOptionBuilder,
    GLOBAL_API_ENDPOINT,
    GLOBAL_BROKER_API_ENDPOINT,
    GLOBAL_FUTURES_API_ENDPOINT,
    TransportOptionBuilder,
)


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


client = DefaultClient(
    ClientOptionBuilder()
    .set_key(required_env("API_KEY"))
    .set_secret(required_env("API_SECRET"))
    .set_passphrase(required_env("API_PASSPHRASE"))
    .set_spot_endpoint(GLOBAL_API_ENDPOINT)
    .set_futures_endpoint(GLOBAL_FUTURES_API_ENDPOINT)
    .set_broker_endpoint(GLOBAL_BROKER_API_ENDPOINT)
    .set_transport_option(TransportOptionBuilder().set_keep_alive(True).build())
    .build()
)

account_api = client.rest_service().get_uta_service().get_account_api()
response = account_api.get_account_overview()
print(response.data)
```

### UTA Public WebSocket: Subscribe to Ticker

UTA public WebSocket channels do not require credentials. SPOT and FUTURES use
separate direct gateways, so create a service with the matching `PushTradeType`.

```python
import json
import time

from kucoin_universal_sdk.api import DefaultClient
from kucoin_universal_sdk.model import (
    ClientOptionBuilder,
    PushTradeType,
    WebSocketClientOptionBuilder,
)


client = DefaultClient(
    ClientOptionBuilder()
    .set_websocket_client_option(
        WebSocketClientOptionBuilder().with_reconnect(True).build()
    )
    .build()
)

public_ws = client.ws_service().new_uta_public_ws(PushTradeType.SPOT)
subscription_id = None
try:
    public_ws.start()
    subscription_id = public_ws.ticker(
        ["BTC-USDT", "ETH-USDT"],
        lambda event: print(json.dumps(event, ensure_ascii=False)),
    )
    print("Subscribed to SPOT ticker. Press Ctrl+C to stop.")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    if subscription_id is not None:
        public_ws.unsubscribe(subscription_id)
    public_ws.stop()
```

For authenticated UTA push channels use
`client.ws_service().new_uta_private_ws()`. For WebSocket order placement,
cancellation and amendment use
`client.ws_service().new_uta_private_trade_ws()`.

## 📚 Documentation
Official Documentation: [KuCoin API Docs](https://www.kucoin.com/docs-new)  

## 📋 Changelog

For a detailed list of changes, see the [Changelog](./CHANGELOG.md).

## 📌 Special Notes on APIs

This section provides specific considerations and recommendations for using the REST and WebSocket APIs.

### REST API Notes

#### Client Features
- **Advanced HTTP Handling**:
  - Supports retries, persistent connections, and connection pooling for efficient request handling.
- **Extensible Interceptors**:
  - Provides HTTP interceptors that users can extend to customize request and response processing.
- **Rich Response Details**:
  - Includes rate-limiting information and raw response data in API responses for better debugging and control.
- **Public API Access**:
  - For public endpoints, API keys are not required, simplifying integration for non-authenticated use cases.

---

### WebSocket API Notes

#### Client Features
- **Flexible Service Creation**:
  - Supports creating services for public/private channels in Spot, Futures, or Margin trading as needed.
  - Multiple services can be created independently.
  - UTA direct WebSocket services are available through `new_uta_public_ws`, `new_uta_private_ws`, and `new_uta_private_trade_ws`.
  - Use a separate UTA public service for `PushTradeType.SPOT` and `PushTradeType.FUTURES`.
- **Service Lifecycle**:
  - If a service is closed, create a new service instead of reusing it to avoid undefined behavior.
- **Connection-to-Channel Mapping**:
  - Each WebSocket connection corresponds to a specific channel type. For example:
    - Spot public/private and Futures public/private services require 4 active WebSocket connections.

#### Threading and Callbacks
- **Simple Thread Model**:
  - WebSocket services follow a simple thread model, ensuring callbacks are handled on a single thread.
- **Subscription Management**:
  - Subscriptions are synchronous. A subscription is considered successful only after receiving an acknowledgment (ACK) from the server.
  - Each subscription has a unique ID, which can be used for unsubscribe.

#### Data and Message Handling
- **Framework-Managed Threads**:
  - Data messages are handled by a single framework-managed thread, ensuring orderly processing.
- **Buffer Management**:
  - When the message buffer is full, excess messages are dropped, and a notification event is sent.
- **Duplicate Subscriptions**:
  - Avoid overlapping subscription parameters. For example:
    - Subscribing to `["BTC-USDT", "ETH-USDT"]` and then to `["ETH-USDT", "DOGE-USDT"]` may result in undefined behavior.
    - Identical subscriptions will raise an error for duplicate subscriptions.

## 📑 Parameter Descriptions

This section provides details about the configurable parameters for both HTTP and WebSocket client behavior.

### HTTP Parameters

| Parameter                  | Type                   | Description                                                                                   | Default Value                         |
|----------------------------|------------------------|-----------------------------------------------------------------------------------------------|---------------------------------------|
| `keep_alive`               | `bool`                | Enables keep-alive for persistent connections.                                                | True                                  |
| `max_pool_size`            | `int`                 | The number of connection pools to cache (number of hosts).                          | 10                                    |
| `max_connection_per_pool`  | `int`                 | The maximum number of connections to save in the pool.                                        | 10                                    |
| `connect_timeout`          | `float`               | Connection timeout duration in seconds.                                                       | 10                                    |
| `read_timeout`             | `float`               | Read timeout duration in seconds.                                                    | 30                                    |
| `proxy`                    | `Optional[dict]`      | HTTP(s) proxy. Example: `{'http': '192.168.1.1', 'https': '192.168.1.1'}`                     | None                                  |
| `max_retries`              | `int`                 | Maximum number of retry attempts.                                                             | 3                                     |
| `interceptors`             | `Optional[List[Interceptor]]` | List of HTTP interceptors.                                                                    | An empty list (`[]`)                  |


### WebSocket Parameters

| Parameter               | Type                      | Description                                                                                     | Default Value |
|-------------------------|---------------------------|-------------------------------------------------------------------------------------------------|---------------|
| `reconnect`             | `bool`                   | Enables automatic reconnection if the connection is lost.                                       | True          |
| `reconnect_attempts`    | `int`                    | Maximum number of reconnection attempts; `-1` for unlimited attempts.                           | -1            |
| `reconnect_interval`    | `int`                    | Interval between reconnection attempts in seconds.                                              | 5.0           |
| `dial_timeout`          | `int`                    | Timeout duration for establishing a WebSocket connection in seconds.                            | 10.0          |
| `read_message_buffer`   | `int`                    | Buffer size for reading messages in the queue.                                                  | 1024          |
| `write_message_buffer`  | `int`                    | Buffer size for writing messages in the queue.                                                  | 256           |
| `write_timeout`         | `int`                    | Timeout for sending messages in seconds.                                                        | 5.0           |
| `event_callback`        | `Optional[WebSocketCallback]` | A callback function to handle WebSocket events.                                                 | None          |


## 📝 License

This project is licensed under the MIT License. For more details, see the [LICENSE](LICENSE) file.

## 📧 Contact Support

If you encounter any issues or have questions, feel free to reach out through:
- GitHub Issues: [Submit an Issue](https://github.com/kucoin/kucoin-universal-sdk/issues)  

## ⚠️ Disclaimer

- **Financial Risk**: This SDK is provided as a development tool to integrate with KuCoin's trading platform. It does not provide financial advice. Trading cryptocurrencies involves substantial risk, including the risk of loss. Users should assess their financial circumstances and consult with financial advisors before engaging in trading.
  
- **No Warranty**: The SDK is provided "as is" without any guarantees of accuracy, reliability, or suitability for a specific purpose. Use it at your own risk.

- **Compliance**: Users are responsible for ensuring compliance with all applicable laws and regulations in their jurisdiction when using this SDK.

By using this SDK, you acknowledge that you have read, understood, and agreed to this disclaimer.
