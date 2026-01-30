#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#############################################################################
#
# OnAirScreen
# Copyright (c) 2012-2026 Sascha Ludwig, astrastudio.de
# All rights reserved.
#
# stream_monitor.py
# This file is part of OnAirScreen
#
# You may use this file under the terms of the BSD license as follows:
#
# "Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in
#     the documentation and/or other materials provided with the
#     distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
#
#############################################################################

"""
Stream Monitor for OnAirScreen

This module monitors an Icecast stream and automatically controls the AIR4
(Stream) widget based on stream availability. When the stream goes online,
AIR4 starts with timer reset. When offline for a configurable threshold,
AIR4 stops.
"""

import logging
import urllib.request
import urllib.error
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSettings, QTimer, QThread

from defaults import (
    DEFAULT_STREAM_MONITOR_ENABLED,
    DEFAULT_STREAM_MONITOR_URL,
    DEFAULT_STREAM_MONITOR_POLL_INTERVAL,
    DEFAULT_STREAM_MONITOR_OFFLINE_THRESHOLD,
)
from exceptions import WidgetAccessError, log_exception
from utils import settings_group

if TYPE_CHECKING:
    from start import MainScreen

logger = logging.getLogger(__name__)


class StreamCheckThread(QThread):
    """
    Thread for checking Icecast stream availability

    Performs HTTP GET to stream URL, reads first few bytes to verify
    the stream is delivering data, then closes connection immediately.
    """

    def __init__(self, monitor: "StreamMonitor"):
        """
        Initialize stream check thread

        Args:
            monitor: Reference to StreamMonitor instance
        """
        self.monitor = monitor
        QThread.__init__(self)
        self._initialized = True  # Mark that __init__ was called

    def __del__(self):
        try:
            # Only call wait() if the thread was properly initialized
            if hasattr(self, '_initialized') and self._initialized:
                self.wait()
        except (RuntimeError, AttributeError) as e:
            error = WidgetAccessError(
                f"Error accessing stream check thread (thread may not be initialized): {e}",
                widget_name="StreamCheckThread",
                attribute="stop"
            )
            log_exception(logger, error, use_exc_info=False)

    def run(self):
        """Check stream and update monitor state (runs in background thread)"""
        logger.debug("StreamCheckThread.run started")

        stream_url = self.monitor.stream_url
        if not stream_url:
            logger.debug("No stream URL configured")
            self.monitor._last_check_success = False
            return

        try:
            # AIDEV-NOTE: Brief HTTP GET with timeout - read first 1KB to prove stream is live
            request = urllib.request.Request(
                stream_url,
                headers={'User-Agent': 'OnAirScreen/1.0 StreamMonitor'}
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                data = response.read(1024)  # Read 1KB max
                self.monitor._last_check_success = len(data) > 0
                logger.debug(f"Stream check success: read {len(data)} bytes")
        except urllib.error.HTTPError as e:
            logger.debug(f"Stream check failed (HTTP {e.code}): {e.reason}")
            self.monitor._last_check_success = False
        except urllib.error.URLError as e:
            logger.debug(f"Stream check failed (URL error): {e.reason}")
            self.monitor._last_check_success = False
        except Exception as e:
            logger.debug(f"Stream check failed: {e}")
            self.monitor._last_check_success = False

    def stop(self):
        """Stop the thread"""
        self.quit()


class StreamMonitor:
    """
    Monitors Icecast stream and controls AIR4 based on availability

    State Machine:
    - UNKNOWN -> check succeeds -> ONLINE (start AIR4 timer)
    - ONLINE -> check fails -> FAILING (increment counter)
    - FAILING -> counter < threshold -> FAILING (keep checking)
    - FAILING -> counter >= threshold -> OFFLINE (stop AIR4 timer)
    - OFFLINE -> check succeeds -> ONLINE (reset timer, start AIR4)

    This class follows the NTPManager pattern: thread updates state,
    timer callback handles UI in main thread.
    """

    def __init__(self, main_screen: "MainScreen"):
        """
        Initialize stream monitor

        Args:
            main_screen: Reference to MainScreen instance for AIR4 control
        """
        self.main_screen = main_screen

        # Load configuration
        self._load_config()

        # State (updated by thread, read by timer callback)
        self._last_check_success: bool = False
        self._is_online: bool = False
        self._consecutive_failures: int = 0

        # Resolved stream URL (from .m3u or direct)
        self._resolved_stream_url: str | None = None
        self._m3u_url: str | None = None

        # Thread and timer (same pattern as NTPManager)
        self._check_thread = StreamCheckThread(self)
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._on_timer_tick)

        if self._enabled and self._stream_url:
            logger.info(f"Stream monitoring enabled, polling every {self._poll_interval}s")
            # Resolve URL immediately if it's an .m3u
            self._resolve_stream_url()
            # Start polling
            self._poll_timer.start(self._poll_interval * 1000)
        elif self._enabled:
            logger.warning("Stream monitoring enabled but no URL configured")

    def _load_config(self) -> None:
        """Load configuration from settings"""
        settings = QSettings(QSettings.Scope.UserScope, "astrastudio", "OnAirScreen")
        with settings_group(settings, "StreamMonitoring"):
            self._enabled = settings.value(
                'streamMonitorEnabled', DEFAULT_STREAM_MONITOR_ENABLED, type=bool
            )
            self._stream_url = settings.value(
                'streamMonitorUrl', DEFAULT_STREAM_MONITOR_URL, type=str
            )
            self._poll_interval = settings.value(
                'streamMonitorPollInterval', DEFAULT_STREAM_MONITOR_POLL_INTERVAL, type=int
            )
            self._offline_threshold = settings.value(
                'streamMonitorOfflineThreshold', DEFAULT_STREAM_MONITOR_OFFLINE_THRESHOLD, type=int
            )

        logger.debug(f"Stream monitor config: enabled={self._enabled}, "
                    f"url={self._stream_url}, poll={self._poll_interval}s, "
                    f"threshold={self._offline_threshold}s")

    def _resolve_stream_url(self) -> None:
        """
        Resolve .m3u playlist to actual stream URL

        If URL ends with .m3u, fetch and parse it to get the stream URL.
        Otherwise use the URL directly.
        """
        if not self._stream_url:
            self._resolved_stream_url = None
            return

        url = self._stream_url.strip()

        # Check if it's an .m3u playlist
        if url.lower().endswith('.m3u'):
            self._m3u_url = url
            try:
                logger.debug(f"Resolving .m3u playlist: {url}")
                request = urllib.request.Request(
                    url,
                    headers={'User-Agent': 'OnAirScreen/1.0 StreamMonitor'}
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    content = response.read().decode('utf-8', errors='ignore')
                    # Parse .m3u - find first line that looks like a URL
                    for line in content.splitlines():
                        line = line.strip()
                        if line and not line.startswith('#'):
                            self._resolved_stream_url = line
                            logger.info(f"Resolved stream URL from .m3u: {line}")
                            return
                logger.warning(f"No stream URL found in .m3u: {url}")
                self._resolved_stream_url = None
            except Exception as e:
                logger.warning(f"Failed to resolve .m3u playlist: {e}")
                self._resolved_stream_url = None
        else:
            # Direct stream URL
            self._resolved_stream_url = url
            self._m3u_url = None

    @property
    def stream_url(self) -> str | None:
        """Get the resolved stream URL (from .m3u or direct)"""
        return self._resolved_stream_url

    def _on_timer_tick(self) -> None:
        """
        Timer callback - runs in main thread, safe to call main_screen methods

        Processes the result from the last check and starts the next one.
        """
        if self._check_thread.isRunning():
            logger.debug("Previous stream check still running, skipping")
            return

        # Process result from last check
        if self._last_check_success:
            self._consecutive_failures = 0
            if not self._is_online:
                logger.info("Stream came online, starting AIR4")
                self._is_online = True
                # Reset timer and start AIR4
                self.main_screen.stream_timer_reset()
                self.main_screen.start_air4()
        else:
            self._consecutive_failures += 1
            failure_duration = self._consecutive_failures * self._poll_interval
            logger.debug(f"Stream check failed, consecutive failures: {self._consecutive_failures} "
                        f"({failure_duration}s)")

            if self._is_online and failure_duration >= self._offline_threshold:
                logger.info(f"Stream offline for {failure_duration}s (threshold: {self._offline_threshold}s), stopping AIR4")
                self._is_online = False
                self.main_screen.stop_air4()

        # If .m3u resolution failed, try again
        if self._m3u_url and not self._resolved_stream_url:
            self._resolve_stream_url()

        # Start next check
        self._check_thread.start()

    def is_enabled(self) -> bool:
        """Check if stream monitoring is enabled"""
        return self._enabled

    def is_online(self) -> bool:
        """Check if stream is currently online"""
        return self._is_online

    def start(self) -> None:
        """Start stream monitoring"""
        if not self._enabled:
            logger.debug("Stream monitoring not enabled, not starting")
            return

        if not self._stream_url:
            logger.warning("No stream URL configured, cannot start monitoring")
            return

        logger.info("Starting stream monitoring")
        self._resolve_stream_url()
        self._poll_timer.start(self._poll_interval * 1000)

    def stop(self) -> None:
        """Stop stream monitoring"""
        logger.debug("Stopping stream monitoring")
        self._poll_timer.stop()
        self._check_thread.stop()

    def restart(self) -> None:
        """Restart stream monitoring with current settings"""
        logger.info("Restarting stream monitoring")
        self.stop()
        self._load_config()

        # Reset state
        self._last_check_success = False
        self._is_online = False
        self._consecutive_failures = 0
        self._resolved_stream_url = None

        if self._enabled and self._stream_url:
            self.start()
