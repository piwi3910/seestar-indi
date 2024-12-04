# Seestar INDI Driver

INDI driver implementation for the Seestar S50 Smart Telescope. This driver provides control for:
- Mount (movement, tracking, sync)
- Camera (exposure, gain)
- Filter Wheel (LP filter control)
- Focuser (manual and auto focus)

## Features

- Robust API communication with retry handling
- Real-time device state monitoring
- Event-based state updates
- Response caching to reduce API calls
- Comprehensive error handling
- Full test coverage
- Configuration management
- Command-line interface
- Web-based control panel
- Structured logging

## Installation

### From Packages

#### Debian/Ubuntu
```bash
# Install the .deb package
sudo dpkg -i seestar-indi_1.0.0-1_all.deb
sudo apt-get install -f  # Install dependencies if needed

# Start services
sudo systemctl enable seestar-indi
sudo systemctl enable seestar-web
sudo systemctl start seestar-indi
sudo systemctl start seestar-web
```

#### RedHat/CentOS/Fedora
```bash
# Install the RPM package
sudo rpm -ivh seestar-indi-1.0.0-1.noarch.rpm

# Start services
sudo systemctl enable seestar-indi
sudo systemctl enable seestar-web
sudo systemctl start seestar-indi
sudo systemctl start seestar-web
```

### From Source

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install the package:
```bash
python setup.py install
```

### Building Packages

The driver can be built into both RPM and DEB packages using the provided build script:

```bash
# Make build script executable
chmod +x build_packages.sh

# Build packages
./build_packages.sh
```

This will create:
- RPM packages in `dist/rpm/`
- DEB packages in `dist/deb/`

#### Build Requirements

For RPM building:
- `rpm-build`
- `python3-devel`
- `python3-setuptools`

For DEB building:
- `build-essential`
- `debhelper`
- `dh-python`
- `python3-all`
- `python3-setuptools`

Install build dependencies:

Debian/Ubuntu:
```bash
sudo apt-get install build-essential debhelper dh-python python3-all python3-setuptools
```

RedHat/CentOS/Fedora:
```bash
sudo dnf install rpm-build python3-devel python3-setuptools
```

## Components

### Core Components
- `seestar.py`: Core mount control implementation
- `seestar_driver.py`: Extended driver combining all components
- `seestar_camera.py`: Camera control implementation
- `seestar_filterwheel.py`: Filter wheel control implementation
- `seestar_focuser.py`: Focuser control implementation

### Support Components
- `seestar_api.py`: Shared API client
- `seestar_monitor.py`: Device state monitoring
- `seestar_config.py`: Configuration management
- `seestar_logging.py`: Logging configuration
- `seestar_cli.py`: Command-line interface
- `seestar_web.py`: Web interface

## Web Interface

The driver includes a web-based control panel accessible through any modern web browser.

### Accessing the Interface
After installation, open http://localhost:8080 in your browser.

### Features
- Real-time device status monitoring
- Interactive mount control
- Camera exposure control
- Filter wheel control
- Focus control (manual and auto)
- Configuration management
- Live log viewing
- WebSocket-based updates

## Command-Line Interface

The driver includes a comprehensive CLI for control and testing.

### Device Status
```bash
seestar-cli status
```

### Mount Control
```bash
# Slew to coordinates
seestar-cli goto 12.345 45.678

# Sync position
seestar-cli sync 12.345 45.678

# Stop movement
seestar-cli stop
```

### Camera Control
```bash
# Take exposure
seestar-cli expose 2.0 --gain 50
```

### Filter Wheel Control
```bash
# Move to filter position
seestar-cli filter 1  # 0=Clear, 1=LP
```

### Focuser Control
```bash
# Move to absolute position
seestar-cli focus --position 50000

# Move relative amount
seestar-cli focus --relative 1000

# Start auto focus
seestar-cli focus --auto
```

## Configuration

Configuration file is located at `/etc/seestar/config.toml` when installed via package, or `~/.config/seestar/config.toml` when installed from source.

### Update Configuration
```bash
seestar-cli config update camera exposure_max 3600
seestar-cli config update api host "192.168.1.100"
```

### Show Current Configuration
```bash
seestar-cli config show
```

## Environment Variables

- `INDIDEV`: Device name
- `INDICONFIG`: Device number
- `SEESTAR_CONFIG_DIR`: Configuration directory
- `SEESTAR_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `SEESTAR_LOG_DIR`: Log directory

## Logging

When installed via package:
- Log directory: `/var/log/seestar/`
- Web interface log viewer: http://localhost:8080/logs

When installed from source:
- Log directory: `./logs/`
- Web interface log viewer: http://localhost:8080/logs

## Testing

Run the test suite:
```bash
cd tests
python run_tests.py
```

## Development

### Adding New Features

1. Extend the appropriate device class
2. Add configuration options if needed
3. Update CLI commands if applicable
4. Add web interface controls if needed
5. Add tests for new functionality
6. Update documentation

### Best Practices

1. Always add tests for new features
2. Update documentation when adding features
3. Use type hints for better code clarity
4. Follow error handling patterns
5. Keep state management in the monitor
6. Use the shared API client for requests
7. Add appropriate logging
8. Update configuration schema if needed

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Make your changes
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the same terms as the original Seestar software.
