#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for stream_monitor.py
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from PyQt6.QtWidgets import QApplication

# Import after QApplication setup
import sys
if not QApplication.instance():
    app = QApplication(sys.argv)


class TestStreamCheckThread:
    """Tests for StreamCheckThread"""

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.urllib.request.urlopen')
    def test_run_success(self, mock_urlopen, mock_del):
        """Test StreamCheckThread.run() with successful stream check"""
        from stream_monitor import StreamCheckThread

        # Create mock monitor
        mock_monitor = Mock()
        mock_monitor.stream_url = "http://example.com/stream"
        mock_monitor._last_check_success = False

        # Mock urlopen response
        mock_response = Mock()
        mock_response.read.return_value = b'audio data here'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        # Create thread without initializing QThread properly
        thread = StreamCheckThread.__new__(StreamCheckThread)
        thread.monitor = mock_monitor
        thread._initialized = True

        # Run the thread logic
        thread.run()

        # Verify success was recorded
        assert mock_monitor._last_check_success is True

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.urllib.request.urlopen')
    def test_run_empty_response(self, mock_urlopen, mock_del):
        """Test StreamCheckThread.run() with empty response (stream offline)"""
        from stream_monitor import StreamCheckThread

        mock_monitor = Mock()
        mock_monitor.stream_url = "http://example.com/stream"
        mock_monitor._last_check_success = True

        mock_response = Mock()
        mock_response.read.return_value = b''
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        thread = StreamCheckThread.__new__(StreamCheckThread)
        thread.monitor = mock_monitor
        thread._initialized = True

        thread.run()

        assert mock_monitor._last_check_success is False

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.urllib.request.urlopen')
    def test_run_http_error(self, mock_urlopen, mock_del):
        """Test StreamCheckThread.run() with HTTP error"""
        from stream_monitor import StreamCheckThread
        import urllib.error

        mock_monitor = Mock()
        mock_monitor.stream_url = "http://example.com/stream"
        mock_monitor._last_check_success = True

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://example.com/stream",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )

        thread = StreamCheckThread.__new__(StreamCheckThread)
        thread.monitor = mock_monitor
        thread._initialized = True

        thread.run()

        assert mock_monitor._last_check_success is False

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.urllib.request.urlopen')
    def test_run_url_error(self, mock_urlopen, mock_del):
        """Test StreamCheckThread.run() with URL error (network unreachable)"""
        from stream_monitor import StreamCheckThread
        import urllib.error

        mock_monitor = Mock()
        mock_monitor.stream_url = "http://example.com/stream"
        mock_monitor._last_check_success = True

        mock_urlopen.side_effect = urllib.error.URLError("Network unreachable")

        thread = StreamCheckThread.__new__(StreamCheckThread)
        thread.monitor = mock_monitor
        thread._initialized = True

        thread.run()

        assert mock_monitor._last_check_success is False

    @patch('stream_monitor.StreamCheckThread.__del__')
    def test_run_no_url(self, mock_del):
        """Test StreamCheckThread.run() with no URL configured"""
        from stream_monitor import StreamCheckThread

        mock_monitor = Mock()
        mock_monitor.stream_url = ""
        mock_monitor._last_check_success = True

        thread = StreamCheckThread.__new__(StreamCheckThread)
        thread.monitor = mock_monitor
        thread._initialized = True

        thread.run()

        assert mock_monitor._last_check_success is False


class TestStreamMonitorConfig:
    """Tests for StreamMonitor configuration loading"""

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.QTimer')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_load_config_defaults(self, mock_settings_group, mock_qsettings, mock_qtimer, mock_del):
        """Test that defaults are loaded correctly"""
        from stream_monitor import StreamMonitor
        from defaults import (
            DEFAULT_STREAM_MONITOR_ENABLED,
            DEFAULT_STREAM_MONITOR_URL,
            DEFAULT_STREAM_MONITOR_POLL_INTERVAL,
            DEFAULT_STREAM_MONITOR_OFFLINE_THRESHOLD,
        )

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: default
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        assert monitor._enabled == DEFAULT_STREAM_MONITOR_ENABLED
        assert monitor._stream_url == DEFAULT_STREAM_MONITOR_URL
        assert monitor._poll_interval == DEFAULT_STREAM_MONITOR_POLL_INTERVAL
        assert monitor._offline_threshold == DEFAULT_STREAM_MONITOR_OFFLINE_THRESHOLD

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.QTimer')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_load_config_custom(self, mock_settings_group, mock_qsettings, mock_qtimer, mock_del):
        """Test that custom settings are loaded correctly"""
        from stream_monitor import StreamMonitor

        custom_values = {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live.m3u',
            'streamMonitorPollInterval': 5,
            'streamMonitorOfflineThreshold': 15,
        }

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: custom_values.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        assert monitor._enabled is True
        assert monitor._stream_url == 'http://stream.example.com/live.m3u'
        assert monitor._poll_interval == 5
        assert monitor._offline_threshold == 15


class TestStreamMonitorM3UParsing:
    """Tests for .m3u playlist parsing"""

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.QTimer')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    @patch('stream_monitor.urllib.request.urlopen')
    def test_resolve_m3u_simple(self, mock_urlopen, mock_settings_group, mock_qsettings, mock_qtimer, mock_del):
        """Test parsing simple .m3u playlist"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/play.m3u',
            'streamMonitorPollInterval': 3,
            'streamMonitorOfflineThreshold': 10,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        # Mock .m3u response
        mock_response = Mock()
        mock_response.read.return_value = b'http://actual-stream.example.com/live\n'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        assert monitor._resolved_stream_url == 'http://actual-stream.example.com/live'

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.QTimer')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    @patch('stream_monitor.urllib.request.urlopen')
    def test_resolve_m3u_with_comments(self, mock_urlopen, mock_settings_group, mock_qsettings, mock_qtimer, mock_del):
        """Test parsing .m3u playlist with comments"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/play.m3u',
            'streamMonitorPollInterval': 3,
            'streamMonitorOfflineThreshold': 10,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        # Mock .m3u response with comments
        mock_response = Mock()
        mock_response.read.return_value = b'#EXTM3U\n#EXTINF:-1,Stream Title\nhttp://actual-stream.example.com/live\n'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        assert monitor._resolved_stream_url == 'http://actual-stream.example.com/live'

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.QTimer')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_resolve_direct_url(self, mock_settings_group, mock_qsettings, mock_qtimer, mock_del):
        """Test that direct stream URL (non-.m3u) is used as-is"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorPollInterval': 3,
            'streamMonitorOfflineThreshold': 10,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        assert monitor._resolved_stream_url == 'http://stream.example.com/live'


class TestStreamMonitorStateMachine:
    """Tests for stream monitor state machine"""

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.QTimer')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_state_unknown_to_online(self, mock_settings_group, mock_qsettings, mock_qtimer, mock_del):
        """Test transition from UNKNOWN to ONLINE when stream comes online"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorPollInterval': 3,
            'streamMonitorOfflineThreshold': 10,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        mock_main_screen.stream_timer_reset = Mock()
        mock_main_screen.start_air4 = Mock()

        monitor = StreamMonitor(mock_main_screen)

        # Simulate check thread completing
        monitor._check_thread = Mock()
        monitor._check_thread.isRunning.return_value = False
        monitor._check_thread.start = Mock()

        # Set successful check result
        monitor._last_check_success = True

        # Trigger timer tick
        monitor._on_timer_tick()

        # Verify state changed to online
        assert monitor._is_online is True
        mock_main_screen.stream_timer_reset.assert_called_once()
        mock_main_screen.start_air4.assert_called_once()

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.QTimer')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_state_online_to_failing(self, mock_settings_group, mock_qsettings, mock_qtimer, mock_del):
        """Test transition from ONLINE to FAILING when check fails"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorPollInterval': 3,
            'streamMonitorOfflineThreshold': 10,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        # Set initial state as online
        monitor._is_online = True
        monitor._consecutive_failures = 0

        # Simulate check thread
        monitor._check_thread = Mock()
        monitor._check_thread.isRunning.return_value = False
        monitor._check_thread.start = Mock()

        # Set failed check result
        monitor._last_check_success = False

        # Trigger timer tick
        monitor._on_timer_tick()

        # Verify failure counter incremented but still online (threshold not reached)
        assert monitor._consecutive_failures == 1
        assert monitor._is_online is True  # Still online, threshold not reached

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.QTimer')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_state_failing_to_offline(self, mock_settings_group, mock_qsettings, mock_qtimer, mock_del):
        """Test transition from FAILING to OFFLINE when threshold reached"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorPollInterval': 3,
            'streamMonitorOfflineThreshold': 10,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        mock_main_screen.stop_air4 = Mock()

        monitor = StreamMonitor(mock_main_screen)

        # Set initial state as online with failures approaching threshold
        monitor._is_online = True
        monitor._consecutive_failures = 3  # 3 * 3 = 9 seconds, need one more to exceed 10

        monitor._check_thread = Mock()
        monitor._check_thread.isRunning.return_value = False
        monitor._check_thread.start = Mock()

        # Set failed check result
        monitor._last_check_success = False

        # Trigger timer tick
        monitor._on_timer_tick()

        # Now at 4 * 3 = 12 seconds >= 10 second threshold
        assert monitor._consecutive_failures == 4
        assert monitor._is_online is False
        mock_main_screen.stop_air4.assert_called_once()

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.QTimer')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_state_offline_to_online(self, mock_settings_group, mock_qsettings, mock_qtimer, mock_del):
        """Test transition from OFFLINE back to ONLINE"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorPollInterval': 3,
            'streamMonitorOfflineThreshold': 10,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        mock_main_screen.stream_timer_reset = Mock()
        mock_main_screen.start_air4 = Mock()

        monitor = StreamMonitor(mock_main_screen)

        # Set initial state as offline
        monitor._is_online = False
        monitor._consecutive_failures = 5

        monitor._check_thread = Mock()
        monitor._check_thread.isRunning.return_value = False
        monitor._check_thread.start = Mock()

        # Set successful check result
        monitor._last_check_success = True

        # Trigger timer tick
        monitor._on_timer_tick()

        # Verify state changed to online
        assert monitor._is_online is True
        assert monitor._consecutive_failures == 0
        mock_main_screen.stream_timer_reset.assert_called_once()
        mock_main_screen.start_air4.assert_called_once()


class TestStreamMonitorMethods:
    """Tests for StreamMonitor public methods"""

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.QTimer')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_is_enabled_true(self, mock_settings_group, mock_qsettings, mock_qtimer, mock_del):
        """Test is_enabled() returns True when enabled"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorPollInterval': 3,
            'streamMonitorOfflineThreshold': 10,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        assert monitor.is_enabled() is True

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.QTimer')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_is_enabled_false(self, mock_settings_group, mock_qsettings, mock_qtimer, mock_del):
        """Test is_enabled() returns False when disabled"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': False,
            'streamMonitorUrl': '',
            'streamMonitorPollInterval': 3,
            'streamMonitorOfflineThreshold': 10,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        assert monitor.is_enabled() is False

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.QTimer')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_is_online(self, mock_settings_group, mock_qsettings, mock_qtimer, mock_del):
        """Test is_online() returns correct state"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': False,
            'streamMonitorUrl': '',
            'streamMonitorPollInterval': 3,
            'streamMonitorOfflineThreshold': 10,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        assert monitor.is_online() is False

        monitor._is_online = True
        assert monitor.is_online() is True

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.QTimer')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_stop(self, mock_settings_group, mock_qsettings, mock_qtimer, mock_del):
        """Test stop() stops timer and thread"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': False,
            'streamMonitorUrl': '',
            'streamMonitorPollInterval': 3,
            'streamMonitorOfflineThreshold': 10,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_timer = Mock()
        mock_qtimer.return_value = mock_timer

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)
        monitor._check_thread = Mock()

        monitor.stop()

        mock_timer.stop.assert_called_once()
        monitor._check_thread.stop.assert_called_once()


class TestStreamMonitorBriefInterruption:
    """Tests for handling brief stream interruptions"""

    @patch('stream_monitor.StreamCheckThread.__del__')
    @patch('stream_monitor.QTimer')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_brief_interruption_stays_online(self, mock_settings_group, mock_qsettings, mock_qtimer, mock_del):
        """Test that brief interruption (<threshold) keeps stream online"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorPollInterval': 3,
            'streamMonitorOfflineThreshold': 10,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        mock_main_screen.stop_air4 = Mock()

        monitor = StreamMonitor(mock_main_screen)

        # Set initial state as online
        monitor._is_online = True
        monitor._consecutive_failures = 0

        monitor._check_thread = Mock()
        monitor._check_thread.isRunning.return_value = False
        monitor._check_thread.start = Mock()

        # Simulate 2 failed checks (6 seconds, less than 10 second threshold)
        monitor._last_check_success = False
        monitor._on_timer_tick()  # 3 seconds
        monitor._on_timer_tick()  # 6 seconds

        # Should still be online
        assert monitor._is_online is True
        assert monitor._consecutive_failures == 2
        mock_main_screen.stop_air4.assert_not_called()

        # Stream comes back
        monitor._last_check_success = True
        monitor._on_timer_tick()

        # Should remain online with reset failure counter
        assert monitor._is_online is True
        assert monitor._consecutive_failures == 0


class TestStreamMonitorDefaults:
    """Tests for stream monitor default values"""

    def test_defaults_exist(self):
        """Test that all default constants are defined"""
        from defaults import (
            DEFAULT_STREAM_MONITOR_ENABLED,
            DEFAULT_STREAM_MONITOR_URL,
            DEFAULT_STREAM_MONITOR_POLL_INTERVAL,
            DEFAULT_STREAM_MONITOR_OFFLINE_THRESHOLD,
        )

        assert DEFAULT_STREAM_MONITOR_ENABLED is True
        assert DEFAULT_STREAM_MONITOR_URL == "http://zipstream.climate.local/play.m3u"
        assert DEFAULT_STREAM_MONITOR_POLL_INTERVAL == 3
        assert DEFAULT_STREAM_MONITOR_OFFLINE_THRESHOLD == 10

    def test_get_default_stream_monitoring_group(self):
        """Test get_default() returns correct values for StreamMonitoring group"""
        from defaults import get_default

        assert get_default("StreamMonitoring", "streamMonitorEnabled") is True
        assert get_default("StreamMonitoring", "streamMonitorUrl") == "http://zipstream.climate.local/play.m3u"
        assert get_default("StreamMonitoring", "streamMonitorPollInterval") == 3
        assert get_default("StreamMonitoring", "streamMonitorOfflineThreshold") == 10

    def test_get_default_unknown_key(self):
        """Test get_default() returns None for unknown key"""
        from defaults import get_default

        assert get_default("StreamMonitoring", "unknownKey") is None
        assert get_default("StreamMonitoring", "unknownKey", "default") == "default"
