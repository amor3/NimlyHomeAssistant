# Nimly Digital Lock

A Home Assistant integration for Nimly Zigbee digital locks, using the ZHA integration.

## Features

- 🔐 Lock/unlock support via Zigbee Home Automation (ZHA)
- 🔋 Battery percentage and voltage sensors
- 📶 Signal strength (RSSI and dBm) sensors
- 🚪 Lock state and user configuration attributes
- ⚠️ Binary sensor for low battery
- 🧩 Full diagnostics parsed from raw cluster attributes
- 📊 UI-ready with device classes, icons, and long-term stats
- 🛠️ Simple UI config flow — just enter your lock's IEEE address

## Installation

1. Copy this repository to your Home Assistant `custom_components/` folder:
   ```
   custom_components/nimly_digital_lock/
   ```

2. Restart Home Assistant.

3. In the UI, go to:
   **Settings → Devices & Services → Add Integration → Nimly Digital Lock**

## Configuration

When adding the integration, supply:
- IEEE address of your lock (as shown by ZHA)
- A friendly name

No YAML needed.

## Requirements

- Home Assistant 2023.5 or newer
- ZHA integration (using a Zigbee coordinator)

## License

MIT
