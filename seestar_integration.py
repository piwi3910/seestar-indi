#!/usr/bin/env python3

"""
Integration system for Seestar INDI driver
Handles ASCOM bridge, FITS handling, and plate solving
"""

import os
import time
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
from astropy import units as u
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from seestar_logging import get_logger
from seestar_config import config_manager

logger = get_logger("SeestarIntegration")

@dataclass
class FITSHeader:
    """FITS header information"""
    object_name: str
    exposure_time: float
    gain: int
    temperature: float
    filter_name: str
    ra: float
    dec: float
    telescope: str = "Seestar S50"
    observer: str = "Seestar INDI Driver"
    date_obs: str = datetime.utcnow().isoformat()

class FITSHandler:
    """FITS file handler"""
    def __init__(self, save_path: str = "images"):
        self.save_path = save_path
        os.makedirs(save_path, exist_ok=True)
        
    def save_fits(self, data: np.ndarray, header: FITSHeader,
                 filename: Optional[str] = None) -> str:
        """Save image data as FITS file"""
        # Create FITS header
        hdr = fits.Header()
        hdr['TELESCOP'] = header.telescope
        hdr['OBSERVER'] = header.observer
        hdr['OBJECT'] = header.object_name
        hdr['EXPTIME'] = header.exposure_time
        hdr['GAIN'] = header.gain
        hdr['CCD-TEMP'] = header.temperature
        hdr['FILTER'] = header.filter_name
        hdr['RA'] = header.ra
        hdr['DEC'] = header.dec
        hdr['DATE-OBS'] = header.date_obs
        
        # Create FITS file
        hdu = fits.PrimaryHDU(data=data, header=hdr)
        
        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{header.object_name}_{timestamp}.fits"
            
        # Save file
        filepath = os.path.join(self.save_path, filename)
        hdu.writeto(filepath, overwrite=True)
        
        logger.info(f"Saved FITS file: {filepath}")
        return filepath
        
    def load_fits(self, filepath: str) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Load FITS file"""
        with fits.open(filepath) as hdul:
            data = hdul[0].data
            header = dict(hdul[0].header)
        return data, header

class PlateSolver:
    """Plate solving handler"""
    def __init__(self):
        # Initialize astrometry.net client
        from astroquery.astrometry_net import AstrometryNet
        self.ast = AstrometryNet()
        
        # Set API key if available
        api_key = os.environ.get('ASTROMETRY_NET_API_KEY')
        if api_key:
            self.ast.api_key = api_key
            
    def solve_field(self, filepath: str) -> Optional[Dict[str, Any]]:
        """
        Solve plate for image
        Returns WCS solution if successful
        """
        try:
            # Try online solving first
            if self.ast.api_key:
                return self._solve_online(filepath)
            
            # Fall back to local solving
            return self._solve_local(filepath)
            
        except Exception as e:
            logger.error(f"Plate solving failed: {e}")
            return None
            
    def _solve_online(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Solve using astrometry.net web service"""
        try:
            # Submit image for solving
            wcs_header = self.ast.solve_from_image(filepath)
            
            if wcs_header:
                # Create WCS object
                wcs = WCS(wcs_header)
                
                # Get center coordinates
                center = wcs.pixel_to_world(
                    wcs.pixel_shape[0]/2,
                    wcs.pixel_shape[1]/2
                )
                
                return {
                    'ra': center.ra.deg,
                    'dec': center.dec.deg,
                    'wcs': wcs,
                    'header': wcs_header
                }
                
        except Exception as e:
            logger.error(f"Online plate solving failed: {e}")
            
        return None
        
    def _solve_local(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Solve using local installation"""
        try:
            import subprocess
            
            # Run solve-field
            cmd = [
                'solve-field',
                '--no-plots',
                '--no-verify',
                '--resort',
                '--downsample', '2',
                filepath
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Load WCS solution
                wcs_file = filepath.replace('.fits', '.wcs')
                wcs = WCS(wcs_file)
                
                # Get center coordinates
                center = wcs.pixel_to_world(
                    wcs.pixel_shape[0]/2,
                    wcs.pixel_shape[1]/2
                )
                
                return {
                    'ra': center.ra.deg,
                    'dec': center.dec.deg,
                    'wcs': wcs
                }
                
        except Exception as e:
            logger.error(f"Local plate solving failed: {e}")
            
        return None

class ASCOMBridge:
    """ASCOM compatibility bridge"""
    def __init__(self, api):
        self.api = api
        self.connected = False
        self.capabilities = {
            'canFindHome': False,
            'canPark': True,
            'canPulseGuide': False,
            'canSetDeclinationRate': False,
            'canSetGuideRates': False,
            'canSetPark': False,
            'canSetPierSide': False,
            'canSetRightAscensionRate': False,
            'canSetTracking': True,
            'canSlew': True,
            'canSlewAltAz': False,
            'canSlewAltAzAsync': False,
            'canSlewAsync': True,
            'canSync': True,
            'canSyncAltAz': False,
            'canUnpark': True
        }
        
    def connect(self) -> bool:
        """Connect to device"""
        try:
            result = self.api.send_command("connect", {})
            self.connected = bool(result)
            return self.connected
        except Exception as e:
            logger.error(f"ASCOM connect failed: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from device"""
        try:
            self.api.send_command("disconnect", {})
        finally:
            self.connected = False
            
    def get_coordinates(self) -> Tuple[float, float]:
        """Get current coordinates"""
        result = self.api.send_command("get_coordinates", {})
        return float(result['ra']), float(result['dec'])
        
    def slew_to_coordinates(self, ra: float, dec: float) -> bool:
        """Slew to coordinates"""
        result = self.api.send_command(
            "goto_target",
            {'ra': str(ra), 'dec': str(dec)}
        )
        return bool(result)
        
    def sync_to_coordinates(self, ra: float, dec: float) -> bool:
        """Sync to coordinates"""
        result = self.api.send_command(
            "sync_position",
            {'ra': ra, 'dec': dec}
        )
        return bool(result)
        
    def stop_slew(self):
        """Stop slew"""
        self.api.send_command("stop_slew", {})
        
    def park(self) -> bool:
        """Park mount"""
        result = self.api.send_command("park", {})
        return bool(result)
        
    def unpark(self) -> bool:
        """Unpark mount"""
        result = self.api.send_command("unpark", {})
        return bool(result)
        
    def set_tracking(self, enabled: bool) -> bool:
        """Set tracking state"""
        result = self.api.send_command(
            "set_tracking",
            {'enabled': enabled}
        )
        return bool(result)

class IntegrationManager:
    """Main integration manager"""
    def __init__(self, api):
        self.api = api
        
        # Initialize components
        self.fits_handler = FITSHandler()
        self.plate_solver = PlateSolver()
        self.ascom_bridge = ASCOMBridge(api)
        
    def save_image(self, data: np.ndarray, header: FITSHeader) -> str:
        """Save image as FITS file"""
        return self.fits_handler.save_fits(data, header)
        
    def solve_and_sync(self, filepath: str) -> bool:
        """
        Solve plate and sync mount position
        Returns True if successful
        """
        try:
            # Solve plate
            solution = self.plate_solver.solve_field(filepath)
            if not solution:
                return False
                
            # Sync mount
            return self.ascom_bridge.sync_to_coordinates(
                solution['ra'],
                solution['dec']
            )
            
        except Exception as e:
            logger.error(f"Solve and sync failed: {e}")
            return False
            
    def get_image_coordinates(self, filepath: str) -> Optional[SkyCoord]:
        """Get coordinates from image"""
        try:
            # Load FITS file
            data, header = self.fits_handler.load_fits(filepath)
            
            # Create SkyCoord object
            coords = SkyCoord(
                ra=header['RA'] * u.degree,
                dec=header['DEC'] * u.degree
            )
            
            return coords
            
        except Exception as e:
            logger.error(f"Failed to get image coordinates: {e}")
            return None
