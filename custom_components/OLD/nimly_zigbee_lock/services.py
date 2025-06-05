import logging
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_SET_PIN,
    SERVICE_CLEAR_PIN,
    SERVICE_SET_RFID,
    SERVICE_CLEAR_RFID,
    SERVICE_SCAN_RFID,
    SERVICE_SCAN_FINGERPRINT,
    SERVICE_CLEAR_FINGERPRINT,
    SERVICE_LOCAL_PROG_DISABLE,
    SERVICE_LOCAL_PROG_ENABLE,
    ATTR_SLOT,
    ATTR_PIN,
    ATTR_RFID,
    ATTR_IEEE,
    COMMAND_SET_PIN,
    COMMAND_CLEAR_PIN,
    COMMAND_SET_RFID,
    COMMAND_CLEAR_RFID,
    COMMAND_SCAN_RFID,
    COMMAND_SCAN_FINGERPRINT,
    COMMAND_CLEAR_FINGERPRINT,
    COMMAND_LOCAL_PROG_DISABLE,
    COMMAND_LOCAL_PROG_ENABLE,
    ENDPOINT_ID,
    LOCK_CLUSTER_ID,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_SCHEMA_SET_PIN = vol.Schema({
    vol.Required(ATTR_IEEE): cv.string,
    vol.Required(ATTR_SLOT): vol.All(int, vol.Range(min=2)),
    vol.Required(ATTR_PIN): cv.string,
})

SERVICE_SCHEMA_CLEAR_PIN = vol.Schema({
    vol.Required(ATTR_IEEE): cv.string,
    vol.Required(ATTR_SLOT): vol.All(int, vol.Range(min=2)),
})

SERVICE_SCHEMA_SET_RFID = vol.Schema({
    vol.Required(ATTR_IEEE): cv.string,
    vol.Required(ATTR_SLOT): vol.All(int, vol.Range(min=2)),
    vol.Required(ATTR_RFID): cv.string,
})

SERVICE_SCHEMA_CLEAR_RFID = vol.Schema({
    vol.Required(ATTR_IEEE): cv.string,
    vol.Required(ATTR_SLOT): vol.All(int, vol.Range(min=2)),
})

SERVICE_SCHEMA_SCAN_RFID = vol.Schema({
    vol.Required(ATTR_IEEE): cv.string,
    vol.Required(ATTR_SLOT): vol.All(int, vol.Range(min=2)),
})

SERVICE_SCHEMA_SCAN_FINGERPRINT = vol.Schema({
    vol.Required(ATTR_IEEE): cv.string,
    vol.Required(ATTR_SLOT): vol.All(int, vol.Range(min=2)),
})

SERVICE_SCHEMA_CLEAR_FINGERPRINT = vol.Schema({
    vol.Required(ATTR_IEEE): cv.string,
    vol.Required(ATTR_SLOT): vol.All(int, vol.Range(min=2)),
})

SERVICE_SCHEMA_LOCAL_PROG = vol.Schema({
    vol.Required(ATTR_IEEE): cv.string,
})

def register_services(hass: HomeAssistant, entry):
    hass.services.register(
        DOMAIN, SERVICE_SET_PIN, _handle_set_pin, schema=SERVICE_SCHEMA_SET_PIN
    )
    hass.services.register(
        DOMAIN, SERVICE_CLEAR_PIN, _handle_clear_pin, schema=SERVICE_SCHEMA_CLEAR_PIN
    )
    hass.services.register(
        DOMAIN, SERVICE_SET_RFID, _handle_set_rfid, schema=SERVICE_SCHEMA_SET_RFID
    )
    hass.services.register(
        DOMAIN, SERVICE_CLEAR_RFID, _handle_clear_rfid, schema=SERVICE_SCHEMA_CLEAR_RFID
    )
    hass.services.register(
        DOMAIN, SERVICE_SCAN_RFID, _handle_scan_rfid, schema=SERVICE_SCHEMA_SCAN_RFID
    )
    hass.services.register(
        DOMAIN, SERVICE_SCAN_FINGERPRINT, _handle_scan_fingerprint, schema=SERVICE_SCHEMA_SCAN_FINGERPRINT
    )
    hass.services.register(
        DOMAIN, SERVICE_CLEAR_FINGERPRINT, _handle_clear_fingerprint, schema=SERVICE_SCHEMA_CLEAR_FINGERPRINT
    )
    hass.services.register(
        DOMAIN, SERVICE_LOCAL_PROG_DISABLE, _handle_local_prog_disable, schema=SERVICE_SCHEMA_LOCAL_PROG
    )
    hass.services.register(
        DOMAIN, SERVICE_LOCAL_PROG_ENABLE, _handle_local_prog_enable, schema=SERVICE_SCHEMA_LOCAL_PROG
    )

async def _handle_set_pin(hass: HomeAssistant, call: ServiceCall):
    ieee = call.data[ATTR_IEEE]
    slot = call.data[ATTR_SLOT]
    pin = call.data[ATTR_PIN]
    user_id = slot
    hex_pin = pin.encode("ascii").hex()
    payload = user_id.to_bytes(2, "little") + bytes([len(pin)]) + bytes.fromhex(hex_pin)
    await hass.services.async_call(
        "zha", "issue_zigbee_cluster_command",
        {
            "ieee": ieee,
            "endpoint_id": ENDPOINT_ID,
            "cluster_id": LOCK_CLUSTER_ID,
            "command": COMMAND_SET_PIN,
            "command_type": "client",
            "args": [payload],
        },
        blocking=True,
    )

async def _handle_clear_pin(hass: HomeAssistant, call: ServiceCall):
    ieee = call.data[ATTR_IEEE]
    slot = call.data[ATTR_SLOT]
    user_id = slot
    payload = user_id.to_bytes(2, "little")
    await hass.services.async_call(
        "zha", "issue_zigbee_cluster_command",
        {
            "ieee": ieee,
            "endpoint_id": ENDPOINT_ID,
            "cluster_id": LOCK_CLUSTER_ID,
            "command": COMMAND_CLEAR_PIN,
            "command_type": "client",
            "args": [payload],
        },
        blocking=True,
    )

async def _handle_set_rfid(hass: HomeAssistant, call: ServiceCall):
    ieee = call.data[ATTR_IEEE]
    slot = call.data[ATTR_SLOT]
    rfid = call.data[ATTR_RFID]
    user_id = slot
    hex_rfid = rfid.encode("ascii").hex()
    payload = user_id.to_bytes(2, "little") + bytes([len(rfid)]) + bytes.fromhex(hex_rfid)
    await hass.services.async_call(
        "zha", "issue_zigbee_cluster_command",
        {
            "ieee": ieee,
            "endpoint_id": ENDPOINT_ID,
            "cluster_id": LOCK_CLUSTER_ID,
            "command": COMMAND_SET_RFID,
            "command_type": "client",
            "args": [payload],
        },
        blocking=True,
    )

async def _handle_clear_rfid(hass: HomeAssistant, call: ServiceCall):
    ieee = call.data[ATTR_IEEE]
    slot = call.data[ATTR_SLOT]
    user_id = slot
    payload = user_id.to_bytes(2, "little")
    await hass.services.async_call(
        "zha", "issue_zigbee_cluster_command",
        {
            "ieee": ieee,
            "endpoint_id": ENDPOINT_ID,
            "cluster_id": LOCK_CLUSTER_ID,
            "command": COMMAND_CLEAR_RFID,
            "command_type": "client",
            "args": [payload],
        },
        blocking=True,
    )

async def _handle_scan_rfid(hass: HomeAssistant, call: ServiceCall):
    ieee = call.data[ATTR_IEEE]
    slot = call.data[ATTR_SLOT]
    payload = slot.to_bytes(2, "little")
    await hass.services.async_call(
        "zha", "issue_zigbee_cluster_command",
        {
            "ieee": ieee,
            "endpoint_id": ENDPOINT_ID,
            "cluster_id": LOCK_CLUSTER_ID,
            "command": COMMAND_SCAN_RFID,
            "command_type": "client",
            "args": [payload],
        },
        blocking=True,
    )

async def _handle_scan_fingerprint(hass: HomeAssistant, call: ServiceCall):
    ieee = call.data[ATTR_IEEE]
    slot = call.data[ATTR_SLOT]
    payload = slot.to_bytes(2, "little")
    await hass.services.async_call(
        "zha", "issue_zigbee_cluster_command",
        {
            "ieee": ieee,
            "endpoint_id": ENDPOINT_ID,
            "cluster_id": LOCK_CLUSTER_ID,
            "command": COMMAND_SCAN_FINGERPRINT,
            "command_type": "client",
            "args": [payload],
        },
        blocking=True,
    )

async def _handle_clear_fingerprint(hass: HomeAssistant, call: ServiceCall):
    ieee = call.data[ATTR_IEEE]
    slot = call.data[ATTR_SLOT]
    payload = slot.to_bytes(2, "little")
    await hass.services.async_call(
        "zha", "issue_zigbee_cluster_command",
        {
            "ieee": ieee,
            "endpoint_id": ENDPOINT_ID,
            "cluster_id": LOCK_CLUSTER_ID,
            "command": COMMAND_CLEAR_FINGERPRINT,
            "command_type": "client",
            "args": [payload],
        },
        blocking=True,
    )

async def _handle_local_prog_disable(hass: HomeAssistant, call: ServiceCall):
    ieee = call.data[ATTR_IEEE]
    await hass.services.async_call(
        "zha", "issue_zigbee_cluster_command",
        {
            "ieee": ieee,
            "endpoint_id": ENDPOINT_ID,
            "cluster_id": LOCK_CLUSTER_ID,
            "command": COMMAND_LOCAL_PROG_DISABLE,
            "command_type": "client",
            "args": [],
        },
        blocking=True,
    )

async def _handle_local_prog_enable(hass: HomeAssistant, call: ServiceCall):
    ieee = call.data[ATTR_IEEE]
    await hass.services.async_call(
        "zha", "issue_zigbee_cluster_command",
        {
            "ieee": ieee,
            "endpoint_id": ENDPOINT_ID,
            "cluster_id": LOCK_CLUSTER_ID,
            "command": COMMAND_LOCAL_PROG_ENABLE,
            "command_type": "client",
            "args": [],
        },
        blocking=True,
    )
