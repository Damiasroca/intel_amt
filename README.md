<p align="center">
  <img src="images/logo.png" alt="Intel vPro" width="160">
</p>

# Intel AMT — Home Assistant Integration

Out-of-band power control for Intel AMT / vPro systems from Home Assistant.

Works with plain HTTP (port **16992**) or TLS (port **16993**). Tested with HP EliteDesk 800 G5 (AMT 12).

Reference: [rgl/intel-amt-notes](https://github.com/rgl/intel-amt-notes)

## Features

- Power on / soft-off / hard off
- Hard reset / soft reset / reboot
- PXE boot (one-time network boot)
- Power state sensor with `available_transitions` attribute
- Live KVM session + SOL/IDER redirection status as binary sensors
- Real device identity on the HA device page (manufacturer, model, serial, BIOS, AMT firmware)
- Diagnostic sensors for the same info so it can be used on Lovelace cards and automations
- UI config flow — no YAML editing required
- Options for poll interval

## Install via HACS

1. Add this repository as a [custom HACS repository](https://hacs.xyz/docs/faq/custom_repositories/):
   - HACS → three dots → **Custom repositories**
   - URL: `https://github.com/Damiasroca/intel_amt`
   - Category: **Integration**
2. Search **Intel AMT** in HACS → **Download**
3. Restart Home Assistant
4. **Settings → Devices & services → Add integration → Intel AMT**

### Manual install

Copy `custom_components/intel_amt/` to `/config/custom_components/intel_amt/` and restart HA.

## Configuration

| Field | Example | Notes |
|-------|---------|-------|
| AMT host | `192.168.0.161` | AMT IP — may differ from the OS/SSH IP |
| Username | `admin` | MEBx admin user |
| Password | *(AMT password)* | Not the OS login password |
| Protocol | `http` | Use `https` only if TLS is provisioned on AMT |

## Entities

Each configured device gets:

### Power & control

| Entity | Description |
|--------|-------------|
| `sensor.*_power_state` | Current state + `available_transitions` attribute |
| `switch.*_power` | On / soft-off |
| `button.*_power_on` | Power on |
| `button.*_hard_off` | Abrupt shutdown |
| `button.*_soft_off` | Graceful shutdown (needs Intel LMS) |
| `button.*_hard_reset` | Abrupt reset |
| `button.*_soft_reset` | Graceful reset (needs Intel LMS) |
| `button.*_reboot` | Reboot |
| `button.*_pxe_boot` | Network boot once |
| `button.*_refresh_status` | Poll now |

### Redirection status (per poll)

| Entity | Description |
|--------|-------------|
| `binary_sensor.*_kvm_session_active` | On when a KVM session is currently connected; `kvm_state` attribute exposes raw state (`connected` / `listening` / `disabled`) |
| `binary_sensor.*_redirection_enabled` | On when AMT is accepting SOL or IDER connections; `sol_enabled` / `ider_enabled` / `redirection_state` attributes for fine-grained automations |

### Hardware / firmware info (diagnostic, read once at setup)

| Entity | Description |
|--------|-------------|
| `sensor.*_model` | e.g. `HP EliteDesk 800 G5 Desktop Mini` |
| `sensor.*_serial_number` | Chassis serial |
| `sensor.*_amt_firmware` | AMT firmware version (e.g. `12.0.35.1450`) |
| `sensor.*_bios_version` | BIOS version string |

The same identity values are also shown on the Home Assistant device page (Manufacturer, Model, Serial number, Hardware version, Firmware version), populated from the same one-time WSMAN inventory fetch.

## Notes

- HA must run on a **different machine** on the LAN — a host cannot reach its own AMT.
- **Soft-off / soft-reset** require the Intel LMS agent in the OS. Use hard off/reset otherwise.
- When KVM/IDER is active, some power transitions return "not ready" (ReturnValue 2). Guard automations with `binary_sensor.*_kvm_session_active` or the `ider_enabled` attribute.
- Poll adds three WSMAN queries per interval (power + KVM + redirection). Negligible at the default 2-min interval; still fine at the 30-second minimum.

## Pyscript alternative

See `homeassistant/pyscript/` for an earlier Pyscript-based approach.

## License

Apache 2.0
