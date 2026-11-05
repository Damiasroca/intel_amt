"""Run real Home Assistant flows with the AMT HTTP transport mocked."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from requests import Response


@pytest.fixture(autouse=True)
def enable_integration(enable_custom_integrations: None) -> None:
    """Make the repository's custom integration available to Home Assistant."""


@pytest.fixture
def mock_amt_post() -> Generator[MagicMock]:
    """Return minimal WS-Man responses without contacting or powering a device."""

    def respond(url: str, *, data: str, **kwargs: object) -> Response:
        if "RequestPowerStateChange_INPUT" in data:
            body = "<Response><ReturnValue>0</ReturnValue></Response>"
        elif "CIM_AssociatedPowerManagementService" in data:
            body = "<Response><PowerState>2</PowerState></Response>"
        else:
            # Empty inventory/optional-feature enumeration, without a next page.
            body = "<EnumerateResponse/>"
        response = Response()
        response.status_code = 200
        response.url = url
        response._content = (
            '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
            f"<s:Body>{body}</s:Body></s:Envelope>"
        ).encode()
        return response

    with patch(
        "custom_components.intel_amt.amt_client.requests.post", side_effect=respond
    ) as mocked:
        yield mocked


@pytest.fixture
def skip_entity_platforms() -> Generator[None]:
    """Keep lifecycle tests focused on connection settings, not entity behavior."""
    with patch("custom_components.intel_amt.coordinator.PLATFORMS", []):
        yield
