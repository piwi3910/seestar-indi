#!/usr/bin/env python3

"""
INDI Camera Driver for Seestar Telescope
"""

import PyIndi
import time
import logging
from threading import Lock
from seestar_api import SeestarAPI
from seestar_monitor import DeviceMonitor

class SeestarCamera(PyIndi.BaseDevice):
    def __init__(self, api: SeestarAPI, monitor: DeviceMonitor):
        super().__init__()
        self.logger = logging.getLogger("SeestarCamera")
        self.lock = Lock()
        
        # API and monitoring
        self.api = api
        self.monitor = monitor
        
        # Register for exposure events
        self.monitor.add_event_callback("exposure_complete", self._handle_exposure_complete)
        self.monitor.add_event_callback("state_change", self._handle_state_change)
        
        # Camera settings
        self.image_width = 1920  # Update with actual camera specs
        self.image_height = 1080
        self.pixel_size = 3.75  # microns
        self.bit_depth = 12
        
    def initProperties(self):
        """Initialize the driver properties"""
        
        # Connection properties
        self.connectProp = PyIndi.ISwitchVectorProperty()
        self.connectProp.name = "CONNECTION"
        self.connectProp.label = "Connection"
        self.connectProp.group = "Main Control"
        self.connectProp.p = self
        self.connectProp.perm = PyIndi.IP_RW
        self.connectProp.rule = PyIndi.ISR_1OFMANY
        
        connect_sw = PyIndi.ISwitch()
        connect_sw.name = "CONNECT"
        connect_sw.label = "Connect"
        connect_sw.s = PyIndi.ISS_OFF
        
        disconnect_sw = PyIndi.ISwitch()
        disconnect_sw.name = "DISCONNECT"
        disconnect_sw.label = "Disconnect"
        disconnect_sw.s = PyIndi.ISS_ON
        
        self.connectProp.nsp = 2
        self.connectProp.sp = [connect_sw, disconnect_sw]
        self.defineProperty(self.connectProp)
        
        # CCD Properties
        self.ccdInfoProp = PyIndi.INumberVectorProperty()
        self.ccdInfoProp.name = "CCD_INFO"
        self.ccdInfoProp.label = "CCD Information"
        self.ccdInfoProp.group = "Image Info"
        self.ccdInfoProp.p = self
        self.ccdInfoProp.perm = PyIndi.IP_RO
        
        width_n = PyIndi.INumber()
        width_n.name = "CCD_MAX_X"
        width_n.label = "Width"
        width_n.format = "%4.0f"
        width_n.value = self.image_width
        
        height_n = PyIndi.INumber()
        height_n.name = "CCD_MAX_Y"
        height_n.label = "Height"
        height_n.format = "%4.0f"
        height_n.value = self.image_height
        
        pixel_size_n = PyIndi.INumber()
        pixel_size_n.name = "CCD_PIXEL_SIZE"
        pixel_size_n.label = "Pixel Size (um)"
        pixel_size_n.format = "%6.2f"
        pixel_size_n.value = self.pixel_size
        
        bit_depth_n = PyIndi.INumber()
        bit_depth_n.name = "CCD_BITSPERPIXEL"
        bit_depth_n.label = "Bits per Pixel"
        bit_depth_n.format = "%3.0f"
        bit_depth_n.value = self.bit_depth
        
        self.ccdInfoProp.nsp = 4
        self.ccdInfoProp.np = [width_n, height_n, pixel_size_n, bit_depth_n]
        
        # Exposure property
        self.exposureProp = PyIndi.INumberVectorProperty()
        self.exposureProp.name = "CCD_EXPOSURE"
        self.exposureProp.label = "Exposure"
        self.exposureProp.group = "Main Control"
        self.exposureProp.p = self
        self.exposureProp.perm = PyIndi.IP_RW
        
        exposure_n = PyIndi.INumber()
        exposure_n.name = "CCD_EXPOSURE_VALUE"
        exposure_n.label = "Duration (s)"
        exposure_n.format = "%5.2f"
        exposure_n.min = 0.001
        exposure_n.max = 3600
        exposure_n.step = 0.001
        exposure_n.value = 1.0
        
        self.exposureProp.nsp = 1
        self.exposureProp.np = [exposure_n]
        
        # Gain property
        self.gainProp = PyIndi.INumberVectorProperty()
        self.gainProp.name = "CCD_GAIN"
        self.gainProp.label = "Gain"
        self.gainProp.group = "Image Settings"
        self.gainProp.p = self
        self.gainProp.perm = PyIndi.IP_RW
        
        gain_n = PyIndi.INumber()
        gain_n.name = "GAIN"
        gain_n.label = "Gain"
        gain_n.format = "%3.0f"
        gain_n.min = 0
        gain_n.max = 100
        gain_n.step = 1
        gain_n.value = 1
        
        self.gainProp.nsp = 1
        self.gainProp.np = [gain_n]
        
        # Frame type property
        self.frameTypeProp = PyIndi.ISwitchVectorProperty()
        self.frameTypeProp.name = "CCD_FRAME_TYPE"
        self.frameTypeProp.label = "Frame Type"
        self.frameTypeProp.group = "Image Settings"
        self.frameTypeProp.p = self
        self.frameTypeProp.perm = PyIndi.IP_RW
        self.frameTypeProp.rule = PyIndi.ISR_1OFMANY
        
        light_sw = PyIndi.ISwitch()
        light_sw.name = "FRAME_LIGHT"
        light_sw.label = "Light"
        light_sw.s = PyIndi.ISS_ON
        
        bias_sw = PyIndi.ISwitch()
        bias_sw.name = "FRAME_BIAS"
        bias_sw.label = "Bias"
        bias_sw.s = PyIndi.ISS_OFF
        
        dark_sw = PyIndi.ISwitch()
        dark_sw.name = "FRAME_DARK"
        dark_sw.label = "Dark"
        dark_sw.s = PyIndi.ISS_OFF
        
        flat_sw = PyIndi.ISwitch()
        flat_sw.name = "FRAME_FLAT"
        flat_sw.label = "Flat"
        flat_sw.s = PyIndi.ISS_OFF
        
        self.frameTypeProp.nsp = 4
        self.frameTypeProp.sp = [light_sw, bias_sw, dark_sw, flat_sw]
        
        return True
        
    def updateProperties(self):
        """Update properties when connection changes"""
        if self.isConnected():
            self.defineProperty(self.ccdInfoProp)
            self.defineProperty(self.exposureProp)
            self.defineProperty(self.gainProp)
            self.defineProperty(self.frameTypeProp)
        else:
            self.deleteProperty(self.ccdInfoProp.name)
            self.deleteProperty(self.exposureProp.name)
            self.deleteProperty(self.gainProp.name)
            self.deleteProperty(self.frameTypeProp.name)
        return True
        
    def ISNewNumber(self, dev, name, values, names):
        """Handle number property changes"""
        if name == "CCD_EXPOSURE":
            exposure = self.IUFindNumber(values, "CCD_EXPOSURE_VALUE")
            if not exposure:
                return False
                
            if self.monitor.state.exposing:
                self.IDMessage("Camera is already exposing")
                return False
                
            # Start exposure via monitor
            if self.monitor.start_exposure(exposure.value, int(self.gainProp.np[0].value)):
                self.exposureProp.s = PyIndi.IPS_BUSY
                self.IDSetNumber(self.exposureProp)
                return True
            else:
                self.IDMessage("Failed to start exposure")
                return False
                
        elif name == "CCD_GAIN":
            gain = self.IUFindNumber(values, "GAIN")
            if not gain:
                return False
                
            if self.monitor.state.exposing:
                self.IDMessage("Cannot change gain while exposing")
                return False
                
            self.gainProp.np[0].value = gain.value
            self.gainProp.s = PyIndi.IPS_OK
            self.IDSetNumber(self.gainProp)
            return True
            
        return False
        
    def ISNewSwitch(self, dev, name, states, names):
        """Handle switch property changes"""
        if name == "CONNECTION":
            connect = self.IUFindSwitch(states, "CONNECT")
            disconnect = self.IUFindSwitch(states, "DISCONNECT")
            
            if connect.s == PyIndi.ISS_ON:
                self.connectCamera()
            else:
                self.disconnectCamera()
                
            return True
            
        elif name == "CCD_FRAME_TYPE":
            if self.monitor.state.exposing:
                self.IDMessage("Cannot change frame type while exposing")
                return False
                
            self.IUUpdateSwitch(self.frameTypeProp, states, names)
            self.frameTypeProp.s = PyIndi.IPS_OK
            self.IDSetSwitch(self.frameTypeProp)
            return True
            
        return False
        
    def connectCamera(self):
        """Connect to the camera"""
        self.connectProp.s = PyIndi.IPS_OK
        self.IDSetSwitch(self.connectProp)
        self.IDMessage("Camera connected successfully")
        return True
        
    def disconnectCamera(self):
        """Disconnect from the camera"""
        if self.monitor.state.exposing:
            self.monitor.abort_exposure()
            
        self.connectProp.s = PyIndi.IPS_IDLE
        self.IDSetSwitch(self.connectProp)
        self.IDMessage("Camera disconnected successfully")
        return True
        
    def _handle_exposure_complete(self, event):
        """Handle exposure completion"""
        self.exposureProp.s = PyIndi.IPS_OK
        self.IDSetNumber(self.exposureProp)
        self.IDMessage("Exposure complete")
        
    def _handle_state_change(self, event):
        """Handle state changes"""
        if event["property"] == "error" and event["new_value"]:
            self.IDMessage(f"Camera error: {event['new_value']}")
            self.exposureProp.s = PyIndi.IPS_ALERT
            self.IDSetNumber(self.exposureProp)
