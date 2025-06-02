# Nimly Digital Lock Troubleshooting Guide

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
