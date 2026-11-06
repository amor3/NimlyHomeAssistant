# Nimly Digital Lock for Home Assistant

[![Validate](https://github.com/amor3/NimlyHomeAssistant/actions/workflows/validate.yml/badge.svg)](https://github.com/amor3/NimlyHomeAssistant/actions/workflows/validate.yml)
[![Tests](https://github.com/amor3/NimlyHomeAssistant/actions/workflows/tests.yml/badge.svg)](https://github.com/amor3/NimlyHomeAssistant/actions/workflows/tests.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Tells you **who** locked or unlocked your Nimly door and **how** (code, key tag,
fingerprint, button, auto relock, Home Assistant), and lets you **manage PIN codes**
from Home Assistant. Everything runs locally over your own Zigbee network through ZHA.

## How it fits with ZHA

The lock itself is handled by ZHA (Zigbee Home Automation). Its built-in Nimly quirk
already gives you the lock entity, battery level, auto relock and sound volume, so this
integration does **not** create those again. It adds what ZHA leaves out:

| Feature | ZHA | This integration |
| --- | --- | --- |
| Lock / unlock, lock state | ✅ | – |
| Battery, signal (LQI/RSSI) | ✅ | – |
| Auto relock switch, sound volume | ✅ (quirk) | – |
| Who operated the lock, by name (also the Home Assistant user who unlocked) | – | ✅ |
| How it was operated (keypad, tag, fingerprint, auto relock…) | ❌ see below | ✅ decoded |
| Event entity and `nimly_digital_lock_activity` event for automations | – | ✅ |
| Set and clear PIN codes, name slots | – | ✅ |
| Temporary PIN codes that remove themselves | – | ✅ |

Since Home Assistant 2026.2, the "Last action" sensors of ZHA's quirk no longer update
([zha-device-handlers#5235](https://github.com/zigpy/zha-device-handlers/issues/5235)): the
lock sends its operation report without a manufacturer code and zigpy no longer matches it.
This integration listens to the Door Lock cluster directly and receives every report.

## Requirements

- Home Assistant 2025.8 or newer with **ZHA** set up (Zigbee2MQTT is not supported).
- A Nimly lock with the **Nimly Zigbee module** (Connect Module) paired with ZHA.
  Zigbee module firmware **4.7.79 (20240625) or newer** is recommended; older firmware
  reports unreliably.
- A mains-powered Zigbee router (a smart plug) within a few metres of the door, on the
  inside. The radio sits in a metal lock body at the edge of the house and sleeps, so it
  depends on the nearest router; this fixes most dropouts.
- Do not leave the Zigbee module in a lock that is not paired: it keeps searching and
  drains the batteries.

The integration is available in English, Swedish, Norwegian (bokmål) and Danish, following
the Home Assistant language.

Supported: every lock whose Zigbee module reports the manufacturer `Onesti Products AS`
and has a Door Lock cluster. That includes NimlyCode, NimlyCodePRO, NimlyTouch, NimlyPRO
(Touch Pro), NimlyPRO24, NimlyIn, NimlyShared, NimlyKeybox, NimlyTwist and the
EasyAccess EasyCodeTouch / EasyFingerTouch.

## Installation

### HACS (recommended)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/amor3/NimlyHomeAssistant`
   as an **Integration**.
2. Install **Nimly Digital Lock** and restart Home Assistant.

### Manual

Copy `custom_components/nimly_digital_lock` to `config/custom_components/` and restart.

## Setup

1. Pair the lock's Zigbee module with ZHA. The lock sleeps, so keep it awake during
   pairing by entering a code and `#` on the keypad while ZHA searches.
2. **Settings → Devices & services → Add integration → Nimly Digital Lock** and pick the
   lock from the list.

Only the first lock is added by hand. After that, every Nimly lock ZHA pairs shows up
under **Discovered** on the integrations page.

**Replaced the Zigbee module?** Pair the new module with ZHA, then choose
**Reconfigure** on the integration entry and pick it. Slot names, PIN state, entities
and their history stay. Remove the old module from ZHA afterwards.

## What you get

A device called **"<lock name> activity"**, linked to ZHA's device for the lock, with:

| Entity | Description |
| --- | --- |
| `event.…_activity` | Fires `lock` / `unlock` with `source`, `slot`, `user`, `ha_user` and `system` attributes. The logbook shows the Home Assistant user for app commands. |
| `sensor.…_last_action` | Locked / Unlocked. |
| `sensor.…_last_operated_by` | Keypad, Key tag, Fingerprint, Button, Auto relock, Home Assistant / Zigbee, Other. |
| `sensor.…_last_user` | The last person who operated the lock: the slot name for a code, tag or finger ("Slot N" if unnamed), or the Home Assistant user who locked or unlocked from the app. Auto relock and a palm lock from outside do not overwrite it. Survives restarts. |
| `sensor.…_pin_codes` | Number of slots with a PIN set from Home Assistant (diagnostic). The `slots` attribute lists names, names per credential kind and the end time of temporary codes, never the codes. |
| `sensor.…_pin_capacity` | PIN slots and code length the lock reports (diagnostic, disabled by default). |
| `sensor.…_last_report` | When the lock last sent an operation report (diagnostic): a quick way to see that reports arrive. |

Every lock event also fires `nimly_digital_lock_activity` on the event bus:

```yaml
event_type: nimly_digital_lock_activity
data:
  config_entry_id: "…"
  ieee: "f4:ce:36:…"
  action: unlock        # lock | unlock | unknown
  source: keypad        # zigbee | button | keypad | fingerprint | rfid | auto | unattributed | unknown
  slot: 5               # null when no user is involved
  user: Anna            # slot name, or null
  ha_user: null         # the Home Assistant user, when the command came from the app
  system: false         # true for auto relock and similar non-human events
```

Example automation:

```yaml
triggers:
  - trigger: event
    event_type: nimly_digital_lock_activity
    event_data:
      action: unlock
conditions:
  - condition: template
    value_template: "{{ not trigger.event.data.system }}"
actions:
  - action: notify.mobile_app_phone
    data:
      message: >
        {{ trigger.event.data.user or trigger.event.data.ha_user or 'Someone' }} unlocked the door
        ({{ trigger.event.data.source }})
```

## Managing PIN codes

**Settings → Devices & services → Nimly Digital Lock → Configure**:

- **Set PIN code**: pick a slot, give it a name and enter the code. Set **Valid until**
  for a temporary code.
- **Clear PIN code**: removes the code from a slot; the name stays.
- **Name a slot**: name any slot (0–999), for example key tags and fingerprints
  enrolled at the lock, so events show the person instead of "Slot 152". Codes and key
  tags share one numbering, but fingerprints have their own (000–199): fingerprint 5 can
  be someone else than code 5. Pick a credential kind to give it its own name.
- **Settings**: number of reserved master slots, and the wake-up option below.

Codes entered in the Configure dialog go straight to the lock and are never stored in
Home Assistant. The same is available as actions for automations:
`nimly_digital_lock.set_pin`, `nimly_digital_lock.clear_pin` and
`nimly_digital_lock.set_slot_name`. Pick the lock with `device_id` (this integration's
device or ZHA's) or `config_entry_id`; with a single lock set up, neither is needed.
`set_slot_name` takes an optional `credential` (`pin`, `rfid` or `fingerprint`) to name
only that kind on the slot.
Home Assistant's recorder stores the data of every action call, so a code passed to
`set_pin` ends up in the database; use the Configure dialog to keep it out.

**Temporary codes.** A code with an end time (`valid_until`, or `valid_for` such as
`{"hours": 48}` in the action) is cleared from the lock automatically at that time, also
if Home Assistant was down then (it is cleared at the next start). If the lock cannot be
reached, it is retried every 10 minutes until it succeeds. The end time is shown in the
`slots` attribute of the PIN codes sensor.

```yaml
action: nimly_digital_lock.set_pin
data:
  slot: 10                  # add device_id when you have more than one lock
  pin_code: "482913"
  name: Plumber
  valid_for:
    hours: 8
```

**Slots.** Slot 0 is the master code on every model, and most models reserve slots 0–2
for master codes, so Home Assistant only writes PINs from slot 3 (configurable 1–3;
the Code Pro has a single master slot). The highest slot comes from the lock's reported
PIN capacity.

**Sleeping lock.** The lock's radio sleeps, and its parent router drops queued messages
after 7.68 seconds. Each attempt is given 10 seconds (zigpy alone would wait up to
84 seconds for a sleeping device), and a command that times out is retried, so a dialog
or action gives up after about half a minute. If it still fails,
wake the lock by turning the knob, or by entering a valid code and `#`, and try again
within a few seconds. Touching the keypad only lights it up. A code you set is only
confirmed by the lock answering; try it on the keypad. The **Wake the lock by locking it**
setting sends a lock command through ZHA before the first retry. That moves the bolt and
locks an open door, so it is off by default.

## Privacy and security

- The lock reports the last typed PIN in clear text on a manufacturer attribute
  (0x0101). This integration never reads it, stores it or logs it. ZHA's own optional
  "Last PIN code" sensor does show it; keep that sensor disabled.
- Digit runs in error messages are masked before logging.
- Diagnostics downloads contain no PIN codes, addresses or slot names.

## Migrating from 1.x

Version 1.x created its own lock, battery, RSSI, auto relock and volume entities, which
duplicated ZHA's. When you upgrade, they and their "service" device are removed
automatically. Use ZHA's entities for lock control, battery, auto relock and volume;
the entities listed above are new. Automations that used the old `lock.nimly_…`,
`sensor.…_battery`, `switch.…_auto_relock` or `select.…_sound_volume` entities need
to point to ZHA's entities instead. The `nimly_digital_lock.update` and
`nimly_digital_lock.export` actions are gone as well.

## Removing the integration

Clear the PIN codes that should stop working first: they live on the lock, and removing
the integration leaves them there. Then delete the entry under **Settings → Devices &
services → Nimly Digital Lock**. Slot names, temporary-code timers and the integration's
repair issues are removed with it. The lock itself stays in ZHA.

## Limitations

- **Key tags and fingerprints** are enrolled at the lock's keypad, not from Home
  Assistant. Name their slots here to see who used them.
- A code changed at the keypad is not seen by Home Assistant.
- **Door open/closed** is not available: the lock has no door sensor (the module always
  reports door state "unspecified"). Use a separate contact sensor.
- ZHA has no public API for what this integration listens to. If an update breaks it, a
  repair issue tells you, and lock control in ZHA keeps working.
- If ZHA replaces the lock's device object (after a rejoin or a re-interview), the
  integration notices within a minute and listens again.
- **After a battery change** the lock can lose its report binding: lock state still
  updates, but who and how stop. The integration notices when this happens a few times in
  a row and raises a repair issue. Fix: wake the lock (knob, or code and `#`) and choose
  **Reconfigure** on the device in ZHA within a few seconds; repeat if it fails, or
  re-pair as a last resort.
- Configuration writes to a sleeping lock (auto relock, volume in ZHA) do not always
  take. Wake the lock first.
- The lock does not say which Home Assistant user unlocked it; the integration credits a
  report to the user whose lock/unlock call came within 20 seconds before it.

## Troubleshooting

### ZHA does not show auto relock or volume

Those come from ZHA's Nimly quirk. If ZHA applied no quirk to the lock, a repair issue
says so. Update Home Assistant, then remove the lock from ZHA and pair it again (or use
**Reconfigure** on the device in ZHA). This integration works either way.

### Repair issues

| Issue (as shown under Settings → Repairs; *lock* is the lock's name) | Meaning |
| --- | --- |
| Nimly lock events cannot be received | ZHA offers no way to listen to the lock (a Home Assistant update changed ZHA). Lock control in ZHA still works. |
| *Lock* reports lock state but not who or how | Operation reports stopped, usually after a battery change. Reconfigure the device in ZHA with the lock awake. |
| ZHA runs *lock* without its Nimly quirk | Auto relock and volume are missing in ZHA. See above. |
| Expired PIN code on *lock* is still active | A temporary code could not be removed yet; it may still open the door. Wake the lock or delete the code at the keypad. |

If the lock is not in ZHA yet, or ZHA has not finished reading it, setup waits and
retries by itself.

### General

Enable debug logging:

```yaml
logger:
  logs:
    custom_components.nimly_digital_lock: debug
```

The **Last report** sensor shows when the lock last sent an operation report. Download
diagnostics from the integration's ⋮ menu when reporting an
[issue](https://github.com/amor3/NimlyHomeAssistant/issues); they contain no PIN codes,
addresses or slot names.

## Development

```bash
uv venv -p 3.14 .venv-test
VIRTUAL_ENV=.venv-test uv pip install -r requirements_test.txt
.venv-test/bin/ruff check custom_components tests
.venv-test/bin/mypy --strict --ignore-missing-imports custom_components/nimly_digital_lock
.venv-test/bin/pytest
```

The oldest supported Home Assistant (2025.8, with the older zigpy that has no
`Cluster.on_event`) is tested the same way with `requirements_test_min.txt` on Python 3.13.

The tests run against a fake ZHA gateway, and `tests/test_real_zigpy.py` also runs the
integration against a genuine zigpy Door Lock cluster with ZHA's Nimly quirk applied:
frames sent to the lock are checked byte for byte against the Zigbee module's format, and
the lock's answers and reports are fed in as raw ZCL frames. CI runs everything on the
current Home Assistant and on the oldest supported one.


## Maintainer

Developed and maintained by **André @ RCO Security AB**. Issues and pull requests are
welcome.
