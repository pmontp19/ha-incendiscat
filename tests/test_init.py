"""Smoke test for the bomberscat integration scaffold."""

from custom_components.bomberscat.const import DOMAIN


def test_domain() -> None:
    """The integration domain must be 'bomberscat'."""
    assert DOMAIN == "bomberscat"
