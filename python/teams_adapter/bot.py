"""Teams bot that forwards messages to ZeroClaw gateway."""

import asyncio
import logging

from botbuilder.core import ActivityHandler, MessageFactory, TurnContext
from botbuilder.schema import Activity, ActivityTypes, ConversationReference

from .zeroclaw_client import ZeroClawClient

logger = logging.getLogger(__name__)


class ZeroClawTeamsBot(ActivityHandler):
    """Receives Teams DMs and @mentions, forwards to ZeroClaw, posts response back."""

    def __init__(self, zeroclaw_client: ZeroClawClient):
        self.zeroclaw_client = zeroclaw_client
        # Store conversation references for proactive messaging
        self._conversation_references: dict[str, ConversationReference] = {}

    async def on_message_activity(self, turn_context: TurnContext):
        """Handle incoming message from Teams user."""
        # Strip bot @mention from text if present
        text = self._clean_message(turn_context)
        if not text:
            return

        logger.info(
            "Received message from %s: %s",
            turn_context.activity.from_property.name,
            text[:100],
        )

        # Store conversation reference for proactive messaging
        self._store_reference(turn_context)

        # Send typing indicator
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))

        # Forward to ZeroClaw gateway
        # Use proactive messaging pattern: respond immediately, then send result later
        # Bot Framework requires response within ~15s; ZeroClaw may take minutes
        conversation_ref = TurnContext.get_conversation_reference(turn_context.activity)

        async def process_and_reply():
            """Background task: call ZeroClaw and send proactive response."""
            try:
                response = await self.zeroclaw_client.send_message(text)
                # Send proactive message back to the conversation
                await turn_context.adapter.continue_conversation(
                    conversation_ref,
                    lambda ctx: ctx.send_activity(MessageFactory.text(response)),
                    turn_context.activity.service_url,
                )
            except Exception:
                logger.exception("Error processing message via ZeroClaw")
                await turn_context.adapter.continue_conversation(
                    conversation_ref,
                    lambda ctx: ctx.send_activity(
                        MessageFactory.text(
                            "Sorry, I encountered an error processing your request."
                        )
                    ),
                    turn_context.activity.service_url,
                )

        # Fire-and-forget the background task
        asyncio.create_task(process_and_reply())

        # Immediately acknowledge with typing (keeps Bot Framework happy)
        await turn_context.send_activity(
            MessageFactory.text("Working on it...")
        )

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        """Welcome new members when bot is added to a conversation."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    MessageFactory.text(
                        "Hi! I'm the ZeroClaw Teammate Agent. "
                        "I can help you with M365 tasks — reading SharePoint files, "
                        "generating reports, checking calendars, and more. "
                        "Just DM me or @mention me in a channel."
                    )
                )

    def _clean_message(self, turn_context: TurnContext) -> str:
        """Remove bot @mention tags from the message text."""
        text = turn_context.activity.text or ""
        # Remove <at>BotName</at> tags from Teams @mentions
        if turn_context.activity.entities:
            for entity in turn_context.activity.entities:
                if entity.type == "mention":
                    mentioned = entity.additional_properties.get("mentioned", {})
                    if mentioned.get("id") == turn_context.activity.recipient.id:
                        mention_text = entity.additional_properties.get("text", "")
                        text = text.replace(mention_text, "").strip()
        return text.strip()

    def _store_reference(self, turn_context: TurnContext):
        """Store conversation reference for proactive messaging."""
        ref = TurnContext.get_conversation_reference(turn_context.activity)
        key = ref.conversation.id
        self._conversation_references[key] = ref
