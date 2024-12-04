# KStars Integration Guide

This guide explains how to integrate the Seestar INDI driver with KStars/EKOS for telescope control and astrophotography.

## Installation

### Method 1: Using Package Manager

1. Install the Seestar INDI driver package:

For Ubuntu/Debian:
```bash
sudo apt install seestar-indi
```

For Fedora/RHEL:
```bash
sudo dnf install seestar-indi
```

### Method 2: Manual Installation

1. Build and install from source:
```bash
# Clone repository
git clone https://github.com/yourusername/seestar-indi.git
cd seestar-indi

# Build packages
./build_packages.sh

# Install package
# For Ubuntu/Debian:
sudo dpkg -i dist/deb/seestar-indi_1.0.0-1_all.deb
sudo apt-get install -f

# For Fedora/RHEL:
sudo rpm -ivh dist/rpm/seestar-indi-1.0.0-1.noarch.rpm
```

## Configuration in KStars

1. Start KStars

2. Open EKOS:
   - Click on the EKOS icon in the toolbar
   - Or go to Tools → EKOS

3. Configure INDI:
   - Click "INDI Control Panel" in EKOS
   - Or go to Tools → Devices → Device Manager

4. Add Seestar Driver:
   - Click "Client" tab
   - Click "Start INDI Server"
   - Select "Telescopes" from the left panel
   - Find "Seestar S50" in the list
   - Click "Run Service"

## Device Setup

### Mount Configuration

1. In EKOS Mount Module:
   - Select "Seestar S50" from the mount dropdown
   - Click "Connect"
   - Wait for successful connection
   - The mount coordinates should update in KStars

2. Configure Mount Settings:
   - Click "Mount Control Panel"
   - Set your location if not already set
   - Configure tracking rates if needed
   - Set park position if desired

### Camera Configuration

1. In EKOS Camera Module:
   - Select "Seestar S50" from the camera dropdown
   - Click "Connect"
   - Camera controls will become available

2. Configure Camera Settings:
   - Set frame type (Light, Dark, Flat, Bias)
   - Configure exposure settings
   - Set gain if needed
   - Configure temperature control if available

### Filter Wheel Configuration

1. In EKOS Filter Module:
   - Select "Seestar S50" from the filter wheel dropdown
   - Click "Connect"
   - Configure filter names and offsets

### Focuser Configuration

1. In EKOS Focus Module:
   - Select "Seestar S50" from the focuser dropdown
   - Click "Connect"
   - Configure autofocus settings if desired

## Using with EKOS

### Basic Operations

1. Slewing:
   - Click desired target in KStars
   - Click "Center" or "Slew" in EKOS Mount module
   - Wait for slew completion

2. Tracking:
   - Enable tracking in Mount module
   - Select desired tracking rate

3. Imaging:
   - Set exposure parameters in Camera module
   - Start single exposure or sequence
   - Images will be saved to configured directory

### Automated Sequences

1. Create Sequence:
   - Open Sequence Queue in EKOS
   - Add sequence items:
     * Set frame type
     * Set exposure time
     * Set filter
     * Set count
   - Configure autofocus between sequences if desired

2. Run Sequence:
   - Click "Start Sequence"
   - Monitor progress in EKOS

### Plate Solving

1. Configure Plate Solving:
   - Open Align module
   - Select solver (built-in astrometry.net recommended)
   - Set solving parameters

2. Perform Alignment:
   - Take image
   - Solve plate
   - Sync or align mount as needed

## Troubleshooting

### Connection Issues

1. Check INDI server:
   ```bash
   systemctl status seestar-indi
   ```

2. Check logs:
   ```bash
   tail -f /var/log/seestar/indi.log
   ```

3. Common solutions:
   - Restart INDI server
   - Check USB connections
   - Verify permissions
   - Check network connectivity

### Mount Issues

1. If mount won't slew:
   - Check park status
   - Verify coordinates
   - Check mount limits
   - Verify tracking status

2. If position is incorrect:
   - Perform plate solving
   - Sync mount position
   - Check location settings

### Camera Issues

1. If exposures fail:
   - Check camera connection
   - Verify exposure settings
   - Check storage space
   - Monitor camera temperature

2. If images are poor quality:
   - Check focus
   - Verify gain settings
   - Check tracking
   - Monitor seeing conditions

## Advanced Features

### Meridian Flips

1. Configure meridian limits:
   - Set in Mount Control Panel
   - Configure flip timing
   - Set safety margins

2. Automated flips:
   - Enable in EKOS sequence
   - Set flip triggers
   - Configure post-flip actions

### Autofocus

1. Configure autofocus:
   - Set focus method
   - Configure step size
   - Set focus criteria
   - Enable temperature compensation

2. Run autofocus:
   - Manual from Focus module
   - Automatic in sequences
   - Based on temperature change

### Weather Integration

1. Setup weather monitoring:
   - Configure weather source
   - Set safety limits
   - Configure automated responses

2. Weather safety:
   - Automatic park on unsafe conditions
   - Equipment protection
   - Data logging

## Best Practices

1. Equipment Setup:
   - Perform polar alignment
   - Balance mount properly
   - Check all connections
   - Verify power supply

2. Session Preparation:
   - Check weather forecast
   - Plan targets
   - Prepare sequences
   - Test all equipment

3. During Session:
   - Monitor equipment
   - Check image quality
   - Watch weather
   - Monitor disk space

4. Session End:
   - Park mount
   - Warm up camera
   - Secure equipment
   - Save logs

## Support

For issues:
1. Check INDI logs
2. Check KStars/EKOS logs
3. Visit support forum
4. Submit detailed bug reports

For updates and documentation:
- Project website
- GitHub repository
- User manual
- Development guide
