import gps

# Connect to the GPS daemon
session = gps.gps(mode=gps.WATCH_ENABLE)

def get_location():
    location_parts = []

    try:
        report = session.next()

        if report['class'] == 'TPV':
            if hasattr(report, 'lat') and hasattr(report, 'lon'):
                location_parts.append(f"Lat: {report.lat}")
                location_parts.append(f"Long: {report.lon}")
            if hasattr(report, 'alt'):
                location_parts.append(f"Alt: {report.alt}m")

    except KeyError:
        pass
    except StopIteration:
        print("GPSD has terminated")
    except Exception as e:
        print(f"GPS error: {e}")

    return ", ".join(location_parts) if location_parts else "Location unavailable"

