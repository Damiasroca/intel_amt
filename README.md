# Intel AMT — Home Assistant Integration

Out-of-band power control for Intel AMT / vPro systems from Home Assistant.

Works with plain HTTP (port **16992**) or TLS (port **16993**). Tested with HP EliteDesk 800 G5 (AMT 12).

Reference: [rgl/intel-amt-notes](https://github.com/rgl/intel-amt-notes)

## Features

- Power on / soft-off / hard off
- Hard reset / soft reset / reboot
- PXE boot (one-time network boot)
- Power state sensor with `available_transitions` attribute
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

| Entity | Description |
|--------|-------------|
| `sensor.*_power_state` | Current state + available transitions |
| `switch.*_power` | On / soft-off |
| `button.*_hard_off` | Abrupt shutdown |
| `button.*_soft_off` | Graceful shutdown (needs Intel LMS) |
| `button.*_hard_reset` | Abrupt reset |
| `button.*_soft_reset` | Graceful reset (needs Intel LMS) |
| `button.*_reboot` | Reboot |
| `button.*_pxe_boot` | Network boot once |
| `button.*_refresh_status` | Poll now |

## Notes

- HA must run on a **different machine** on the LAN — a host cannot reach its own AMT.
- **Soft-off / soft-reset** require the Intel LMS agent in the OS. Use hard off/reset otherwise.
- When KVM/IDER is active, some transitions return "not ready" (ReturnValue 2).

## Pyscript alternative

See `homeassistant/pyscript/` for an earlier Pyscript-based approach.

## License

Apache 2.0
