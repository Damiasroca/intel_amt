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

## 0.2.4

The 24h power uptime sensor now reads Recorder history on Home Assistant's database executor, which removes the warning about accessing the database outside that executor. The power switch has a unique ID, so Home Assistant keeps it attached to the AMT device.

## 0.3.0

New **Verify TLS certificate** option for devices that use HTTPS. It is on by default and stays on for existing devices. If AMT uses a self-signed certificate, you can turn it off when adding the device, or later under **Configure → TLS settings**. Contributed by AVidal88.

## 0.4.0

New **Allow legacy TLS (older AMT firmware)** option for devices whose AMT firmware (for example 12.x) cannot connect over HTTPS with current Home Assistant, even with certificate verification off. It is off by default and independent of **Verify TLS certificate**. Enable it when adding the device, or under **Configure → TLS settings**. See the README for the trade-offs.
