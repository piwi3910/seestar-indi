#!/usr/bin/env python3

from setuptools import setup, find_packages
from pathlib import Path

# Read requirements
with open('requirements.txt') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

# Read README
readme = Path('README.md').read_text()

setup(
    name='seestar-indi',
    version='1.0.0',
    description='INDI Driver for Seestar Telescope',
    long_description=readme,
    long_description_content_type='text/markdown',
    author='Your Name',
    author_email='your.email@example.com',
    url='https://github.com/yourusername/seestar-indi',
    packages=find_packages(exclude=['tests*']),
    include_package_data=True,
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'seestar-indi=seestar_driver:main',
            'seestar-cli=seestar_cli:main',
            'seestar-web=seestar_web:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Astronomy',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],
    python_requires='>=3.8',
)
