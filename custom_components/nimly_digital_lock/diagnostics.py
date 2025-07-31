import logging
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, COMMON_ENDPOINTS

_LOGGER = logging.getLogger(__name__)

TO_REDACT = {"ieee", "unique_id", "identifiers"}

async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry):
    """Return diagnostics for a config entry."""
    ieee = entry.data["ieee"]
    ieee_no_colons = ieee.replace(':', '')
    ieee_with_colons = ':'.join([ieee_no_colons[i:i+2] for i in range(0, len(ieee_no_colons), 2)])

    device_data = {}
    for key in hass.data:
        if key.startswith(f"{DOMAIN}:{ieee}:"):
            device_data[key.replace(f"{DOMAIN}:{ieee}:", "")] = hass.data[key]

    available_services = {}
    service_domains = ["zigbee", "zha"]
    service_methods = [
        "issue_zigbee_cluster_command", 
        "get_zigbee_cluster_attribute",
        "read_zigbee_cluster_attribute"
    ]

    for domain in service_domains:
        available_services[domain] = {}
        for method in service_methods:
            available_services[domain][method] = hass.services.has_service(domain, method)

    # Get all data with domain prefix
    domain_data = {}
    for key in hass.data:
        if key.startswith(f"{DOMAIN}_"):
            # Redact any sensitive information
            if "IEEE" in key or "ZHA_DEVICE" in key:
                domain_data[key] = "REDACTED"
            else:
                domain_data[key] = hass.data[key]

    # Test communication with lock on different endpoints
    endpoint_test = {}
    for endpoint in COMMON_ENDPOINTS:
        try:
            # Try to send a simple read command to the endpoint
            service_data = {
                "ieee": ieee_with_colons,
                "endpoint_id": endpoint,
                "cluster_id": 0x0101,  # Lock cluster
                "attribute": 0x0000,   # Lock state attribute
                "manufacturer": None
            }

            # Try with both service domains
            for domain in service_domains:
                for method in ["get_zigbee_cluster_attribute", "read_zigbee_cluster_attribute"]:
                    if hass.services.has_service(domain, method):
                        try:
                            endpoint_test[f"{endpoint}_{domain}_{method}"] = "Testing..."
                            await hass.services.async_call(
                                domain, method, service_data, blocking=True
                            )
                            endpoint_test[f"{endpoint}_{domain}_{method}"] = "Success"
                        except Exception as e:
                            endpoint_test[f"{endpoint}_{domain}_{method}"] = f"Failed: {str(e)}"
        except Exception as e:
            endpoint_test[f"endpoint_{endpoint}"] = f"Error: {str(e)}"

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "ieee_formats": {
            "original": "REDACTED",
            "no_colons": "REDACTED",
            "with_colons": "REDACTED"
        },
        "device_data": device_data,
        "domain_data": domain_data,
        "available_services": available_services,
        "endpoint_test": endpoint_test
    }
