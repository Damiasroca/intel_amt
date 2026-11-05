"""Tests for the opt-in legacy TLS mode used by older AMT firmware."""

import datetime
import ipaddress
import socket
import ssl
import threading
from collections.abc import Generator
from unittest.mock import PropertyMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from requests.exceptions import SSLError

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intel_amt.amt_client import (
    AMT_LEGACY_TLS_CIPHERS,
    AmtClient,
    _LegacyTlsAdapter,
    build_legacy_ssl_context,
)
from custom_components.intel_amt.const import (
    CONF_LEGACY_TLS,
    CONF_VERIFY_TLS,
    DOMAIN,
)

BASE_DATA = {
    "host": "192.0.2.10",
    "username": "admin",
    "password": "test-password",
    "protocol": "https",
    "name": "Workstation",
}


def default_value(result: dict, name: str) -> object:
    """Read the value a form offers for a field."""
    marker = next(key for key in result["data_schema"].schema if key.schema == name)
    return marker.default()


# --- The SSL context itself -------------------------------------------------


@pytest.mark.parametrize("verify_tls", [True, False])
def test_adapter_context_is_narrow(verify_tls: bool) -> None:
    """Compatibility only adds one cipher and legacy connect, and keeps TLS 1.2+."""
    context = build_legacy_ssl_context(verify_tls)

    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2
    assert context.options & ssl.OP_LEGACY_SERVER_CONNECT
    names = {cipher["name"] for cipher in context.get_ciphers()}
    assert "AES128-GCM-SHA256" in names
    # Nothing weaker than the library defaults is added, and the security
    # level is not lowered to make it work.
    assert AMT_LEGACY_TLS_CIPHERS == "DEFAULT:AES128-GCM-SHA256"
    assert "SECLEVEL" not in AMT_LEGACY_TLS_CIPHERS
    assert not any("RC4" in name or "3DES" in name or "NULL" in name for name in names)
    expected = ssl.CERT_REQUIRED if verify_tls else ssl.CERT_NONE
    assert context.verify_mode == expected


def legacy_mounts(mount: object) -> list:
    """Return the mount calls that installed the legacy adapter."""
    return [
        call
        for call in mount.call_args_list
        if isinstance(call.args[1], _LegacyTlsAdapter)
    ]


def test_default_client_does_not_mount_the_adapter() -> None:
    """Without the opt-in, the standard requests TLS stack is used."""
    with patch("requests.Session.mount") as mount, patch("requests.Session.post"):
        AmtClient("192.0.2.10", "pw", protocol="https")._send("<x/>")
        assert not legacy_mounts(mount)
        AmtClient("192.0.2.10", "pw", protocol="https", legacy_tls=True)._send("<x/>")
        (call,) = legacy_mounts(mount)
        assert call.args[0] == "https://"


def test_http_never_uses_the_adapter() -> None:
    """Legacy mode only concerns HTTPS."""
    with patch("requests.Session.mount") as mount, patch("requests.Session.post"):
        AmtClient("192.0.2.10", "pw", protocol="http", legacy_tls=True)._send("<x/>")
        assert not legacy_mounts(mount)


# --- A real TLS handshake against a local server ----------------------------


def make_certificate(tmp_path) -> tuple[str, str]:
    """Create a self-signed certificate for 127.0.0.1."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return str(cert_path), str(key_path)


def read_request(tls: ssl.SSLSocket) -> None:
    """Read a whole HTTP request, so the client is never cut off mid-send."""
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = tls.recv(65536)
        if not chunk:
            return
        data += chunk
    head, _, body = data.partition(b"\r\n\r\n")
    length = 0
    for line in head.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1])
    while len(body) < length:
        chunk = tls.recv(65536)
        if not chunk:
            return
        body += chunk


@pytest.fixture
def tls_server(tmp_path, socket_enabled: None) -> Generator[int]:
    """Serve a canned 200 response over TLS 1.2 with a self-signed certificate."""
    cert, key = make_certificate(tmp_path)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert, key)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(0.2)
    stop = threading.Event()

    def serve() -> None:
        while not stop.is_set():
            try:
                raw, _ = listener.accept()
            except (TimeoutError, OSError):
                continue
            try:
                with context.wrap_socket(raw, server_side=True) as tls:
                    read_request(tls)
                    tls.sendall(
                        b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n"
                        b"Connection: close\r\n\r\nok"
                    )
            except (ssl.SSLError, OSError):
                pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield listener.getsockname()[1]
    finally:
        stop.set()
        thread.join(timeout=2)
        listener.close()


def client_for(port: int, **kwargs: object) -> AmtClient:
    client = AmtClient("127.0.0.1", "pw", protocol="https", timeout=5, **kwargs)
    return client


@pytest.mark.parametrize("legacy_tls", [False, True])
def test_untrusted_certificate_fails_with_verification(
    tls_server: int, legacy_tls: bool
) -> None:
    """Legacy mode never turns an untrusted certificate into a success."""
    client = client_for(tls_server, verify_tls=True, legacy_tls=legacy_tls)
    with patch.object(
        AmtClient, "uri", new_callable=PropertyMock,
        return_value=f"https://127.0.0.1:{tls_server}/wsman",
    ), pytest.raises(SSLError, match="CERTIFICATE_VERIFY_FAILED"):
        client._post("<x/>")


@pytest.mark.parametrize("legacy_tls", [False, True])
def test_untrusted_certificate_connects_when_verification_is_off(
    tls_server: int, legacy_tls: bool
) -> None:
    """Disabling verification still works, with or without legacy mode."""
    client = client_for(tls_server, verify_tls=False, legacy_tls=legacy_tls)
    with patch.object(
        AmtClient, "uri", new_callable=PropertyMock,
        return_value=f"https://127.0.0.1:{tls_server}/wsman",
    ):
        assert client._post("<x/>").status_code == 200


# --- Home Assistant flows ----------------------------------------------------


async def test_user_flow_legacy_is_off_by_default(
    hass: HomeAssistant, amt_requests: list
) -> None:
    """The option is off unless chosen, and independent of verification."""
    with patch("custom_components.intel_amt.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert default_value(result, CONF_LEGACY_TLS) is False
        assert default_value(result, CONF_VERIFY_TLS) is True
        submitted = result["data_schema"](dict(BASE_DATA))
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=submitted
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LEGACY_TLS] is False
    assert amt_requests
    assert all(not legacy for _, legacy in amt_requests)


async def test_user_flow_can_opt_in_without_disabling_verification(
    hass: HomeAssistant, amt_requests: list
) -> None:
    """Legacy mode and certificate verification are separate choices."""
    with patch("custom_components.intel_amt.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={**BASE_DATA, CONF_LEGACY_TLS: True}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LEGACY_TLS] is True
    assert result["data"].get(CONF_VERIFY_TLS, True) is True
    assert amt_requests
    assert all(legacy for _, legacy in amt_requests)


async def test_certificate_error_stays_a_tls_error_in_legacy_mode(
    hass: HomeAssistant, mock_amt_post
) -> None:
    """A certificate failure is reported as such and is not retried."""
    mock_amt_post.side_effect = SSLError("CERTIFICATE_VERIFY_FAILED")
    with patch("custom_components.intel_amt.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={**BASE_DATA, CONF_LEGACY_TLS: True}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "tls_error"}
    assert mock_amt_post.call_count == 1


@pytest.mark.parametrize(
    ("data_setting", "option_setting", "expected"),
    [
        ({}, {}, False),
        ({CONF_LEGACY_TLS: True}, {}, True),
        ({CONF_LEGACY_TLS: True}, {CONF_LEGACY_TLS: False}, False),
        ({CONF_LEGACY_TLS: False}, {CONF_LEGACY_TLS: True}, True),
    ],
    ids=["legacy-default", "initial-opt-in", "options-disable", "options-enable"],
)
@pytest.mark.usefixtures("skip_entity_platforms")
async def test_runtime_legacy_precedence(
    hass: HomeAssistant,
    amt_requests: list,
    data_setting: dict,
    option_setting: dict,
    expected: bool,
) -> None:
    """Entries created before the option existed keep the standard TLS stack."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={**BASE_DATA, **data_setting}, options=option_setting
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    await hass.data[DOMAIN][entry.entry_id].async_run_power("on")
    assert amt_requests
    assert all(legacy is expected for _, legacy in amt_requests)


@pytest.mark.usefixtures("skip_entity_platforms")
async def test_legacy_mode_is_isolated_between_devices(
    hass: HomeAssistant, amt_requests: list
) -> None:
    """Enabling it for one device does not change another device."""
    entries = [
        MockConfigEntry(domain=DOMAIN, data={**BASE_DATA, CONF_LEGACY_TLS: True}),
        MockConfigEntry(domain=DOMAIN, data={**BASE_DATA, "host": "192.0.2.20"}),
    ]
    for entry in entries:
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    for entry in entries:
        await hass.data[DOMAIN][entry.entry_id].async_run_power("on")

    for host, expected in [("192.0.2.10", True), ("192.0.2.20", False)]:
        flags = [
            legacy for url, legacy in amt_requests if f"https://{host}:16993" in url
        ]
        assert flags
        assert all(flag is expected for flag in flags)


@pytest.mark.usefixtures("skip_entity_platforms", "amt_requests")
async def test_options_set_legacy_and_keep_other_settings(
    hass: HomeAssistant, amt_requests: list
) -> None:
    """The TLS options page offers both switches and preserves everything else."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**BASE_DATA, CONF_VERIFY_TLS: False},
        options={"scan_interval": 300},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "tls"}
    )
    assert default_value(result, CONF_VERIFY_TLS) is False
    assert default_value(result, CONF_LEGACY_TLS) is False
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_VERIFY_TLS: False, CONF_LEGACY_TLS: True},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        "scan_interval": 300,
        CONF_VERIFY_TLS: False,
        CONF_LEGACY_TLS: True,
    }
    amt_requests.clear()
    await hass.data[DOMAIN][entry.entry_id].async_run_power("on")
    assert amt_requests
    assert all(legacy for _, legacy in amt_requests)
