# Intel AMT

Out-of-band power control for Intel AMT / vPro systems from Home Assistant.

- Power on / soft-off / hard off
- Hard reset / soft reset / reboot
- PXE boot (one-time network boot)
- Firmware wake alarms (schedule and delete)
- Power state sensor with `available_transitions`
- UI config flow

After install: **Settings → Devices & services → Add integration → Intel AMT**.

Use the AMT IP and MEBx admin credentials. Home Assistant must run on a different LAN host (a machine cannot reach its own AMT).

## 0.2.3

Scheduling a wake alarm no longer fails when Home Assistant's datetime picker submits the date and time as one invalid string (`2026-09-26T00:00:00 13:15:00`). The wake time still has to be in the future.
