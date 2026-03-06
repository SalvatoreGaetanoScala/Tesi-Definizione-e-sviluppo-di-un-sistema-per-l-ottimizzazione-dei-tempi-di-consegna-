#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Preferences.h>
#include <WiFi.h>
//#include <HTTPClient.h>  //Non serve più senza invio diretto
#include "time.h"

// PIN
#define BUTTON_PIN 4
#define POT_PIN 34 

// --- CONFIGURAZIONE WIFI E SERVER ---
const char* ssid = "Wokwi-GUEST"; 
const char* password = "";

// URL Server (Nota: L'invio effettivo ora è gestito da Python per avere i dati completi)
// --- PARTE COMMENTATA PERCHE' RIDONDANTE (L'invio lo fa Python) ---
/*
const char* serverUrl = "https://webhook.site/e01ed0f8-9be4-41df-b0e5-ad2f334c6adb"; 
*/
// ------------------------------------------------------------------

// --- CONFIGURAZIONE ORARIO (NTP) ---
const char* ntpServer = "pool.ntp.org";
const long  gmtOffset_sec = 3600;      // GMT+1
const int   daylightOffset_sec = 3600; // Ora legale

LiquidCrystal_I2C lcd(0x27, 16, 2); 
Preferences preferences;

// STATI DEL SISTEMA
enum StatoCorriere { 
  IN_VIAGGIO,       
  IN_PAUSA,         
  PRONTO_CONSEGNA,  
  CONSEGNA_IN_CORSO 
};

StatoCorriere statoAttuale = IN_PAUSA;

// VARIABILI GLOBALI
unsigned long inizioConsegna = 0;
unsigned long durataConsegna = 0;
int numeroConsegne = 0;
float velocitaSimulata = 0.0; 
unsigned long lastSpeedSend = 0;

// Debounce Button
unsigned long lastDebounceTime = 0;
unsigned long debounceDelay = 200;

// Variabili per i dati da Python
String currentVia = "Sconosciuta";
String currentCoord = "(?,?)";

class Esp {
public:
  void avvioDisplay() {
    lcd.init(); lcd.backlight();
    lcd.setCursor(0, 0); lcd.print("Digital Twin v3");
    delay(1000); lcd.clear();
  }

  void avvioPulsante() { pinMode(BUTTON_PIN, INPUT_PULLUP); }
  void avvioPotenziometro() { pinMode(POT_PIN, INPUT); }

  void avvioMemoria() {
    preferences.begin("tesi", false);
    numeroConsegne = preferences.getInt("counter", 0);
  }

  void connettiWiFi() {
    lcd.setCursor(0, 0); lcd.print("WiFi Start...");
    WiFi.begin(ssid, password);
    
    int tentativi = 0;
    while (WiFi.status() != WL_CONNECTED && tentativi < 20) {
      delay(500); lcd.print(".");
      tentativi++;
    }

    lcd.clear();
    if (WiFi.status() == WL_CONNECTED) {
      lcd.print("WiFi OK!");
      configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
    } else {
      lcd.print("WiFi Error!");
    }
    delay(1000); lcd.clear();
  }

  String getOrario() {
    struct tm timeinfo;
    if(!getLocalTime(&timeinfo)){
      return "00:00:00";
    }
    char timeStringBuff[10];
    strftime(timeStringBuff, sizeof(timeStringBuff), "%H:%M:%S", &timeinfo);
    return String(timeStringBuff);
  }

  void setDatiConsegna(String via, String coord) {
    currentVia = via;
    currentCoord = coord;
    currentVia.trim();
    currentCoord.trim();
  }

  // Funzione mantenuta per compatibilità, ma non chiamata automaticamente per evitare doppio invio
  // --- FUNZIONE COMMENTATA PERCHE' INUTILIZZATA ---
  /*
  void inviaDatiOnline(String jsonPayload) {
    if (WiFi.status() == WL_CONNECTED) {
      WiFiClient client;
      HTTPClient http;
      
      // Nota: serverUrl è commentato sopra, quindi questa funzione darebbe errore se decommentata
      // senza decommentare anche la variabile.
      if (http.begin(client, serverUrl)) {
        http.addHeader("Content-Type", "application/json");
        int responseCode = http.POST(jsonPayload);
        http.end();
      }
    }
  }
  */
  // ------------------------------------------------

  void salvaDatiReali(unsigned long durata) {
    numeroConsegne++;
    String timestamp = getOrario();

    // Costruzione JSON per Python
    String jsonCompleto = "{";
    jsonCompleto += "\"id\": " + String(numeroConsegne) + ", ";
    jsonCompleto += "\"tempo_sec\": " + String(durata) + ", ";
    jsonCompleto += "\"via\": \"" + currentVia + "\", ";
    jsonCompleto += "\"coord\": \"" + currentCoord + "\", ";
    jsonCompleto += "\"ts\": \"" + timestamp + "\"";
    jsonCompleto += "}";

    // 1. Salvataggio Locale (Memoria ESP32)
    preferences.putInt("counter", numeroConsegne);
    String key = "log_" + String(numeroConsegne);
    preferences.putString(key.c_str(), jsonCompleto);
    
    // 2. Invio a Seriale (Così Python riceve, arricchisce i dati e invia online)
    Serial.println(jsonCompleto);
    
    // 3. FEEDBACK VISIVO
    lcd.clear(); lcd.print("SALVATAGGIO PC..");
    
    // NOTA: Abbiamo disabilitato l'invio diretto da ESP32 qui sotto
    // perché l'ESP non possiede i dati completi (es. ts1, ts_netto).
    // Ci pensa Python a inviare tutto al Webhook nel formato corretto.
    // inviaDatiOnline(jsonCompleto); <--- GIA' RIMOSSO/COMMENTATO NELLA LOGICA ORIGINALE
    
    delay(1500); lcd.clear();
  }

  // GESTIONE STATI
  void inViaggio() {
    lcd.setCursor(0, 0); lcd.print(">> IN VIAGGIO >>");
    lcd.setCursor(0, 1); lcd.print("Vel: "); lcd.print((int)velocitaSimulata); lcd.print(" km/h   ");
  }

  void inPausa() {
    lcd.setCursor(0, 0); lcd.print("!! STOP AUTO !! ");
    lcd.setCursor(0, 1); lcd.print("In attesa...    ");
  }

  void prontoConsegna(bool buttonPressed) {
    lcd.setCursor(0, 0); lcd.print("ARRIVATO: ");
    lcd.print(currentVia.substring(0, 6)); 
    lcd.setCursor(0, 1); lcd.print("Premi x Start   ");
    
    if (buttonPressed) {
      inizioConsegna = millis();
      statoAttuale = CONSEGNA_IN_CORSO;
      lcd.clear();
    }
  }

  void consegnaInCorso(bool buttonPressed) {
    unsigned long sec = (millis() - inizioConsegna) / 1000;
    lcd.setCursor(0, 0); lcd.print("SCARICO MERCE...");
    lcd.setCursor(0, 1); lcd.print("Tempo: "); lcd.print(sec); lcd.print("s       ");

    if (buttonPressed) {
      durataConsegna = sec;
      salvaDatiReali(durataConsegna);
      
      statoAttuale = IN_PAUSA; 
      currentVia = "Sconosciuta";
      currentCoord = "(?,?)";
      lcd.clear();
    }
  }
};