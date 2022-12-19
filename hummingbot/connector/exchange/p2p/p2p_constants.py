from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "com"

HBOT_ORDER_ID_PREFIX = "x-XEKWYICX"
MAX_ORDER_ID_LEN = 32

# Base URL
REST_URL = "https://api.p2pb2b.{}/api/"
WSS_URL = "wss://apiws.p2pb2b.{}/"

PUBLIC_API_VERSION = "v2"
PRIVATE_API_VERSION = "v2"

# Public API endpoints
TICKER_PRICE_URL = "/public/ticker?market={}"
EXCHANGE_INFO_PATH_URL = "/public/markets"
SNAPSHOT_PATH_URL = "/depth"

# Private API endpoints
BALANCES_PATH_URL = "/account/balances"
NEW_ORDER_PATH_URL = "/order/new"
CANCEL_ORDER_PATH_URL = "/order/cancel"
PENDING_ORDERS_PATH_URL = "/orders"
ORDER_HISTORY_PATH_URL = "/account/order_history"

WS_HEARTBEAT_TIME_INTERVAL = 60

# P2P params

SIDE_BUY = 'buy'
SIDE_SELL = 'sell'

# P2P has a rate limit that is higher per second, but lower per minute
# this is the fastest rate limit that will work for both
# 100 requests per endpoint per minute (Lowest Common Denominator)
LCD_RATE_LIMIT = 100 / 60
ONE_SECOND = 1

# Order States
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "NEW": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING_CANCEL": OrderState.OPEN,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
}

# Websocket event types
DIFF_EVENT_TYPE = "depthUpdate"
TRADE_EVENT_TYPE = "trade"

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=LCD_RATE_LIMIT, time_interval=ONE_SECOND),
    RateLimit(limit_id=TICKER_PRICE_URL, limit=LCD_RATE_LIMIT, time_interval=ONE_SECOND),
    RateLimit(limit_id=BALANCES_PATH_URL, limit=LCD_RATE_LIMIT, time_interval=ONE_SECOND),
    RateLimit(limit_id=ORDER_HISTORY_PATH_URL, limit=LCD_RATE_LIMIT, time_interval=ONE_SECOND),
    RateLimit(limit_id=NEW_ORDER_PATH_URL, limit=LCD_RATE_LIMIT, time_interval=ONE_SECOND),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=LCD_RATE_LIMIT, time_interval=ONE_SECOND),
    RateLimit(limit_id=PENDING_ORDERS_PATH_URL, limit=LCD_RATE_LIMIT, time_interval=ONE_SECOND)
]
