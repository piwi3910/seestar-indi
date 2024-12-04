#!/usr/bin/env python3

"""
Test runner for Seestar INDI driver
Runs all tests and generates coverage report
"""

import unittest
import coverage
import sys
import os
from pathlib import Path

def run_tests_with_coverage():
    """Run all tests with coverage reporting"""
    # Start coverage monitoring
    cov = coverage.Coverage(
        branch=True,
        source=[str(Path(__file__).parent.parent)],
        omit=[
            '*/__pycache__/*',
            '*/tests/*',
            '*/.venv/*'
        ]
    )
    cov.start()
    
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # Run tests with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Stop coverage monitoring
    cov.stop()
    cov.save()
    
    # Generate reports
    print("\nCoverage Report:")
    cov.report()
    
    # Generate HTML report
    html_dir = os.path.join(start_dir, 'htmlcov')
    cov.html_report(directory=html_dir)
    print(f"\nDetailed HTML coverage report generated in: {html_dir}")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    print("Running Seestar INDI Driver Tests\n")
    
    # Add parent directory to Python path for imports
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    # Run tests with coverage
    success = run_tests_with_coverage()
    
    # Exit with appropriate status
    sys.exit(0 if success else 1)
