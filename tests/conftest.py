"""Shared pytest fixtures for bomberscat tests."""

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for every test automatically.

    Required by pytest-homeassistant-custom-component so that Home Assistant
    picks up custom_components/bomberscat during tests.
    """
    return enable_custom_integrations
