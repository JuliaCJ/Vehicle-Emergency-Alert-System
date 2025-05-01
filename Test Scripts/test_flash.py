import sys
import threading
from sense_hat import SenseHat
import time
from time import sleep

sense = SenseHat()
alert = False

red = (255, 0, 0)

sense.clear()

run = True

loop = 0

def led_flash():
	while alert:
		print("ALERT ON")
		sense.clear(red)
		sleep(0.5)
		sense.clear()
		sleep(0.5)
		
while run:
	for event in sense.stick.get_events():
		if event.action == 'released' and not alert:
			alert = True
			flash = threading.Thread(target=led_flash)
			flash.start()
			break
			
		if event.action == 'released' and alert:
			alert = False
			print("ALERT OFF")
			
		if event.action == 'held':
			alert = False
			run = False
			print("ENDING SCRIPT")
			sys.exit()
	
	loop += 1
	print(f"loop {loop}")
		
		
