import hashlib
import hmac
from typing import Any, Dict

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class AAXAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.header_for_authentication(request))
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. AAX does not use this
        functionality
        """
        return request  # pass-through

    def header_for_authentication(self, request: RESTRequest) -> Dict[str, str]:
        nonce = self.time_provider.time() * 1000 + 30000  # invalid after 30 seconds to prevent replay attacks
        return {"X-ACCESS-KEY": self.api_key,
                "X-ACCESS-NONCE": f"{nonce}",
                "X-ACCESS-SIGN": self._generate_signature({"nonce": nonce, "verb": str(request.method), "path": request.endpoint_url, "data": str(request.data)})}

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        digest = hmac.new(self.secret_key.encode("utf8"), f"{params['nonce']}:{params['verb']}{params['path']}{params['data']}", hashlib.sha256).hexdigest()
        return digest
