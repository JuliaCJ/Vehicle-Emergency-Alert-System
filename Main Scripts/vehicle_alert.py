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

sense.clear()

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

flash_thread = None
flash_running = False

filtered_response = ""
current_time = datetime.now().isoformat()

def extract_number(value):
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return 0.0
    parts = value.strip().split(" ")[0]
    try:
        return float(parts)
    except ValueError:
        return 0.0

def filter_important_parameters(data):
    important_keys = [
        "COOLANT_TEMP", "CONTROL_MODULE_VOLTAGE", "RPM", "SPEED",
        "ENGINE_LOAD", "FUEL_LEVEL", "CATALYST_TEMP_B1S1", "CATALYST_TEMP_B2S1",
        "GET_CURRENT_DTC", "GET_DTC"
    ]
    filtered = {}

    for key in important_keys:
        if key in data:
            filtered[key] = data[key]
        else:
            filtered[key] = "N/A"  # Add missing keys with default value

    # Handle missing DTC fields
    if filtered["GET_CURRENT_DTC"] in ("[]", [], None, "N/A"):
        filtered["GET_CURRENT_DTC"] = "No codes"
    if filtered["GET_DTC"] in ("[]", [], None, "N/A"):
        filtered["GET_DTC"] = "No codes"

    return filtered

def generate_alert(data):
    alerts = []

    try:
        coolant_temp = extract_number(data.get("COOLANT_TEMP", "0"))
        control_voltage = extract_number(data.get("CONTROL_MODULE_VOLTAGE", "0"))
        rpm = extract_number(data.get("RPM", "0"))
        speed = extract_number(data.get("SPEED", "0"))
        speed = speed / 0.621371 # Convert KPH to MPH
        engine_load = extract_number(data.get("ENGINE_LOAD", "0"))
        fuel_level = extract_number(data.get("FUEL_LEVEL", "100"))
        catalyst_temp_b1s1 = extract_number(data.get("CATALYST_TEMP_B1S1", "0"))
        catalyst_temp_b2s1 = extract_number(data.get("CATALYST_TEMP_B2S1", "0"))

        if coolant_temp > 110:
            alerts.append("Engine Overheating")
        if control_voltage < 11.5:
            alerts.append("Low Battery Voltage")
        if rpm > 6000:
            alerts.append("High RPM - Possible Redline")
        if speed > 90:
            alerts.append("Overspeed Condition")
        if engine_load > 85:
            alerts.append("High Engine Load")
        #if fuel_level < 10:
            
            #print(fuel_level)
            #alerts.append("Low Fuel Warning")
        if catalyst_temp_b1s1 > 900 or catalyst_temp_b2s1 > 900:
            alerts.append("Catalyst Overheating - Fire Risk")
        if "Check Engine Light Active" in (data.get("GET_CURRENT_DTC"), data.get("GET_DTC")):
            alerts.append("Check Engine Light Active")

        # If no alerts, add a "No Alerts" message
        if not alerts:
            alerts.append("No Auto-Alerts")

    except Exception as e:
        alerts.append(f"Alert System Error: {e}")

    return alerts

def save_data_to_json(data, path="obd_data.json"):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def pretty_print_obd_data(location, time, obd_data, alerts):
    print("\n--- OBD Data Snapshot ---")
    print(f"Location: {location}\n")
    print(f"Time: {time}\n")
     # Print the alerts
    print(f"Alerts: {' | '.join(alerts)}\n") 

    for key in [
        "COOLANT_TEMP", "CONTROL_MODULE_VOLTAGE", "RPM", "SPEED",
        "ENGINE_LOAD", "FUEL_LEVEL", "CATALYST_TEMP_B1S1", "CATALYST_TEMP_B2S1",
        "GET_CURRENT_DTC", "GET_DTC"
    ]:
        value = obd_data.get(key, "N/A")
        print(f"{key:30}: {value}")


def led_flash():
    global flash_running
    flash_running = True
    while alert:
        sense.clear(red)
        sleep(0.5)
        sense.clear()
        sleep(0.5)
    flash_running = False


def prune_old_data(data, minutes=5):
    cutoff = datetime.now() - timedelta(minutes=minutes)
    return [entry for entry in data if datetime.fromisoformat(entry["timestamp"]) > cutoff]

def capture_data(entry):
    global rolling_data
    rolling_data.append(entry)
    rolling_data = prune_old_data(rolling_data, minutes=rolling_window_minutes)
    save_data_to_json(rolling_data, path=json_path)
    upload_to_aws(entry)  # ?? Send to AWS
    sleep(0.15)

def get_entry(location, filtered_response):
    global last_logged_time
    global snapshot_interval
    global auto_alert
    global manual_alert
    global alert
    global initial_alert
    global deactivated
    global flash_thread

    now = time.time()
    if (now - last_logged_time >= snapshot_interval) or initial_alert or deactivated:
        last_logged_time = now
        current_time = datetime.now().isoformat()

        system_alerts = generate_alert(filtered_response)

        if manual_alert:
            if initial_alert:
                initial_alert = False
                system_alerts.append(f"MANUAL ALERT ACTIVATED AT {current_time}")
            else:
                system_alerts.append("MANUAL ALERT!")

        if deactivated:
            deactivated = False
            system_alerts.append(f"MANUAL ALERT DEACTIVATED AT {current_time}")

        if auto_alert:
            if initial_alert:
                initial_alert = False
                system_alerts.append(f"AUTO ALERT ACTIVATED AT {current_time}")
            else:
                system_alerts.append("AUTO ALERT!")

        if system_alerts and system_alerts != ["No Auto-Alerts"]:
            alert = True
            if flash_thread is None or not flash_thread.is_alive():
                flash_thread = threading.Thread(target=led_flash)
                flash_thread.start()
        else:
            alert = False

        return {
            "Alert": system_alerts,
            "location": location,
            "timestamp": current_time,
            "data": filtered_response
        }
    return None


from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import json

# Initialize AWS IoT Client
def initialize_iot_client():
    iot_client = AWSIoTMQTTClient("YourID")  # Replace with your IoT client ID
    iot_client.configureEndpoint("YourEndpoint", 8883)  # Replace with your endpoint
    iot_client.configureCredentials("/your/path/root-CA.crt", "/your/path/thingName.private.key", "/your/path/thingName.cert.pem")  # Paths to your certificates
    return iot_client

# Function to publish data to an IoT Core topic
def upload_to_aws(entry):
    iot_client = initialize_iot_client()
    iot_client.connect()
    
    topic = "vehicle/data"  # MQTT topic to publish data to
    payload = json.dumps(entry)  # Convert entry to JSON string
    
    # Publish the payload to the specified topic
    iot_client.publish(topic, payload, 1)  # QoS level 1 for at least once delivery
    
    print("Data uploaded to AWS IoT Core.")
    iot_client.disconnect()

# Main Loop
while run:
    for event in sense.stick.get_events():
        if event.action == 'pressed':
            press_time = time.time()
    
        if event.action == 'released':
            release_time = time.time()
            duration = release_time - press_time
    
            if duration >= 2:
                print("Ending data collection (Joystick held).")
                run = False
                sys.exit()
            else:
                if not manual_alert:  # If manual alert not active, activate it
                    manual_alert = True
                    alert = True
                    initial_alert = True
                    flash = threading.Thread(target=led_flash)
                    flash.start()
                    print("Manual alert activated.")
                else:  # If manual alert is active, deactivate it
                    manual_alert = False
                    alert = False
                    print("Manual alert deactivated.")

    obd_data = run_obd.get_data()

    if isinstance(obd_data, str):
        print(obd_data)
        break

    # Get location
    location = run_gps.get_location()
    current_time = datetime.now().isoformat()

    # Filter important parameters
    filtered_obd_data = filter_important_parameters(obd_data)

    # Build new entry
    entry = get_entry(location, filtered_obd_data)

    if entry:
        alerts = entry['Alert']
        pretty_print_obd_data(location, current_time, filtered_obd_data, alerts)
        capture_data(entry)

    sleep(0.15)
