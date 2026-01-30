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

This module monitors an Icecast stream using a CONTINUOUS CONNECTION approach
instead of polling. This avoids the rapid connect/disconnect cycle that can
overwhelm resource-limited streaming appliances like the Telos Z/IPStream R/1.

Architecture:
- Maintains a single persistent connection to the stream
- Monitors data flow in real-time (instant online/offline detection)
- On disconnect, waits before attempting reconnection (no thread churn)
- Actually verifies audio is flowing, not just "server responds"

When the stream goes online, AIR4 starts with timer reset.
When offline for a configurable threshold, AIR4 stops.
"""

import logging
import socket
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSettings, QThread, pyqtSignal

from defaults import (
    DEFAULT_STREAM_MONITOR_ENABLED,
    DEFAULT_STREAM_MONITOR_URL,
    DEFAULT_STREAM_MONITOR_OFFLINE_THRESHOLD,
    DEFAULT_STREAM_MONITOR_RECONNECT_DELAY,
)
from exceptions import WidgetAccessError, log_exception
from utils import settings_group

if TYPE_CHECKING:
    from start import MainScreen

logger = logging.getLogger(__name__)


class StreamMonitorThread(QThread):
    """
    Maintains persistent connection to stream, monitors data flow.

    AIDEV-NOTE: This approach uses ONE long-lived connection instead of rapid
    connect/disconnect polling. This is critical for Z/IPStream R/1 appliances
    which have limited thread pools and fail under rapid connection churn.

    Signals:
        stream_online: Emitted when stream comes online (data flowing)
        stream_offline: Emitted when stream goes offline (no data for threshold)
    """

    stream_online = pyqtSignal()
    stream_offline = pyqtSignal()

    def __init__(self, stream_url: str, offline_threshold: int, reconnect_delay: int):
        """
        Initialize stream monitor thread.

        Args:
            stream_url: URL of the stream to monitor
            offline_threshold: Seconds without data before declaring offline
            reconnect_delay: Seconds to wait between reconnection attempts
        """
        super().__init__()
        self._stream_url = stream_url
        self._offline_threshold = offline_threshold
        self._reconnect_delay = reconnect_delay
        self._running = True
        self._is_online = False
        self._initialized = True

    def __del__(self):
        try:
            if hasattr(self, '_initialized') and self._initialized:
                self.wait()
        except (RuntimeError, AttributeError) as e:
            error = WidgetAccessError(
                f"Error accessing stream monitor thread: {e}",
                widget_name="StreamMonitorThread",
                attribute="stop"
            )
            log_exception(logger, error, use_exc_info=False)

    def run(self):
        """
        Main thread loop - maintains persistent stream connection.

        Architecture:
        1. Connect to stream
        2. Read chunks continuously, emit online signal
        3. On error/timeout/no data, emit offline signal
        4. Wait reconnect_delay seconds
        5. Goto 1
        """
        logger.debug("StreamMonitorThread started")

        while self._running:
            try:
                self._monitor_stream()
            except Exception as e:
                if self._running:
                    if self._is_online:
                        logger.info(f"Stream connection lost: {e}")
                        self._is_online = False
                        self.stream_offline.emit()
                    else:
                        logger.debug(f"Stream connection attempt failed: {e}")

                    # Wait before reconnecting (don't spam the device)
                    self._sleep_with_check(self._reconnect_delay)

        logger.debug("StreamMonitorThread stopped")

    def _sleep_with_check(self, seconds: int) -> None:
        """Sleep for specified seconds, checking _running flag periodically."""
        for _ in range(seconds * 10):  # Check every 100ms
            if not self._running:
                return
            time.sleep(0.1)

    def _monitor_stream(self) -> None:
        """
        Connect to stream and monitor data flow.

        Reads small chunks continuously, verifying data is actually flowing.
        If no data received for offline_threshold seconds, raises exception.
        """
        if not self._stream_url:
            raise ValueError("No stream URL configured")

        logger.debug(f"Connecting to stream: {self._stream_url}")

        request = urllib.request.Request(
            self._stream_url,
            headers={
                'User-Agent': 'OnAirScreen/1.0 StreamMonitor',
                'Connection': 'keep-alive',
                'Accept': '*/*',
            }
        )

        # AIDEV-NOTE: timeout here is for initial connection only
        with urllib.request.urlopen(request, timeout=10) as response:
            logger.info(f"Stream connection established: {self._stream_url}")

            if not self._is_online:
                self._is_online = True
                self.stream_online.emit()

            last_data_time = time.time()

            while self._running:
                try:
                    # Read small chunk, discard it (just verify data is flowing)
                    # AIDEV-NOTE: 4KB is small enough to not buffer much audio
                    # but large enough to avoid excessive syscall overhead
                    chunk = response.read(4096)

                    if chunk:
                        last_data_time = time.time()
                    else:
                        # Empty read = stream ended
                        raise ConnectionError("Stream ended (empty read)")

                except socket.timeout:
                    # Check if we've exceeded offline threshold
                    elapsed = time.time() - last_data_time
                    if elapsed > self._offline_threshold:
                        raise ConnectionError(f"No data received for {elapsed:.1f}s")
                    # Otherwise continue waiting

    def stop(self) -> None:
        """Signal thread to stop and wait for it to finish."""
        logger.debug("Stopping StreamMonitorThread")
        self._running = False

    def is_online(self) -> bool:
        """Check if stream is currently online."""
        return self._is_online


class StreamMonitor:
    """
    Monitors Icecast stream and controls AIR4 based on availability.

    Uses continuous connection approach instead of polling:
    - Single persistent connection (no thread pool exhaustion)
    - Real-time detection (instant online/offline signals)
    - Graceful reconnection with configurable delay

    This class follows the NTPManager pattern: thread updates state,
    signals handle UI in main thread.
    """

    def __init__(self, main_screen: "MainScreen"):
        """
        Initialize stream monitor.

        Args:
            main_screen: Reference to MainScreen instance for AIR4 control
        """
        self.main_screen = main_screen

        # Load configuration
        self._load_config()

        # Resolved stream URL (from .m3u or direct)
        self._resolved_stream_url: str | None = None
        self._m3u_url: str | None = None

        # Monitor thread
        self._monitor_thread: StreamMonitorThread | None = None

        if self._enabled and self._stream_url:
            logger.info(f"Stream monitoring enabled (continuous connection mode)")
            # Resolve URL immediately if it's an .m3u
            self._resolve_stream_url()
            # Start monitoring
            self._start_monitor_thread()
        elif self._enabled:
            logger.warning("Stream monitoring enabled but no URL configured")

    def _load_config(self) -> None:
        """Load configuration from settings."""
        settings = QSettings(QSettings.Scope.UserScope, "astrastudio", "OnAirScreen")
        with settings_group(settings, "StreamMonitoring"):
            self._enabled = settings.value(
                'streamMonitorEnabled', DEFAULT_STREAM_MONITOR_ENABLED, type=bool
            )
            self._stream_url = settings.value(
                'streamMonitorUrl', DEFAULT_STREAM_MONITOR_URL, type=str
            )
            self._offline_threshold = settings.value(
                'streamMonitorOfflineThreshold', DEFAULT_STREAM_MONITOR_OFFLINE_THRESHOLD, type=int
            )
            self._reconnect_delay = settings.value(
                'streamMonitorReconnectDelay', DEFAULT_STREAM_MONITOR_RECONNECT_DELAY, type=int
            )

        logger.debug(f"Stream monitor config: enabled={self._enabled}, "
                    f"url={self._stream_url}, threshold={self._offline_threshold}s, "
                    f"reconnect_delay={self._reconnect_delay}s")

    def _resolve_stream_url(self) -> None:
        """
        Resolve .m3u playlist to actual stream URL.

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
        """Get the resolved stream URL (from .m3u or direct)."""
        return self._resolved_stream_url

    def _start_monitor_thread(self) -> None:
        """Create and start the monitor thread."""
        if not self._resolved_stream_url:
            logger.warning("Cannot start monitor: no resolved stream URL")
            return

        self._monitor_thread = StreamMonitorThread(
            stream_url=self._resolved_stream_url,
            offline_threshold=self._offline_threshold,
            reconnect_delay=self._reconnect_delay,
        )
        self._monitor_thread.stream_online.connect(self._on_stream_online)
        self._monitor_thread.stream_offline.connect(self._on_stream_offline)
        self._monitor_thread.start()

    def _on_stream_online(self) -> None:
        """Handle stream coming online (runs in main thread via signal)."""
        logger.info("Stream online - starting AIR4 with timer reset")
        self.main_screen.stream_timer_reset()
        self.main_screen.start_air4()

    def _on_stream_offline(self) -> None:
        """Handle stream going offline (runs in main thread via signal)."""
        logger.info("Stream offline - stopping AIR4")
        self.main_screen.stop_air4()

    def is_enabled(self) -> bool:
        """Check if stream monitoring is enabled."""
        return self._enabled

    def is_online(self) -> bool:
        """Check if stream is currently online."""
        if self._monitor_thread:
            return self._monitor_thread.is_online()
        return False

    def start(self) -> None:
        """Start stream monitoring."""
        if not self._enabled:
            logger.debug("Stream monitoring not enabled, not starting")
            return

        if not self._stream_url:
            logger.warning("No stream URL configured, cannot start monitoring")
            return

        logger.info("Starting stream monitoring")
        self._resolve_stream_url()
        self._start_monitor_thread()

    def stop(self) -> None:
        """Stop stream monitoring."""
        logger.debug("Stopping stream monitoring")
        if self._monitor_thread:
            self._monitor_thread.stop()
            self._monitor_thread.wait(5000)  # Wait up to 5s for thread to finish
            self._monitor_thread = None

    def restart(self) -> None:
        """Restart stream monitoring with current settings."""
        logger.info("Restarting stream monitoring")
        self.stop()
        self._load_config()

        # Reset state
        self._resolved_stream_url = None

        if self._enabled and self._stream_url:
            self.start()
