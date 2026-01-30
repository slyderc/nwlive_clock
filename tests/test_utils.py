#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for utils.py
"""

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSettings

from utils import settings_group, parse_seconds_value


@pytest.fixture(scope="module")
def qapp():
    """Fixture for QApplication - created once per test module"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestSettingsGroup:
    """Tests for the settings_group context manager"""

    def test_settings_group_enters_and_exits(self, qapp):
        """Test that settings_group properly enters and exits the group"""
        settings = QSettings("test_org", "test_app")

        # Write a value inside the group
        with settings_group(settings, "TestGroup"):
            settings.setValue("test_key", "test_value")

        # Verify we're outside the group (no group prefix)
        # Reading without group should not find the key
        assert settings.value("test_key") is None

        # Reading with group should find the key
        with settings_group(settings, "TestGroup"):
            assert settings.value("test_key") == "test_value"

        # Clean up
        settings.clear()

    def test_settings_group_yields_settings(self, qapp):
        """Test that settings_group yields the settings object"""
        settings = QSettings("test_org", "test_app")

        with settings_group(settings, "TestGroup") as s:
            assert s is settings

        # Clean up
        settings.clear()

    def test_settings_group_handles_exception(self, qapp):
        """Test that settings_group properly exits group even if exception occurs"""
        settings = QSettings("test_org", "test_app")

        try:
            with settings_group(settings, "TestGroup"):
                settings.setValue("test_key", "test_value")
                raise ValueError("Test exception")
        except ValueError:
            pass

        # After exception, we should still be outside the group
        # The group should have been properly ended
        with settings_group(settings, "TestGroup"):
            assert settings.value("test_key") == "test_value"

        # Clean up
        settings.clear()


class TestParseSecondsValue:
    """Tests for the parse_seconds_value function"""

    def test_integer_string(self):
        """Test parsing an integer string"""
        assert parse_seconds_value("312") == 312

    def test_fractional_rounds_down(self):
        """Test that fractional values round down when < 0.5"""
        assert parse_seconds_value("312.38") == 312

    def test_fractional_rounds_up(self):
        """Test that fractional values round up when >= 0.5"""
        assert parse_seconds_value("312.78") == 313

    def test_exactly_half_rounds_up(self):
        """Test that 0.5 rounds to nearest even (banker's rounding)"""
        # Python's round() uses banker's rounding: 312.5 -> 312 (even), 313.5 -> 314 (even)
        assert parse_seconds_value("312.5") == 312  # rounds to even
        assert parse_seconds_value("313.5") == 314  # rounds to even

    def test_zero(self):
        """Test parsing zero values"""
        assert parse_seconds_value("0") == 0
        assert parse_seconds_value("0.4") == 0

    def test_zero_point_five(self):
        """Test parsing 0.5"""
        assert parse_seconds_value("0.5") == 0  # rounds to even (0)

    def test_large_value(self):
        """Test parsing large values"""
        assert parse_seconds_value("86400") == 86400
        assert parse_seconds_value("86400.4") == 86400

    def test_invalid_raises_valueerror(self):
        """Test that invalid values raise ValueError"""
        with pytest.raises(ValueError):
            parse_seconds_value("abc")
        with pytest.raises(ValueError):
            parse_seconds_value("")
        with pytest.raises(ValueError):
            parse_seconds_value("12.34.56")

    def test_negative_value(self):
        """Test parsing negative values (valid float, but will fail validation later)"""
        assert parse_seconds_value("-5") == -5
        assert parse_seconds_value("-5.5") == -6  # rounds away from zero for negative
