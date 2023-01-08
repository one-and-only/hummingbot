import hashlib
import hmac
import json
from base64 import b64encode
from collections import OrderedDict
from typing import Dict
from uuid import uuid4

from hummingbot.connector.exchange.p2p import p2p_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class P2PAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        # Public requests don't need auth
        # Requests are either GET or POST
        if request.method == RESTMethod.GET:
            return request

        # There are some endpoints that don't require more than basic params
        data = OrderedDict() if request.data is None else OrderedDict(json.loads(request.data))
        data["request"] = request.url.split(f".{CONSTANTS.DEFAULT_DOMAIN}")[1]
        data["nonce"] = int(self.time_provider.time() * 1e3)

        request.data = data

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)

        headers.update(self.headers_for_authentication(request))
        headers.update(self.headers_for_postman_tricks())
        request.headers = headers
        if "balances" in request.url:
            print(json.dumps(headers))
            print("\n\n")
            print(json.dumps(request.data))
            print("\n\n")
            print(json.dumps(request.url))

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. P2P does not use this
        functionality
        """
        return request  # pass-through

    def headers_for_authentication(self, request: RESTRequest) -> Dict[str, str]:
        payload = b64encode(json.dumps(request.data).encode("ascii")).decode("ascii")

        return {"X-TXC-APIKEY": self.api_key,
                "X-TXC-PAYLOAD": payload,
                "X-TXC-SIGNATURE": hmac.new(self.secret_key.encode("ascii"), payload.encode("ascii"), hashlib.sha512).hexdigest()}

    def headers_for_postman_tricks(self) -> Dict[str, str]:
        return {"Postman-Token": str(uuid4()),
                "User-Agent": "PostmanRuntime/7.29.2"}
