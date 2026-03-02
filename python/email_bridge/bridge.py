#!/usr/bin/env python3
"""
Email Bridge — polls Zero's M365 inbox via Graph API and forwards new emails
to ZeroClaw gateway. Responses are sent back as email replies.

Uses certificate-based application auth (same as teams_bridge).
"""

import asyncio
import base64
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiohttp
import msal

logging.basicConfig(
    level=logging.INFO,
    format="[email-bridge] %(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("email-bridge")

# --- Configuration (env vars with sensible defaults) ---
TENANT_ID = os.environ.get("TENANT_ID", "36e770ef-e6fd-4f9d-9ace-a949f98a0caa")
CLIENT_ID = os.environ.get("CLIENT_ID", "836086a7-0308-4c57-a817-5699613f6d8c")
CERT_KEY_PATH = os.environ.get("CERT_KEY_PATH", "/etc/zeroclaw/m365-key.pem")
CERT_THUMBPRINT = os.environ.get(
    "CERT_THUMBPRINT", "A2672B07930718938659A36C171B0DEB5548B0A7"
)
ZERO_USER_ID = os.environ.get("ZERO_USER_ID", "84e4cd1c-a1a1-4746-8132-e4d1b39a0d04")
ZERO_UPN = os.environ.get("ZERO_UPN", "Zero@dirtybirdusa.com")
GATEWAY_URL = os.environ.get("ZEROCLAW_GATEWAY_URL", "http://127.0.0.1:3000")
GATEWAY_TOKEN = os.environ.get("ZEROCLAW_GATEWAY_TOKEN", "")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "30"))
GATEWAY_TIMEOUT = int(os.environ.get("GATEWAY_TIMEOUT", "300"))
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
ATTACHMENT_DIR = Path(os.environ.get("ATTACHMENT_DIR", "/tmp/zeroclaw-email-attachments"))
IMAGE_MIME_TYPES = frozenset({
    "image/png", "image/jpeg", "image/jpg",
    "image/webp", "image/gif", "image/bmp",
})
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB


def extract_inline_data_images(html: str) -> list[str]:
    """Extract data:image URIs embedded directly in HTML img tags.

    Returns list of data URIs suitable for saving to disk.
    """
    return re.findall(r'src="(data:image/[^"]+)"', html, re.IGNORECASE)


def strip_html(html: str) -> str:
    """Strip HTML tags and decode common entities."""
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"<[^>]+>", "", text)
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&nbsp;", " ")
    )
    return text.strip()


class EmailBridge:
    """Polls Zero's inbox and bridges emails to ZeroClaw gateway."""

    def __init__(self):
        self.msal_app = None
        self.graph_token = None
        self.token_expiry = datetime.min.replace(tzinfo=timezone.utc)

    # --- Auth ---

    def _get_msal_app(self) -> msal.ConfidentialClientApplication:
        if self.msal_app is None:
            with open(CERT_KEY_PATH) as f:
                private_key = f.read()
            self.msal_app = msal.ConfidentialClientApplication(
                CLIENT_ID,
                authority=f"https://login.microsoftonline.com/{TENANT_ID}",
                client_credential={
                    "thumbprint": CERT_THUMBPRINT,
                    "private_key": private_key,
                },
            )
        return self.msal_app

    def _acquire_token(self) -> str:
        now = datetime.now(timezone.utc)
        if self.graph_token and now < self.token_expiry - timedelta(minutes=5):
            return self.graph_token

        app = self._get_msal_app()
        result = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            raise RuntimeError(
                f"Token acquisition failed: {result.get('error_description', result)}"
            )
        self.graph_token = result["access_token"]
        self.token_expiry = now + timedelta(seconds=result.get("expires_in", 3600))
        log.info("Graph token acquired (expires in %ds)", result.get("expires_in", 3600))
        return self.graph_token

    # --- Graph helpers ---

    async def _graph_get(self, session: aiohttp.ClientSession, path: str) -> dict:
        token = self._acquire_token()
        async with session.get(
            f"{GRAPH_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            body = await resp.text()
            log.warning("Graph GET %s -> %d: %s", path, resp.status, body[:300])
            return {}

    async def _graph_post(
        self, session: aiohttp.ClientSession, path: str, body: dict
    ) -> int:
        token = self._acquire_token()
        async with session.post(
            f"{GRAPH_BASE}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        ) as resp:
            if resp.status in (200, 201, 202):
                return resp.status
            data = await resp.text()
            log.warning("Graph POST %s -> %d: %s", path, resp.status, data[:300])
            return resp.status

    async def _graph_patch(
        self, session: aiohttp.ClientSession, path: str, body: dict
    ) -> int:
        token = self._acquire_token()
        async with session.patch(
            f"{GRAPH_BASE}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        ) as resp:
            return resp.status

    # --- Mail operations ---

    async def _get_unread_messages(self, session: aiohttp.ClientSession) -> list:
        """Fetch unread messages from Zero's inbox."""
        data = await self._graph_get(
            session,
            f"/users/{ZERO_USER_ID}/mailFolders/inbox/messages"
            f"?$filter=isRead eq false"
            f"&$top=10"
            f"&$select=id,subject,from,body,receivedDateTime,conversationId,hasAttachments"
            f"&$orderby=receivedDateTime asc",
        )
        return data.get("value", [])

    async def _fetch_image_attachments(
        self, session: aiohttp.ClientSession, message_id: str
    ) -> list[str]:
        """Fetch image attachments (both regular and inline) via Graph API.

        Returns local file paths suitable for ZeroClaw [IMAGE:] markers.
        """
        data = await self._graph_get(
            session,
            f"/users/{ZERO_USER_ID}/messages/{message_id}/attachments"
            f"?$select=id,name,contentType,size,contentBytes,isInline",
        )
        attachments = data.get("value", [])
        log.info("Attachment API returned %d item(s) for message %s",
                 len(attachments), message_id[:12])

        if not attachments:
            return []

        ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
        saved = []

        for att in attachments:
            mime = (att.get("contentType") or "").lower().split(";")[0].strip()
            name = att.get("name", "image.bin")
            is_inline = att.get("isInline", False)

            if mime not in IMAGE_MIME_TYPES:
                log.debug("Skipping non-image attachment: %s (%s)", name, mime)
                continue
            if att.get("size", 0) > MAX_IMAGE_SIZE:
                log.warning("Skipping oversized attachment %s (%d bytes)", name, att.get("size"))
                continue
            raw_b64 = att.get("contentBytes")
            if not raw_b64:
                log.warning("Attachment %s has no contentBytes (may need /$value fetch)", name)
                continue
            try:
                raw = base64.b64decode(raw_b64)
            except Exception:
                log.warning("Failed to decode attachment %s", name)
                continue

            tag = "inline" if is_inline else "attached"
            safe_name = re.sub(r"[^\w.\-]", "_", name)
            file_path = ATTACHMENT_DIR / f"{message_id[:12]}_{safe_name}"
            file_path.write_bytes(raw)
            saved.append(str(file_path))
            log.info("Saved %s image: %s (%d bytes)", tag, file_path.name, len(raw))

        return saved

    def _save_data_uri_images(self, data_uris: list[str], message_id: str) -> list[str]:
        """Save data:image URIs extracted from HTML body to disk.

        Returns local file paths.
        """
        if not data_uris:
            return []

        ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
        saved = []
        ext_map = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
                    "image/webp": "webp", "image/bmp": "bmp"}

        for i, uri in enumerate(data_uris):
            try:
                header, payload = uri.split(",", 1)
                mime = header.split(":")[1].split(";")[0].lower()
                ext = ext_map.get(mime, "bin")
                raw = base64.b64decode(payload)
                if len(raw) > MAX_IMAGE_SIZE:
                    log.warning("Skipping oversized inline data URI (%d bytes)", len(raw))
                    continue
                file_path = ATTACHMENT_DIR / f"{message_id[:12]}_inline_{i}.{ext}"
                file_path.write_bytes(raw)
                saved.append(str(file_path))
                log.info("Saved data-URI image: %s (%d bytes)", file_path.name, len(raw))
            except Exception as e:
                log.warning("Failed to process data URI image %d: %s", i, e)

        return saved

    async def _mark_as_read(self, session: aiohttp.ClientSession, message_id: str):
        """Mark a message as read."""
        await self._graph_patch(
            session,
            f"/users/{ZERO_USER_ID}/messages/{message_id}",
            {"isRead": True},
        )

    async def _send_reply(
        self,
        session: aiohttp.ClientSession,
        message_id: str,
        reply_text: str,
    ):
        """Reply to a specific email message."""
        status = await self._graph_post(
            session,
            f"/users/{ZERO_USER_ID}/messages/{message_id}/reply",
            {"message": {"body": {"contentType": "Text", "content": reply_text}}},
        )
        return status in (200, 201, 202)

    # --- Gateway ---

    async def _forward_to_gateway(
        self, session: aiohttp.ClientSession, message: str
    ) -> str:
        headers = {"Content-Type": "application/json"}
        if GATEWAY_TOKEN:
            headers["Authorization"] = f"Bearer {GATEWAY_TOKEN}"
        try:
            async with session.post(
                f"{GATEWAY_URL}/webhook",
                json={"message": message},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=GATEWAY_TIMEOUT),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", data.get("message", str(data)))
                body = await resp.text()
                log.error("Gateway HTTP %d: %s", resp.status, body[:300])
                return f"I encountered an error processing your request (HTTP {resp.status})."
        except asyncio.TimeoutError:
            log.error("Gateway timeout after %ds", GATEWAY_TIMEOUT)
            return "I'm still processing your request. Please try again later."
        except Exception as e:
            log.error("Gateway unreachable: %s", e)
            return "I'm currently unavailable. Please try again later."

    # --- Polling ---

    async def _poll_once(self, session: aiohttp.ClientSession):
        messages = await self._get_unread_messages(session)
        if not messages:
            return

        log.info("Found %d unread email(s)", len(messages))
        for msg in messages:
            msg_id = msg["id"]
            subject = msg.get("subject", "(no subject)")
            sender = msg.get("from", {}).get("emailAddress", {})
            sender_addr = sender.get("address", "unknown")
            sender_name = sender.get("name", sender_addr)

            # Skip automated/system emails
            if sender_addr.endswith("@teams.mail.microsoft") or "noreply" in sender_addr:
                log.info("Skipping system email from %s: %s", sender_addr, subject)
                await self._mark_as_read(session, msg_id)
                continue

            # Extract body text — check for embedded data URI images before stripping HTML
            body = msg.get("body", {})
            raw_content = body.get("content", "")
            data_uri_images = []
            if body.get("contentType") == "html":
                data_uri_images = extract_inline_data_images(raw_content)
                if data_uri_images:
                    log.info("Found %d data-URI image(s) in HTML body", len(data_uri_images))
                content = strip_html(raw_content)
            else:
                content = raw_content
            content = content.strip()
            if not content:
                content = subject

            log.info("Processing email from %s <%s>: %s", sender_name, sender_addr, subject)

            # Mark as read immediately to prevent re-processing
            await self._mark_as_read(session, msg_id)

            # Collect images from all sources:
            # 1. Graph API attachments (regular + inline cid: images)
            # 2. Data URI images embedded in HTML body
            all_image_paths = await self._fetch_image_attachments(session, msg_id)
            all_image_paths.extend(self._save_data_uri_images(data_uri_images, msg_id))

            image_markers = ""
            if all_image_paths:
                image_markers = "\n".join(f"[IMAGE:{p}]" for p in all_image_paths)
                log.info("Including %d image(s) in prompt", len(all_image_paths))

            # Forward to ZeroClaw gateway
            prompt = f"[Email from {sender_name} <{sender_addr}>]\nSubject: {subject}\n\n{content}"
            if image_markers:
                prompt = f"{prompt}\n\n{image_markers}"
            response = await self._forward_to_gateway(session, prompt)

            # Reply to the email
            if response:
                success = await self._send_reply(session, msg_id, response)
                if success:
                    log.info("Replied to %s: %s", sender_addr, subject)
                else:
                    log.error("Failed to send reply to %s", sender_addr)

    # --- Main loop ---

    async def run(self):
        log.info("Starting Email Bridge")
        log.info("  Gateway: %s", GATEWAY_URL)
        log.info("  Poll interval: %ds", POLL_INTERVAL)
        log.info("  Zero mailbox: %s (%s)", ZERO_UPN, ZERO_USER_ID)

        async with aiohttp.ClientSession() as session:
            # Verify token works on startup
            self._acquire_token()
            log.info("Auth OK — entering poll loop")

            while True:
                try:
                    await self._poll_once(session)
                except Exception as e:
                    log.error("Poll error: %s", e, exc_info=True)
                await asyncio.sleep(POLL_INTERVAL)


def main():
    bridge = EmailBridge()
    try:
        asyncio.run(bridge.run())
    except KeyboardInterrupt:
        log.info("Shutting down")
        sys.exit(0)


if __name__ == "__main__":
    main()
