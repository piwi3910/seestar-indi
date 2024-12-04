#!/usr/bin/env python3

"""
INDI Focuser Driver for Seestar Telescope
"""

import PyIndi
import logging
from threading import Lock
from seestar_api import SeestarAPI
from seestar_monitor import DeviceMonitor

class SeestarFocuser(PyIndi.BaseDevice):
    def __init__(self, api: SeestarAPI, monitor: DeviceMonitor):
        super().__init__()
        self.logger = logging.getLogger("SeestarFocuser")
        self.lock = Lock()
        
        # API and monitoring
        self.api = api
        self.monitor = monitor
        
        # Register for state changes
        self.monitor.add_event_callback("state_change", self._handle_state_change)
        
        # Focuser settings
        self.max_position = 100000  # Maximum steps
        self.step_size = 1  # Microns per step
        self.backlash = 0
        
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
        
        # Absolute Position
        self.positionProp = PyIndi.INumberVectorProperty()
        self.positionProp.name = "ABS_FOCUS_POSITION"
        self.positionProp.label = "Absolute Position"
        self.positionProp.group = "Main Control"
        self.positionProp.p = self
        self.positionProp.perm = PyIndi.IP_RW
        
        position_n = PyIndi.INumber()
        position_n.name = "FOCUS_ABSOLUTE_POSITION"
        position_n.label = "Position"
        position_n.format = "%6.0f"
        position_n.min = 0
        position_n.max = self.max_position
        position_n.step = 1
        position_n.value = self.monitor.state.focus_position
        
        self.positionProp.nsp = 1
        self.positionProp.np = [position_n]
        
        # Relative Position
        self.relativeProp = PyIndi.INumberVectorProperty()
        self.relativeProp.name = "REL_FOCUS_POSITION"
        self.relativeProp.label = "Relative Position"
        self.relativeProp.group = "Main Control"
        self.relativeProp.p = self
        self.relativeProp.perm = PyIndi.IP_RW
        
        relative_n = PyIndi.INumber()
        relative_n.name = "FOCUS_RELATIVE_POSITION"
        relative_n.label = "Position"
        relative_n.format = "%6.0f"
        relative_n.min = -50000
        relative_n.max = 50000
        relative_n.step = 1
        relative_n.value = 0
        
        self.relativeProp.nsp = 1
        self.relativeProp.np = [relative_n]
        
        # Auto Focus
        self.autoFocusProp = PyIndi.ISwitchVectorProperty()
        self.autoFocusProp.name = "FOCUS_AUTO"
        self.autoFocusProp.label = "Auto Focus"
        self.autoFocusProp.group = "Main Control"
        self.autoFocusProp.p = self
        self.autoFocusProp.perm = PyIndi.IP_RW
        self.autoFocusProp.rule = PyIndi.ISR_1OFMANY
        
        auto_sw = PyIndi.ISwitch()
        auto_sw.name = "FOCUS_AUTO_TOGGLE"
        auto_sw.label = "Auto Focus"
        auto_sw.s = PyIndi.ISS_OFF
        
        self.autoFocusProp.nsp = 1
        self.autoFocusProp.sp = [auto_sw]
        
        # Temperature
        self.temperatureProp = PyIndi.INumberVectorProperty()
        self.temperatureProp.name = "FOCUS_TEMPERATURE"
        self.temperatureProp.label = "Temperature"
        self.temperatureProp.group = "Main Control"
        self.temperatureProp.p = self
        self.temperatureProp.perm = PyIndi.IP_RO
        
        temp_n = PyIndi.INumber()
        temp_n.name = "TEMPERATURE"
        temp_n.label = "Celsius"
        temp_n.format = "%6.2f"
        temp_n.value = self.monitor.state.focus_temperature
        
        self.temperatureProp.nsp = 1
        self.temperatureProp.np = [temp_n]
        
        return True
        
    def updateProperties(self):
        """Update properties when connection changes"""
        if self.isConnected():
            self.defineProperty(self.positionProp)
            self.defineProperty(self.relativeProp)
            self.defineProperty(self.autoFocusProp)
            self.defineProperty(self.temperatureProp)
        else:
            self.deleteProperty(self.positionProp.name)
            self.deleteProperty(self.relativeProp.name)
            self.deleteProperty(self.autoFocusProp.name)
            self.deleteProperty(self.temperatureProp.name)
        return True
        
    def ISNewNumber(self, dev, name, values, names):
        """Handle number property changes"""
        if name == "ABS_FOCUS_POSITION":
            position = self.IUFindNumber(values, "FOCUS_ABSOLUTE_POSITION")
            if not position:
                return False
                
            if self.monitor.state.focus_moving or self.monitor.state.auto_focusing:
                self.IDMessage("Focuser is already moving")
                return False
                
            target = int(position.value)
            if target < 0 or target > self.max_position:
                self.IDMessage(f"Target position {target} is out of range")
                return False
                
            # Move focuser via API
            if self.api.send_command("method_sync", {
                "method": "set_focus_position",
                "params": {"position": target}
            }):
                self.positionProp.s = PyIndi.IPS_BUSY
                self.IDSetNumber(self.positionProp)
                return True
            else:
                self.IDMessage("Failed to move focuser")
                return False
                
        elif name == "REL_FOCUS_POSITION":
            steps = self.IUFindNumber(values, "FOCUS_RELATIVE_POSITION")
            if not steps:
                return False
                
            if self.monitor.state.focus_moving or self.monitor.state.auto_focusing:
                self.IDMessage("Focuser is already moving")
                return False
                
            target = self.monitor.state.focus_position + int(steps.value)
            if target < 0 or target > self.max_position:
                self.IDMessage(f"Target position {target} is out of range")
                return False
                
            # Move focuser via API
            if self.api.send_command("method_sync", {
                "method": "set_focus_position",
                "params": {"position": target}
            }):
                self.positionProp.s = PyIndi.IPS_BUSY
                self.IDSetNumber(self.positionProp)
                return True
            else:
                self.IDMessage("Failed to move focuser")
                return False
                
        return False
        
    def ISNewSwitch(self, dev, name, states, names):
        """Handle switch property changes"""
        if name == "CONNECTION":
            connect = self.IUFindSwitch(states, "CONNECT")
            disconnect = self.IUFindSwitch(states, "DISCONNECT")
            
            if connect.s == PyIndi.ISS_ON:
                self.connectFocuser()
            else:
                self.disconnectFocuser()
                
            return True
            
        elif name == "FOCUS_AUTO":
            auto = self.IUFindSwitch(states, "FOCUS_AUTO_TOGGLE")
            if auto.s == PyIndi.ISS_ON:
                if self.monitor.state.focus_moving or self.monitor.state.auto_focusing:
                    self.IDMessage("Focuser is already moving")
                    return False
                    
                # Start auto focus via monitor
                if self.monitor.start_autofocus():
                    self.autoFocusProp.s = PyIndi.IPS_BUSY
                    self.IDSetSwitch(self.autoFocusProp)
                    return True
                else:
                    self.IDMessage("Failed to start auto focus")
                    return False
                    
            return True
            
        return False
        
    def connectFocuser(self):
        """Connect to the focuser"""
        self.connectProp.s = PyIndi.IPS_OK
        self.IDSetSwitch(self.connectProp)
        self.IDMessage("Focuser connected successfully")
        return True
        
    def disconnectFocuser(self):
        """Disconnect from the focuser"""
        self.connectProp.s = PyIndi.IPS_IDLE
        self.IDSetSwitch(self.connectProp)
        self.IDMessage("Focuser disconnected successfully")
        return True
        
    def _handle_state_change(self, event):
        """Handle state changes"""
        if event["property"] == "focus_position":
            self.positionProp.np[0].value = event["new_value"]
            if not self.monitor.state.focus_moving:
                self.positionProp.s = PyIndi.IPS_OK
                self.IDSetNumber(self.positionProp)
                
        elif event["property"] == "focus_moving":
            if event["new_value"]:
                self.positionProp.s = PyIndi.IPS_BUSY
            else:
                self.positionProp.s = PyIndi.IPS_OK
            self.IDSetNumber(self.positionProp)
            
        elif event["property"] == "auto_focusing":
            if event["new_value"]:
                self.autoFocusProp.s = PyIndi.IPS_BUSY
            else:
                self.autoFocusProp.sp[0].s = PyIndi.ISS_OFF
                self.autoFocusProp.s = PyIndi.IPS_OK
            self.IDSetSwitch(self.autoFocusProp)
            
        elif event["property"] == "focus_temperature":
            self.temperatureProp.np[0].value = event["new_value"]
            self.temperatureProp.s = PyIndi.IPS_OK
            self.IDSetNumber(self.temperatureProp)
            
        elif event["property"] == "error" and event["new_value"]:
            self.IDMessage(f"Focuser error: {event['new_value']}")
            self.positionProp.s = PyIndi.IPS_ALERT
            self.IDSetNumber(self.positionProp)
