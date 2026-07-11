"""WSMAN client for Intel AMT power management."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from xml.etree import ElementTree

import requests
from requests.auth import HTTPDigestAuth

from .const import PORT_HTTP, PORT_HTTPS, POWER_STATES, PROTOCOL_HTTP, RETURN_VALUES

SCHEMA_BASE = "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/"
AMT_SCHEMA_BASE = "http://intel.com/wbem/wscim/1/amt-schema/1/"
CIM_ASSOCIATED_POWER = SCHEMA_BASE + "CIM_AssociatedPowerManagementService"
CIM_CHASSIS = SCHEMA_BASE + "CIM_Chassis"
CIM_BIOS_ELEMENT = SCHEMA_BASE + "CIM_BIOSElement"
CIM_SOFTWARE_IDENTITY = SCHEMA_BASE + "CIM_SoftwareIdentity"
CIM_KVM_SAP = SCHEMA_BASE + "CIM_KVMRedirectionSAP"
CIM_CHIP = SCHEMA_BASE + "CIM_Chip"
CIM_COMPUTER_SYSTEM_PACKAGE = SCHEMA_BASE + "CIM_ComputerSystemPackage"
AMT_REDIRECTION_SERVICE = AMT_SCHEMA_BASE + "AMT_RedirectionService"
AMT_ETHERNET_PORT_SETTINGS = AMT_SCHEMA_BASE + "AMT_EthernetPortSettings"
AMT_GENERAL_SETTINGS = AMT_SCHEMA_BASE + "AMT_GeneralSettings"
AMT_SETUP_CONFIGURATION_SERVICE = AMT_SCHEMA_BASE + "AMT_SetupAndConfigurationService"
AMT_EVENT_LOG_ENTRY = AMT_SCHEMA_BASE + "AMT_EventLogEntry"

BOOT_DEVICES = {
    "pxe": "Intel(r) AMT: Force PXE Boot",
    "hd": "Intel(r) AMT: Force Hard-drive Boot",
    "cd": "Intel(r) AMT: Force CD/DVD Boot",
}

# AMT_SetupAndConfigurationService value maps.
PROVISIONING_STATES = {0: "pre", 1: "in-progress", 2: "post"}
PROVISIONING_MODES = {1: "acm", 3: "ccm"}

FRIENDLY = {value: name for name, value in POWER_STATES.items()}


def _parse_event_record(record: str) -> str | None:
    """AMT_EventLogEntry.RecordData format: ';string Source;string Description'."""
    parts = record.split(";")
    if len(parts) < 3:
        return None
    return parts[2].strip() or None


class AmtError(Exception):
    """Raised when an AMT operation fails."""


@dataclass
class AmtStatus:
    """Current AMT power state and live redirection/KVM status."""

    power_state: str
    available_transitions: list[str]
    kvm_state: str | None = None
    kvm_session_active: bool | None = None
    redirection_state: str | None = None
    sol_enabled: bool | None = None
    ider_enabled: bool | None = None
    link_up: bool | None = None
    ip_address: str | None = None
    mac_address: str | None = None
    provisioning_state: str | None = None
    provisioning_mode: str | None = None
    last_event_time: str | None = None
    last_event_description: str | None = None


@dataclass
class AmtDeviceInfo:
    """Static hardware/firmware identity read once at setup."""

    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    chassis_version: str | None = None
    bios_version: str | None = None
    amt_version: str | None = None
    hostname: str | None = None
    domain_name: str | None = None
    cpu_model: str | None = None
    platform_guid: str | None = None


class AmtClient:
    """Intel AMT WSMAN client."""

    def __init__(
        self,
        host: str,
        password: str,
        username: str = "admin",
        protocol: str = PROTOCOL_HTTP,
        timeout: int = 15,
        verify_tls: bool = True,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.protocol = protocol
        self.timeout = timeout
        self.verify_tls = verify_tls

    @property
    def uri(self) -> str:
        port = PORT_HTTP if self.protocol == PROTOCOL_HTTP else PORT_HTTPS
        return f"{self.protocol}://{self.host}:{port}/wsman"

    def _auth(self) -> HTTPDigestAuth:
        return HTTPDigestAuth(self.username, self.password)

    def _post(self, payload: str) -> requests.Response:
        resp = requests.post(
            self.uri,
            headers={"content-type": "application/soap+xml;charset=UTF-8"},
            auth=self._auth(),
            data=payload,
            timeout=self.timeout,
            verify=self.verify_tls if self.protocol == "https" else True,
        )
        resp.raise_for_status()
        return resp

    @staticmethod
    def _get_request(uri: str, resource: str) -> str:
        body = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
 xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd">
  <s:Header>
    <wsa:Action s:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2004/09/transfer/Get</wsa:Action>
    <wsa:To s:mustUnderstand="true">%(uri)s</wsa:To>
    <wsman:ResourceURI s:mustUnderstand="true">%(resource)s</wsman:ResourceURI>
    <wsa:MessageID s:mustUnderstand="true">uuid:%(uuid)s</wsa:MessageID>
    <wsa:ReplyTo>
      <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
  </s:Header>
  <s:Body/>
</s:Envelope>"""
        return body % {"uri": uri, "resource": resource, "uuid": uuid.uuid4()}

    @staticmethod
    def _power_request(uri: str, power_state: int) -> str:
        body = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
 xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
 xmlns:n1="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_PowerManagementService">
  <s:Header>
    <wsa:Action s:mustUnderstand="true">http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_PowerManagementService/RequestPowerStateChange</wsa:Action>
    <wsa:To s:mustUnderstand="true">%(uri)s</wsa:To>
    <wsman:ResourceURI s:mustUnderstand="true">http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_PowerManagementService</wsman:ResourceURI>
    <wsa:MessageID s:mustUnderstand="true">uuid:%(uuid)s</wsa:MessageID>
    <wsa:ReplyTo>
      <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
    <wsman:SelectorSet>
      <wsman:Selector Name="Name">Intel(r) AMT Power Management Service</wsman:Selector>
    </wsman:SelectorSet>
  </s:Header>
  <s:Body>
    <n1:RequestPowerStateChange_INPUT>
      <n1:PowerState>%(power_state)d</n1:PowerState>
      <n1:ManagedElement>
        <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
        <wsa:ReferenceParameters>
          <wsman:ResourceURI>http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ComputerSystem</wsman:ResourceURI>
          <wsman:SelectorSet>
            <wsman:Selector wsman:Name="Name">ManagedSystem</wsman:Selector>
          </wsman:SelectorSet>
        </wsa:ReferenceParameters>
      </n1:ManagedElement>
    </n1:RequestPowerStateChange_INPUT>
  </s:Body>
</s:Envelope>"""
        return body % {"uri": uri, "power_state": power_state, "uuid": uuid.uuid4()}

    @staticmethod
    def _change_boot_order_request(uri: str, boot_device: str) -> str:
        body = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
 xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
 xmlns:n1="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_BootConfigSetting">
  <s:Header>
    <wsa:Action s:mustUnderstand="true">http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_BootConfigSetting/ChangeBootOrder</wsa:Action>
    <wsa:To s:mustUnderstand="true">%(uri)s</wsa:To>
    <wsman:ResourceURI s:mustUnderstand="true">http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_BootConfigSetting</wsman:ResourceURI>
    <wsa:MessageID s:mustUnderstand="true">uuid:%(uuid)s</wsa:MessageID>
    <wsa:ReplyTo>
      <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
    <wsman:SelectorSet>
      <wsman:Selector Name="InstanceID">Intel(r) AMT: Boot Configuration 0</wsman:Selector>
    </wsman:SelectorSet>
  </s:Header>
  <s:Body>
    <n1:ChangeBootOrder_INPUT>
      <n1:Source>
        <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
        <wsa:ReferenceParameters>
          <wsman:ResourceURI>http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_BootSourceSetting</wsman:ResourceURI>
          <wsman:SelectorSet>
            <wsman:Selector wsman:Name="InstanceID">%(boot_device)s</wsman:Selector>
          </wsman:SelectorSet>
        </wsa:ReferenceParameters>
      </n1:Source>
    </n1:ChangeBootOrder_INPUT>
  </s:Body>
</s:Envelope>"""
        return body % {
            "uri": uri,
            "uuid": uuid.uuid4(),
            "boot_device": BOOT_DEVICES[boot_device],
        }

    @staticmethod
    def _enable_boot_config_request(uri: str) -> str:
        body = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
 xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
 xmlns:n1="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_BootService">
  <s:Header>
    <wsa:Action s:mustUnderstand="true">http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_BootService/SetBootConfigRole</wsa:Action>
    <wsa:To s:mustUnderstand="true">%(uri)s</wsa:To>
    <wsman:ResourceURI s:mustUnderstand="true">http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_BootService</wsman:ResourceURI>
    <wsa:MessageID s:mustUnderstand="true">uuid:%(uuid)s</wsa:MessageID>
    <wsa:ReplyTo>
      <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
    <wsman:SelectorSet>
      <wsman:Selector Name="Name">Intel(r) AMT Boot Service</wsman:Selector>
    </wsman:SelectorSet>
  </s:Header>
  <s:Body>
    <n1:SetBootConfigRole_INPUT>
      <n1:BootConfigSetting>
        <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
        <wsa:ReferenceParameters>
          <wsman:ResourceURI>http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_BootConfigSetting</wsman:ResourceURI>
          <wsman:SelectorSet>
            <wsman:Selector wsman:Name="InstanceID">Intel(r) AMT: Boot Configuration 0</wsman:Selector>
          </wsman:SelectorSet>
        </wsa:ReferenceParameters>
      </n1:BootConfigSetting>
      <n1:Role>1</n1:Role>
    </n1:SetBootConfigRole_INPUT>
  </s:Body>
</s:Envelope>"""
        return body % {"uri": uri, "uuid": uuid.uuid4()}

    @staticmethod
    def _enumerate_request(uri: str, resource: str) -> str:
        body = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
 xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
 xmlns:wsen="http://schemas.xmlsoap.org/ws/2004/09/enumeration">
  <s:Header>
    <wsa:Action s:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2004/09/enumeration/Enumerate</wsa:Action>
    <wsa:To s:mustUnderstand="true">%(uri)s</wsa:To>
    <wsman:ResourceURI s:mustUnderstand="true">%(resource)s</wsman:ResourceURI>
    <wsa:MessageID s:mustUnderstand="true">uuid:%(uuid)s</wsa:MessageID>
    <wsa:ReplyTo>
      <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
  </s:Header>
  <s:Body>
    <wsen:Enumerate/>
  </s:Body>
</s:Envelope>"""
        return body % {"uri": uri, "resource": resource, "uuid": uuid.uuid4()}

    @staticmethod
    def _pull_request(uri: str, resource: str, context: str) -> str:
        body = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
 xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
 xmlns:wsen="http://schemas.xmlsoap.org/ws/2004/09/enumeration">
  <s:Header>
    <wsa:Action s:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2004/09/enumeration/Pull</wsa:Action>
    <wsa:To s:mustUnderstand="true">%(uri)s</wsa:To>
    <wsman:ResourceURI s:mustUnderstand="true">%(resource)s</wsman:ResourceURI>
    <wsa:MessageID s:mustUnderstand="true">uuid:%(uuid)s</wsa:MessageID>
    <wsa:ReplyTo>
      <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
  </s:Header>
  <s:Body>
    <wsen:Pull>
      <wsen:EnumerationContext>%(context)s</wsen:EnumerationContext>
      <wsen:MaxElements>32</wsen:MaxElements>
    </wsen:Pull>
  </s:Body>
</s:Envelope>"""
        return body % {
            "uri": uri,
            "resource": resource,
            "context": context,
            "uuid": uuid.uuid4(),
        }

    @staticmethod
    def _local_name(elem: ElementTree.Element) -> str:
        tag = elem.tag
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    @classmethod
    def _find_in_xml(cls, content: bytes, tag: str) -> str | None:
        doc = ElementTree.fromstring(content)
        for elem in doc.iter():
            if cls._local_name(elem) == tag and elem.text is not None:
                return elem.text
        return None

    @classmethod
    def _child_text(cls, item: ElementTree.Element, name: str) -> str | None:
        for child in item.iter():
            if cls._local_name(child) == name and child.text is not None:
                text = child.text.strip()
                if text:
                    return text
        return None

    @classmethod
    def _find_return_value(cls, content: bytes) -> int | None:
        text = cls._find_in_xml(content, "ReturnValue")
        if text is None:
            return None
        return int(text)

    @classmethod
    def _parse_available_transitions(cls, content: bytes) -> list[str]:
        text = cls._find_in_xml(content, "AvailableRequestedPowerStates")
        if not text:
            return []
        transitions: list[str] = []
        for token in text.replace(",", " ").split():
            try:
                code = int(token)
            except ValueError:
                continue
            name = FRIENDLY.get(code)
            if name and name not in transitions:
                transitions.append(name)
        return transitions

    def get_status(self) -> AmtStatus:
        """Return current power state plus KVM + redirection status."""
        payload = self._get_request(self.uri, CIM_ASSOCIATED_POWER)
        resp = requests.post(
            self.uri,
            auth=self._auth(),
            data=payload,
            timeout=self.timeout,
            verify=self.verify_tls if self.protocol == "https" else True,
        )
        resp.raise_for_status()
        power_text = self._find_in_xml(resp.content, "PowerState")
        if power_text is None:
            power_state = "unknown"
        else:
            power_state = FRIENDLY.get(int(power_text), f"state-{power_text}")

        kvm_state, kvm_active = self._fetch_kvm_state()
        redirection_state, sol, ider = self._fetch_redirection_state()
        link_up, ip_address, mac_address = self._fetch_ethernet()
        prov_state, prov_mode = self._fetch_provisioning()
        last_event_time, last_event_desc = self._fetch_last_event()

        return AmtStatus(
            power_state=power_state,
            available_transitions=self._parse_available_transitions(resp.content),
            kvm_state=kvm_state,
            kvm_session_active=kvm_active,
            redirection_state=redirection_state,
            sol_enabled=sol,
            ider_enabled=ider,
            link_up=link_up,
            ip_address=ip_address,
            mac_address=mac_address,
            provisioning_state=prov_state,
            provisioning_mode=prov_mode,
            last_event_time=last_event_time,
            last_event_description=last_event_desc,
        )

    def _fetch_kvm_state(self) -> tuple[str | None, bool | None]:
        """Return (state_name, session_active) or (None, None) on failure."""
        try:
            items = self._enumerate(CIM_KVM_SAP)
            if not items:
                return None, None
            code_text = self._child_text(items[0], "EnabledState")
            if code_text is None:
                return None, None
            code = int(code_text)
        except Exception:
            return None, None
        # CIM_KVMRedirectionSAP.EnabledState:
        # 2 = Enabled (active session)
        # 3 = Disabled
        # 6 = Enabled but Offline (listening, no session)
        mapping = {2: ("connected", True), 3: ("disabled", False), 6: ("listening", False)}
        return mapping.get(code, (f"state-{code}", False))

    def _fetch_redirection_state(
        self,
    ) -> tuple[str | None, bool | None, bool | None]:
        """Return (state_name, sol_enabled, ider_enabled) or (None,None,None)."""
        try:
            items = self._enumerate(AMT_REDIRECTION_SERVICE)
            if not items:
                return None, None, None
            code_text = self._child_text(items[0], "EnabledState")
            if code_text is None:
                return None, None, None
            code = int(code_text)
        except Exception:
            return None, None, None
        # AMT_RedirectionService.EnabledState (bit 0 = SOL, bit 1 = IDER):
        # 32768 disabled, 32769 SOL only, 32770 IDER only, 32771 both
        sol = bool(code & 1)
        ider = bool(code & 2)
        if not sol and not ider:
            name = "disabled"
        elif sol and not ider:
            name = "sol"
        elif ider and not sol:
            name = "ider"
        else:
            name = "sol+ider"
        return name, sol, ider

    def _fetch_ethernet(self) -> tuple[bool | None, str | None, str | None]:
        """Return (link_up, ip_address, mac_address) for the wired AMT NIC."""
        try:
            items = self._enumerate(AMT_ETHERNET_PORT_SETTINGS)
        except Exception:
            return None, None, None
        if not items:
            return None, None, None
        # Prefer the wired port (InstanceID ends in " 0"); fall back to first.
        primary = items[0]
        for item in items:
            instance = self._child_text(item, "InstanceID") or ""
            if instance.endswith(" 0"):
                primary = item
                break
        link_text = self._child_text(primary, "LinkIsUp")
        link_up: bool | None = None
        if link_text:
            link_up = link_text.strip().lower() == "true"
        return (
            link_up,
            self._child_text(primary, "IPAddress"),
            self._child_text(primary, "MACAddress"),
        )

    def _fetch_provisioning(self) -> tuple[str | None, str | None]:
        """Return (provisioning_state, provisioning_mode) names."""
        try:
            items = self._enumerate(AMT_SETUP_CONFIGURATION_SERVICE)
        except Exception:
            return None, None
        if not items:
            return None, None
        state_text = self._child_text(items[0], "ProvisioningState")
        mode_text = self._child_text(items[0], "ProvisioningMode")
        state: str | None = None
        mode: str | None = None
        if state_text is not None:
            try:
                state = PROVISIONING_STATES.get(int(state_text), f"state-{state_text}")
            except ValueError:
                pass
        if mode_text is not None:
            try:
                mode = PROVISIONING_MODES.get(int(mode_text), f"mode-{mode_text}")
            except ValueError:
                pass
        return state, mode

    def _fetch_last_event(self) -> tuple[str | None, str | None]:
        """Return (iso_timestamp, description) of the newest AMT event."""
        try:
            items = self._enumerate(AMT_EVENT_LOG_ENTRY)
        except Exception:
            return None, None
        newest_time: str | None = None
        newest_desc: str | None = None
        for item in items:
            time_text = self._child_text(item, "Datetime")
            if not time_text:
                continue
            if newest_time is None or time_text > newest_time:
                newest_time = time_text
                newest_desc = _parse_event_record(self._child_text(item, "RecordData") or "")
        return newest_time, newest_desc

    def set_power(self, action: str) -> None:
        """Request a power state change."""
        if action not in POWER_STATES:
            raise AmtError(f"Unknown power action: {action}")

        payload = self._power_request(self.uri, POWER_STATES[action])
        resp = self._post(payload)
        return_value = self._find_return_value(resp.content)
        if return_value is None:
            return
        if return_value != 0:
            reason = RETURN_VALUES.get(return_value, f"code {return_value}")
            raise AmtError(
                f"RequestPowerStateChange({action}) failed: "
                f"ReturnValue {return_value} ({reason})"
            )

    def set_next_boot(self, boot_device: str) -> None:
        """Configure one-time next boot device."""
        if boot_device not in BOOT_DEVICES:
            raise AmtError(f"Unknown boot device: {boot_device}")
        self._post(self._change_boot_order_request(self.uri, boot_device))
        self._post(self._enable_boot_config_request(self.uri))

    def pxe_boot(self) -> None:
        """Set next boot to PXE and reboot."""
        self.set_next_boot("pxe")
        self.set_power("reboot")

    def _enumerate(self, resource: str) -> list[ElementTree.Element]:
        """Enumerate a CIM class, following WS-Enumeration pagination."""
        enum_resp = self._post(self._enumerate_request(self.uri, resource))
        context = self._find_in_xml(enum_resp.content, "EnumerationContext")
        items: list[ElementTree.Element] = []
        while context:
            pull_resp = self._post(self._pull_request(self.uri, resource, context))
            doc = ElementTree.fromstring(pull_resp.content)
            end_of_sequence = False
            next_context: str | None = None
            for elem in doc.iter():
                local = self._local_name(elem)
                if local == "Items":
                    items.extend(list(elem))
                elif local == "EndOfSequence":
                    end_of_sequence = True
                elif local == "EnumerationContext" and elem.text:
                    next_context = elem.text.strip()
            if end_of_sequence:
                break
            context = next_context
        return items

    def get_device_info(self) -> AmtDeviceInfo:
        """One-time hardware/firmware inventory. Each block fails softly."""
        info = AmtDeviceInfo()
        try:
            chassis_items = self._enumerate(CIM_CHASSIS)
            if chassis_items:
                item = chassis_items[0]
                info.manufacturer = self._child_text(item, "Manufacturer")
                info.model = self._child_text(item, "Model")
                info.serial_number = self._child_text(item, "SerialNumber")
                info.chassis_version = self._child_text(item, "Version")
        except Exception:
            pass
        try:
            for item in self._enumerate(CIM_BIOS_ELEMENT):
                version = self._child_text(item, "Version")
                if version:
                    info.bios_version = version
                    break
        except Exception:
            pass
        try:
            for item in self._enumerate(CIM_SOFTWARE_IDENTITY):
                if self._child_text(item, "InstanceID") == "AMT":
                    version = self._child_text(item, "VersionString")
                    if version:
                        info.amt_version = version
                        break
        except Exception:
            pass
        try:
            general_items = self._enumerate(AMT_GENERAL_SETTINGS)
            if general_items:
                info.hostname = self._child_text(general_items[0], "HostName")
                info.domain_name = self._child_text(general_items[0], "DomainName")
        except Exception:
            pass
        try:
            pkg_items = self._enumerate(CIM_COMPUTER_SYSTEM_PACKAGE)
            if pkg_items:
                guid = self._child_text(pkg_items[0], "PlatformGUID")
                if guid:
                    info.platform_guid = guid.lower()
        except Exception:
            pass
        try:
            # CIM_Chip enumeration returns CPU chips *and* memory (as CIM_PhysicalMemory).
            # CPU entries carry a Tag like "CPU 0".
            for chip in self._enumerate(CIM_CHIP):
                tag = self._child_text(chip, "Tag") or ""
                if tag.upper().startswith("CPU"):
                    version = self._child_text(chip, "Version")
                    if version:
                        info.cpu_model = version.strip()
                        break
        except Exception:
            pass
        return info
