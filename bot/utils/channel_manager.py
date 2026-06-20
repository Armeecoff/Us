import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def get_all_clients_info() -> list[dict]:
    """Return list of {client, phone, username, id} for all loaded sessions."""
    from bot.utils.session_manager import _clients
    result = []
    for client in _clients:
        try:
            me = await client.get_me()
            result.append({
                "client": client,
                "phone": me.phone or "",
                "username": me.username or "",
                "id": me.id,
            })
        except Exception as e:
            logger.warning(f"Could not get client info: {e}")
    return result


async def find_client_for_channel(channel_id: int) -> Optional[dict]:
    """Find which loaded session is admin/owner of the channel."""
    from telethon.tl.functions.channels import GetParticipantRequest
    from telethon.tl.types import ChannelParticipantCreator, ChannelParticipantAdmin
    clients_info = await get_all_clients_info()
    for info in clients_info:
        client = info["client"]
        try:
            part = await client(GetParticipantRequest(channel=channel_id, participant="me"))
            p = part.participant
            if isinstance(p, (ChannelParticipantCreator, ChannelParticipantAdmin)):
                return info
        except Exception:
            pass
    return None


async def register_username_on_channel(channel_id: int, new_username: str) -> Optional[dict]:
    """
    Try all clients to set username on a channel.
    Returns {account_phone, account_username, channel_title} on success, None on failure.
    """
    from telethon.tl.functions.channels import UpdateUsernameRequest
    clients_info = await get_all_clients_info()
    for info in clients_info:
        client = info["client"]
        try:
            entity = await client.get_entity(channel_id)
            result = await client(UpdateUsernameRequest(channel=entity, username=new_username))
            if result:
                title = getattr(entity, "title", str(channel_id))
                return {
                    "account_phone": info["phone"],
                    "account_username": info["username"],
                    "channel_title": title,
                    "channel_id": channel_id,
                }
        except Exception as e:
            logger.debug(f"Client @{info['username']} failed to set username: {e}")
    return None


async def register_new_channel_with_username(channel_username: str) -> Optional[dict]:
    """
    Create a new public channel and set the username on it using available accounts.
    Tries each client until one succeeds.
    Returns channel info dict or None.
    """
    from telethon.tl.functions.channels import CreateChannelRequest, UpdateUsernameRequest
    clients_info = await get_all_clients_info()
    for info in clients_info:
        client = info["client"]
        try:
            created = await client(CreateChannelRequest(
                title=channel_username,
                about="",
                megagroup=False,
            ))
            channel = created.chats[0]
            channel_id = channel.id
            try:
                await client(UpdateUsernameRequest(channel=channel, username=channel_username))
                return {
                    "account_phone": info["phone"],
                    "account_username": info["username"],
                    "channel_title": channel.title,
                    "channel_id": channel_id,
                    "channel_username": channel_username,
                }
            except Exception as e:
                logger.warning(f"Channel created but username set failed: {e}")
                return {
                    "account_phone": info["phone"],
                    "account_username": info["username"],
                    "channel_title": channel.title,
                    "channel_id": channel_id,
                    "channel_username": "",
                }
        except Exception as e:
            logger.debug(f"Client @{info['username']} failed to create channel: {e}")
    return None


async def remove_username_from_channel(channel_id: int) -> bool:
    """Remove the public username from a channel (make it private)."""
    from telethon.tl.functions.channels import UpdateUsernameRequest
    info = await find_client_for_channel(channel_id)
    if not info:
        clients_info = await get_all_clients_info()
        if not clients_info:
            return False
        info = clients_info[0]
    client = info["client"]
    try:
        entity = await client.get_entity(channel_id)
        await client(UpdateUsernameRequest(channel=entity, username=""))
        return True
    except Exception as e:
        logger.error(f"remove_username_from_channel error: {e}")
        return False


async def delete_channel(channel_id: int) -> bool:
    """Delete a channel entirely."""
    from telethon.tl.functions.channels import DeleteChannelRequest
    info = await find_client_for_channel(channel_id)
    if not info:
        clients_info = await get_all_clients_info()
        if not clients_info:
            return False
        info = clients_info[0]
    client = info["client"]
    try:
        entity = await client.get_entity(channel_id)
        await client(DeleteChannelRequest(channel=entity))
        return True
    except Exception as e:
        logger.error(f"delete_channel error: {e}")
        return False


async def transfer_channel_ownership(channel_id: int, new_owner_username: str) -> tuple[bool, str]:
    """
    Transfer channel ownership to new_owner_username.
    The bot account must be a member/admin of the channel.
    Returns (success, message).
    """
    from telethon.tl.functions.channels import EditCreatorRequest
    from telethon.tl.types import InputCheckPasswordEmpty
    info = await find_client_for_channel(channel_id)
    if not info:
        clients_info = await get_all_clients_info()
        if not clients_info:
            return False, "Нет доступных сессий"
        info = clients_info[0]
    client = info["client"]
    try:
        entity = await client.get_entity(channel_id)
        new_owner = await client.get_entity(new_owner_username)
        await client(EditCreatorRequest(
            channel=entity,
            user_id=new_owner,
            password=InputCheckPasswordEmpty(),
        ))
        return True, f"@{new_owner_username}"
    except Exception as e:
        err = str(e)
        if "PASSWORD_HASH_INVALID" in err or "PASSWORD_REQUIRED" in err:
            return False, "Аккаунт требует пароль 2FA для передачи канала"
        logger.error(f"transfer_channel_ownership error: {e}")
        return False, str(e)
