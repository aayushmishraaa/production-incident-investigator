"""Structured agent-to-agent message bus backed by the shared investigation state."""
from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

from app.models.agent import AgentMessage, AgentName, MessageType
from app.models.investigation import InvestigationState

logger = logging.getLogger("bus")


class MessageBus:
    def __init__(self, state: InvestigationState):
        self.state = state

    def send(self, sender: AgentName, recipient: AgentName, message_type: MessageType, payload: dict[str, Any],
             in_reply_to: Optional[str] = None) -> AgentMessage:
        msg = AgentMessage(investigation_id=self.state.investigation_id, sender=sender, recipient=recipient,
                           message_type=message_type, payload=payload, in_reply_to=in_reply_to)
        self.state.messages.append(msg)
        self.state.log(sender.value, f"message:{message_type.value}", to=recipient.value, message_id=msg.message_id)
        logger.debug("%s -> %s %s", sender.value, recipient.value, message_type.value)
        return msg

    def inbox(self, recipient: AgentName, types: Optional[Iterable[MessageType]] = None,
              include_consumed: bool = False, consume: bool = True) -> list[AgentMessage]:
        wanted = set(types) if types else None
        out = []
        for m in self.state.messages:
            if m.recipient != recipient or (wanted and m.message_type not in wanted):
                continue
            if m.status == "consumed" and not include_consumed:
                continue
            out.append(m)
            if consume:
                m.status = "consumed"
        return out

    def latest(self, recipient: AgentName, message_type: MessageType) -> Optional[AgentMessage]:
        msgs = [m for m in self.state.messages if m.recipient == recipient and m.message_type == message_type]
        return msgs[-1] if msgs else None
