"""Regression tests for per-device TLS verification and Home Assistant flows."""

from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import SSLError

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intel_amt.const import CONF_VERIFY_TLS, DOMAIN

BASE_DATA = {
    "host": "192.0.2.10",
    "username": "admin",
    "password": "test-password",
    "protocol": "https",
    "name": "Workstation",
}


def suggested_value(result: dict, name: str) -> object:
    """Read the value offered by a form, whether suggested or a default."""
    marker = next(key for key in result["data_schema"].schema if key.schema == name)
    if marker.description and "suggested_value" in marker.description:
        return marker.description["suggested_value"]
    return marker.default()


@pytest.mark.parametrize("verify_tls", [True, False])
async def test_user_flow_verification(
    hass: HomeAssistant, mock_amt_post: MagicMock, verify_tls: bool
) -> None:
    """A new device verifies by default and can explicitly opt out."""
    with patch("custom_components.intel_amt.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert suggested_value(result, CONF_VERIFY_TLS) is True
        submitted = dict(BASE_DATA)
        if not verify_tls:
            submitted[CONF_VERIFY_TLS] = False
        # Apply the actual form schema, including its default for an omitted flag.
        submitted = result["data_schema"](submitted)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=submitted
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_VERIFY_TLS] is verify_tls
    assert mock_amt_post.call_args_list
    assert all(
        call.kwargs["verify"] is verify_tls for call in mock_amt_post.call_args_list
    )


async def test_ssl_error_requires_explicit_opt_out(
    hass: HomeAssistant, mock_amt_post: MagicMock
) -> None:
    """A certificate error never silently retries insecurely or redisplays a secret."""
    successful_response = mock_amt_post.side_effect
    mock_amt_post.side_effect = SSLError("self-signed certificate")
    with patch("custom_components.intel_amt.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=BASE_DATA
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "tls_error"}
        assert mock_amt_post.call_count == 1
        assert mock_amt_post.call_args.kwargs["verify"] is True
        for name in ("host", "username", "protocol", "name"):
            assert suggested_value(result, name) == BASE_DATA[name]
        assert suggested_value(result, CONF_VERIFY_TLS) is True
        password_field = next(
            key for key in result["data_schema"].schema if key.schema == "password"
        )
        assert "suggested_value" not in (password_field.description or {})

        # Only an explicit second submission may disable certificate verification.
        mock_amt_post.side_effect = successful_response
        mock_amt_post.reset_mock()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={**BASE_DATA, CONF_VERIFY_TLS: False}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_VERIFY_TLS] is False
    assert mock_amt_post.call_args_list
    assert all(
        call.kwargs["verify"] is False for call in mock_amt_post.call_args_list
    )


@pytest.mark.parametrize(
    ("data_setting", "option_setting", "expected"),
    [
        ({}, {}, True),
        ({CONF_VERIFY_TLS: False}, {}, False),
        ({CONF_VERIFY_TLS: True}, {CONF_VERIFY_TLS: False}, False),
        ({CONF_VERIFY_TLS: False}, {CONF_VERIFY_TLS: True}, True),
    ],
    ids=["legacy-default", "initial-opt-out", "options-disable", "options-reenable"],
)
@pytest.mark.usefixtures("skip_entity_platforms")
async def test_runtime_verification_precedence(
    hass: HomeAssistant,
    mock_amt_post: MagicMock,
    data_setting: dict,
    option_setting: dict,
    expected: bool,
) -> None:
    """Legacy defaults and options apply to polling and real client power requests."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={**BASE_DATA, **data_setting}, options=option_setting
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_run_power("on")
    assert mock_amt_post.call_args_list
    assert all(
        call.kwargs["verify"] is expected for call in mock_amt_post.call_args_list
    )
    assert all(
        call.args[0] == "https://192.0.2.10:16993/wsman"
        for call in mock_amt_post.call_args_list
    )
    assert any(
        "RequestPowerStateChange_INPUT" in call.kwargs["data"]
        for call in mock_amt_post.call_args_list
    )


@pytest.mark.usefixtures("skip_entity_platforms")
async def test_verification_is_isolated_between_devices(
    hass: HomeAssistant, mock_amt_post: MagicMock
) -> None:
    """One device's exception does not weaken another device's TLS connections."""
    entries = [
        MockConfigEntry(domain=DOMAIN, data={**BASE_DATA, CONF_VERIFY_TLS: False}),
        MockConfigEntry(domain=DOMAIN, data={**BASE_DATA, "host": "192.0.2.20"}),
    ]
    for entry in entries:
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    for entry in entries:
        await hass.data[DOMAIN][entry.entry_id].async_run_power("on")

    for host, expected in [("192.0.2.10", False), ("192.0.2.20", True)]:
        calls = [
            call
            for call in mock_amt_post.call_args_list
            if call.args[0] == f"https://{host}:16993/wsman"
        ]
        assert calls
        assert all(call.kwargs["verify"] is expected for call in calls)


@pytest.mark.usefixtures("skip_entity_platforms")
async def test_options_preserve_settings_and_reload(
    hass: HomeAssistant, mock_amt_post: MagicMock
) -> None:
    """TLS options reload the client, can be reversed, and preserve polling settings."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**BASE_DATA, CONF_VERIFY_TLS: True},
        options={"scan_interval": 300},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    scan_interval = 300
    for current_value, new_value in [(True, False), (False, True)]:
        previous_coordinator = hass.data[DOMAIN][entry.entry_id]
        with patch.object(
            hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
        ) as reload_entry:
            result = await hass.config_entries.options.async_init(entry.entry_id)
            assert "tls" in result["menu_options"]
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], user_input={"next_step_id": "tls"}
            )
            assert suggested_value(result, CONF_VERIFY_TLS) is current_value
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], user_input={CONF_VERIFY_TLS: new_value}
            )
            await hass.async_block_till_done()
            reload_entry.assert_awaited_once_with(entry.entry_id)

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options == {
            "scan_interval": scan_interval,
            CONF_VERIFY_TLS: new_value,
        }
        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert coordinator is not previous_coordinator
        mock_amt_post.reset_mock()
        await coordinator.async_run_power("on")
        assert mock_amt_post.call_args_list
        assert all(
            call.kwargs["verify"] is new_value for call in mock_amt_post.call_args_list
        )

        if new_value is False:
            # Updating the other page must preserve an explicit False, too.
            result = await hass.config_entries.options.async_init(entry.entry_id)
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], user_input={"next_step_id": "scan_interval"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], user_input={"scan_interval": 600}
            )
            await hass.async_block_till_done()
            assert result["type"] is FlowResultType.CREATE_ENTRY
            assert entry.options == {"scan_interval": 600, CONF_VERIFY_TLS: False}
            scan_interval = 600
