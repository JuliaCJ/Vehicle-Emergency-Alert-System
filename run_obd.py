import atexit
import sys
import time
import json
from datetime import datetime, timedelta
from time import sleep

import obdpi.shared_settings
from obdpi.log_manager import LogManager
from obdpi.obd_manager import ObdManager
from obdpi.print_manager import PrintManager
from obdpi.serial_manager import SerialManager

log_man = LogManager()
print_man = PrintManager()
ser_man = SerialManager()
obd_man = ObdManager()

last_logged_time = 0
snapshot_interval = 3  # Save at least once every 3 seconds
rolling_data = []
rolling_window_minutes = 5
json_path = "obd_data.json"


#@print_man.print_event_decorator("Initialize Serial Connection")
#@log_man.log_event_decorator("Initialize Serial Connection", "INFO")
def init_serial(is_testing, environment):
    try:
        ser_man.init_serial_connection(is_testing, environment)
        return "SUCCESS" if ser_man.has_serial_connection() else "FAIL"
    except Exception as e:
        return "[EXCEPTION] " + str(e)


#@print_man.print_event_decorator("Initialize OBD Connection")
#@log_man.log_event_decorator("Initialize OBD Connection", "INFO")
def init_obd(connection_id):
    try:
        obd_man.init_obd_connection(connection_id)
        return "SUCCESS" if obd_man.has_obd_connection() else "FAIL"
    except Exception as e:
        return "[EXCEPTION] " + str(e)


def pretty_print_obd_data(obd_data):
    print("\n--- OBD Data Snapshot ---")
    for key, value in sorted(obd_data.items()):
        if isinstance(value, str) and "Unknown : 0.0" in value:
            continue  # Skip noisy/irrelevant values

        if key == "O2_SENSORS":
            try:
                _, bank1, bank2 = value
                b1 = ", ".join(["?" if v else "?" for v in bank1])
                b2 = ", ".join(["?" if v else "?" for v in bank2])
                print(f"{key:30}: Bank1 [{b1}] | Bank2 [{b2}]")
            except:
                print(f"{key:30}: {value}")
        else:
            print(f"{key:30}: {value}")


def prune_old_data(data, minutes=5):
    cutoff = datetime.now() - timedelta(minutes=minutes)
    return [entry for entry in data if datetime.fromisoformat(entry["timestamp"]) > cutoff]


def get_data():
    global last_logged_time, rolling_data

    # Init connections

    if not init_serial(obdpi.shared_settings.is_testing, obdpi.shared_settings.environment) == "SUCCESS":
        return "SERIAL FAILURE"
    if not init_obd(ser_man.connection_id) == "SUCCESS":
        return "OBD FAILURE"
            


    
    try:
        # Check if serial connection is still valid
        if not ser_man.has_serial_connection():
            #print("[ERROR] Serial connection lost. Exiting...")
            return "SERIAL ERROR"  # Exit if serial connection is lost

        # Check if OBD connection is still valid
        if not obd_man.has_obd_connection():
            #print("[ERROR] OBD connection lost. Exiting...")
            return "OBD ERROR"  # Exit if OBD connection is lost

        raw_response = obd_man.generate_obd_response()

        # Filter values: Remove unwanted "Unknown" data
        filtered_response = {}
        for key, val in raw_response.items():
            if isinstance(val, str) and "Unknown" in val:
                continue
            if key == "O2_SENSORS" and isinstance(val, str):
                try:
                    val = eval(val)  # Convert string to tuple if needed
                except:
                    pass
            filtered_response[key] = val
        return filtered_response

    except KeyboardInterrupt:
        return "KEYBOARD ERROR"
    except Exception as e:
        print(f"[ERROR] Runtime exception: {e}")
        sleep(1.0)

    # End the script when disconnected
    print("[INFO] Exiting script due to lost connection.")
    sys.exit()


@print_man.print_event_decorator("Ending Script")
@log_man.log_event_decorator("Ending Script", "INFO")
def end():
    sys.exit()


if __name__ == "__main__":
    atexit.register(end)
    start()
