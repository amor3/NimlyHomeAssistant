"""Diagnostic utilities for the Nimly Digital Lock integration."""

import logging
import json
from homeassistant.core import HomeAssistant
from ..const import DOMAIN, LOCK_CLUSTER_ID

_LOGGER = logging.getLogger(__name__)

async def run_connection_diagnostics(hass: HomeAssistant, ieee: str) -> dict:
    """Run comprehensive diagnostics on the ZigBee connection.

    This function attempts to diagnose issues with connecting to the lock device.
    It tries multiple endpoints, formats and services to determine what works.
    """
    results = {
        "ieee_formats": {},
        "endpoints_tested": {},
        "services_available": {},
        "zigbee_networks": {}
    }

    # Test IEEE formats
    ieee_no_colons = ieee.replace(':', '')
    ieee_with_colons = ':'.join([ieee_no_colons[i:i+2] for i in range(0, len(ieee_no_colons), 2)])

    results["ieee_formats"] = {
        "original": ieee,
        "no_colons": ieee_no_colons,
        "with_colons": ieee_with_colons
    }

    # Check available services
    service_domains = ["zigbee", "zha"]
    service_methods = ["issue_zigbee_cluster_command", "get_zigbee_cluster_attribute"]

    for domain in service_domains:
        results["services_available"][domain] = {}
        for method in service_methods:
            service_available = hass.services.has_service(domain, method)
            results["services_available"][domain][method] = service_available

    # Test endpoints
    endpoints_to_test = [1, 11, 242, 2, 3]

    for endpoint in endpoints_to_test:
        results["endpoints_tested"][endpoint] = {"zigbee": False, "zha": False}

        for domain in service_domains:
            if not results["services_available"][domain]["get_zigbee_cluster_attribute"]:
                continue

            try:
                # Try reading a simple attribute to check endpoint responsiveness
                service_data = {
                    "ieee": ieee_with_colons,
                    "endpoint_id": endpoint,
                    "cluster_id": LOCK_CLUSTER_ID,
                    "attribute": 0,  # LockState attribute
                    "manufacturer": None
                }

                _LOGGER.debug(f"Testing endpoint {endpoint} with {domain}")

                # We don't actually care about the result, just if it doesn't error
                await hass.services.async_call(
                    domain,
                    "get_zigbee_cluster_attribute",
                    service_data,
                    blocking=True
                )

                # If we got here, it worked
                results["endpoints_tested"][endpoint][domain] = True
                _LOGGER.info(f"Endpoint {endpoint} responsive with {domain} service")

            except Exception as e:
                _LOGGER.debug(f"Endpoint {endpoint} test failed with {domain}: {e}")

    # Check if ZHA integration is available and get device info
    if "zha" in hass.data:
        zha_gateway = hass.data["zha"].get("gateway")
        if zha_gateway and hasattr(zha_gateway, "devices"):
            results["zigbee_networks"]["zha"] = {
                "device_count": len(zha_gateway.devices),
                "network_up": True
            }

            # Check if our device is in the ZHA device list
            device_found = False
            for dev in zha_gateway.devices.values():
                if hasattr(dev, "ieee") and str(dev.ieee).replace(':', '').lower() == ieee_no_colons.lower():
                    device_found = True
                    results["zigbee_networks"]["zha"]["device_found"] = True
                    results["zigbee_networks"]["zha"]["device_info"] = {
                        "ieee": str(dev.ieee),
                        "nwk": hex(dev.nwk) if hasattr(dev, "nwk") else None,
                        "available": dev.available if hasattr(dev, "available") else None,
                        "endpoints": list(dev.endpoints.keys()) if hasattr(dev, "endpoints") else []
                    }
                    break

            if not device_found:
                results["zigbee_networks"]["zha"]["device_found"] = False

    # Check if Nabu Casa Zigbee integration is available
    if "zigbee" in hass.data:
        results["zigbee_networks"]["nabu_casa"] = {
            "available": True
        }

    # Add the results to hass.data for future reference
    hass.data[f"{DOMAIN}_DIAGNOSTICS_{ieee}"] = results

    return results

async def dump_diagnostics_to_log(hass: HomeAssistant, ieee: str):
    """Run diagnostics and dump results to log file."""
    _LOGGER.info("Starting comprehensive diagnostics for Nimly lock")

    try:
        results = await run_connection_diagnostics(hass, ieee)

        # Log the results in a readable format
        _LOGGER.info("===== NIMLY LOCK DIAGNOSTICS REPORT =====")
        _LOGGER.info(f"IEEE Formats: {json.dumps(results['ieee_formats'], indent=2)}")
        _LOGGER.info(f"Services Available: {json.dumps(results['services_available'], indent=2)}")
        _LOGGER.info(f"Endpoints Tested: {json.dumps(results['endpoints_tested'], indent=2)}")
        _LOGGER.info(f"Zigbee Networks: {json.dumps(results['zigbee_networks'], indent=2)}")
        _LOGGER.info("=======================================")

        # Provide recommendations based on results
        responsive_endpoints = []
        for endpoint, status in results["endpoints_tested"].items():
            if status["zigbee"] or status["zha"]:
                responsive_endpoints.append(endpoint)

        if responsive_endpoints:
            _LOGGER.info(f"RECOMMENDATION: Use the following responsive endpoints: {responsive_endpoints}")

            # Determine which service to use
            if any(status["zigbee"] for _, status in results["endpoints_tested"].items()):
                _LOGGER.info("RECOMMENDATION: Nabu Casa Zigbee service is responsive, use this as primary")
            elif any(status["zha"] for _, status in results["endpoints_tested"].items()):
                _LOGGER.info("RECOMMENDATION: ZHA service is responsive, use this as primary")
        else:
            _LOGGER.error("RECOMMENDATION: No responsive endpoints found. Check device power and ZigBee network")

        return True
    except Exception as e:
        _LOGGER.error(f"Error running diagnostics: {e}")
        return False
