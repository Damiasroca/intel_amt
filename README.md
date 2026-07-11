

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
- AMT NIC link status, IP and MAC address exposed for automations
- Provisioning state / mode diagnostic sensors (post-provisioning, ACM/CCM)
- Last AMT event log entry as a timestamp sensor (with description attribute)
- Real device identity on the HA device page (manufacturer, model, serial, BIOS, AMT firmware, CPU, hostname, platform GUID)
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


| Field    | Example          | Notes                                         |
| -------- | ---------------- | --------------------------------------------- |
| AMT host | `192.168.X.X`    | AMT IP — may differ from the OS/SSH IP        |
| Username | `(User)`         | MEBx admin user                               |
| Password | *(AMT password)* | Not the OS login password                     |
| Protocol | `http`           | Use `https` only if TLS is provisioned on AMT |




## Entities

Each configured device gets:

### Power & control


| Entity                    | Description                                       |
| ------------------------- | ------------------------------------------------- |
| `sensor.*_power_state`    | Current state + `available_transitions` attribute |
| `switch.*_power`          | On / soft-off                                     |
| `button.*_power_on`       | Power on                                          |
| `button.*_hard_off`       | Abrupt shutdown                                   |
| `button.*_soft_off`       | Graceful shutdown (needs Intel LMS)               |
| `button.*_hard_reset`     | Abrupt reset                                      |
| `button.*_soft_reset`     | Graceful reset (needs Intel LMS)                  |
| `button.*_reboot`         | Reboot                                            |
| `button.*_pxe_boot`       | Network boot once                                 |
| `button.*_refresh_status` | Poll now                                          |




### Redirection status (per poll)


| Entity                                | Description                                                                                                                                    |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `binary_sensor.*_kvm_session_active`  | On when a KVM session is currently connected; `kvm_state` attribute exposes raw state (`connected` / `listening` / `disabled`)                 |
| `binary_sensor.*_redirection_enabled` | On when AMT is accepting SOL or IDER connections; `sol_enabled` / `ider_enabled` / `redirection_state` attributes for fine-grained automations |




### Network (per poll)


| Entity                         | Description                                                                                       |
| ------------------------------ | ------------------------------------------------------------------------------------------------- |
| `binary_sensor.*_network_link` | On when the AMT NIC reports `LinkIsUp=true`; `ip_address` and `mac_address` exposed as attributes |
| `sensor.*_ip_address`          | Current AMT-side IP address (from `AMT_EthernetPortSettings`, wired port preferred)               |




### Provisioning (per poll, diagnostic)


| Entity                        | Description                                                    |
| ----------------------------- | -------------------------------------------------------------- |
| `sensor.*_provisioning_state` | `pre` / `in-progress` / `post` (post = normal operating state) |
| `sensor.*_provisioning_mode`  | `acm` (Admin Control Mode) or `ccm` (Client Control Mode)      |




### Event log (per poll, diagnostic)


| Entity                    | Description                                                                                                                                                |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sensor.*_last_amt_event` | Timestamp of the newest `AMT_EventLogEntry`; parsed source/description exposed as `description` attribute (e.g. `Starting operating system boot process.`) |




### Hardware / firmware info (diagnostic, read once at setup)


| Entity                   | Description                                                                         |
| ------------------------ | ----------------------------------------------------------------------------------- |
| `sensor.*_model`         | e.g. `HP EliteDesk 800 G5 Desktop Mini`                                             |
| `sensor.*_serial_number` | Chassis serial                                                                      |
| `sensor.*_amt_firmware`  | AMT firmware version (e.g. `12.0.35.1450`)                                          |
| `sensor.*_bios_version`  | BIOS version string                                                                 |
| `sensor.*_hostname`      | AMT hostname (from `AMT_GeneralSettings`)                                           |
| `sensor.*_cpu`           | CPU model string (from `CIM_Chip`, e.g. `Intel(R) Core(TM) i5-9600T CPU @ 2.30GHz`) |
| `sensor.*_system_id`     | Platform GUID / SMBIOS UUID (from `CIM_ComputerSystemPackage`)                      |


The same identity values are also shown on the Home Assistant device page (Manufacturer, Model, Serial number, Hardware version, Firmware version), populated from the same one-time WSMAN inventory fetch.

## Dashboard example

A copy-pasteable Lovelace card that groups every entity from a single AMT device into a coherent panel. Uses only built-in HA cards (no custom-card install).

**Replace** `elitedesk` **with your device's entity slug** — pick any entity under Settings → Devices & services → Intel AMT and copy the prefix before `_power_state`.

```yaml
type: vertical-stack
title: Intel AMT — EliteDesk
cards:
  - type: entities
    entities:
      - entity: sensor.elitedesk_power_state
        name: State
        icon: mdi:power-plug
      - entity: switch.elitedesk_power
        name: Power switch
  - type: horizontal-stack
    cards:
      - type: button
        entity: button.elitedesk_power_on
        icon: mdi:power
        name: On
        show_state: false
      - type: button
        entity: button.elitedesk_reboot
        icon: mdi:restart
        name: Reboot
        show_state: false
      - type: button
        entity: button.elitedesk_hard_off
        icon: mdi:power-off
        name: Hard off
        show_state: false
  - type: entities
    title: Redirection status
    entities:
      - entity: binary_sensor.elitedesk_kvm_session_active
        name: KVM session
      - entity: binary_sensor.elitedesk_redirection_enabled
        name: SOL / IDER enabled
  - type: entities
    title: Network
    entities:
      - entity: binary_sensor.elitedesk_network_link
        name: Link
      - entity: sensor.elitedesk_ip_address
        name: IP address
  - type: entities
    title: More actions
    show_header_toggle: false
    entities:
      - entity: button.elitedesk_soft_off
      - entity: button.elitedesk_soft_reset
      - entity: button.elitedesk_hard_reset
      - entity: button.elitedesk_pxe_boot
      - entity: button.elitedesk_refresh_status
  - type: entities
    title: Device info
    entities:
      - entity: sensor.elitedesk_model
      - entity: sensor.elitedesk_serial_number
      - entity: sensor.elitedesk_hostname
      - entity: sensor.elitedesk_cpu
      - entity: sensor.elitedesk_amt_firmware
      - entity: sensor.elitedesk_bios_version
      - entity: sensor.elitedesk_system_id
      - entity: sensor.elitedesk_provisioning_state
      - entity: sensor.elitedesk_provisioning_mode
      - entity: sensor.elitedesk_last_amt_event
```

To use it: **Dashboard → Edit → Add card → Manual → paste the YAML above → Save**.

### Fancier dashboard (with custom cards)

If you don't mind installing two custom cards from HACS, you get colored state tiles, a "% powered on last 24h" gauge, and a 24-hour timeline. AMT only exposes categorical data (no numeric metrics), so charts are limited to on/off history — this layout leans on `custom:button-card` for the heavy lifting.

Install via HACS → Frontend:

- [`custom:button-card`](https://github.com/custom-cards/button-card) — state-based colored tiles
- [`apexcharts-card`](https://github.com/RomRider/apexcharts-card) — the radial gauge

The 24-hour timeline uses HA's built-in `history-graph`, no install needed.

Same `elitedesk` slug replacement rule applies.

```yaml
type: vertical-stack
title: Intel AMT — EliteDesk
cards:
  - type: custom:button-card
    entity: sensor.elitedesk_power_state
    name: EliteDesk
    show_state: true
    show_icon: true
    size: 25%
    icon: |
      [[[
        if (!entity) return 'mdi:help-circle-outline';
        const s = entity.state;
        if (s === 'on') return 'mdi:desktop-tower';
        if (['reboot','hard-reboot','reset','soft-reset'].includes(s)) return 'mdi:restart';
        if (['soft-off','off','hibernate','sleep','standby'].includes(s)) return 'mdi:desktop-tower-monitor';
        return 'mdi:help-circle-outline';
      ]]]
    tap_action:
      action: more-info
    state:
      - value: 'on'
        color: '#4caf50'
        styles:
          card:
            - background: linear-gradient(135deg, rgba(76,175,80,0.30), rgba(76,175,80,0.05))
            - box-shadow: 0 0 24px rgba(76,175,80,0.35)
            - border: 1px solid rgba(76,175,80,0.4)
      - operator: 'in'
        value:
          - 'reboot'
          - 'hard-reboot'
          - 'reset'
          - 'soft-reset'
        color: '#ffa726'
        spin: true
        styles:
          card:
            - background: linear-gradient(135deg, rgba(255,167,38,0.25), rgba(255,167,38,0.05))
            - border: 1px solid rgba(255,167,38,0.35)
      - operator: 'in'
        value:
          - 'off'
          - 'soft-off'
          - 'hibernate'
          - 'sleep'
          - 'standby'
        color: '#ef5350'
        styles:
          card:
            - background: linear-gradient(135deg, rgba(239,83,80,0.25), rgba(239,83,80,0.05))
            - border: 1px solid rgba(239,83,80,0.35)
    styles:
      card:
        - border-radius: 18px
        - padding: 18px
        - height: 140px
      name:
        - font-size: 18px
        - font-weight: 600
      state:
        - font-size: 13px
        - text-transform: uppercase
        - letter-spacing: 2px
        - opacity: 0.9

  - type: horizontal-stack
    cards:
      - type: custom:button-card
        entity: button.elitedesk_power_on
        name: Power on
        icon: mdi:power
        color: '#4caf50'
        show_state: false
        size: 30%
        tap_action:
          action: perform-action
          perform_action: button.press
          target:
            entity_id: button.elitedesk_power_on
        styles:
          card:
            - border-radius: 14px
            - height: 92px
            - background: rgba(76,175,80,0.12)
            - border: 1px solid rgba(76,175,80,0.3)
      - type: custom:button-card
        entity: button.elitedesk_reboot
        name: Reboot
        icon: mdi:restart
        color: '#ffa726'
        show_state: false
        size: 30%
        tap_action:
          action: perform-action
          perform_action: button.press
          target:
            entity_id: button.elitedesk_reboot
          confirmation:
            text: Reboot EliteDesk?
        styles:
          card:
            - border-radius: 14px
            - height: 92px
            - background: rgba(255,167,38,0.12)
            - border: 1px solid rgba(255,167,38,0.3)
      - type: custom:button-card
        entity: button.elitedesk_hard_off
        name: Hard off
        icon: mdi:power-off
        color: '#ef5350'
        show_state: false
        size: 30%
        tap_action:
          action: perform-action
          perform_action: button.press
          target:
            entity_id: button.elitedesk_hard_off
          confirmation:
            text: Force power off EliteDesk?
        styles:
          card:
            - border-radius: 14px
            - height: 92px
            - background: rgba(239,83,80,0.12)
            - border: 1px solid rgba(239,83,80,0.3)

  - type: horizontal-stack
    cards:
      - type: custom:button-card
        entity: binary_sensor.elitedesk_kvm_session_active
        name: KVM
        show_state: true
        size: 26%
        tap_action:
          action: more-info
        state:
          - value: 'on'
            color: '#ab47bc'
            icon: mdi:monitor-eye
            styles:
              card:
                - background: rgba(171,71,188,0.20)
                - border: 1px solid rgba(171,71,188,0.4)
          - value: 'off'
            color: var(--secondary-text-color)
            icon: mdi:monitor-off
        styles:
          card:
            - border-radius: 12px
            - height: 76px
          state:
            - font-size: 11px
            - text-transform: uppercase
            - opacity: 0.8
      - type: custom:button-card
        entity: binary_sensor.elitedesk_redirection_enabled
        name: SOL / IDER
        show_state: true
        size: 26%
        tap_action:
          action: more-info
        state:
          - value: 'on'
            color: '#42a5f5'
            icon: mdi:console-network
            styles:
              card:
                - background: rgba(66,165,245,0.20)
                - border: 1px solid rgba(66,165,245,0.4)
          - value: 'off'
            color: var(--secondary-text-color)
            icon: mdi:console-network-outline
        styles:
          card:
            - border-radius: 12px
            - height: 76px
          state:
            - font-size: 11px
            - text-transform: uppercase
            - opacity: 0.8
      - type: custom:button-card
        entity: binary_sensor.elitedesk_network_link
        name: Link
        show_state: true
        size: 26%
        tap_action:
          action: more-info
        state:
          - value: 'on'
            color: '#4caf50'
            icon: mdi:lan-connect
            styles:
              card:
                - background: rgba(76,175,80,0.20)
                - border: 1px solid rgba(76,175,80,0.4)
          - value: 'off'
            color: '#ef5350'
            icon: mdi:lan-disconnect
            styles:
              card:
                - background: rgba(239,83,80,0.20)
                - border: 1px solid rgba(239,83,80,0.4)
        styles:
          card:
            - border-radius: 12px
            - height: 76px
          state:
            - font-size: 11px
            - text-transform: uppercase
            - opacity: 0.8

  - type: custom:apexcharts-card
    header:
      show: true
      title: Powered on (last 24h)
      show_states: false
    graph_span: 24h
    chart_type: radialBar
    apex_config:
      chart:
        height: 220
      plotOptions:
        radialBar:
          hollow:
            size: 60%
          dataLabels:
            name:
              fontSize: 14px
            value:
              fontSize: 28px
              formatter: |
                EVAL:function(val) { return Math.round(val) + '%'; }
      colors:
        - '#4caf50'
    series:
      - entity: sensor.elitedesk_power_state
        name: On-time
        color: '#4caf50'
        transform: 'return x === "on" ? 100 : 0;'
        group_by:
          func: avg
          duration: 24h
        min: 0
        max: 100

  - type: history-graph
    title: 24h history
    hours_to_show: 24
    entities:
      - entity: sensor.elitedesk_power_state
      - entity: binary_sensor.elitedesk_kvm_session_active
      - entity: binary_sensor.elitedesk_network_link

  - type: entities
    title: Device
    entities:
      - entity: sensor.elitedesk_model
      - entity: sensor.elitedesk_hostname
      - entity: sensor.elitedesk_ip_address
      - entity: sensor.elitedesk_cpu
      - entity: sensor.elitedesk_amt_firmware
      - entity: sensor.elitedesk_bios_version
      - entity: sensor.elitedesk_serial_number
      - entity: sensor.elitedesk_system_id
      - entity: sensor.elitedesk_provisioning_state
      - entity: sensor.elitedesk_provisioning_mode
      - entity: sensor.elitedesk_last_amt_event

  - type: entities
    title: More actions
    show_header_toggle: false
    entities:
      - entity: button.elitedesk_soft_off
      - entity: button.elitedesk_soft_reset
      - entity: button.elitedesk_hard_reset
      - entity: button.elitedesk_pxe_boot
      - entity: button.elitedesk_refresh_status
```

Notes:

- The radial gauge computes the average over the last 24h by transforming `on` → 100 and everything else → 0, then averaging. So `soft-off`, `sleep`, `hibernate`, transitions and `unknown` all count as "not on". If you want to count `sleep`/`standby` as "on", edit the `transform` line.
- `history-graph` reads from HA's Recorder — make sure `sensor.elitedesk_power_state` and the two binary sensors aren't excluded from Recorder in `configuration.yaml`.
- If you're on the Sections dashboard, replace the outer `type: vertical-stack` with `type: grid` and give each inner card an appropriate `grid_options` — the individual card configs above work unchanged.

## Notes

- HA must run on a **different machine** on the LAN — a host cannot reach its own AMT.
- **Soft-off / soft-reset** require the Intel LMS agent in the OS. Use hard off/reset otherwise.
- When KVM/IDER is active, some power transitions return "not ready" (ReturnValue 2). Guard automations with `binary_sensor.*_kvm_session_active` or the `ider_enabled` attribute.
- Each poll issues one WSMAN GET (power) plus five enumerations (KVM, redirection, ethernet, provisioning, event log). Negligible at the default 2-min interval; still fine at the 30-second minimum on LAN.
- The `Last AMT event` sensor enumerates `AMT_EventLogEntry` and picks the newest by `CreationTimeStamp`. AMT caps the log at ~390 records, so pagination stays cheap.



## Pyscript alternative

See `homeassistant/pyscript/` for an earlier Pyscript-based approach.

## License

Apache 2.0