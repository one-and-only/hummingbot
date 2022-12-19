import re
from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

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


KEYS = P2PConfigMap.construct()
