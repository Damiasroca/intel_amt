# Intel AMT

Out-of-band power control for Intel AMT / vPro systems from Home Assistant.

- Power on / soft-off / hard off
- Hard reset / soft reset / reboot
- PXE boot (one-time network boot)
- Power state sensor with `available_transitions`
- UI config flow

After install: **Settings → Devices & services → Add integration → Intel AMT**.

Use the AMT IP and MEBx admin credentials. Home Assistant must run on a different LAN host (a machine cannot reach its own AMT).
