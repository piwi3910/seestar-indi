#!/bin/bash

# Script to build RPM and DEB packages for Seestar INDI driver

set -e  # Exit on error

VERSION="1.0.0"
PACKAGE="seestar-indi"

echo "Building packages for $PACKAGE version $VERSION"

# Create source distribution
echo "Creating source distribution..."
python3 setup.py sdist

# Build RPM package
echo "Building RPM package..."
if command -v rpmbuild &> /dev/null; then
    # Copy source tarball to RPM build directory
    RPM_SOURCE_DIR=$(rpm --eval '%{_sourcedir}')
    cp dist/$PACKAGE-$VERSION.tar.gz $RPM_SOURCE_DIR/

    # Build RPM
    rpmbuild -ba $PACKAGE.spec

    # Move RPMs to dist directory
    mkdir -p dist/rpm
    mv $(rpm --eval '%{_rpmdir}')/noarch/$PACKAGE-$VERSION-*.rpm dist/rpm/
    mv $(rpm --eval '%{_srcrpmdir}')/$PACKAGE-$VERSION-*.src.rpm dist/rpm/
    
    echo "RPM packages built successfully:"
    ls -l dist/rpm/
else
    echo "rpmbuild not found, skipping RPM package build"
fi

# Build DEB package
echo "Building DEB package..."
if command -v dpkg-buildpackage &> /dev/null; then
    # Create debian package build directory
    BUILD_DIR="build/debian"
    mkdir -p $BUILD_DIR
    
    # Copy source to build directory
    cp -r . $BUILD_DIR/
    cd $BUILD_DIR

    # Build debian package
    dpkg-buildpackage -us -uc

    # Move packages to dist directory
    cd ../..
    mkdir -p dist/deb
    mv build/$PACKAGE*.deb dist/deb/
    mv build/$PACKAGE*.changes dist/deb/
    mv build/$PACKAGE*.buildinfo dist/deb/
    
    echo "DEB packages built successfully:"
    ls -l dist/deb/
else
    echo "dpkg-buildpackage not found, skipping DEB package build"
fi

echo "Build process complete!"
echo "Packages can be found in:"
echo "  RPM: dist/rpm/"
echo "  DEB: dist/deb/"

# Clean up
echo "Cleaning up build directories..."
rm -rf build/
rm -rf *.egg-info/

echo "Done!"
