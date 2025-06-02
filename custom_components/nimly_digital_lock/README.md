# Nimly Digital Lock Integration for Home Assistant

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
