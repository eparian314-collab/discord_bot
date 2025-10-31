"""Core utility functions for the Discord bot."""

from .role_utils import (
    get_helper_role_id,
    has_helper_role,
    is_admin_or_helper,
    is_bot_owner,
    is_server_owner,
)
from .channel_utils import (
    get_bot_channel_ids,  # Updated from get_bot_channel_id
    get_sos_channel_id,
    find_bot_channel,
    find_sos_channel,
    get_allowed_channel_ids,
    is_allowed_channel,
)

__all__ = [
    "is_server_owner",
    "is_bot_owner",
    "has_helper_role",
    "is_admin_or_helper",
    "get_helper_role_id",
    "get_bot_channel_ids",  # Updated from get_bot_channel_id
    "get_sos_channel_id",
    "find_bot_channel",
    "find_sos_channel",
    "get_allowed_channel_ids",
    "is_allowed_channel",
]
