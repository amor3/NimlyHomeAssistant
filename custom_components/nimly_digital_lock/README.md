# Nimly Lock Integration for Home Assistant

This custom integration enables Home Assistant to control and monitor **Nimly** Zigbee-based digital locks through the **ZHA (Zigbee Home Automation)** integration.

## Features

- 🔒 Lock and unlock your Nimly device via Home Assistant  
- 🔋 Battery level monitoring  
- 📶 RSSI diagnostics (signal strength)  
- 📊 Attribute reporting for door state, lock status, and access method  
- 🧠 Priority-based Zigbee command queue (lock/unlock overrides background polling)  
- ⚙️ Background polling for diagnostics  
- 🧪 Custom sensors for advanced lock status insights  

## Requirements

To use this integration, you need the following:

### Supported Locks (from Nimly)
- **Nimly Code**
- **Nimly Touch**
- **Nimly Touch Pro**

Each of these locks must be equipped with the **Nimly Zigbee Module**, which is sold separately.

### Zigbee Coordinator (USB Stick)
You also need a compatible Zigbee dongle plugged into your Home Assistant server. This integration is developed and tested with:

- **Nabu Casa ZBT-1** USB Zigbee stick (recommended)

### Software
- Home Assistant (latest version recommended)
- ZHA (Zigbee Home Automation) integration enabled and working

## Installation

### HACS (Recommended)

> **Note:** This integration is not yet in the default HACS store.

1. Go to **HACS → Integrations** → ⋮ → **Custom Repositories**
2. Add this GitHub repository as a custom integration
3. Search for `Nimly Digital Lock` in HACS and install it
4. Restart Home Assistant

### Manual Installation

1. Download this repository as a ZIP and extract it
2. Copy the `nimly_digital_lock` folder into `config/custom_components/`
3. Restart Home Assistant

## Configuration

Once installed:

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for `Nimly Digital Lock`
3. Select your lock from the list (discovered via ZHA)
4. Follow the prompts to complete setup

## Diagnostics

### Attributes Monitored

- **Lock State** (Locked / Unlocked)  
- **Battery Percentage**  
- **Door State** (Open / Closed / Forced Open / Jammed / Error)  
- **Actuator Enabled**  
- **Event Logging** (PIN, RFID, Fingerprint, etc.)  
- **RSSI (Signal Strength)**  

## Developer Notes

- Lock/unlock commands are prioritized by canceling background polling tasks when triggered.
- Real-time attribute updates are handled via ZHA cluster listeners.
- Diagnostic sensors are dynamically registered based on available configuration.

## Known Limitations

- Zigbee stack may timeout under heavy command queuing — ensure signal strength is good.
- Only tested with Nimly ZBT-1 hardware.
- PIN management and access user configuration are not yet supported.

## Maintainer

Developed and maintained by **André @ RCO Security AB**  
Pull requests, feedback, and issues are welcome!
