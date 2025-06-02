"""Polling service for Nimly Digital Lock.

This module implements a dedicated polling service that regularly fetches
data from the ZHA device to update the lock and sensor states.
"""

import logging
import asyncio
from datetime import datetime
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOCK_CLUSTER_ID, POWER_CLUSTER_ID
from .safe4_lock import read_safe4_attribute, SAFE4_DOOR_LOCK_CLUSTER, SAFE4_POWER_CLUSTER
from .zbt1_support import async_read_attribute_zbt1

_LOGGER = logging.getLogger(__name__)

async def start_polling_service(hass: HomeAssistant, ieee: str, poll_interval: int = 30):
    """Start a polling service to update lock data periodically.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the lock
        poll_interval: Polling interval in seconds (default: 30)
    """

    _LOGGER.info(f"Starting polling service for lock with IEEE {ieee}, interval: {poll_interval}s")

    # Format the IEEE addresses
    ieee_no_colons = ieee.replace(':', '').lower()
    ieee_with_colons = ':'.join([ieee_no_colons[i:i+2] for i in range(0, len(ieee_no_colons), 2)]) if ':' not in ieee else ieee

    # Known ZHA device IEEE as fallback
    zha_ieee = "f4:ce:36:0a:04:4d:31:f5"

    # Store the initial polling timestamp
    hass.data[f"{DOMAIN}:{ieee}:last_poll"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    while True:
        try:
            _LOGGER.debug(f"Polling lock with IEEE {ieee}")

            # Try to read lock state
            try:
                # Try first with ZHA device IEEE
                result = await read_safe4_attribute(
                    hass,
                    zha_ieee,
                    SAFE4_DOOR_LOCK_CLUSTER,
                    0x0000  # Lock state attribute
                )

                if not result:
                    # Fallback to the user-provided IEEE
                    result = await read_safe4_attribute(
                        hass,
                        ieee_with_colons,
                        SAFE4_DOOR_LOCK_CLUSTER,
                        0x0000  # Lock state attribute
                    )

                # Try to read battery level
                battery_result = await read_safe4_attribute(
                    hass,
                    zha_ieee,
                    SAFE4_POWER_CLUSTER,
                    0x0021  # Battery percentage remaining
                )

                # Read door state
                door_state_result = await read_safe4_attribute(
                    hass,
                    zha_ieee,
                    SAFE4_DOOR_LOCK_CLUSTER,
                    0x0003  # Door state attribute
                )

                # Update last poll timestamp
                hass.data[f"{DOMAIN}:{ieee}:last_poll"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Force update of all entities
                entity_ids = [
                    f"lock.{DOMAIN}_{ieee_no_colons}",
                    f"sensor.{DOMAIN}_{ieee_no_colons}_battery",
                    f"binary_sensor.{DOMAIN}_{ieee_no_colons}_battery_low"
                ]

                for entity_id in entity_ids:
                    try:
                        await hass.services.async_call(
                            "homeassistant", "update_entity", {"entity_id": entity_id}
                        )
                        _LOGGER.debug(f"Updated entity {entity_id}")
                    except Exception as e:
                        _LOGGER.debug(f"Error updating entity {entity_id}: {e}")

            except Exception as e:
                _LOGGER.warning(f"Error reading attributes during polling: {e}")

        except Exception as e:
            _LOGGER.error(f"Error in polling service: {e}")

        # Wait for the next poll interval
        await asyncio.sleep(poll_interval)
