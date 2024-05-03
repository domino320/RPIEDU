#!/usr/bin/env python3

import RPi.GPIO as GPIO
import time
import LCD1602
import pygame
import threading

dhtPin = 19
touchPin = 26
ledPin = 20
pirPin = 13

GPIO.setmode(GPIO.BCM)

MAX_UNCHANGE_COUNT = 100

STATE_INIT_PULL_DOWN = 1
STATE_INIT_PULL_UP = 2
STATE_DATA_FIRST_PULL_DOWN = 3
STATE_DATA_PULL_UP = 4
STATE_DATA_PULL_DOWN = 5

last_activity_time = 0

def readDht11():
    GPIO.setup(dhtPin, GPIO.OUT)
    GPIO.output(dhtPin, GPIO.HIGH)
    time.sleep(0.05)
    GPIO.output(dhtPin, GPIO.LOW)
    time.sleep(0.02)
    GPIO.setup(dhtPin, GPIO.IN, GPIO.PUD_UP)

    unchanged_count = 0
    last = -1
    data = []
    while True:
        current = GPIO.input(dhtPin)
        data.append(current)
        if last != current:
            unchanged_count = 0
            last = current
        else:
            unchanged_count += 1
            if unchanged_count > MAX_UNCHANGE_COUNT:
                break

    state = STATE_INIT_PULL_DOWN

    lengths = []
    current_length = 0

    for current in data:
        current_length += 1

        if state == STATE_INIT_PULL_DOWN:
            if current == GPIO.LOW:
                state = STATE_INIT_PULL_UP
            else:
                continue
        if state == STATE_INIT_PULL_UP:
            if current == GPIO.HIGH:
                state = STATE_DATA_FIRST_PULL_DOWN
            else:
                continue
        if state == STATE_DATA_FIRST_PULL_DOWN:
            if current == GPIO.LOW:
                state = STATE_DATA_PULL_UP
            else:
                continue
        if state == STATE_DATA_PULL_UP:
            if current == GPIO.HIGH:
                current_length = 0
                state = STATE_DATA_PULL_DOWN
            else:
                continue
        if state == STATE_DATA_PULL_DOWN:
            if current == GPIO.LOW:
                lengths.append(current_length)
                state = STATE_DATA_PULL_UP
            else:
                continue
    if len(lengths) != 40:
        return False

    shortest_pull_up = min(lengths)
    longest_pull_up = max(lengths)
    halfway = (longest_pull_up + shortest_pull_up) / 2
    bits = []
    the_bytes = []
    byte = 0

    for length in lengths:
        bit = 0
        if length > halfway:
            bit = 1
        bits.append(bit)
    for i in range(0, len(bits)):
        byte = byte << 1
        if (bits[i]):
            byte = byte | 1
        else:
            byte = byte | 0
        if ((i + 1) % 8 == 0):
            the_bytes.append(byte)
            byte = 0

    checksum = (the_bytes[0] + the_bytes[1] + the_bytes[2] + the_bytes[3]) & 0xFF
    if the_bytes[4] != checksum:
        return False

    return the_bytes[2], the_bytes[0]  # Oprava v poradí

class Keypad():
    def __init__(self, rowsPins, colsPins, keys):
        self.rowsPins = rowsPins
        self.colsPins = colsPins
        self.keys = keys
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.rowsPins, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.colsPins, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    def read(self):
        pressed_keys = []
        for i, row in enumerate(self.rowsPins):
            GPIO.output(row, GPIO.HIGH)
            for j, col in enumerate(self.colsPins):
                index = i * len(self.colsPins) + j
                if GPIO.input(col) == 1:
                    pressed_keys.append(self.keys[index])
            GPIO.output(row, GPIO.LOW)
        return pressed_keys

def setup():
    global keypad
    # Initialize LCD1602
    LCD1602.init()
    # Initialize Keypad
    rowsPins = [18, 23, 24, 25]
    colsPins = [10, 22, 27, 17]
    keys = ["1", "2", "3", "A",
            "4", "5", "6", "B",
            "7", "8", "9", "C",
            "*", "0", "#", "D"]
    keypad = Keypad(rowsPins, colsPins, keys)
    GPIO.setup(ledPin, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(touchPin, GPIO.IN)  # Inicializácia pinu touchPin
    GPIO.setup(pirPin, GPIO.IN)

def play_mp3(file_name):
    pygame.mixer.init()
    pygame.mixer.music.load(file_name)
    pygame.mixer.music.play()

def stop_mp3():
    pygame.mixer.music.stop()

def display_message(message, duration):
    LCD1602.write(0, 0, message)
    time.sleep(duration)
    LCD1602.clear()

def motion_detection():
    global last_activity_time
    while True:
        pir_state = GPIO.input(pirPin)
        if pir_state == GPIO.HIGH:
            last_activity_time = time.time()  # Aktualizujeme čas poslednej aktivity
            display_message("      AHOJ      ", 2)
            LCD1602.write(0, 0, "   EDUANATEMS")  # Zobrazení domovské obrazovky
            last_activity_time = time.time()  # Resetujeme čas poslednej aktivity
            time.sleep(300)  # Počkáme 5 minút
            LCD1602.clear()
           

def main():
    global last_activity_time
    setup()  # Pridáme volanie setup() na začiatok funkcie
    # Zobrazenie domovskej obrazovky "EDUANATEMS"
    LCD1602.clear()
    LCD1602.write(0, 0, "   EDUANATEMS")
    time.sleep(2)  # Zobrazenie na 2 sekundy
    # Spustíme vlákno pre monitorovanie PIR senzora
    pir_thread = threading.Thread(target=motion_detection)
    pir_thread.daemon = True  # Nastavíme demonické vlákno
    pir_thread.start()  # Spustíme vlákno
    last_touch_time = 0
    while True:
        if GPIO.input(touchPin) == GPIO.HIGH:
            current_time = time.time()
            if current_time - last_touch_time > 3:
                result = readDht11()
                if result:
                    temperature, humidity = result
                    # Zobraziť teplotu a vlhkosť
                    LCD1602.clear()
                    if temperature is not False:
                        LCD1602.write(0, 0, ' Teplota: %.1fC' % temperature)
                    if humidity is not False:
                        LCD1602.write(1, 1, 'Vlhkost: %.1f%%' % humidity)
                    last_touch_time = current_time
                    time.sleep(5)  # Počkáme 5 sekúnd
                    LCD1602.clear()  # Vymažeme displej
                    LCD1602.write(0, 0, "   EDUANATEMS")  # Zobrazení domovské obrazovky po 5 sekundách
                GPIO.output(ledPin, GPIO.LOW)
                time.sleep(0.1)  # Počkáme, kým sa tlačidlo uvoľní
                GPIO.output(ledPin, GPIO.HIGH)
        # Kontrola nečinnosti
        if time.time() - last_activity_time > 600:  # 600 sekúnd = 10 minút
            LCD1602.clear()
            LCD1602.write(0, 0, "   EDUANATEMS")
            time.sleep(2)
            last_activity_time = time.time()
        pressed_keys = keypad.read()
        if '1' in pressed_keys:
            play_mp3("skuska.mp3")
            LCD1602.clear()
            LCD1602.write(0, 0, "Prehrava sa 1")
            time.sleep(2)  # Počkáme 2 sekundy na dokončenie prehrávania
        elif '2' in pressed_keys:
            play_mp3("reklama.mp3")
            LCD1602.clear()
            LCD1602.write(0, 0, "Prehrava sa 2")
            time.sleep(2)  # Počkáme 2 sekundy na dokončenie prehrávania
        elif '3' in pressed_keys:
            play_mp3("reklama.mp3")
            LCD1602.clear()
            LCD1602.write(0, 0, "Prehrava sa 3")
            time.sleep(2)  # Počkáme 2 sekundy na dokončenie prehrávania
        elif '4' in pressed_keys:
            play_mp3("reklama.mp3")
            LCD1602.clear()
            LCD1602.write(0, 0, "Prehrava sa 4")
            time.sleep(2)  # Počkáme 2 sekundy na dokončenie prehrávania
        elif '5' in pressed_keys:
            play_mp3("reklama.mp3")
            LCD1602.clear()
            LCD1602.write(0, 0, "Prehrava sa 5")
            time.sleep(2)  # Počkáme 2 sekundy na dokončenie prehrávania
        elif '6' in pressed_keys:
            play_mp3("reklama.mp3")
            LCD1602.clear()
            LCD1602.write(0, 0, "Prehrava sa 6")
            time.sleep(2)  # Počkáme 2 sekundy na dokončenie prehrávania
        elif '7' in pressed_keys:
            play_mp3("reklama.mp3")
            LCD1602.clear()
            LCD1602.write(0, 0, "Prehrava sa 7")
            time.sleep(2)  # Počkáme 2 sekundy na dokončenie prehrávania
        elif '8' in pressed_keys:
            play_mp3("reklama.mp3")
            LCD1602.clear()
            LCD1602.write(0, 0, "Prehrava sa 8")
            time.sleep(2)  # Počkáme 2 sekundy na dokončenie prehrávania
        elif '9' in pressed_keys:
            play_mp3("reklama.mp3")
            LCD1602.clear()
            LCD1602.write(0, 0, "Prehrava sa 9")
            time.sleep(2)  # Počkáme 2 sekundy na dokončenie prehrávania
        elif '0' in pressed_keys:
            play_mp3("reklama.mp3")
            LCD1602.clear()
            LCD1602.write(0, 0, "Prehrava sa 0")
            time.sleep(2)  # Počkáme 2 sekundy na dokončenie prehrávania
        elif 'A' in pressed_keys:
            play_mp3("reklama.mp3")
            LCD1602.clear()
            LCD1602.write(0, 0, "Prehrava sa A")
            time.sleep(2)  # Počkáme 2 sekundy na dokončenie prehrávania
        elif 'B' in pressed_keys:
            play_mp3("reklama.mp3")
            LCD1602.clear()
            LCD1602.write(0, 0, "Prehrava sa B")
            time.sleep(2)  # Počkáme 2 sekundy na dokončenie prehrávania
        elif 'C' in pressed_keys:
            play_mp3("reklama.mp3")
            LCD1602.clear()
            LCD1602.write(0, 0, "Prehrava sa C")
            time.sleep(2)  # Počkáme 2 sekundy na dokončenie prehrávania
        elif 'D' in pressed_keys:
            play_mp3("reklama.mp3")
            LCD1602.clear()
            LCD1602.write(0, 0, "Prehrava sa D")
            time.sleep(2)  # Počkáme 2 sekundy na dokončenie prehrávania
        elif '*' in pressed_keys:
            stop_mp3()
            LCD1602.clear()
            LCD1602.write(0, 0, "   Prehravanie")
            LCD1602.write(1, 1, "   Zastavene")
        time.sleep(0.1)

def destroy():
    GPIO.cleanup()
    LCD1602.clear()

if __name__ == '__main__':
    setup()
    try:
        main()
    except KeyboardInterrupt:
        destroy()
