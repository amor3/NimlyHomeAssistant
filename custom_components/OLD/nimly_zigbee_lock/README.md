# Nimly Zigbee Door Lock (custom component)

This custom integration adds support for the Safe4/Nimly Zigbee door lock via ZHA.

## Features

- Lock / Unlock using ZHA commands
- Read and display:
  - Lock state
  - Battery voltage & percentage
  - Battery Low status (binary sensor)
  - Diagnostics (RSSI)
- Advanced services:
  - `nimly_zigbee_lock.set_pin_code`
  - `nimly_zigbee_lock.clear_pin_code`
  - `nimly_zigbee_lock.set_rfid_code`
  - `nimly_zigbee_lock.clear_rfid_code`
  - `nimly_zigbee_lock.scan_rfid`
  - `nimly_zigbee_lock.scan_fingerprint`
  - `nimly_zigbee_lock.clear_fingerprint`
  - `nimly_zigbee_lock.local_prog_disable`
  - `nimly_zigbee_lock.local_prog_enable`

## Installation

1. Copy `nimly_zigbee_lock` into `<config_dir>/custom_components/`.
2. Restart Home Assistant.
3. Add the integration in the UI: search “Nimly Zigbee Door Lock” and follow prompts.

## Lovelace Example

```yaml
views:
  - title: Front Door
    cards:
      - type: lock
        entity: lock.nimly_lock_f4ce3604044d31f5
      - type: entities
        entities:
          - sensor.nimly_sensor_battery_percent_remaining_f4ce3604044d31f5
          - sensor.nimly_sensor_battery_voltage_f4ce3604044d31f5
          - binary_sensor.nimly_battery_low_f4ce3604044d31f5
          - sensor.nimly_sensor_diagnostics_data_f4ce3604044d31f5
```