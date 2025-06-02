# Nordic ZBT-1 Safe4 Digital Lock Troubleshooting Guide
# Nimly Digital Lock Troubleshooting Guide

## Common Issues

### Coroutine Errors

If you see errors like:

```
RuntimeWarning: coroutine 'get_zbt1_endpoints' was never awaited
```

or

```
Error reading attributes from device: 'coroutine' object is not iterable
```

Try restarting Home Assistant after installation, as this will ensure all components are properly initialized.

### Connection Issues

If your lock is not responding:

1. Verify that your lock is within good range of your ZigBee coordinator
2. Check the battery level of your lock
3. Try using the diagnostics service to run tests:

```yaml
service: nimly_digital_lock.run_diagnostics
data:
  entity_id: lock.nimly_digital_lock_YOUR_IEEE
```

### Manual Command Testing

You can test direct commands to the lock using the following service:

```yaml
service: nimly_digital_lock.send_direct_command
data:
  ieee: "YOUR_IEEE_ADDRESS"  # e.g., "f4:ce:36:0a:04:4d:31:f5"
  command: 0  # 0 for lock, 1 for unlock
  endpoint: 11
```

### Logs

Enable debug logging by adding to configuration.yaml:

```yaml
logger:
  default: warning
  logs:
    custom_components.nimly_digital_lock: debug
```

## Device Information

The integration uses endpoint 11 as the primary endpoint for Nordic ZBT-1 devices per the Safe4 specification. If you have issues, the integration will try multiple endpoints (11, 1, 2, 3, 242) to find which one works with your device.

## Support

If you continue to have issues, please collect your Home Assistant logs with debug enabled and report them to the project maintainers.
## Finding Your Lock's ZigBee Address

When adding a new lock, the integration now provides a dropdown list of all ZigBee devices discovered in your Home Assistant system, with Nordic ZBT-1 devices prioritized at the top. This makes it easier to identify your lock without having to manually find the IEEE address.

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for and select **Nimly Digital Lock**
3. Select your lock from the dropdown of available ZigBee devices
4. If your lock doesn't appear in the list, you can still enter its IEEE address manually

<details>
<summary><b>Where to find the IEEE address manually</b></summary>

If your lock doesn't appear in the dropdown, you can find its IEEE address by:

1. Go to **Settings** > **Devices & Services**
2. Find your ZigBee integration (ZHA or Zigbee)
3. Click on **Devices**
4. Look for your lock in the device list
5. The IEEE address will be shown in the device details or as part of the device identifier

Alternatively, check your ZigBee coordinator's web interface or logs for the list of paired devices.
</details>

## Nordic Semiconductor ZBT-1 Command Format

The Nimly digital lock uses the Nordic Semiconductor ZBT-1 module, which requires a specific command format to communicate properly. If you're experiencing issues with your lock, this guide will help you troubleshoot.

## Common Error: "Failed to send request: device did not respond"

This error typically means one of the following:

1. The ZigBee network can't reach your lock
2. The lock is in power-saving mode or has low batteries
3. The command format is incorrect

## Using the Nordic ZBT-1 Command Service

The integration now provides a service specifically for sending commands in the correct Nordic ZBT-1 format:

1. Go to **Developer Tools** > **Services**
2. Select the `nimly_digital_lock.send_nordic_command` service
3. Enter your lock's IEEE address and the command ID:
   - `0x00` (0) = Lock
   - `0x01` (1) = Unlock

```yaml
service: nimly_digital_lock.send_nordic_command
data:
  ieee: "f4:ce:36:0a:04:4d:31:f5"  # Your lock's IEEE address
  command_id: 0  # 0 for lock, 1 for unlock
```

## Nordic ZBT-1 Command Requirements

The Nordic documentation specifies the following format for ZBT-1 locks:

```
zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>
```

Critical requirements:
- Endpoint **MUST** be exactly 11
- Door Lock cluster ID is 0x0101
- Profile ID must be 0x0104 (Home Automation)
- Lock command ID is 0x00
- Unlock command ID is 0x01
- The command must NOT have any parameters

## Setting PIN Codes

You can set PIN codes using the service:

```yaml
service: nimly_digital_lock.set_pin_code
data:
  ieee: "f4:ce:36:0a:04:4d:31:f5"  # Your lock's IEEE address
  user_id: 3  # Slot number (2 or higher)
  pin_code: "123456"  # The PIN code to set
```

## Clearing PIN Codes

```yaml
service: nimly_digital_lock.clear_pin_code
data:
  ieee: "f4:ce:36:0a:04:4d:31:f5"  # Your lock's IEEE address
  user_id: 3  # Slot number to clear
```

## Additional Troubleshooting Steps

1. **Check the lock's batteries** - Low batteries are a common cause of connectivity issues

2. **Run the diagnostics service** to check connectivity:
   ```yaml
   service: nimly_digital_lock.run_diagnostics
   target:
     entity_id: lock.nimly_front_door
   ```

3. **Restart your ZigBee coordinator** - Power cycle your coordinator device

4. **Check Home Assistant logs** - Look for detailed error messages

5. **Try a different ZigBee coordinator** - Some locks work better with certain coordinators

## ZigBee Network Optimization

For best results with Nordic ZBT-1 devices:

1. Minimize distance between the lock and ZigBee coordinator
2. Add ZigBee repeaters/routers to strengthen the network
3. Keep the ZigBee network on a channel with minimal WiFi interference
4. Ensure your coordinator has the latest firmware
