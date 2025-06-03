# Nimly Digital Lock Integration for Home Assistant
# Nimly Digital Lock for Home Assistant
# Nimly Digital Lock Integration for Home Assistant

## Overview
This integration provides support for Nimly Digital Lock devices in Home Assistant via ZHA (Zigbee Home Automation).

## Requirements
- Home Assistant with ZHA integration set up
- Nimly Digital Lock (ZBT-1 model)

## ZHA Implementation Details

This integration communicates with the lock using standard ZHA commands with these specifics:

### Door Lock Cluster (0x0101)

| Name | Type | ID | Default | Access | Description |
|------|------|-----|---------|--------|-------------|
| Lock State | U8 enum | 0x0000 | 1 | R | 0 = Unlocked, 1 = Locked |
| Lock Type | U8 enum | 0x0001 | 0 | R | Lock type |
| Actuator Enabled | BOOL | 0x0002 | true | R | Whether actuator is enabled |
| Door State | U8 enum | 0x0003 | 0x04 | R | Door state (always 0x04) |

### Lock/Unlock Commands

| Operation | Command ID | Cluster | Endpoint |
|-----------|------------|---------|----------|
| Lock | 0x00 | 0x0101 | 11 |
| Unlock | 0x01 | 0x0101 | 11 |

### Battery Information

Battery level is read from Power Configuration cluster (0x0001) using attribute 0x0021 (Battery percentage remaining).

## Troubleshooting

If you have issues with lock control:

1. Make sure your lock is properly paired with ZHA
2. Verify the correct IEEE address is being used
3. Check the ZHA logs for any command errors
4. The lock requires endpoint 11 for commands
This integration provides support for Nimly Digital Lock devices, with specific support for Safe4 ZigBee Door Lock Module used with Nabu Casa ZBT-1.

## Safe4 ZigBee Door Lock Module

The integration implements the exact command format required by the Safe4 ZigBee Door Lock specification:

### Lock Command

Command format: `zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 0x00`

- Endpoint must be exactly 11
- Cluster ID must be 0x0101 (Door Lock)
- Profile ID must be 0x0104 (Home Automation)
- Command ID must be 0x00 for lock
- NO parameters can be passed

### Unlock Command

Command format: `zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 0x01`

- Endpoint must be exactly 11
- Cluster ID must be 0x0101 (Door Lock)
- Profile ID must be 0x0104 (Home Automation)
- Command ID must be 0x01 for unlock
- NO parameters can be passed

## Troubleshooting

If you're having issues with the lock, try these steps:

1. Use the `nimly_digital_lock.send_safe4_command` service with:
   - IEEE: your lock's IEEE address (with or without colons)
   - Command: "lock" or "unlock"

2. Check the logs for detailed information about the commands being sent

3. For additional troubleshooting, try the `nimly_digital_lock.try_all_endpoints` service

## Requirements

- Home Assistant with Nabu Casa Zigbee integration
- A supported lock device with proper pairing

This integration specifically targets the Safe4 ZigBee Door Lock Module requirements.
## ZBT-1 Configuration

This integration is specifically designed to work with Nabu Casa ZBT-1 coordinator for controlling Nimly Digital Locks.

### Command Structure

Based on Nordic Semiconductor Zigbee CLI documentation, the following command structure is used:

```
Cluster:    Door Lock: 0x0101
Profile:    Home Automation (0x0104)
Endpoint:   11 (default for ZBT-1)
```

### Debug Commands

If the lock is not responding correctly, you can try manually sending commands using the service:
# Nimly Digital Lock Integration for Home Assistant

## Troubleshooting

If you're experiencing connection issues with your Nimly lock, there are several troubleshooting steps you can take:

### 1. Run the Diagnostics Service

The integration now includes a diagnostic service that can help identify connection problems:

1. Go to **Developer Tools** > **Services**
2. Select the `nimly_digital_lock.run_diagnostics` service
3. For the target entity, select your Nimly lock entity
4. Click **Call Service**
5. Check your Home Assistant logs for detailed diagnostic information

### 2. Common Error: "Failed to send request: device did not respond"

This error typically means:

- The ZigBee network can't reach your lock
- The lock is in power-saving mode or has low batteries
- There's interference in your ZigBee network

**Solutions:**

1. **Check the lock's batteries** - Low batteries are a common cause of connectivity issues
2. **Restart your ZigBee coordinator** - Power cycle your coordinator device
3. **Reduce distance/obstacles** - Try moving your coordinator closer to the lock
4. **Try different endpoints** - Use the `send_direct_command` service with different endpoint values (common ones are 1, 11, and 242)

### 3. Using the Direct Command Service

For advanced troubleshooting, you can bypass the normal lock controls and send commands directly:

1. Go to **Developer Tools** > **Services**
2. Select the `nimly_digital_lock.send_direct_command` service
3. Fill in the parameters:
   - `ieee`: Your lock's IEEE address (from the diagnostics report)
   - `command`: 0 for lock, 1 for unlock
   - `endpoint`: Try different values (11 is default, but 1 or 242 may work better)
   - `retry_count`: Increase for more attempts (default is 3)
4. Click **Call Service**

### 4. ZHA-Specific Troubleshooting

If you're using ZHA (ZigBee Home Automation):

1. Check if the lock is properly paired in ZHA
2. Try removing and re-adding the lock to your ZigBee network
3. Ensure your ZHA coordinator firmware is up to date

### 5. Checking the Logs

Detailed logs are essential for troubleshooting:

1. Enable debug logging by adding to your `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.nimly_digital_lock: debug
```
2. Restart Home Assistant
3. Try operating the lock and check the logs for detailed information
# Nimly Digital Lock Integration for Home Assistant

## Overview

This integration provides support for Nimly Digital Locks with ZigBee connectivity through the Home Assistant ZHA integration. It allows you to control your lock, view battery status, and monitor other diagnostic information.

## Features

- Lock/unlock control
- Battery level monitoring
- PIN code management
- Door state monitoring
- Diagnostics and troubleshooting tools

## Configuration

Add your Nimly lock through the Home Assistant UI by going to:

Configuration → Integrations → Add Integration → Nimly Digital Lock

You'll need to provide the IEEE address of your lock, which can be found in the ZHA device list.

## Using the Integration

After adding your lock, you'll have access to:

- A lock entity for basic control
- Sensor entities for battery level and other attributes
- Services for PIN code management and advanced controls

## Services

The integration provides several services for advanced functionality:

- `nimly_digital_lock.set_pin_code`: Set a PIN code for a specific user
- `nimly_digital_lock.clear_pin_code`: Remove a PIN code
- `nimly_digital_lock.run_diagnostics`: Run diagnostic tests to check lock connectivity
- `nimly_digital_lock.send_direct_command`: Send direct ZigBee commands (advanced users)

## Troubleshooting

If you encounter issues with your lock:

1. Check that your ZigBee coordinator can reach the lock (good signal strength)
2. Run diagnostics using the `nimly_digital_lock.run_diagnostics` service
3. Verify the IEEE address matches your actual device
4. Check your logs for error messages related to the integration

## Support

For help with this integration, please create an issue in the GitHub repository or ask on the Home Assistant community forums.
## Common Working Configurations

Users have reported success with these configurations:

1. **ZHA with Silicon Labs EZSP coordinator**:
   - Endpoint: 11
   - Retry count: 3

2. **Nabu Casa Yellow with ZHA**:
   - Endpoint: 1
   - Retry count: 5

3. **ConBee II with deCONZ**:
   - Use the ZigBee service domain
   - Endpoint: 242
```yaml
service: nimly_digital_lock.send_raw_zigbee_command
data:
  ieee: "00:11:22:33:44:55:66:77"  # Your lock's IEEE address
  command: 1  # 0=lock, 1=unlock
  cluster_id: 257  # 0x0101 Door Lock cluster
  endpoint_id: 11  # Default endpoint for ZBT-1
```

Or try multiple endpoints at once:

```yaml
service: nimly_digital_lock.try_all_endpoints
data:
  ieee: "00:11:22:33:44:55:66:77"  # Your lock's IEEE address
  command: 1  # 0=lock, 1=unlock
  cluster_id: 257  # 0x0101 Door Lock cluster
```

### Troubleshooting

If your lock shows as unlocked in the UI but doesn't physically unlock, check:

1. Make sure you're using the correct IEEE address format
2. Try sending unlock commands to different endpoints (especially endpoint 11)
3. Check the logs for any error messages
4. Verify the lock is within good signal range of your ZBT-1 coordinator
