# -*- coding: utf-8 -*-

import obd

class ObdManager:

    KPA_TO_PSI_CONVERSION_FACTOR = 0.145038

    def __init__(self):
        self.obd_connection = None

    def init_obd_connection(self, serial_connection_id):
        try:
            available_ports = obd.scan_serial()
            if serial_connection_id in available_ports:
                self.obd_connection = obd.OBD(serial_connection_id, fast=False)  # slow mode for older vehicles
                #print("Initialize OBD Connection: SUCCESS")
        except Exception as e:
            print("[ERROR] OBD Init: " + str(e))
            self.obd_connection = None

    def has_obd_connection(self):
        return self.obd_connection is not None and self.obd_connection.is_connected()

    def generate_obd_response(self):
        if not self.has_obd_connection():
            return "No OBD connection"

        # Get the set of supported commands from the car
        supported = self.obd_connection.supported_commands
        results = {}
    
        # Optional unit map (can also pull dynamically if needed)
        units = {
            "RPM": "RPM",
            "SPEED": "MPH",
            "COOLANT_TEMP": "\u00b0C",
            "THROTTLE_POS": "%",
            "MAF": "g/s",
            "INTAKE_PRESSURE": "PSI",
            "FUEL_LEVEL": "%",
            "ENGINE_LOAD": "%",
            "TIMING_ADVANCE": "\u00b0",
            "MASS_AIR_FLOW": "g/s",
            "O2_SENSORS": "",
        }
    
        # Go through all possible commands in the obd.commands module
        for name in dir(obd.commands):
            command = getattr(obd.commands, name)
            if not isinstance(command, obd.OBDCommand):
                continue
    
            # Only query if the car supports it
            if command not in supported:
                continue
    
            try:
                response = self.obd_connection.query(command)
                if response.is_null():
                    continue  # skip empty values
    
                val = response.value
    
                # Format special responses like O2_SENSORS
                if name == "O2_SENSORS":
                    results[name] = str(val)
                elif hasattr(val, 'magnitude'):
                    if units.get(name) == "PSI":
                        converted = round(val.magnitude * self.KPA_TO_PSI_CONVERSION_FACTOR, 3)
                        results[name] = "{} {}".format(converted, units.get(name, ""))
                    else:
                        results[name] = "{} {}".format(val.magnitude, units.get(name, ""))
                else:
                    results[name] = str(val)
    
            except Exception as e:
                results[name] = f"[EXCEPTION] {name}: {e}"
    
        return results   
        

    def get_unit(self, name):
        # Define units for each command
        units = {
            "RPM": "RPM",
            "SPEED": "MPH",
            "COOLANT_TEMP": "\u00b0C",
            "THROTTLE_POS": "%",
            "MAF": "g/s",
            "INTAKE_PRESSURE": "PSI",
            "FUEL_LEVEL": "%",
            "ENGINE_LOAD": "%",
            "TIMING_ADVANCE": "\u00b0",
            "MASS_AIR_FLOW": "g/s",
            "O2_SENSORS": "V"
        }
        return units.get(name, "Unknown")

