# Nordic ZBT-1 Safe4 Digital Lock Troubleshooting Guide
# Nimly Digital Lock Troubleshooting Guide
# Troubleshooting Nimly Digital Lock Integration

## Common Issues

### "Failed to read attribute X from endpoint 11: Action zha.get_zigbee_cluster_attribute not found"

This error occurs when the integration tries to read attributes from the ZigBee device but the ZHA service isn't correctly matched to your installation.

**Solution:**

1. The integration now automatically tries multiple service methods and endpoints to find one that works
2. If you're still seeing this error, check that your ZHA integration is properly configured
3. You can also try using the direct Safe4 commands from Developer Tools > Services:

```yaml
service: nimly_digital_lock.send_safe4_command
data:
  ieee: "your_device_ieee_address"
  command: "lock"  # or "unlock"
```

### Device Not Found

If your Nimly lock device can't be found by the integration:

1. Make sure the IEEE address you provided is correct
2. Check that the ZHA integration properly recognizes your device
3. Try removing and re-adding the ZHA device before setting up this integration

### Battery or Lock State Not Updating

If the battery level or lock state doesn't update:

1. Check your logs for any error messages
2. Try manually sending a command to refresh the state
3. Ensure the device is within range of your ZigBee network

## Advanced Troubleshooting

You can run diagnostics on your lock by using the service:

```yaml
service: nimly_digital_lock.run_diagnostics
data:
  entity_id: "lock.nimly_digital_lock_your_device_id"
```

This will output detailed information to your logs that can help identify issues.

## ZigBee Network Issues

If you're experiencing connectivity problems:

1. Check the signal strength sensor provided by this integration
2. Consider adding ZigBee repeaters to improve network coverage
3. Make sure your ZigBee coordinator is not experiencing interference from other wireless devices

## Reporting Issues

When reporting issues, please include:

1. Your Home Assistant version
2. The version of this integration
3. Any relevant error messages from the logs
4. The model of your Nimly lock device
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
# Nimly Digital Lock Troubleshooting Guide

## Nordic ZBT-1 Door Lock Issues

If you're experiencing issues with your Nimly lock that uses the Nordic ZBT-1 implementation, follow these steps:

### 1. Verify Lock Requirements

The Nordic ZBT-1 Door Lock module requires EXACT command format:

```
zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>
```

Where:
- Endpoint MUST be exactly 11
- Cluster ID must be exactly 0x0101 (Door Lock cluster)
- Profile ID must be exactly 0x0104 (Home Automation)
- Command ID must be exactly 0x00 for lock, 0x01 for unlock
- NO parameters can be passed

### 2. Check Your Zigbee Services

Verify which Zigbee services you have available:

1. Go to Developer Tools > Services
2. Look for either:
   - `zigbee.issue_zigbee_cluster_command` (Nabu Casa Yellow)
   - `zha.issue_zigbee_cluster_command` (ZHA integration)

### 3. Try The Direct Command Service

This integration provides a direct command service that bypasses the normal Home Assistant flow:

```yaml
service: nimly_digital_lock.send_direct_command
data:
  ieee: "00:11:22:33:44:55:66:77"  # Your lock's IEEE address
  command: 1  # 0=lock, 1=unlock
  endpoint: 11  # MUST be 11 for Nordic ZBT-1
  retry_count: 5
```

### 4. Try All Methods At Once

If you're still having trouble, the integration provides a service that tries all possible methods:

```yaml
service: nimly_digital_lock.try_all_methods
data:
  ieee: "00:11:22:33:44:55:66:77"  # Your lock's IEEE address
  command: 1  # 0=lock, 1=unlock
```

### 5. Common Issues and Solutions

#### "Failed to send request: device did not respond"

This usually means:
- Your lock is out of range or has network connectivity issues
- The batteries are low in your lock
- The wrong endpoint is being used (must be 11 for Nordic ZBT-1)

Solutions:
1. Replace the batteries in your lock
2. Move your Zigbee coordinator closer to the lock
3. Use the `send_direct_command` service with endpoint 11
4. Restart your Zigbee coordinator and try again

#### "Cannot connect to coordinator"

This indicates an issue with your Zigbee network rather than the lock itself.

Solutions:
1. Restart your Zigbee coordinator
2. Restart Home Assistant
3. Check if your coordinator's firmware is up to date

### 6. Still Having Issues?

If you're still experiencing problems after trying all of the above:

1. Run the diagnostics service and check your Home Assistant logs
2. Run the following commands in Developer Tools > Services:

```yaml
service: nimly_digital_lock.run_diagnostics
target:
  entity_id: lock.nimly_front_door
```

3. Look for error messages in your Home Assistant logs with "nimly" in them
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
