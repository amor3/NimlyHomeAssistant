import logging

from zigpy.types import EUI64
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

LOCK_CLUSTER_ID = 0x0101
POWER_CLUSTER_ID = 0x0001
BATTERY_PERCENT_ATTR = 0x0021

# Read a Zigbee attribute using the ZBT-1 bridge
async def async_read_attribute_zbt1(hass: HomeAssistant, ieee: EUI64, endpoint: int, cluster: int, attribute: int):
    try:
        devices = hass.data["zha"].gateway_proxy.gateway.devices.items()
        _LOGGER.info("[AM] DEVICES IN async_read_attribute_zbt1 %s", devices)

        for dev_id, d in devices:
            _LOGGER.info("[AM] d: %s", d)

            if str(d.ieee).lower() == str(ieee).lower():
                _LOGGER.info("[AM] endpoints items: %s", d.endpoints.items())

                for ep_id, endpoint in d.device.endpoints.items():
                    if ep_id == 0:
                        continue  # Skip ZDO endpoint

                    # Choose the correct cluster based on the attribute
                    if attribute == BATTERY_PERCENT_ATTR and POWER_CLUSTER_ID in endpoint.in_clusters:
                        cluster = endpoint.in_clusters[POWER_CLUSTER_ID]
                        _LOGGER.info(f"[AM] Reading battery from Power cluster on endpoint {ep_id}")
                    elif LOCK_CLUSTER_ID in endpoint.in_clusters:
                        cluster = endpoint.in_clusters[LOCK_CLUSTER_ID]
                        _LOGGER.info(f"[AM] Reading attribute from Door Lock cluster on endpoint {ep_id}")
                    else:
                        continue  # Skip if neither cluster exists

                    _LOGGER.info("[AM] Reading entire cluster: %s", cluster)

                    try:
                        _LOGGER.info("[AM] Going to read attribute: %s", attribute)

                        result = await cluster.read_attributes([attribute])

                        _LOGGER.info("[AM] BEFORE: Reading result read_attributes: %s", result)

                        # Some ZHA versions return a tuple: (data_dict, _)
                        if isinstance(result, tuple):
                            result = result[0]

                        _LOGGER.info("[AM] AFTER: Reading result read_attributes: %s", result)
                        return result.get(attribute)
                    except Exception as e:
                        _LOGGER.warning(f"[AM] Failed reading attribute {attribute:#04x}: {e}")
        # If no matching device or attribute found
        return None

        #zha_device = zha_gateway.device_registry[ieee]
        #cluster_instance = zha_device.endpoints[endpoint].in_clusters[cluster]
        #result = await cluster_instance.read_attributes([attribute])
        #return result.get(attribute)

    except Exception as e:
        _LOGGER.error(f"[ZBT1] Failed to read attribute {attribute:#04x} from cluster {cluster:#04x} on endpoint {endpoint}: {e}")
        return None

# Send a Zigbee cluster command using ZBT-1
async def async_send_command_zbt1(hass: HomeAssistant, ieee: EUI64, endpoint: int, cluster: int, command_id: int, args=None):
    args = args or []
    try:
        zha_gateway = hass.data["zha"]
        zha_device = zha_gateway.device_registry[ieee]
        cluster_instance = zha_device.endpoints[endpoint].in_clusters[cluster]
        result = await cluster_instance.command(command_id, *args)
        return result
    except Exception as e:
        _LOGGER.error(f"[ZBT1] Failed to send command {command_id} to cluster {cluster:#04x} on endpoint {endpoint}: {e}")
        return None

# Discover endpoints for a given device
def get_zbt1_endpoints(hass: HomeAssistant, ieee: EUI64):
    try:
        zha_gateway = hass.data["zha"]
        zha_device = zha_gateway.device_registry[ieee]
        return list(zha_device.endpoints.keys())
    except Exception as e:
        _LOGGER.error(f"[ZBT1] Failed to get endpoints for device {ieee}: {e}")
        return []




async def async_write_attribute_zbt1(
    hass,
    ieee: str,
    endpoint_id: int,
    cluster_id: int,
    attribute_id: int,
    value,
) -> None:
    """Write a Zigbee attribute using Home Assistant's set_zigbee_cluster_attribute."""
    try:
        ieee_colon = ":".join(ieee[i:i+2] for i in range(0, len(ieee), 2))
        service_data = {
            "ieee": ieee_colon,
            "endpoint_id": endpoint_id,
            "cluster_id": cluster_id,
            "attribute": attribute_id,
            "value": value,
            "cluster_type": "in"
        }

        result = await hass.services.async_call(
            "zha", "set_zigbee_cluster_attribute", service_data, blocking=True
        )
        _LOGGER.info(f"[ZBT1] Attribute write result: {result}")
    except Exception as e:
        _LOGGER.error(f"[ZBT1] Failed to write attribute via set_zigbee_cluster_attribute: {e}")
