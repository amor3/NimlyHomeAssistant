# Nimly Zigbee Digital Lock Integration

This integration adds support for the Nimly Zigbee door lock module.

## Install

Copy `custom_components/nimly_digital_lock` into your HA config, include blueprints, translations, restart, then add integration via UI.

## Lovelace Example

```yaml
views:
  - title: Front Door
    cards:
      - type: lock
        entity: lock.nimly_<your_ieee>
      - type: entities
        entities:
          - sensor.nimly_battery_<your_ieee>
```
