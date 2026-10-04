"""
Unit tests for time_formatter.py
"""

import pytest

from time_formatter import TimeFormatter


class TestEnglishQuarterTo:
    """Tests for the English "quarter to" hour rollover"""

    @pytest.mark.parametrize("hour, expected", [
        (11, "It's a quarter to 12"),
        (12, "It's a quarter to 1"),
        (23, "It's a quarter to 12"),
    ])
    def test_quarter_to_wraps_after_twelve(self, hour, expected):
        """Test that xx:45 names the next hour on a 12-hour dial"""
        assert TimeFormatter.format_time(hour, 45, "English") == expected


class TestEnglishMidnightHour:
    """Tests for the English text clock in the hour after midnight"""

    @pytest.mark.parametrize("minute, expected", [
        (0, "It's 12 o'clock"),
        (10, "It's 10 minutes past 12"),
        (15, "It's a quarter-past 12"),
        (30, "It's half-past 12"),
        (45, "It's a quarter to 1"),
        (50, "It's 10 minutes to 1"),
    ])
    def test_hour_zero_reads_as_twelve(self, minute, expected):
        """Test that 00:xx is spoken as 12, never 0"""
        assert TimeFormatter.format_time(0, minute, "English") == expected
