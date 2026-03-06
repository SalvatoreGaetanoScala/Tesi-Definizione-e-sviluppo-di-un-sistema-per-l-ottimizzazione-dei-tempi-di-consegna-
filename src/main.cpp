#include "funzioni_esp.h"

Esp e;

void setup() {
  Serial.begin(115200);
  e.avvioDisplay();
  
  e.connettiWiFi();
  
  e.avvioPulsante();
  e.avvioPotenziometro();
  e.avvioMemoria(); 
}

void loop() {
  // 1. Invio Velocità
  int val = analogRead(POT_PIN);
  velocitaSimulata = (float)val * 100.0 / 4095.0; 
  if (millis() - lastSpeedSend > 150) {
    Serial.print("SPEED:"); Serial.println(velocitaSimulata);
    lastSpeedSend = millis();
  }

  // 2. Lettura Comandi Python
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    if (cmd.startsWith("DATI:")) {
      int separatorIndex = cmd.indexOf('|');
      if (separatorIndex > 0) {
        String v = cmd.substring(5, separatorIndex);
        String c = cmd.substring(separatorIndex + 1);
        e.setDatiConsegna(v, c);
      }
    }
    else if (statoAttuale != CONSEGNA_IN_CORSO) {
        if (cmd == "CMD_MOVE") statoAttuale = IN_VIAGGIO;
        else if (cmd == "CMD_PAUSE") statoAttuale = IN_PAUSA;
        else if (cmd == "CMD_ARRIVATO") statoAttuale = PRONTO_CONSEGNA;
    }
  }

  // 3. Pulsante
  bool btn = false;
  if (digitalRead(BUTTON_PIN) == LOW) {
    if ((millis() - lastDebounceTime) > debounceDelay) {
      btn = true;
      lastDebounceTime = millis();
    }
  }

  // 4. Stati
  switch (statoAttuale) {
    case IN_VIAGGIO: e.inViaggio(); break;
    case IN_PAUSA: e.inPausa(); break;
    case PRONTO_CONSEGNA: e.prontoConsegna(btn); break;
    case CONSEGNA_IN_CORSO: e.consegnaInCorso(btn); break;
  }
}