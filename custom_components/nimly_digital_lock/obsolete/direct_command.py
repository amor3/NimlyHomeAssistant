#
# """Direct command implementation for Nimly locks to bypass service layers."""
#
# import logging
# import asyncio
# from custom_components.nimly_digital_lock.zha_mapping import validate_ieee
#
# _LOGGER = logging.getLogger(__name__)
#
# async def send_direct_command(
#     hass, ieee, command, endpoint=11, cluster_id=0x0101, retry_count=5,
#     retry_delay=1.0, profile=0x0104
# ):
#     """Send a direct command to the lock using ZHA."""
#     _LOGGER.info(f"Sending direct command {command} to endpoint {endpoint}")
#
#     try:
#         is_valid, ieee_formatted, error_message = validate_ieee(ieee)
#         if not is_valid:
#             _LOGGER.error(f"Invalid IEEE address: {error_message}")
#             return False
#         ieee = ieee_formatted
#     except Exception as e:
#         _LOGGER.error(f"Error validating IEEE address: {str(e)}")
#         _LOGGER.warning(f"Using original IEEE address as fallback: {ieee}")
#
#     if "NIMLY_LAST_COMMAND" not in hass.data:
#         hass.data["NIMLY_LAST_COMMAND"] = []
#     hass.data["NIMLY_LAST_COMMAND"].append({
#         "ieee": ieee,
#         "command": command,
#         "endpoint": endpoint,
#         "cluster_id": cluster_id,
#         "timestamp": hass.loop.time()
#     })
#
#     for attempt in range(retry_count):
#         try:
#             service_data = {
#                 "ieee": ieee,
#                 "endpoint_id": endpoint,
#                 "cluster_id": cluster_id,
#                 "command": command,
#                 "command_type": "server",
#                 "params": []  # Ensure empty param list is sent
#             }
#
#             _LOGGER.debug(f"Attempt {attempt+1}: Calling zha.command with {service_data}")
#             await hass.services.async_call("zha", "command", service_data)
#
#             _LOGGER.info(f"Command {command} sent successfully on attempt {attempt+1}")
#             return True
#         except Exception as e:
#             _LOGGER.warning(f"Attempt {attempt+1} failed to send command {command}: {e}")
#             await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
#
#     _LOGGER.error(f"Failed to send direct command {command} after {retry_count} attempts")
#     return False
