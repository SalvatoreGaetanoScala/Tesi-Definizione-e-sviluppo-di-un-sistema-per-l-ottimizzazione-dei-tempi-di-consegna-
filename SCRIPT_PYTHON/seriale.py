import threading
import serial
import time
import re
import json

# --- CONFIGURAZIONE ---
URL_WOKWI = "socket://localhost:4000"

# --- THREAD SERIALE ---
class SerialManager(threading.Thread):
    def __init__(self, map_app):
        super().__init__()
        self.map_app = map_app
        self.ser = None
        self.running = True
        self.connected = False
        self.daemon = True 

    def run(self):
        print(f"Tentativo connessione a Wokwi su {URL_WOKWI}...")
        while self.running:
            if not self.connected:
                try:
                    self.ser = serial.serial_for_url(URL_WOKWI, baudrate=115200, timeout=1)
                    self.connected = True
                    print("\n[PYTHON] Connesso a ESP32 (Wokwi)!")
                except Exception:
                    time.sleep(2)
                    continue
            
            try:
                if self.ser.in_waiting:
                    riga_bytes = self.ser.readline()
                    riga = riga_bytes.decode('utf-8', errors='replace').strip()
                    if riga: self.processa_messaggio_esp(riga)
                time.sleep(0.01)
            except Exception as e:
                print(f"Errore Seriale: {e}")
                self.connected = False
                if self.ser: self.ser.close()

    def processa_messaggio_esp(self, riga):
        # 1. VELOCITÀ
        if riga.startswith("SPEED:"):
            try:
                self.map_app.set_speed_from_potentiometer(float(riga.split(":")[1]))
            except: pass
            return 

        # 2. CONSEGNA COMPLETATA (JSON)
        match = re.search(r'(\{.*\})', riga)
        if match:
            try:
                dati = json.loads(match.group(1))
                if "id" in dati and "tempo_sec" in dati:
                    print(f"[SERIAL] Consegna Fatta: {dati}")
                    # NOTA: Il salvataggio locale e l'invio online ora sono gestiti 
                    # direttamente da MappaApp.notify_delivery_completed
                    # usando i dati arricchiti (ts1, ts2, micro, ecc.)
                    self.map_app.notify_delivery_completed(dati)
            except: pass

    def invia_comando(self, comando):
        if self.connected and self.ser:
            try: self.ser.write(f"{comando}\n".encode('utf-8'))
            except: pass