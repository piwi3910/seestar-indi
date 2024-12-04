#!/usr/bin/env python3

"""
INDI Filter Wheel Driver for Seestar Telescope
"""

import PyIndi
import logging
from threading import Lock
from seestar_api import SeestarAPI
from seestar_monitor import DeviceMonitor

class SeestarFilterWheel(PyIndi.BaseDevice):
    def __init__(self, api: SeestarAPI, monitor: DeviceMonitor):
        super().__init__()
        self.logger = logging.getLogger("SeestarFilterWheel")
        self.lock = Lock()
        
        # API and monitoring
        self.api = api
        self.monitor = monitor
        
        # Register for state changes
        self.monitor.add_event_callback("state_change", self._handle_state_change)
        
        # Filter settings
        self.filter_count = 2  # LP filter on/off
        self.filter_names = ["Clear", "LP"]  # Default filter names
        
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
        
        # Filter Slot property
        self.filterSlotProp = PyIndi.INumberVectorProperty()
        self.filterSlotProp.name = "FILTER_SLOT"
        self.filterSlotProp.label = "Filter"
        self.filterSlotProp.group = "Main Control"
        self.filterSlotProp.p = self
        self.filterSlotProp.perm = PyIndi.IP_RW
        
        filter_n = PyIndi.INumber()
        filter_n.name = "FILTER_SLOT_VALUE"
        filter_n.label = "Filter Position"
        filter_n.format = "%3.0f"
        filter_n.min = 1
        filter_n.max = self.filter_count
        filter_n.step = 1
        filter_n.value = self.monitor.state.filter_position + 1  # 1-based index for display
        
        self.filterSlotProp.nsp = 1
        self.filterSlotProp.np = [filter_n]
        
        # Filter names property
        self.filterNamesProp = PyIndi.ITextVectorProperty()
        self.filterNamesProp.name = "FILTER_NAME"
        self.filterNamesProp.label = "Filter Names"
        self.filterNamesProp.group = "Main Control"
        self.filterNamesProp.p = self
        self.filterNamesProp.perm = PyIndi.IP_RW
        
        filter_names = []
        for i in range(self.filter_count):
            filter_t = PyIndi.IText()
            filter_t.name = f"FILTER_NAME_{i+1}"
            filter_t.label = f"Filter #{i+1}"
            filter_t.text = self.filter_names[i]
            filter_names.append(filter_t)
            
        self.filterNamesProp.ntp = self.filter_count
        self.filterNamesProp.tp = filter_names
        
        return True
        
    def updateProperties(self):
        """Update properties when connection changes"""
        if self.isConnected():
            self.defineProperty(self.filterSlotProp)
            self.defineProperty(self.filterNamesProp)
        else:
            self.deleteProperty(self.filterSlotProp.name)
            self.deleteProperty(self.filterNamesProp.name)
        return True
        
    def ISNewNumber(self, dev, name, values, names):
        """Handle number property changes"""
        if name == "FILTER_SLOT":
            filter_slot = self.IUFindNumber(values, "FILTER_SLOT_VALUE")
            if not filter_slot:
                return False
                
            # Convert from 1-based to 0-based index
            target_filter = int(filter_slot.value) - 1
            
            if target_filter < 0 or target_filter >= self.filter_count:
                self.IDMessage(f"Invalid filter position {target_filter + 1}")
                return False
                
            if self.monitor.state.filter_moving:
                self.IDMessage("Filter wheel is already moving")
                return False
                
            # Move filter via monitor
            if self.monitor.move_filter(target_filter):
                self.filterSlotProp.s = PyIndi.IPS_BUSY
                self.IDSetNumber(self.filterSlotProp)
                return True
            else:
                self.IDMessage("Failed to move filter")
                return False
                
        return False
        
    def ISNewText(self, dev, name, texts, names):
        """Handle text property changes"""
        if name == "FILTER_NAME":
            # Update filter names
            for i in range(self.filter_count):
                filter_name = self.IUFindText(texts, f"FILTER_NAME_{i+1}")
                if filter_name:
                    self.filter_names[i] = filter_name.text
                    
            self.filterNamesProp.s = PyIndi.IPS_OK
            self.IDSetText(self.filterNamesProp)
            return True
            
        return False
        
    def ISNewSwitch(self, dev, name, states, names):
        """Handle switch property changes"""
        if name == "CONNECTION":
            connect = self.IUFindSwitch(states, "CONNECT")
            disconnect = self.IUFindSwitch(states, "DISCONNECT")
            
            if connect.s == PyIndi.ISS_ON:
                self.connectFilterWheel()
            else:
                self.disconnectFilterWheel()
                
            return True
            
        return False
        
    def connectFilterWheel(self):
        """Connect to the filter wheel"""
        self.connectProp.s = PyIndi.IPS_OK
        self.IDSetSwitch(self.connectProp)
        self.IDMessage("Filter wheel connected successfully")
        return True
        
    def disconnectFilterWheel(self):
        """Disconnect from the filter wheel"""
        self.connectProp.s = PyIndi.IPS_IDLE
        self.IDSetSwitch(self.connectProp)
        self.IDMessage("Filter wheel disconnected successfully")
        return True
        
    def _handle_state_change(self, event):
        """Handle state changes"""
        if event["property"] == "filter_position":
            # Update position display (convert to 1-based index)
            self.filterSlotProp.np[0].value = event["new_value"] + 1
            self.filterSlotProp.s = PyIndi.IPS_OK
            self.IDSetNumber(self.filterSlotProp)
            self.IDMessage(f"Filter changed to {self.filter_names[event['new_value']]}")
            
        elif event["property"] == "filter_moving":
            if event["new_value"]:
                self.filterSlotProp.s = PyIndi.IPS_BUSY
            else:
                self.filterSlotProp.s = PyIndi.IPS_OK
            self.IDSetNumber(self.filterSlotProp)
            
        elif event["property"] == "error" and event["new_value"]:
            self.IDMessage(f"Filter wheel error: {event['new_value']}")
            self.filterSlotProp.s = PyIndi.IPS_ALERT
            self.IDSetNumber(self.filterSlotProp)
