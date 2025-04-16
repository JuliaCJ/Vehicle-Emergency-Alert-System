import run_obd
import run_gps

import sys
import time
import json
from datetime import datetime, timedelta
from time import sleep
import threading

from sense_hat import SenseHat

sense = SenseHat()
red = (255, 0, 0)

run = True

last_logged_time = 0
snapshot_interval = 3  # Save at least once every 3 seconds
rolling_data = []
rolling_window_minutes = 5
json_path = "obd_data.json"

auto_alert = False
manual_alert = False
alert = False
initial_alert = False
deactivated = False

filtered_response = ""
current_time = datetime.now().isoformat()

entry = {
		"Alert" : "",
		"location": "",
		"timestamp": "",
		"data": ""
	}

def save_data_to_json(data, path="obd_data.json"):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        
def pretty_print_obd_data(location, time, obd_data):
    print("\n--- OBD Data Snapshot ---")
    print(f"Location: {location}\n")
    print(f"Time {time}\n")
    for key, value in sorted(obd_data.items()):
        if isinstance(value, str) and "Unknown" in value:
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

def led_flash():
	global alert
	while alert:
		sense.clear(red)
		sleep(0.5)
		sense.clear()
		sleep(0.5)
		
def prune_old_data(data, minutes=5):
    cutoff = datetime.now() - timedelta(minutes=minutes)
    return [entry for entry in data if datetime.fromisoformat(entry["timestamp"]) > cutoff]
		
def capture_data(entry):
	global rolling_data
	global rolling_window_minutes
	global json_path
	
	# Keep only last 5 minutes of entries
	rolling_data.append(entry)
	rolling_data = prune_old_data(rolling_data, minutes=rolling_window_minutes)
	save_data_to_json(rolling_data, path=json_path)
	sleep(0.15)
	
def get_entry(location, filtered_response):
    global last_logged_time
    global snapshot_interval
    global auto_alert 
    global manual_alert
    global alert
    global initial_alert
    global deactivated

    now = time.time()
    if (now - last_logged_time >= snapshot_interval) or initial_alert or deactivated:
        last_logged_time = now
        current_time = datetime.now().isoformat()

        if not alert:
            return {
                "Alert": "No Alerts",
                "location": location,
                "timestamp": current_time,
                "data": filtered_response
            }
        elif deactivated:
            deactivated = False
            return {
                "Alert": f"MANUAL ALERT DEACTIVATED AT {current_time}",
                "location": location,
                "timestamp": current_time,
                "data": filtered_response
            }
        elif manual_alert:
            if initial_alert:
                initial_alert = False
                return {
                    "Alert": f"MANUAL ALERT ACTIVATED AT {current_time}",
                    "location": location,
                    "timestamp": current_time,
                    "data": filtered_response
                }
            else:
                return {
                    "Alert": "MANUAL ALERT!",
                    "location": location,
                    "timestamp": current_time,
                    "data": filtered_response
                }
        elif auto_alert:
            if initial_alert:
                initial_alert = False
                return {
                    "Alert": f"AUTO ALERT ACTIVATED AT {current_time}",
                    "location": location,
                    "timestamp": current_time,
                    "data": filtered_response
                }
            else:
                return {
                    "Alert": "AUTO ALERT!",
                    "location": location,
                    "timestamp": current_time,
                    "data": filtered_response
                }
    return None
	


while run:
	for event in sense.stick.get_events():
		if event.action == 'released' and not alert:
			manual_alert = True
			alert = True
			initial_alert = True
			flash = threading.Thread(target=led_flash)
			flash.start()
			break
			
		if event.action == 'released' and alert:
			alert = False
			manual_alert = False
			deactivated = True
			break
		
		if event.held == 'held':
			alert = False
			manual_alert = False
			deactivated = False
			run = False
			print("ENDING DATA COLLECTION")
			sys.exit()
	
	obd_data = run_obd.get_data()
	
	if isinstance (obd_data, str):
		print(obd_data)
		break

	# Print pretty formatted OBD data
	location = run_gps.get_location()
	current_time = datetime.now().isoformat()

	entry = get_entry(location, obd_data)

	if entry:
		pretty_print_obd_data(location, current_time, obd_data)
		capture_data(entry)

	sleep(0.15)
	
