"""Shared ToolAnnotations so clients can rate tools by risk.

DESTRUCTIVE means: deletes or overwrites data that Grocy cannot restore.
Stock bookings (consume, open, transfer) are logged by Grocy and can be undone, so they are WRITE.
"""

from mcp.types import ToolAnnotations

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True)
