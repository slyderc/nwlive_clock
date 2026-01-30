#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for stream_monitor.py

Tests the continuous connection approach for stream monitoring.
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from PyQt6.QtWidgets import QApplication

# Import after QApplication setup
import sys
if not QApplication.instance():
    app = QApplication(sys.argv)


class TestStreamMonitorThread:
    """Tests for StreamMonitorThread"""

    @patch('stream_monitor.StreamMonitorThread.__del__')
    @patch('stream_monitor.urllib.request.urlopen')
    def test_run_emits_online_signal(self, mock_urlopen, mock_del):
        """Test that stream_online signal is emitted when connection established"""
        from stream_monitor import StreamMonitorThread

        # Mock response that returns data then raises to exit
        mock_response = Mock()
        mock_response.read.side_effect = [b'audio data', ConnectionError("test exit")]
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        # Create thread
        thread = StreamMonitorThread.__new__(StreamMonitorThread)
        thread._stream_url = "http://example.com/stream"
        thread._offline_threshold = 10
        thread._reconnect_delay = 5
        thread._running = False  # Will stop after first iteration
        thread._is_online = False
        thread._initialized = True
        thread.stream_online = Mock()
        thread.stream_offline = Mock()

        # Run _monitor_stream directly
        try:
            thread._running = True
            thread._monitor_stream()
        except ConnectionError:
            pass

        # Verify online signal was emitted
        thread.stream_online.emit.assert_called_once()

    @patch('stream_monitor.StreamMonitorThread.__del__')
    @patch('stream_monitor.urllib.request.urlopen')
    def test_run_emits_offline_on_empty_read(self, mock_urlopen, mock_del):
        """Test that offline signal is emitted when stream returns empty data"""
        from stream_monitor import StreamMonitorThread

        mock_response = Mock()
        mock_response.read.return_value = b''  # Empty read = stream ended
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        thread = StreamMonitorThread.__new__(StreamMonitorThread)
        thread._stream_url = "http://example.com/stream"
        thread._offline_threshold = 10
        thread._reconnect_delay = 5
        thread._running = True
        thread._is_online = False
        thread._initialized = True
        thread.stream_online = Mock()
        thread.stream_offline = Mock()

        # Should raise ConnectionError on empty read
        with pytest.raises(ConnectionError, match="empty read"):
            thread._monitor_stream()

    @patch('stream_monitor.StreamMonitorThread.__del__')
    @patch('stream_monitor.urllib.request.urlopen')
    def test_run_http_error(self, mock_urlopen, mock_del):
        """Test that connection errors are raised"""
        from stream_monitor import StreamMonitorThread
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://example.com/stream",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )

        thread = StreamMonitorThread.__new__(StreamMonitorThread)
        thread._stream_url = "http://example.com/stream"
        thread._offline_threshold = 10
        thread._reconnect_delay = 5
        thread._running = True
        thread._is_online = False
        thread._initialized = True
        thread.stream_online = Mock()
        thread.stream_offline = Mock()

        with pytest.raises(urllib.error.HTTPError):
            thread._monitor_stream()

    @patch('stream_monitor.StreamMonitorThread.__del__')
    @patch('stream_monitor.urllib.request.urlopen')
    def test_run_url_error(self, mock_urlopen, mock_del):
        """Test that URL errors are raised"""
        from stream_monitor import StreamMonitorThread
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("Network unreachable")

        thread = StreamMonitorThread.__new__(StreamMonitorThread)
        thread._stream_url = "http://example.com/stream"
        thread._offline_threshold = 10
        thread._reconnect_delay = 5
        thread._running = True
        thread._is_online = False
        thread._initialized = True
        thread.stream_online = Mock()
        thread.stream_offline = Mock()

        with pytest.raises(urllib.error.URLError):
            thread._monitor_stream()

    @patch('stream_monitor.StreamMonitorThread.__del__')
    def test_run_no_url(self, mock_del):
        """Test that ValueError is raised with no URL configured"""
        from stream_monitor import StreamMonitorThread

        thread = StreamMonitorThread.__new__(StreamMonitorThread)
        thread._stream_url = ""
        thread._offline_threshold = 10
        thread._reconnect_delay = 5
        thread._running = True
        thread._is_online = False
        thread._initialized = True
        thread.stream_online = Mock()
        thread.stream_offline = Mock()

        with pytest.raises(ValueError, match="No stream URL"):
            thread._monitor_stream()

    @patch('stream_monitor.StreamMonitorThread.__del__')
    def test_run_none_url(self, mock_del):
        """Test that ValueError is raised with None URL"""
        from stream_monitor import StreamMonitorThread

        thread = StreamMonitorThread.__new__(StreamMonitorThread)
        thread._stream_url = None
        thread._offline_threshold = 10
        thread._reconnect_delay = 5
        thread._running = True
        thread._is_online = False
        thread._initialized = True
        thread.stream_online = Mock()
        thread.stream_offline = Mock()

        with pytest.raises(ValueError, match="No stream URL"):
            thread._monitor_stream()

    @patch('stream_monitor.StreamMonitorThread.__del__')
    def test_stop(self, mock_del):
        """Test that stop() sets _running to False"""
        from stream_monitor import StreamMonitorThread

        thread = StreamMonitorThread.__new__(StreamMonitorThread)
        thread._running = True
        thread._initialized = True

        thread.stop()

        assert thread._running is False

    @patch('stream_monitor.StreamMonitorThread.__del__')
    def test_is_online(self, mock_del):
        """Test that is_online() returns correct state"""
        from stream_monitor import StreamMonitorThread

        thread = StreamMonitorThread.__new__(StreamMonitorThread)
        thread._is_online = False
        thread._initialized = True

        assert thread.is_online() is False

        thread._is_online = True
        assert thread.is_online() is True

    @patch('stream_monitor.StreamMonitorThread.__del__')
    @patch('stream_monitor.time.sleep')
    def test_sleep_with_check_stops_early(self, mock_sleep, mock_del):
        """Test that _sleep_with_check exits early when _running becomes False"""
        from stream_monitor import StreamMonitorThread

        thread = StreamMonitorThread.__new__(StreamMonitorThread)
        thread._running = True
        thread._initialized = True

        # After 5 sleep calls, set _running to False
        call_count = [0]
        def side_effect(duration):
            call_count[0] += 1
            if call_count[0] >= 5:
                thread._running = False

        mock_sleep.side_effect = side_effect

        thread._sleep_with_check(10)  # Would be 100 iterations normally

        # Should have exited early
        assert call_count[0] == 5


class TestStreamMonitorConfig:
    """Tests for StreamMonitor configuration loading"""

    @patch('stream_monitor.StreamMonitorThread')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_load_config_defaults(self, mock_settings_group, mock_qsettings, mock_thread):
        """Test that defaults are loaded correctly"""
        from stream_monitor import StreamMonitor
        from defaults import (
            DEFAULT_STREAM_MONITOR_ENABLED,
            DEFAULT_STREAM_MONITOR_URL,
            DEFAULT_STREAM_MONITOR_OFFLINE_THRESHOLD,
            DEFAULT_STREAM_MONITOR_RECONNECT_DELAY,
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
        assert monitor._offline_threshold == DEFAULT_STREAM_MONITOR_OFFLINE_THRESHOLD
        assert monitor._reconnect_delay == DEFAULT_STREAM_MONITOR_RECONNECT_DELAY

    @patch('stream_monitor.StreamMonitorThread')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_load_config_custom(self, mock_settings_group, mock_qsettings, mock_thread):
        """Test that custom settings are loaded correctly"""
        from stream_monitor import StreamMonitor

        custom_values = {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live.m3u',
            'streamMonitorOfflineThreshold': 15,
            'streamMonitorReconnectDelay': 10,
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
        assert monitor._offline_threshold == 15
        assert monitor._reconnect_delay == 10


class TestStreamMonitorM3UParsing:
    """Tests for .m3u playlist parsing"""

    @patch('stream_monitor.StreamMonitorThread')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    @patch('stream_monitor.urllib.request.urlopen')
    def test_resolve_m3u_simple(self, mock_urlopen, mock_settings_group, mock_qsettings, mock_thread):
        """Test parsing simple .m3u playlist"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/play.m3u',
            'streamMonitorOfflineThreshold': 10,
            'streamMonitorReconnectDelay': 5,
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

    @patch('stream_monitor.StreamMonitorThread')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    @patch('stream_monitor.urllib.request.urlopen')
    def test_resolve_m3u_with_comments(self, mock_urlopen, mock_settings_group, mock_qsettings, mock_thread):
        """Test parsing .m3u playlist with comments"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/play.m3u',
            'streamMonitorOfflineThreshold': 10,
            'streamMonitorReconnectDelay': 5,
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

    @patch('stream_monitor.StreamMonitorThread')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_resolve_direct_url(self, mock_settings_group, mock_qsettings, mock_thread):
        """Test that direct stream URL (non-.m3u) is used as-is"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorOfflineThreshold': 10,
            'streamMonitorReconnectDelay': 5,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        assert monitor._resolved_stream_url == 'http://stream.example.com/live'


class TestStreamMonitorSignals:
    """Tests for signal-based state handling"""

    @patch('stream_monitor.StreamMonitorThread')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_on_stream_online_starts_air4(self, mock_settings_group, mock_qsettings, mock_thread):
        """Test that _on_stream_online starts AIR4 with timer reset"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorOfflineThreshold': 10,
            'streamMonitorReconnectDelay': 5,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        mock_main_screen.stream_timer_reset = Mock()
        mock_main_screen.start_air4 = Mock()

        monitor = StreamMonitor(mock_main_screen)

        # Call the handler directly
        monitor._on_stream_online()

        mock_main_screen.stream_timer_reset.assert_called_once()
        mock_main_screen.start_air4.assert_called_once()

    @patch('stream_monitor.StreamMonitorThread')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_on_stream_offline_stops_air4(self, mock_settings_group, mock_qsettings, mock_thread):
        """Test that _on_stream_offline stops AIR4"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorOfflineThreshold': 10,
            'streamMonitorReconnectDelay': 5,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        mock_main_screen.stop_air4 = Mock()

        monitor = StreamMonitor(mock_main_screen)

        # Call the handler directly
        monitor._on_stream_offline()

        mock_main_screen.stop_air4.assert_called_once()


class TestStreamMonitorMethods:
    """Tests for StreamMonitor public methods"""

    @patch('stream_monitor.StreamMonitorThread')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_is_enabled_true(self, mock_settings_group, mock_qsettings, mock_thread):
        """Test is_enabled() returns True when enabled"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorOfflineThreshold': 10,
            'streamMonitorReconnectDelay': 5,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        assert monitor.is_enabled() is True

    @patch('stream_monitor.StreamMonitorThread')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_is_enabled_false(self, mock_settings_group, mock_qsettings, mock_thread):
        """Test is_enabled() returns False when disabled"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': False,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorOfflineThreshold': 10,
            'streamMonitorReconnectDelay': 5,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        assert monitor.is_enabled() is False

    @patch('stream_monitor.StreamMonitorThread')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_is_online_no_thread(self, mock_settings_group, mock_qsettings, mock_thread):
        """Test is_online() returns False when no thread"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': False,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorOfflineThreshold': 10,
            'streamMonitorReconnectDelay': 5,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)
        monitor._monitor_thread = None

        assert monitor.is_online() is False

    @patch('stream_monitor.StreamMonitorThread')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_is_online_from_thread(self, mock_settings_group, mock_qsettings, mock_thread_class):
        """Test is_online() returns thread's online state"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorOfflineThreshold': 10,
            'streamMonitorReconnectDelay': 5,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_thread = Mock()
        mock_thread.is_online.return_value = True
        mock_thread_class.return_value = mock_thread

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        assert monitor.is_online() is True
        mock_thread.is_online.assert_called()

    @patch('stream_monitor.StreamMonitorThread')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_stop(self, mock_settings_group, mock_qsettings, mock_thread_class):
        """Test stop() stops thread"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorOfflineThreshold': 10,
            'streamMonitorReconnectDelay': 5,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        monitor.stop()

        mock_thread.stop.assert_called()
        mock_thread.wait.assert_called_with(5000)
        assert monitor._monitor_thread is None

    @patch('stream_monitor.StreamMonitorThread')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_restart_resets_and_restarts(self, mock_settings_group, mock_qsettings, mock_thread_class):
        """Test restart() resets state and restarts"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorOfflineThreshold': 10,
            'streamMonitorReconnectDelay': 5,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        # Set some state
        monitor._resolved_stream_url = "http://old-url.com/stream"

        monitor.restart()

        # Verify old thread was stopped
        mock_thread.stop.assert_called()

        # Verify state was reset (new thread created)
        assert mock_thread_class.call_count >= 2  # Initial + restart


class TestStreamMonitorDisabled:
    """Tests for disabled stream monitor"""

    @patch('stream_monitor.StreamMonitorThread')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_disabled_no_thread_created(self, mock_settings_group, mock_qsettings, mock_thread_class):
        """Test that no thread is created when disabled"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': False,
            'streamMonitorUrl': 'http://stream.example.com/live',
            'streamMonitorOfflineThreshold': 10,
            'streamMonitorReconnectDelay': 5,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        mock_thread_class.assert_not_called()
        assert monitor._monitor_thread is None

    @patch('stream_monitor.StreamMonitorThread')
    @patch('stream_monitor.QSettings')
    @patch('stream_monitor.settings_group')
    def test_no_url_no_thread_created(self, mock_settings_group, mock_qsettings, mock_thread_class):
        """Test that no thread is created when no URL configured"""
        from stream_monitor import StreamMonitor

        mock_settings = Mock()
        mock_settings.value.side_effect = lambda key, default, **kwargs: {
            'streamMonitorEnabled': True,
            'streamMonitorUrl': '',
            'streamMonitorOfflineThreshold': 10,
            'streamMonitorReconnectDelay': 5,
        }.get(key, default)
        mock_qsettings.return_value = mock_settings
        mock_settings_group.return_value.__enter__ = Mock(return_value=mock_settings)
        mock_settings_group.return_value.__exit__ = Mock(return_value=False)

        mock_main_screen = Mock()
        monitor = StreamMonitor(mock_main_screen)

        mock_thread_class.assert_not_called()


class TestStreamMonitorThreadMainLoop:
    """Tests for the main run() loop behavior"""

    @patch('stream_monitor.StreamMonitorThread.__del__')
    @patch('stream_monitor.time.sleep')
    @patch('stream_monitor.urllib.request.urlopen')
    def test_reconnects_after_failure(self, mock_urlopen, mock_sleep, mock_del):
        """Test that thread reconnects after connection failure"""
        from stream_monitor import StreamMonitorThread
        import urllib.error

        # First call fails, second call also fails (to exit cleanly)
        call_count = [0]
        def urlopen_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise urllib.error.URLError("Connection refused")
            else:
                raise urllib.error.URLError("Still failing")

        mock_urlopen.side_effect = urlopen_side_effect

        thread = StreamMonitorThread.__new__(StreamMonitorThread)
        thread._stream_url = "http://example.com/stream"
        thread._offline_threshold = 10
        thread._reconnect_delay = 5
        thread._running = True
        thread._is_online = False
        thread._initialized = True
        thread.stream_online = Mock()
        thread.stream_offline = Mock()

        # Mock _sleep_with_check to stop after second iteration
        sleep_count = [0]
        original_running = thread._running
        def sleep_side_effect(duration):
            sleep_count[0] += 1
            if sleep_count[0] >= 2:
                thread._running = False

        with patch.object(thread, '_sleep_with_check', side_effect=sleep_side_effect):
            thread.run()

        # Should have attempted connection at least twice
        assert call_count[0] >= 2

    @patch('stream_monitor.StreamMonitorThread.__del__')
    @patch('stream_monitor.urllib.request.urlopen')
    def test_emits_offline_when_was_online(self, mock_urlopen, mock_del):
        """Test that offline signal is emitted when connection lost after being online"""
        from stream_monitor import StreamMonitorThread
        import urllib.error

        # First connect succeeds, then fails
        mock_response = Mock()
        mock_response.read.side_effect = [b'audio', ConnectionError("Lost connection")]
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        call_count = [0]
        def urlopen_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_response
            else:
                raise urllib.error.URLError("Still down")

        mock_urlopen.side_effect = urlopen_side_effect

        thread = StreamMonitorThread.__new__(StreamMonitorThread)
        thread._stream_url = "http://example.com/stream"
        thread._offline_threshold = 10
        thread._reconnect_delay = 5
        thread._running = True
        thread._is_online = False
        thread._initialized = True
        thread.stream_online = Mock()
        thread.stream_offline = Mock()

        # Stop after first reconnect attempt
        def sleep_side_effect(duration):
            thread._running = False

        with patch.object(thread, '_sleep_with_check', side_effect=sleep_side_effect):
            thread.run()

        # Should have emitted online then offline
        thread.stream_online.emit.assert_called_once()
        thread.stream_offline.emit.assert_called_once()
