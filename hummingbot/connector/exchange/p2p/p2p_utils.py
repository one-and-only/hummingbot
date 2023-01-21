import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict

import ujson
from pydantic import Field, SecretStr

import hummingbot.connector.exchange.p2p.p2p_constants as CONSTANTS
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.web_assistant.connections.data_types import EndpointRESTRequest, RESTMethod

CENTRALIZED = True
EXAMPLE_PAIR = "YFI_BTC"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.002"),
    taker_percent_fee_decimal=Decimal("0.002"),
    buy_percent_fee_deducted_from_returns=True
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    pair = exchange_info["name"]
    validitiy_check = re.compile("[a-zA-Z]+_[a-zA-Z]+").search(pair)
    return (exchange_info["stock"] in pair & exchange_info["money"] in pair) & (validitiy_check is not None)


class P2PConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="p2p", const=True, client_data=None)
    p2p_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your P2PB2B API key",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    p2p_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your P2PB2B API secret",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "p2p"

# We need forward slashes unescaped for auth endpoints to work fine


@dataclass
class P2PRESTRequest(EndpointRESTRequest):
    def _ensure_data(self):
        if self.method == RESTMethod.POST:
            if self.data is not None:
                self.data = ujson.dumps(self.data, escape_forward_slashes=False)
        elif self.data is not None:
            raise ValueError(
                "The `data` field should be used only for POST requests. Use `params` instead."
            )

    @property
    def base_url(self) -> str:
        return CONSTANTS.REST_URL.format(CONSTANTS.DEFAULT_DOMAIN) + CONSTANTS.PRIVATE_API_VERSION


KEYS = P2PConfigMap.construct()
