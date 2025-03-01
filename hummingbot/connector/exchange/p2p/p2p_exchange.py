import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.p2p import p2p_constants as CONSTANTS, p2p_utils, p2p_web_utils as web_utils
from hummingbot.connector.exchange.p2p.p2p_api_order_book_data_source import P2PAPIOrderBookDataSource
from hummingbot.connector.exchange.p2p.p2p_api_user_stream_data_source import P2PAPIUserStreamDataSource
from hummingbot.connector.exchange.p2p.p2p_auth import P2PAuth
from hummingbot.connector.exchange.p2p.p2p_utils import P2PRESTRequest
from hummingbot.connector.exchange.p2p.p2p_web_utils import build_api_factory
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None


class P2pExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 p2p_api_key: str,
                 p2p_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        self.api_key = p2p_api_key
        self.secret_key = p2p_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_p2p_timestamp = 1.0
        self._time_synchronizer = TimeSynchronizer()
        self._auth = P2PAuth(self.api_key, self.secret_key, self._time_synchronizer)
        self._web_assistants_factory = build_api_factory(time_synchronizer=self._time_synchronizer, auth=self._auth)
        super().__init__(client_config_map)

    @staticmethod
    def p2p_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    async def p2p_private_request(self, path_url, data=None, return_err=False, headers={}, method=RESTMethod.POST) -> Dict[str, Any]:
        api_url = f"{CONSTANTS.REST_URL.format(CONSTANTS.DEFAULT_DOMAIN)}{CONSTANTS.API_VERSION}{path_url}"

        local_headers = {
            "Content-Type": "application/json"}
        local_headers.update(headers)

        request = P2PRESTRequest(
            method=method,
            url=api_url,
            data=data,
            headers=local_headers,
            is_auth_required=True,
            throttler_limit_id=path_url
        )

        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        async with self._web_assistants_factory.throttler.execute_task(limit_id=path_url):
            response = await rest_assistant.call(request=request, timeout=10)

            if 400 <= response.status:
                if return_err:
                    error_response = await response.json()
                    return error_response
                else:
                    error_response = await response.text()
                    error_text = "N/A" if "<html" in error_response else error_response
                    raise IOError(f"Error executing request POST {api_url}. HTTP status is {response.status}. "
                                  f"Error: {error_text}")
            result = await response.json()
            return result

    @staticmethod
    def to_hb_order_type(p2p_type: str) -> OrderType:
        return OrderType[p2p_type]

    @property
    def authenticator(self):
        return P2PAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "p2p"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return self._domain

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pair_prices: List[Dict[str, str]] = List()
        for pair in self.trading_pairs:
            market = self._connector.trading_pair_associated_to_exchange_symbol(symbol=pair)
            pair_price = await self._api_get(
                path_url=CONSTANTS.TICKER_PRICE_URL.format(market),
                limit_id=CONSTANTS.TICKER_PRICE_URL)
            pair_prices.append({"symbol": market,
                                "bidPrice": pair_price["result"]["bid"],
                                "askPrice": pair_price["result"]["ask"]})

        return pair_prices

    # P2P doesn't need time sync
    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return P2PAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return P2PAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(False))

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        order_result = None
        amount_str = f"{amount:f}"
        price_str = f"{price:f}"
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        api_params = {"market": symbol,
                      "side": side_str,
                      "amount": amount_str,
                      "price": price_str}

        order_result = await self.p2p_private_request(CONSTANTS.NEW_ORDER_PATH_URL, api_params)
        o_id = str(order_result["result"]["orderId"])
        transact_time = int(order_result["result"]["timestamp"])
        return (o_id, transact_time)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {
            "market": symbol,
            "orderId": order_id,
        }
        cancel_result = await self.p2p_private_request(CONSTANTS.CANCEL_ORDER_PATH_URL, api_params)
        return cancel_result["success"]

    # TODO understand how this works 😳
    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "name":"ETH_BTC",
            "stock":"ETH",
            "money":"BTC",
            "precision": {
                "money":"6",
                "stock":"3",
                "fee":"4"
            },
            "limits": {
                "min_amount":"0.001",
                "max_amount":"100000",
                "step_size":"0.001",
                "min_price":"0.000001",
                "max_price":"100000",
                "tick_size":"0.000001",
                "min_total":"0.0001"
            }
        }
        """
        trading_pair_rules = exchange_info_dict.get("result", [])
        retval = []
        for rule in filter(p2p_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = rule.get("name")
                limits = rule.get("limits")
                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=Decimal(limits.get("min_amount"),
                                               min_price_increment=Decimal(limits.get("tick_size")),
                                               min_base_amount_increment=Decimal(limits.get("step_size")),
                                               min_notional_size=Decimal(0)
                                               ))
                )

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    async def _status_polling_loop_fetch_updates(self):
        await self._update_order_fills_from_trades()
        await super()._status_polling_loop_fetch_updates()

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    # TODO make this work within the websocket
    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("e")
                # Refer to https://github.com/binance-exchange/binance-official-api-docs/blob/master/user-data-stream.md
                # As per the order update section in Binance the ID of the order being canceled is under the "C" key
                if event_type == "executionReport":
                    execution_type = event_message.get("x")
                    if execution_type != "CANCELED":
                        client_order_id = event_message.get("c")
                    else:
                        client_order_id = event_message.get("C")

                    if execution_type == "TRADE":
                        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
                        if tracked_order is not None:
                            fee = TradeFeeBase.new_spot_fee(
                                fee_schema=self.trade_fee_schema(),
                                trade_type=tracked_order.trade_type,
                                percent_token=event_message["N"],
                                flat_fees=[TokenAmount(amount=Decimal(event_message["n"]), token=event_message["N"])]
                            )
                            trade_update = TradeUpdate(
                                trade_id=str(event_message["t"]),
                                client_order_id=client_order_id,
                                exchange_order_id=str(event_message["i"]),
                                trading_pair=tracked_order.trading_pair,
                                fee=fee,
                                fill_base_amount=Decimal(event_message["l"]),
                                fill_quote_amount=Decimal(event_message["l"]) * Decimal(event_message["L"]),
                                fill_price=Decimal(event_message["L"]),
                                fill_timestamp=event_message["T"] * 1e-3,
                            )
                            self._order_tracker.process_trade_update(trade_update)

                    tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                    if tracked_order is not None:
                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=event_message["E"] * 1e-3,
                            new_state=CONSTANTS.ORDER_STATE[event_message["X"]],
                            client_order_id=client_order_id,
                            exchange_order_id=str(event_message["i"]),
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

                elif event_type == "outboundAccountPosition":
                    balances = event_message["B"]
                    for balance_entry in balances:
                        asset_name = balance_entry["a"]
                        free_balance = Decimal(balance_entry["f"])
                        total_balance = Decimal(balance_entry["f"]) + Decimal(balance_entry["l"])
                        self._account_available_balances[asset_name] = free_balance
                        self._account_balances[asset_name] = total_balance

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    # TODO do this later
    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = int(order.exchange_order_id)
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                params={
                    "symbol": trading_pair,
                    "orderId": exchange_order_id
                },
                is_auth_required=True,
                limit_id=CONSTANTS.MY_TRADES_PATH_URL)

            for trade in all_fills_response:
                exchange_order_id = str(trade["orderId"])
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=trade["commissionAsset"],
                    flat_fees=[TokenAmount(amount=Decimal(trade["commission"]), token=trade["commissionAsset"])]
                )
                trade_update = TradeUpdate(
                    trade_id=str(trade["id"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(trade["qty"]),
                    fill_quote_amount=Decimal(trade["quoteQty"]),
                    fill_price=Decimal(trade["price"]),
                    fill_timestamp=trade["time"] * 1e-3,
                )
                trade_updates.append(trade_update)

        return trade_updates

    def _order_update_from_order(self, order_id: str, trading_pair: Any, new_state: OrderState):
        return OrderUpdate(
            client_order_id=order_id,
            exchange_order_id=order_id,
            trading_pair=trading_pair,
            update_timestamp=int(self._time_synchronizer.time()),
            new_state=new_state
        )

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)

        pending_orders = await self.p2p_private_request(CONSTANTS.PENDING_ORDERS_PATH_URL)
        for order in pending_orders["result"]:
            if (tracked_order.exchange_order_id == str(order["id"])):
                return self._order_update_from_order(str(order["id"]), tracked_order.trading_pair, CONSTANTS.OrderState.OPEN if order["amount"] == order["left"] else CONSTANTS.OrderState.PARTIALLY_FILLED)

        executed_orders = await self.p2p_private_request(CONSTANTS.ORDER_HISTORY_PATH_URL)
        for order in executed_orders["result"][trading_pair]:
            if (tracked_order.exchange_order_id == str(order["id"])):
                return self._order_update_from_order(str(order["id"]), trading_pair, CONSTANTS.OrderState.COMPLETED)

        return self._order_update_from_order(tracked_order.exchange_order_id, trading_pair, CONSTANTS.OrderState.FAILED)

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        balance_info = await self.p2p_private_request(CONSTANTS.BALANCES_PATH_URL, data={})

        if not balance_info["success"]:
            return False

        balances = balance_info["result"]
        for asset in balances:
            self._account_available_balances[asset] = Decimal(balances[asset]["available"])
            self._account_balances[asset] = Decimal(balances[asset]["available"]) + Decimal(balances[asset]["freeze"])
            remote_asset_names.add(asset)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for name in asset_names_to_remove:
            del self._account_available_balances[name]
            del self._account_balances[name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in exchange_info["result"]:
            mapping[symbol_data["stock"]] = symbol_data["name"]  # f"{symbol_data["stock"]}_{symbol_data["money"]}" is the same thing as this

        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        resp_json = await self._api_get(
            path_url=CONSTANTS.TICKER_PRICE_URL.format(await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)),
            limit_id=CONSTANTS.TICKER_PRICE_URL
        )

        return float(resp_json["result"]["last"])
