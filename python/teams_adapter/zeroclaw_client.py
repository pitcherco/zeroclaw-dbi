"""HTTP client for ZeroClaw gateway webhook."""

import logging

import aiohttp

logger = logging.getLogger(__name__)


class ZeroClawClient:
    """Sends messages to ZeroClaw gateway and receives responses."""

    def __init__(self, gateway_url: str, token: str, timeout: int = 300):
        self.gateway_url = gateway_url.rstrip("/")
        self.token = token
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def send_message(self, message: str) -> str:
        """POST a message to ZeroClaw's /webhook endpoint and return the response."""
        url = f"{self.gateway_url}/webhook"
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        payload = {"message": message}

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # ZeroClaw returns response in the JSON body
                        return data.get("response", data.get("message", str(data)))
                    else:
                        body = await resp.text()
                        logger.error("ZeroClaw returned %d: %s", resp.status, body[:500])
                        return f"Agent error (HTTP {resp.status}). Please try again."
        except aiohttp.ClientError as e:
            logger.exception("Failed to reach ZeroClaw gateway")
            return f"Agent is unreachable: {e}"
        except TimeoutError:
            logger.warning("ZeroClaw gateway timed out after %ds", self.timeout.total)
            return "Agent is still processing your request. Please wait and try again shortly."

    async def health_check(self) -> bool:
        """Check if ZeroClaw gateway is reachable."""
        url = f"{self.gateway_url}/health"
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(url) as resp:
                    return resp.status == 200
        except Exception:
            return False
