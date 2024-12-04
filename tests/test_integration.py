#!/usr/bin/env python3

"""
Unit tests for Seestar integration system
"""

import unittest
import os
import numpy as np
from unittest.mock import Mock, patch
from datetime import datetime
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
from astropy import units as u

from seestar_integration import (
    FITSHeader,
    FITSHandler,
    PlateSolver,
    ASCOMBridge,
    IntegrationManager
)

class TestFITSHandler(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.test_dir = "test_images"
        self.fits_handler = FITSHandler(save_path=self.test_dir)
        
        # Create test data
        self.test_data = np.random.random((100, 100))
        self.test_header = FITSHeader(
            object_name="Test Object",
            exposure_time=1.0,
            gain=100,
            temperature=20.0,
            filter_name="Clear",
            ra=10.0,
            dec=45.0
        )
        
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            
    def test_fits_saving(self):
        """Test FITS file saving"""
        # Save FITS file
        filepath = self.fits_handler.save_fits(
            self.test_data,
            self.test_header
        )
        
        # Verify file exists
        self.assertTrue(os.path.exists(filepath))
        
        # Verify file content
        with fits.open(filepath) as hdul:
            # Check data
            np.testing.assert_array_almost_equal(
                hdul[0].data,
                self.test_data
            )
            
            # Check header
            header = hdul[0].header
            self.assertEqual(header['OBJECT'], self.test_header.object_name)
            self.assertEqual(header['EXPTIME'], self.test_header.exposure_time)
            self.assertEqual(header['GAIN'], self.test_header.gain)
            self.assertEqual(header['CCD-TEMP'], self.test_header.temperature)
            self.assertEqual(header['FILTER'], self.test_header.filter_name)
            self.assertEqual(header['RA'], self.test_header.ra)
            self.assertEqual(header['DEC'], self.test_header.dec)
            
    def test_fits_loading(self):
        """Test FITS file loading"""
        # Save test file
        filepath = self.fits_handler.save_fits(
            self.test_data,
            self.test_header
        )
        
        # Load file
        data, header = self.fits_handler.load_fits(filepath)
        
        # Verify data
        np.testing.assert_array_almost_equal(data, self.test_data)
        
        # Verify header
        self.assertEqual(header['OBJECT'], self.test_header.object_name)
        self.assertEqual(header['EXPTIME'], self.test_header.exposure_time)

class TestPlateSolver(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.plate_solver = PlateSolver()
        
        # Create test FITS file
        self.fits_handler = FITSHandler("test_images")
        self.test_data = np.random.random((100, 100))
        self.test_header = FITSHeader(
            object_name="Test Object",
            exposure_time=1.0,
            gain=100,
            temperature=20.0,
            filter_name="Clear",
            ra=10.0,
            dec=45.0
        )
        self.test_file = self.fits_handler.save_fits(
            self.test_data,
            self.test_header
        )
        
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        if os.path.exists("test_images"):
            shutil.rmtree("test_images")
            
    @patch('astroquery.astrometry_net.AstrometryNet.solve_from_image')
    def test_online_solving(self, mock_solve):
        """Test online plate solving"""
        # Setup mock WCS solution
        mock_wcs = WCS(naxis=2)
        mock_wcs.wcs.crval = [10.0, 45.0]
        mock_wcs.wcs.crpix = [50, 50]
        mock_wcs.wcs.cdelt = [0.1, 0.1]
        mock_solve.return_value = mock_wcs.to_header()
        
        # Solve plate
        solution = self.plate_solver._solve_online(self.test_file)
        
        # Verify solution
        self.assertIsNotNone(solution)
        self.assertIsInstance(solution['wcs'], WCS)
        self.assertAlmostEqual(solution['ra'], 10.0, places=1)
        self.assertAlmostEqual(solution['dec'], 45.0, places=1)
        
    def test_local_solving(self):
        """Test local plate solving"""
        with patch('subprocess.run') as mock_run:
            # Setup mock solve-field response
            mock_run.return_value.returncode = 0
            
            # Create mock WCS file
            wcs = WCS(naxis=2)
            wcs.wcs.crval = [10.0, 45.0]
            wcs.wcs.crpix = [50, 50]
            wcs.wcs.cdelt = [0.1, 0.1]
            wcs.to_header().tofile(self.test_file.replace('.fits', '.wcs'))
            
            # Solve plate
            solution = self.plate_solver._solve_local(self.test_file)
            
            # Verify solution
            self.assertIsNotNone(solution)
            self.assertIsInstance(solution['wcs'], WCS)
            self.assertAlmostEqual(solution['ra'], 10.0, places=1)
            self.assertAlmostEqual(solution['dec'], 45.0, places=1)

class TestASCOMBridge(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.mock_api = Mock()
        self.bridge = ASCOMBridge(self.mock_api)
        
    def test_connection(self):
        """Test device connection"""
        # Test successful connection
        self.mock_api.send_command.return_value = True
        self.assertTrue(self.bridge.connect())
        self.assertTrue(self.bridge.connected)
        
        # Test failed connection
        self.mock_api.send_command.return_value = False
        self.assertFalse(self.bridge.connect())
        self.assertFalse(self.bridge.connected)
        
    def test_coordinates(self):
        """Test coordinate handling"""
        # Setup mock response
        self.mock_api.send_command.return_value = {
            'ra': '10.5',
            'dec': '45.5'
        }
        
        # Get coordinates
        ra, dec = self.bridge.get_coordinates()
        self.assertEqual(ra, 10.5)
        self.assertEqual(dec, 45.5)
        
    def test_slewing(self):
        """Test mount slewing"""
        # Test successful slew
        self.mock_api.send_command.return_value = True
        self.assertTrue(
            self.bridge.slew_to_coordinates(10.0, 45.0)
        )
        
        # Verify command
        self.mock_api.send_command.assert_called_with(
            "goto_target",
            {'ra': '10.0', 'dec': '45.0'}
        )
        
    def test_sync(self):
        """Test position syncing"""
        # Test successful sync
        self.mock_api.send_command.return_value = True
        self.assertTrue(
            self.bridge.sync_to_coordinates(10.0, 45.0)
        )
        
        # Verify command
        self.mock_api.send_command.assert_called_with(
            "sync_position",
            {'ra': 10.0, 'dec': 45.0}
        )

class TestIntegrationManager(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.mock_api = Mock()
        self.manager = IntegrationManager(self.mock_api)
        
        # Create test data
        self.test_data = np.random.random((100, 100))
        self.test_header = FITSHeader(
            object_name="Test Object",
            exposure_time=1.0,
            gain=100,
            temperature=20.0,
            filter_name="Clear",
            ra=10.0,
            dec=45.0
        )
        
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        if os.path.exists("images"):
            shutil.rmtree("images")
            
    def test_image_saving(self):
        """Test image saving"""
        filepath = self.manager.save_image(
            self.test_data,
            self.test_header
        )
        self.assertTrue(os.path.exists(filepath))
        
    @patch('seestar_integration.PlateSolver.solve_field')
    def test_solve_and_sync(self, mock_solve):
        """Test plate solving and syncing"""
        # Setup mock solution
        mock_solve.return_value = {
            'ra': 10.0,
            'dec': 45.0,
            'wcs': Mock()
        }
        
        # Create test file
        filepath = self.manager.save_image(
            self.test_data,
            self.test_header
        )
        
        # Test successful solve and sync
        self.mock_api.send_command.return_value = True
        self.assertTrue(self.manager.solve_and_sync(filepath))
        
    def test_image_coordinates(self):
        """Test coordinate extraction"""
        # Save test image
        filepath = self.manager.save_image(
            self.test_data,
            self.test_header
        )
        
        # Get coordinates
        coords = self.manager.get_image_coordinates(filepath)
        
        # Verify coordinates
        self.assertIsInstance(coords, SkyCoord)
        self.assertEqual(coords.ra.deg, self.test_header.ra)
        self.assertEqual(coords.dec.deg, self.test_header.dec)

if __name__ == '__main__':
    unittest.main()
