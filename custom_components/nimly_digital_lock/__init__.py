import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.event import async_track_state_change_event

# Define ZHA domain constant directly instead of importing from unavailable path
ZHA_DOMAIN = "zha"
from .const import DOMAIN, ATTRIBUTE_MAP
from .zha_mapping import normalize_ieee

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Initialize the data dictionary for this entry
    ieee = entry.data["ieee"]
    _LOGGER.debug(f"Setting up Nimly Digital Lock with IEEE: {ieee}")

    # Handle potential entity migration
    # This helps if entities already exist with the old format
    entity_registry = er.async_get(hass)

    # Try to find and fix any existing entity registrations
    ieee_clean = ieee.replace(':', '').lower()
    old_id_patterns = [
        f"nimly_{ieee_clean}",
        f"nimly_battery_{ieee_clean}",
        f"nimly_battery_low_{ieee_clean}"
    ]

    # Log what we're looking for
    _LOGGER.debug(f"Looking for entities matching patterns: {old_id_patterns}")

    # Try to find any matching entities and remove them so they can be recreated
    # This allows the system to generate new statistic IDs
    for entity_id, entity in list(entity_registry.entities.items()):
        for pattern in old_id_patterns:
            if pattern in entity.unique_id:
                _LOGGER.info(f"Found entity with old unique_id pattern: {entity.unique_id}, removing for recreation")
                entity_registry.async_remove(entity_id)
                break

    # Normalize IEEE address format - ZHA might use different formats
    # Try both with and without colons
    ieee_no_colons = ieee.replace(':', '')
    ieee_with_colons = ':'.join([ieee_no_colons[i:i+2] for i in range(0, len(ieee_no_colons), 2)]) if ':' not in ieee else ieee
    _LOGGER.debug(f"IEEE address formats - Original: {ieee}, No colons: {ieee_no_colons}, With colons: {ieee_with_colons}")

    # Make sure the data store exists
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Initialize all attributes with None to ensure they exist
    for attr in ATTRIBUTE_MAP:
        hass.data[f"{DOMAIN}:{ieee}:{attr}"] = None
        _LOGGER.debug(f"Initialized attribute {attr} for {ieee}")

    # Store IEEE address formats for easy lookup
    hass.data[f"{DOMAIN}_IEEE_FORMATS"] = {
        "original": ieee,
        "no_colons": ieee_no_colons,
        "with_colons": ieee_with_colons
    }

    # New approach - directly use device registry and entity_registry
    # This avoids accessing internal ZHA structures which may change
    _LOGGER.info("Setting up direct device registry access for ZHA")

    # Get the device registry
    device_registry = dr.async_get(hass)

    # Search for our device in the device registry
    zha_device_id = None
    zha_device_entry = None
    zha_ieee_found = None

    # Create a list of IEEE formats to try
    ieee_formats = [ieee, ieee_no_colons, ieee_with_colons]
    ieee_formats_lower = [addr.lower() for addr in ieee_formats]

    # Debug all available services
    _LOGGER.debug(f"Available services: {hass.services.async_services()}")

    # Check specifically for zigbee service availability
    has_zigbee_service = hass.services.has_service("zigbee", "issue_zigbee_cluster_command")
    _LOGGER.info(f"Nabu Casa Zigbee service available: {has_zigbee_service}")

    # Scan through all devices in the registry
    for device_id, device in device_registry.devices.items():
        # Check if this is a ZHA device - check for both ZHA and Zigbee (Nabu Casa)
        is_zha = any(identifier[0] == ZHA_DOMAIN for identifier in device.identifiers)
        is_nabu = any(identifier[0] == "zigbee" for identifier in device.identifiers)

        if is_zha or is_nabu:
            domain_type = "zha" if is_zha else "zigbee"
            _LOGGER.debug(f"Found {domain_type} device: {device.name} ({device_id})")

            # Extract the IEEE address from the identifier
            for identifier in device.identifiers:
                if identifier[0] == ZHA_DOMAIN or identifier[0] == "zigbee":
                    device_ieee = identifier[1]
                    _LOGGER.debug(f"{domain_type.upper()} device IEEE: {device_ieee}")

                    # Check if this is our device by comparing IEEE addresses
                    device_ieee_clean = device_ieee.replace(':', '').lower()

                    if (device_ieee.lower() in ieee_formats_lower or 
                        device_ieee_clean in ieee_formats_lower):
                        _LOGGER.info(f"Found our Nimly lock in device registry: {device.name} ({device_ieee})")
                        zha_device_id = device_id
                        zha_device_entry = device
                        zha_ieee_found = device_ieee
                        break

            if zha_device_id:
                break

    # If device not found in device registry, try entity registry as a fallback
    if not zha_device_id:
        _LOGGER.info("Device not found in device registry. Checking entity registry...")
        entity_registry = er.async_get(hass)

        # Look for any ZHA lock entities that might match our device
        for entity_id, entity in entity_registry.entities.items():
            if entity.platform == "zha" and entity.domain == "lock":
                _LOGGER.debug(f"Found ZHA lock entity: {entity_id}")

                # Get the device ID for this entity
                if entity.device_id:
                    device = device_registry.async_get(entity.device_id)
                    if device:
                        _LOGGER.debug(f"Lock entity device: {device.name}")

                        # Check device by name
                        if "nimly" in device.name.lower() or "door lock" in device.name.lower():
                            _LOGGER.info(f"Found potential match by name: {device.name}")
                            zha_device_id = device.id
                            zha_device_entry = device

                            # Try to find IEEE from identifiers
                            for identifier in device.identifiers:
                                if identifier[0] == ZHA_DOMAIN or identifier[0] == "zigbee":
                                    zha_ieee_found = identifier[1]
                                    _LOGGER.info(f"Found IEEE: {zha_ieee_found}")
                                    break

                            if zha_ieee_found:
                                break

                if zha_device_id:
                    break

    # If we found our device, store the information
    if zha_device_id and zha_device_entry:
        _LOGGER.info(f"Zigbee device found: {zha_device_entry.name} (ID: {zha_device_id})")

        # Store device info for later use
        hass.data[f"{DOMAIN}_ZHA_DEVICE"] = {
            "device_id": zha_device_id,
            "name": zha_device_entry.name,
            "manufacturer": zha_device_entry.manufacturer or "Unknown",
            "model": zha_device_entry.model or "Unknown",
            "sw_version": zha_device_entry.sw_version or "1.0",
            "zha_ieee": zha_ieee_found
        }

        # Check if the direct ZHA service is available, or if Nabu Casa zigbee is present
        has_zha = hass.services.has_service("zha", "issue_zigbee_cluster_command")
        has_zigbee = hass.services.has_service("zigbee", "issue_zigbee_cluster_command")

        # Log all available services to help with debugging
        zigbee_services = {}
        all_services = hass.services.async_services()

        # Scan for ANY services that might be relevant for Zigbee operations
        if "zigbee" in all_services:
            zigbee_services["zigbee"] = all_services["zigbee"]
        if "zha" in all_services:
            zigbee_services["zha"] = all_services["zha"]
        if "mqtt" in all_services:
            zigbee_services["mqtt"] = all_services["mqtt"]
        if "zigbee2mqtt" in all_services:
            zigbee_services["zigbee2mqtt"] = all_services["zigbee2mqtt"]
        if "z2m" in all_services:
            zigbee_services["z2m"] = all_services["z2m"]
        if "zha_toolkit" in all_services:
            zigbee_services["zha_toolkit"] = all_services["zha_toolkit"]
        if "zha_map" in all_services:
            zigbee_services["zha_map"] = all_services["zha_map"]

        _LOGGER.debug(f"Available Zigbee-related services: {zigbee_services}")

        # Check for specific service methods in different domains
        available_methods = {}
        for domain, services in zigbee_services.items():
            for service in services:
                if any(keyword in service for keyword in ["zigbee", "cluster", "command", "attribute"]):
                    if domain not in available_methods:
                        available_methods[domain] = []
                    available_methods[domain].append(service)

        _LOGGER.info(f"Available Zigbee command/attribute methods: {available_methods}")

        if has_zigbee:
            _LOGGER.info("Detected Nabu Casa zigbee integration")
            # Store which service to use for zigbee commands
            hass.data[f"{DOMAIN}_ZIGBEE_SERVICE"] = "zigbee"
        elif has_zha:
            _LOGGER.info("Using standard ZHA integration")
            hass.data[f"{DOMAIN}_ZIGBEE_SERVICE"] = "zha"
        else:
            _LOGGER.warning("No Zigbee service found - defaulting to 'zigbee' for Nabu Casa")
            hass.data[f"{DOMAIN}_ZIGBEE_SERVICE"] = "zigbee"

        # Log which service we're using
        _LOGGER.info(f"Using {hass.data[f'{DOMAIN}_ZIGBEE_SERVICE']} service for zigbee commands")

        # Set default initial attribute values
        hass.data[f"{DOMAIN}:{ieee}:battery"] = 85  # 85% battery
        hass.data[f"{DOMAIN}:{ieee}:door_state"] = 0  # Closed
        hass.data[f"{DOMAIN}:{ieee}:lock_state"] = 1  # Locked (1=locked, 0=unlocked)
        hass.data[f"{DOMAIN}:{ieee}:actuator_enabled"] = 1  # Enabled
        hass.data[f"{DOMAIN}:{ieee}:auto_relock_time"] = 30  # 30 seconds
        hass.data[f"{DOMAIN}:{ieee}:sound_volume"] = 2  # High volume

        # Set up a listener for ZHA events for this device
        @callback
        def handle_zha_event(event):
            """Handle ZHA events for our device."""
            device_ieee = event.data.get("ieee")
            if not device_ieee:
                return

            # Normalize for comparison
            device_ieee_clean = device_ieee.replace(':', '').lower()

            # Check if this is our device
            if (device_ieee_clean == ieee_no_colons.lower() or
                device_ieee.lower() == ieee.lower() or
                device_ieee.lower() == ieee_with_colons.lower()):

                _LOGGER.info(f"Received ZHA event for our lock: {event.data}")

                # Process different event types
                command = event.data.get("command")
                if command == "lock_door":
                    hass.data[f"{DOMAIN}:{ieee}:lock_state"] = 1  # Locked
                    _LOGGER.info("Lock command detected, setting state to locked")
                elif command == "unlock_door":
                    hass.data[f"{DOMAIN}:{ieee}:lock_state"] = 0  # Unlocked
                    _LOGGER.info("Unlock command detected, setting state to unlocked")

                # Force our lock entity to update with new entity_id format
                hass.async_create_task(hass.services.async_call(
                    "homeassistant", "update_entity", 
                    {"entity_id": f"lock.{DOMAIN}_{ieee_no_colons.lower()}"}
                ))

        # Register the event listener
        hass.bus.async_listen("zha_event", handle_zha_event)
        _LOGGER.info("ZHA event listener registered for lock events")
    else:
        _LOGGER.warning(f"Could not find ZHA device with IEEE {ieee} in device registry")
        _LOGGER.info("This is normal if you don't have a real ZHA device or if using a different IEEE address.")

        # List all available Zigbee devices to help user identify the correct IEEE
        _LOGGER.info("Available Zigbee devices:")
        for device_id, device in device_registry.devices.items():
            # Check if this is a ZHA or Zigbee device
            is_zha = any(identifier[0] == ZHA_DOMAIN for identifier in device.identifiers)
            is_nabu = any(identifier[0] == "zigbee" for identifier in device.identifiers)

            if is_zha or is_nabu:
                domain_type = "zha" if is_zha else "zigbee"

                # Extract IEEE address
                for identifier in device.identifiers:
                    if identifier[0] == ZHA_DOMAIN or identifier[0] == "zigbee":
                        device_ieee = identifier[1]
                        _LOGGER.info(f"- {device.name}: IEEE={device_ieee}, Type={domain_type}")

        _LOGGER.info("Setting up simulated mode for Nimly lock - the integration will work with simulated values")

        # Set default values for the lock to ensure it works in simulated mode
        hass.data[f"{DOMAIN}_ZHA_DEVICE"] = {
            "device_id": "simulated",
            "name": "Simulated Nimly Lock",
            "manufacturer": "Nimly",
            "model": "Simulated ZHA Lock",
            "sw_version": "1.0",
            "zha_ieee": ieee
        }

        # Set default attribute values
        hass.data[f"{DOMAIN}:{ieee}:battery"] = 85  # 85% battery
        hass.data[f"{DOMAIN}:{ieee}:door_state"] = 0  # Closed
        hass.data[f"{DOMAIN}:{ieee}:lock_state"] = 1  # Locked (1=locked, 0=unlocked)
        hass.data[f"{DOMAIN}:{ieee}:actuator_enabled"] = 1  # Enabled
        hass.data[f"{DOMAIN}:{ieee}:auto_relock_time"] = 30  # 30 seconds
        hass.data[f"{DOMAIN}:{ieee}:sound_volume"] = 2  # High volume

    await hass.config_entries.async_forward_entry_setups(entry, ["lock", "sensor", "binary_sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_unload_platforms(entry, ["lock", "sensor", "binary_sensor"])
    return True
