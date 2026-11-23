"""Edit this composition to change the footer in both clients."""

from core import agent_status, context, identity, limits, lines, row


render = lines(row(identity, context, limits), agent_status)
