# Seestar INDI Driver Development Guide

This guide explains how to set up and use the development environment for the Seestar INDI driver.

## Development Environment

The development environment is containerized using Docker to ensure consistency across different systems.

### Prerequisites

- Docker
- Docker Compose
- Git
- Make (optional)

### Getting Started

1. Clone the repository:
```bash
git clone https://github.com/yourusername/seestar-indi.git
cd seestar-indi
```

2. Start the development environment:
```bash
docker-compose up dev
```

This will:
- Build the development container
- Mount your local code into the container
- Start the INDI driver with hot reload

### Development Commands

All development tasks are containerized for consistency:

#### Running Tests
```bash
# Run all tests with coverage
docker-compose run test

# Run specific test file
docker-compose run test pytest tests/test_api.py

# Run tests with specific marker
docker-compose run test pytest -m "integration"
```

#### Code Quality
```bash
# Run all code quality checks
docker-compose run lint

# Run specific checks
docker-compose run dev black .
docker-compose run dev isort .
docker-compose run dev flake8 .
docker-compose run dev pylint indi/
docker-compose run dev mypy indi/
```

#### Building Documentation
```bash
# Build documentation
docker-compose run docs

# Documentation will be available in docs/build/html
```

#### Building Packages
```bash
# Build DEB and RPM packages
docker-compose run build
```

### Project Structure

```
indi/
├── seestar_api.py         # API client
├── seestar_monitor.py     # Device monitoring
├── seestar_driver.py      # Main INDI driver
├── seestar_camera.py      # Camera control
├── seestar_filterwheel.py # Filter wheel control
├── seestar_focuser.py     # Focuser control
├── seestar_auth.py        # Authentication system
├── seestar_recovery.py    # Error recovery system
├── seestar_performance.py # Performance optimization
├── seestar_monitoring.py  # System monitoring
├── seestar_integration.py # Integration features
├── seestar_web.py         # Web interface
├── tests/                 # Test files
├── templates/             # HTML templates
└── docker/               # Docker configuration
```

### Development Workflow

1. Create a new branch for your feature:
```bash
git checkout -b feature/your-feature-name
```

2. Make your changes with the development container running:
```bash
docker-compose up dev
```

3. Run tests and code quality checks:
```bash
docker-compose run test
docker-compose run lint
```

4. Build and test packages:
```bash
docker-compose run build
```

5. Submit a pull request

### CI/CD Pipeline

The project uses GitHub Actions for continuous integration and deployment:

1. On every push:
   - Run tests
   - Check code quality
   - Build documentation

2. On pull requests:
   - Run tests
   - Check code quality
   - Build documentation
   - Build test packages

3. On releases:
   - Run tests
   - Check code quality
   - Build documentation
   - Build and publish packages
   - Build and push Docker images
   - Deploy documentation

### Testing

#### Test Categories

1. Unit Tests
   - Test individual components
   - Mock external dependencies
   - Fast execution

2. Integration Tests
   - Test component interactions
   - Use test doubles for external services
   - Marked with `@pytest.mark.integration`

3. System Tests
   - Test complete system
   - Require running services
   - Marked with `@pytest.mark.system`

#### Running Tests

```bash
# Run all tests
docker-compose run test

# Run with coverage
docker-compose run test pytest --cov=. --cov-report=html

# Run specific test category
docker-compose run test pytest -m "integration"
```

### Code Quality

The project enforces code quality through several tools:

1. Black
   - Code formatting
   - No configuration needed
   - Enforced through CI

2. isort
   - Import sorting
   - Configured to work with Black
   - Enforced through CI

3. flake8
   - Style guide enforcement
   - Configured in setup.cfg
   - Enforced through CI

4. pylint
   - Code analysis
   - Configured in pylintrc
   - Enforced through CI

5. mypy
   - Static type checking
   - Configured in setup.cfg
   - Enforced through CI

### Documentation

The project uses Sphinx for documentation:

1. API Documentation
   - Automatically generated from docstrings
   - Follow Google style guide
   - Include type hints

2. User Guide
   - Installation instructions
   - Configuration guide
   - Usage examples

3. Developer Guide
   - Setup instructions
   - Architecture overview
   - Contributing guidelines

### Debugging

1. Using debugger:
```bash
docker-compose run --service-ports dev python -m debugpy --listen 0.0.0.0:5678 -m indi.seestar_driver
```

2. View logs:
```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs dev

# Follow logs
docker-compose logs -f dev
```

3. Access container shell:
```bash
docker-compose exec dev bash
```

### Performance Profiling

1. Run with profiler:
```bash
docker-compose run dev python -m cProfile -o profile.stats indi.seestar_driver
```

2. Analyze results:
```bash
docker-compose run dev python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(50)"
```

### Release Process

1. Update version:
   - Update version in setup.py
   - Update changelog
   - Commit changes

2. Create release:
   - Create GitHub release
   - Tag with version
   - CI will build and publish packages

3. Verify release:
   - Check GitHub release
   - Verify package availability
   - Test installation

### Support

For development support:
1. Check existing issues
2. Review documentation
3. Join developer chat
4. Submit detailed bug reports
