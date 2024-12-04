#!/usr/bin/env python3

"""
Extended INDI Driver for Seestar Telescope
Adds additional functionality while preserving existing mount control
"""

import logging
from seestar import SeeStarDevice
from seestar_camera import SeestarCamera
from seestar_filterwheel import SeestarFilterWheel
from seestar_focuser import SeestarFocuser
from seestar_api import SeestarAPI
from seestar_monitor import DeviceMonitor

class ExtendedSeestarDevice(SeeStarDevice):
    def __init__(self, name=None, number=1):
        """
        Extend the base SeestarDevice with additional capabilities
        """
        super().__init__(name=name, number=number)
        
        # Setup logging
        self.logger = logging.getLogger("SeestarDriver")
        
        # Initialize API client
        self.api = SeestarAPI(device_num=number)
        
        # Initialize device monitor
        self.monitor = DeviceMonitor(self.api)
        
        # Initialize additional devices
        self.camera = SeestarCamera(self.api, self.monitor)
        self.filterwheel = SeestarFilterWheel(self.api, self.monitor)
        self.focuser = SeestarFocuser(self.api, self.monitor)
        
        # Register state change callbacks
        self.monitor.add_event_callback("state_change", self._handle_state_change)
        
    def ISGetProperties(self, device=None):
        """
        Add properties from all devices
        """
        # Get mount properties from parent class
        super().ISGetProperties(device)
        
        # Initialize properties for additional devices
        self.camera.initProperties()
        self.filterwheel.initProperties()
        self.focuser.initProperties()
        
    def ISNewNumber(self, device, name, names, values):
        """
        Handle number property changes for all devices
        """
        # Check if the property belongs to additional devices
        if name.startswith("CCD_"):
            return self.camera.ISNewNumber(device, name, names, values)
        elif name.startswith("FILTER_"):
            return self.filterwheel.ISNewNumber(device, name, names, values)
        elif name.startswith("FOCUS_"):
            return self.focuser.ISNewNumber(device, name, names, values)
            
        # Otherwise, handle mount properties
        return super().ISNewNumber(device, name, names, values)
        
    def ISNewSwitch(self, device, name, names, values):
        """
        Handle switch property changes for all devices
        """
        if name == "CONNECTION":
            connect = self.IUFindSwitch(values, "CONNECT")
            if connect.s == PyIndi.ISS_ON:
                # Start monitoring when connecting
                self.monitor.start()
            else:
                # Stop monitoring when disconnecting
                self.monitor.stop()
                
        # Check if the property belongs to additional devices
        if name.startswith("CCD_"):
            return self.camera.ISNewSwitch(device, name, names, values)
        elif name.startswith("FILTER_"):
            return self.filterwheel.ISNewSwitch(device, name, names, values)
        elif name.startswith("FOCUS_"):
            return self.focuser.ISNewSwitch(device, name, names, values)
            
        # Otherwise, handle mount properties
        return super().ISNewSwitch(device, name, names, values)
        
    def ISNewText(self, device, name, names, values):
        """
        Handle text property changes for all devices
        """
        # Check if the property belongs to additional devices
        if name.startswith("CCD_"):
            return self.camera.ISNewText(device, name, names, values)
        elif name.startswith("FILTER_"):
            return self.filterwheel.ISNewText(device, name, names, values)
        elif name.startswith("FOCUS_"):
            return self.focuser.ISNewText(device, name, names, values)
            
        # Otherwise, handle mount properties
        return super().ISNewText(device, name, names, values)
        
    def updateProperties(self):
        """
        Update properties when connection changes
        """
        # Update mount properties
        super().updateProperties()
        
        # Update additional device properties
        if self.isConnected():
            self.camera.updateProperties()
            self.filterwheel.updateProperties()
            self.focuser.updateProperties()
            
    def _handle_state_change(self, event):
        """Handle device state changes"""
        property_name = event["property"]
        new_value = event["new_value"]
        
        # Update INDI properties based on state changes
        if property_name in ["ra", "dec"]:
            self.IUUpdate(
                self._devname,
                "EQUATORIAL_EOD_COORD",
                [self.monitor.state.ra, self.monitor.state.dec],
                ["RA", "DEC"],
                Set=True
            )
            
        elif property_name == "slewing":
            if new_value:
                self.eqProp.s = PyIndi.IPS_BUSY
            else:
                self.eqProp.s = PyIndi.IPS_OK
            self.IDSetNumber(self.eqProp)
            
        elif property_name == "error":
            if new_value:
                self.IDMessage(f"Error: {new_value}")
                
    @property
    def isConnected(self):
        """Check if all devices are connected"""
        conn = self.__getitem__("CONNECTION")
        return conn["CONNECT"].value == 'On'
        
    def Cleanup(self):
        """Clean up resources"""
        self.monitor.stop()
        super().Cleanup()

# Only create the extended device if this file is run directly
if __name__ == "__main__":
    import os
    import PyIndi
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s: %(message)s'
    )
    
    # Get device configuration from environment
    name = os.environ['INDIDEV']
    number = int(os.environ['INDICONFIG'])
    
    # Create and start device
    device = ExtendedSeestarDevice(name, number)
    device.start()
