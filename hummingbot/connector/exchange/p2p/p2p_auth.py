import hashlib
import hmac
import json
from base64 import b64encode
from typing import Dict

from hummingbot.connector.exchange.p2p import p2p_constants as CONSTANTS
from hummingbot.connector.exchange.p2p.p2p_utils import P2PRESTRequest
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import WSRequest


class P2PAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    async def rest_authenticate(self, request: P2PRESTRequest) -> P2PRESTRequest:
        # All private requests require some "basic" params
        data = {} if request.data is None else dict(json.loads(request.data))
        data["request"] = request.url.split(f".{CONSTANTS.DEFAULT_DOMAIN}")[1]
        data["nonce"] = int(self.time_provider.time() * 1e3)

        request.data = data

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)

        headers.update(self.headers_for_authentication(request))
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. P2P does not use this
        functionality
        """
        return request  # pass-through

    def headers_for_authentication(self, request: P2PRESTRequest) -> Dict[str, str]:
        payload = b64encode(json.dumps(request.data, separators=(',', ':')).encode("ascii")).decode("ascii")

        return {"X-TXC-APIKEY": self.api_key,
                "X-TXC-PAYLOAD": payload,
                "X-TXC-SIGNATURE": hmac.new(self.secret_key.encode("ascii"), payload.encode("ascii"), hashlib.sha512).hexdigest()}
