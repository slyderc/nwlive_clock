# Raspberry Pi Kiosk Mode Setup Guide for OnAirScreen

This guide walks you through setting up OnAirScreen as a production-ready kiosk on a Raspberry Pi. By the end, you'll have a reliable, auto-starting display that survives power outages and SD card wear.

## Table of Contents

1. [Hardware Requirements](#1-hardware-requirements)
2. [Base OS Installation](#2-base-os-installation)
3. [Initial System Setup](#3-initial-system-setup)
4. [Package Installation](#4-package-installation)
5. [OnAirScreen Installation](#5-onairscreen-installation)
6. [Kiosk Autostart Configuration](#6-kiosk-autostart-configuration)
7. [Display Configuration](#7-display-configuration)
8. [Network Configuration](#8-network-configuration)
9. [Passwordless Sudo for System Commands](#9-passwordless-sudo-for-system-commands)
10. [Hardware Watchdog (Auto-Recovery)](#10-hardware-watchdog-auto-recovery)
11. [Read-Only Filesystem (SD Card Protection)](#11-read-only-filesystem-sd-card-protection)
12. [NTP Time Synchronization](#12-ntp-time-synchronization)
13. [Remote Management](#13-remote-management)
14. [Maintenance Procedures](#14-maintenance-procedures)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Hardware Requirements

### Minimum Hardware
- **Raspberry Pi 3B** or newer
  - PyQt6 requires OpenGL ES 2.0 and ARMv7+ architecture
  - RPi 2 and older are **not supported** (insufficient performance, missing OpenGL features)
- **8GB microSD card** (Class 10 or better)
- **Power supply**: Official 5V/3A supply recommended
- **HDMI display**: Any monitor with HDMI input

### Recommended Hardware
- **Raspberry Pi 4 with 2GB+ RAM** (4GB ideal for smoother operation)
- **16GB+ microSD card** (headroom for logs, updates)
- **Official Raspberry Pi power supply** (5V/3A for Pi 4)
- **Heatsink or case with passive cooling** (24/7 operation generates heat)

### Supported Displays
- Standard HDMI monitors (any resolution)
- Official Raspberry Pi 7" touchscreen (DSI)
- Third-party DSI displays
- HDMI-to-VGA adapters (for older monitors)

### Why Not Raspberry Pi 2 or Older?
- PyQt6 and Raspberry Pi OS Bookworm require ARMv7+ with hardware floating point
- OpenGL ES 2.0 is required for Qt's rendering pipeline
- Insufficient RAM and CPU for smooth animation

---

## 2. Base OS Installation

### Download Raspberry Pi Imager
Get the official imager from https://www.raspberrypi.com/software/

### Choose the OS
1. Open Raspberry Pi Imager
2. Click "Choose OS"
3. Select: **Raspberry Pi OS (other)** → **Raspberry Pi OS Lite (64-bit)**
   - Lite = no desktop environment (we'll add minimal X11)
   - 64-bit = better performance on Pi 3/4/5

### Pre-Configure with Imager (Important!)
Before writing, click the **gear icon** (⚙️) or press `Ctrl+Shift+X` to configure:

```
☑ Set hostname: onairscreen
☑ Enable SSH: Use password authentication
☑ Set username and password:
    Username: pi (or your preference)
    Password: [strong password]
☑ Configure wireless LAN: (if using WiFi)
    SSID: [your network]
    Password: [your password]
    Country: [your country code]
☑ Set locale settings:
    Time zone: [your timezone]
    Keyboard layout: [your layout]
```

### Write and Boot
1. Insert microSD card
2. Click "Write" and wait for completion
3. Insert card into Pi and power on
4. Wait 2-3 minutes for first boot to complete

---

## 3. Initial System Setup

### Connect via SSH
```bash
ssh pi@onairscreen.local
# or use IP address if mDNS doesn't work
ssh pi@192.168.x.x
```

### Update the System
```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

### Reconnect After Reboot
```bash
ssh pi@onairscreen.local
```

---

## 4. Package Installation

### Install X11 and Display Dependencies
```bash
sudo apt install -y \
    xserver-xorg \
    xinit \
    x11-xserver-utils \
    openbox \
    unclutter
```

**What these do:**
- `xserver-xorg`: X11 display server
- `xinit`: Start X sessions without a display manager
- `x11-xserver-utils`: xset and other display utilities
- `openbox`: Lightweight window manager
- `unclutter`: Hides the mouse cursor after inactivity

### Install Python and PyQt6
```bash
sudo apt install -y \
    python3-pyqt6 \
    python3-pyqt6.qtnetwork \
    python3-pip \
    git
```

### Install Python Dependencies
```bash
pip3 install --break-system-packages \
    ntplib \
    websockets \
    paho-mqtt \
    requests
```

> **Note**: `--break-system-packages` is required on Bookworm due to PEP 668. These packages are safe to install system-wide for a dedicated kiosk.

---

## 5. OnAirScreen Installation

### Create Dedicated User
```bash
sudo useradd -m -s /bin/bash onairscreen
sudo usermod -aG video,audio,input,tty onairscreen
```

### Clone the Repository
```bash
sudo git clone https://github.com/saschaludwig/OnAirScreen.git /opt/onairscreen
sudo chown -R onairscreen:onairscreen /opt/onairscreen
```

### Test Manual Launch
```bash
# Switch to onairscreen user
sudo -u onairscreen -i

# Set display (from console, not SSH)
export DISPLAY=:0

# Navigate and test
cd /opt/onairscreen
python3 start.py --loglevel DEBUG
```

If testing from the console (keyboard/monitor attached), this should display OnAirScreen. Press `Ctrl+Q` to exit.

---

## 6. Kiosk Autostart Configuration

### Create X Session Startup Script
```bash
sudo -u onairscreen tee /home/onairscreen/.xinitrc << 'EOF'
#!/bin/bash

# Disable screen blanking and power management
xset s off
xset s noblank
xset -dpms

# Hide mouse cursor after 0.1 seconds of inactivity
unclutter -idle 0.1 -root &

# Start window manager in background
openbox-session &

# Small delay to let X settle
sleep 2

# Launch OnAirScreen (this blocks until app exits)
cd /opt/onairscreen
exec python3 start.py
EOF

chmod +x /home/onairscreen/.xinitrc
```

### Create Systemd Service
```bash
sudo tee /etc/systemd/system/onairscreen.service << 'EOF'
[Unit]
Description=OnAirScreen Kiosk Display
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=onairscreen
Environment=DISPLAY=:0
WorkingDirectory=/opt/onairscreen

# Start X server with our xinitrc
ExecStart=/usr/bin/xinit /home/onairscreen/.xinitrc -- :0 vt1 -keeptty -nocursor

# Restart if it crashes
Restart=always
RestartSec=5

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

### Enable the Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable onairscreen.service
```

### Configure Auto-Login TTY (Alternative Method)
If the systemd service doesn't start X properly, you can use getty auto-login:

```bash
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d/
sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin onairscreen --noclear %I $TERM
EOF
```

Then add to `/home/onairscreen/.bash_profile`:
```bash
sudo -u onairscreen tee -a /home/onairscreen/.bash_profile << 'EOF'

# Auto-start X on tty1
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    exec startx /home/onairscreen/.xinitrc -- -nocursor
fi
EOF
```

### Test the Service
```bash
sudo systemctl start onairscreen.service
sudo systemctl status onairscreen.service

# View logs
journalctl -u onairscreen.service -f
```

### Reboot to Verify
```bash
sudo reboot
```

OnAirScreen should now start automatically on boot.

---

## 7. Display Configuration

### Disable Screen Blanking (Belt and Suspenders)

Create an X11 configuration file:
```bash
sudo mkdir -p /etc/X11/xorg.conf.d/
sudo tee /etc/X11/xorg.conf.d/10-blanking.conf << 'EOF'
Section "ServerFlags"
    Option "BlankTime" "0"
    Option "StandbyTime" "0"
    Option "SuspendTime" "0"
    Option "OffTime" "0"
EndSection

Section "ServerLayout"
    Identifier "Layout0"
    Option "BlankTime" "0"
    Option "StandbyTime" "0"
    Option "SuspendTime" "0"
    Option "OffTime" "0"
EndSection
EOF
```

### Force HDMI Output (No Monitor Detection Issues)
Edit boot config:
```bash
sudo nano /boot/firmware/config.txt
```

Add or modify these lines:
```ini
# Force HDMI output even if no monitor detected
hdmi_force_hotplug=1

# Uncomment and set if you have display issues
#hdmi_group=1
#hdmi_mode=16  # 1080p 60Hz

# Disable overscan (removes black borders)
disable_overscan=1
```

### Display Rotation (If Needed)
For portrait mode or rotated displays, add to `/boot/firmware/config.txt`:
```ini
# Rotate display: 0=normal, 1=90°, 2=180°, 3=270°
display_rotate=0
```

Or for Wayland/DRM (Pi 4/5):
```ini
# Use display_hdmi_rotate for newer firmware
display_hdmi_rotate=0
```

### Apply Changes
```bash
sudo reboot
```

---

## 8. Network Configuration

### Static IP Address (Recommended for Production)

Edit the network configuration:
```bash
sudo nano /etc/dhcpcd.conf
```

Add at the end (adjust for your network):
```ini
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8

# For WiFi instead:
#interface wlan0
#static ip_address=192.168.1.100/24
#static routers=192.168.1.1
#static domain_name_servers=192.168.1.1 8.8.8.8
```

### Firewall Configuration (Optional)
If using `ufw`:
```bash
sudo apt install -y ufw
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 3310/udp    # OnAirScreen UDP API
sudo ufw allow 8010/tcp    # OnAirScreen HTTP/WebSocket
sudo ufw enable
```

### Enable Multicast (For UDP Discovery)
Multicast should work by default, but verify:
```bash
# Check if multicast route exists
ip route | grep 239

# If not, add it (temporary)
sudo ip route add 239.0.0.0/8 dev eth0

# To make permanent, add to /etc/rc.local or a systemd service
```

### Network Ports Used by OnAirScreen
| Port | Protocol | Purpose |
|------|----------|---------|
| 3310 | UDP | Command reception (also multicast 239.194.0.1) |
| 8010 | TCP | HTTP API, Web UI, WebSocket |

---

## 9. Passwordless Sudo for System Commands

OnAirScreen needs sudo access for `CMD:REBOOT` and `CMD:SHUTDOWN` API commands.

```bash
sudo tee /etc/sudoers.d/onairscreen << 'EOF'
# Allow onairscreen user to reboot/shutdown without password
onairscreen ALL=(ALL) NOPASSWD: /sbin/reboot
onairscreen ALL=(ALL) NOPASSWD: /sbin/halt
onairscreen ALL=(ALL) NOPASSWD: /sbin/shutdown
onairscreen ALL=(ALL) NOPASSWD: /sbin/poweroff
EOF

# Set correct permissions (critical for sudoers files)
sudo chmod 440 /etc/sudoers.d/onairscreen
```

### Test
```bash
sudo -u onairscreen sudo /sbin/reboot --help
# Should show help without password prompt
```

---

## 10. Hardware Watchdog (Auto-Recovery)

The Raspberry Pi has a built-in hardware watchdog that can automatically reboot the system if it becomes unresponsive. This is crucial for unattended kiosks.

### Enable Watchdog Hardware
Edit boot config:
```bash
sudo nano /boot/firmware/config.txt
```

Add:
```ini
# Enable hardware watchdog
dtparam=watchdog=on
```

### Install Watchdog Daemon
```bash
sudo apt install -y watchdog
```

### Configure Watchdog
```bash
sudo nano /etc/watchdog.conf
```

Uncomment and modify these lines:
```ini
# Use hardware watchdog
watchdog-device = /dev/watchdog

# Reboot if load average exceeds this for 1 minute
max-load-1 = 24

# Reboot if this process dies (create PID file in OnAirScreen)
#pidfile = /var/run/onairscreen.pid

# Ping test (reboot if network unreachable)
#ping = 192.168.1.1

# Reboot on any watchdog failure
watchdog-timeout = 15

# Log watchdog activity
realtime = yes
priority = 1
```

### Create PID File for Process Monitoring (Optional)
To have the watchdog monitor OnAirScreen specifically, modify the startup script to create a PID file:

```bash
sudo -u onairscreen tee /home/onairscreen/start_with_pid.sh << 'EOF'
#!/bin/bash
cd /opt/onairscreen
python3 start.py &
echo $! > /var/run/onairscreen.pid
wait
EOF

chmod +x /home/onairscreen/start_with_pid.sh
```

Then update `.xinitrc` to use this script.

### Enable Watchdog Service
```bash
sudo systemctl enable watchdog
sudo systemctl start watchdog
```

### Test Watchdog
**Warning**: This will forcibly reboot your Pi!
```bash
# Fork bomb to trigger load watchdog (DON'T do this in production during work hours!)
# :(){ :|:& };:

# Or simulate stuck system
sudo bash -c 'echo 1 > /dev/watchdog'
# Wait ~15 seconds, system should reboot
```

---

## 11. Read-Only Filesystem (SD Card Protection)

SD cards have limited write cycles. For 24/7 kiosk operation, a read-only filesystem prevents wear and corruption from power loss.

### Option A: Using raspi-config Overlay (Simplest)
```bash
sudo raspi-config
```
Navigate to: **Performance Options** → **Overlay File System** → **Enable**

This creates a RAM-based overlay where all writes go to memory and are lost on reboot.

### Option B: Manual Overlay Setup

#### Install overlayroot
```bash
sudo apt install -y overlayroot
```

#### Configure Overlay
```bash
sudo nano /etc/overlayroot.conf
```

Set:
```ini
overlayroot="tmpfs:swap=1,recurse=0"
```

### Persistent Storage for Settings

OnAirScreen stores settings in `~/.config/astrastudio/OnAirScreen.conf`. To persist settings across reboots with overlay enabled:

#### Create a Persistent Partition
```bash
# Create a small ext4 partition on the SD card (during setup, not with overlay enabled)
# Then mount it for settings

sudo mkdir -p /mnt/persistent
# Add to /etc/fstab:
# /dev/mmcblk0p3  /mnt/persistent  ext4  defaults,noatime  0  2

# Symlink settings directory
sudo -u onairscreen mkdir -p /mnt/persistent/onairscreen-config
sudo -u onairscreen ln -s /mnt/persistent/onairscreen-config /home/onairscreen/.config/astrastudio
```

### Toggle Read-Write Mode for Updates
Create a helper script:
```bash
sudo tee /usr/local/bin/rw-mode << 'EOF'
#!/bin/bash
# Toggle between read-only and read-write mode

case "$1" in
    on|rw)
        echo "Remounting filesystem read-write..."
        sudo mount -o remount,rw /
        echo "Filesystem is now READ-WRITE. Remember to run 'rw-mode off' when done!"
        ;;
    off|ro)
        echo "Syncing filesystem..."
        sync
        echo "Remounting filesystem read-only..."
        sudo mount -o remount,ro /
        echo "Filesystem is now READ-ONLY."
        ;;
    status)
        mount | grep "on / " | grep -q "ro," && echo "READ-ONLY" || echo "READ-WRITE"
        ;;
    *)
        echo "Usage: rw-mode [on|off|rw|ro|status]"
        echo "  on/rw  - Make filesystem writable"
        echo "  off/ro - Make filesystem read-only"
        echo "  status - Show current mode"
        exit 1
        ;;
esac
EOF

sudo chmod +x /usr/local/bin/rw-mode
```

### Tmpfs for Volatile Data
Even without full overlay, mount volatile directories as tmpfs:

```bash
sudo nano /etc/fstab
```

Add:
```
tmpfs    /tmp         tmpfs    defaults,noatime,nosuid,size=100m    0 0
tmpfs    /var/log     tmpfs    defaults,noatime,nosuid,mode=0755,size=50m    0 0
tmpfs    /var/tmp     tmpfs    defaults,noatime,nosuid,size=30m    0 0
```

> **Note**: With `/var/log` as tmpfs, logs are lost on reboot. Consider remote syslog for persistent logging.

---

## 12. NTP Time Synchronization

OnAirScreen displays time and has a built-in NTP sync checker that shows warnings when time may be inaccurate.

### Enable systemd-timesyncd
```bash
sudo systemctl enable systemd-timesyncd
sudo systemctl start systemd-timesyncd
```

### Configure NTP Servers
```bash
sudo nano /etc/systemd/timesyncd.conf
```

```ini
[Time]
NTP=pool.ntp.org
FallbackNTP=0.pool.ntp.org 1.pool.ntp.org 2.pool.ntp.org 3.pool.ntp.org
```

### Verify Time Sync
```bash
timedatectl status
# Should show "System clock synchronized: yes"
```

### OnAirScreen NTP Settings
In the OnAirScreen settings dialog or via API:
- NTP Server: `pool.ntp.org` (default)
- Sync interval: Configurable

---

## 13. Remote Management

### SSH Access
SSH is always available for maintenance:
```bash
ssh pi@onairscreen.local
# or
ssh pi@192.168.1.100
```

### Web UI
Access the web interface from any browser:
```
http://onairscreen.local:8010/
http://192.168.1.100:8010/
```

Features:
- Real-time status display
- LED and timer controls
- Text field updates (NOW/NEXT/WARN)
- Dark mode support

### API Control
```bash
# HTTP API
curl "http://onairscreen.local:8010/api/status"
curl "http://onairscreen.local:8010/api/command?cmd=LED1:ON"

# UDP API (from Linux)
echo "LED1:ON" > /dev/udp/onairscreen.local/3310
```

### MQTT Integration
Configure MQTT in settings for Home Assistant integration:
- Automatic device discovery
- LED switches, timer controls, text entities
- State synchronization

### Pre-Configure via API
You can configure OnAirScreen without touching the keyboard:
```bash
# Set station name
curl "http://onairscreen.local:8010/api/command?cmd=CONF:General:stationname=MyStation"

# Set LED labels
curl "http://onairscreen.local:8010/api/command?cmd=CONF:LED1:text=ON%20AIR"
curl "http://onairscreen.local:8010/api/command?cmd=CONF:LED2:text=RECORDING"
```

---

## 14. Maintenance Procedures

### Updating OnAirScreen

1. **SSH into the Pi**:
   ```bash
   ssh pi@onairscreen.local
   ```

2. **Stop the service**:
   ```bash
   sudo systemctl stop onairscreen
   ```

3. **If using read-only filesystem, enable writes**:
   ```bash
   sudo rw-mode on
   ```

4. **Update the code**:
   ```bash
   cd /opt/onairscreen
   sudo -u onairscreen git pull
   ```

5. **Update dependencies if needed**:
   ```bash
   pip3 install --break-system-packages -r requirements.txt
   ```

6. **Re-enable read-only mode**:
   ```bash
   sudo rw-mode off
   ```

7. **Restart the service**:
   ```bash
   sudo systemctl start onairscreen
   ```

### Updating the OS

```bash
# Enable writes first if using overlay
sudo rw-mode on

# Update packages
sudo apt update && sudo apt full-upgrade -y

# Reboot to apply
sudo reboot
```

### Backing Up the SD Card

From another Linux machine with the SD card inserted:
```bash
# Find the device (usually /dev/sdX or /dev/mmcblkX)
lsblk

# Create compressed image backup
sudo dd if=/dev/sdX bs=4M status=progress | gzip > onairscreen-backup-$(date +%Y%m%d).img.gz

# Restore from backup
gunzip -c onairscreen-backup-20240115.img.gz | sudo dd of=/dev/sdX bs=4M status=progress
```

### Viewing Logs

```bash
# OnAirScreen service logs
journalctl -u onairscreen.service -f

# With timestamps
journalctl -u onairscreen.service --since "1 hour ago"

# All system logs
journalctl -b
```

### Restarting OnAirScreen

```bash
# Via systemd
sudo systemctl restart onairscreen

# Via API (from remote machine)
curl "http://onairscreen.local:8010/api/command?cmd=CMD:QUIT"
# Service will auto-restart due to Restart=always
```

---

## 15. Troubleshooting

### Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Black screen at boot | HDMI timing issues | Add `hdmi_force_hotplug=1` and `config_hdmi_boost=4` to config.txt |
| App not starting | Missing dependencies | Check `journalctl -u onairscreen -e` for import errors |
| "Could not connect to display" | X server not running | Verify xinit is working: `sudo systemctl status onairscreen` |
| Mouse cursor visible | unclutter not running | Check .xinitrc has `unclutter -idle 0.1 -root &` |
| Network not ready at boot | Service starts too early | Service already has `After=network-online.target` |
| Settings won't save | Overlay filesystem | Use `rw-mode on` or configure persistent partition |
| No audio | User not in audio group | `sudo usermod -aG audio onairscreen` |
| Permission denied on ports | Need elevated privileges | UDP 3310 and TCP 8010 are > 1024, should work |
| Time is wrong | NTP not syncing | Check `timedatectl status` and network connectivity |
| Screen blanks after inactivity | DPMS still enabled | Verify xset commands in .xinitrc and xorg.conf.d |
| Watchdog not rebooting | Not enabled in config.txt | Add `dtparam=watchdog=on` |

### Diagnostic Commands

```bash
# Check service status
sudo systemctl status onairscreen

# View recent logs
journalctl -u onairscreen.service -n 50

# Check if X is running
ps aux | grep X

# Check network listeners
ss -tlnp | grep -E "(3310|8010)"

# Check display
echo $DISPLAY

# Test OnAirScreen manually
sudo -u onairscreen DISPLAY=:0 python3 /opt/onairscreen/start.py --loglevel DEBUG

# Check filesystem mount options
mount | grep " / "

# Check watchdog status
sudo systemctl status watchdog
dmesg | grep watchdog

# Check time sync
timedatectl status
```

### PyQt6 Issues

If PyQt6 fails to start:
```bash
# Check for OpenGL issues
DISPLAY=:0 glxinfo | head -20

# Try software rendering (slower but works)
export QT_QUICK_BACKEND=software
python3 /opt/onairscreen/start.py

# Check for missing libraries
ldd /usr/lib/python3/dist-packages/PyQt6/QtWidgets.abi3.so | grep "not found"
```

### Network Debugging

```bash
# Test UDP reception
nc -u -l 3310

# Test HTTP
curl -v http://localhost:8010/api/status

# Check multicast
ip maddr show

# Test multicast reception
socat UDP4-RECVFROM:3310,ip-add-membership=239.194.0.1:eth0,fork -
```

### Emergency Recovery

If the Pi won't boot or OnAirScreen won't start:

1. **Remove SD card and mount on another Linux machine**
2. **Disable the service temporarily**:
   ```bash
   sudo mount /dev/sdX2 /mnt
   sudo rm /mnt/etc/systemd/system/multi-user.target.wants/onairscreen.service
   sudo umount /mnt
   ```
3. **Boot and debug**:
   ```bash
   ssh pi@onairscreen.local
   journalctl -b  # Check what failed
   ```

### Factory Reset

To reset to defaults:
```bash
# Remove OnAirScreen settings
rm -rf /home/onairscreen/.config/astrastudio

# Or if using persistent partition
rm -rf /mnt/persistent/onairscreen-config/*

# Restart
sudo systemctl restart onairscreen
```

---

## Quick Reference Card

### Service Management
```bash
sudo systemctl start onairscreen    # Start
sudo systemctl stop onairscreen     # Stop
sudo systemctl restart onairscreen  # Restart
sudo systemctl status onairscreen   # Status
journalctl -u onairscreen -f        # Live logs
```

### Filesystem
```bash
sudo rw-mode on      # Enable writes
sudo rw-mode off     # Read-only mode
sudo rw-mode status  # Check current mode
```

### Network Access
```
Web UI:  http://<ip>:8010/
SSH:     ssh pi@<ip>
API:     http://<ip>:8010/api/status
UDP:     port 3310
```

### Common API Commands
```bash
curl "http://<ip>:8010/api/command?cmd=LED1:ON"
curl "http://<ip>:8010/api/command?cmd=LED1:OFF"
curl "http://<ip>:8010/api/command?cmd=CMD:REBOOT"
curl "http://<ip>:8010/api/command?cmd=NOW:Current%20Song"
```

---

## Support

- **Documentation**: https://saschaludwig.github.io/OnAirScreen/
- **Issues**: https://github.com/saschaludwig/OnAirScreen/issues
- **Commercial support**: https://www.astrastudio.de/
