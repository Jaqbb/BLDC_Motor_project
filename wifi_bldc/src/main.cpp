#include <Arduino.h>
#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <AsyncTCP.h>
#include "password.h"

// Serwer WebSocket
AsyncWebServer server(80);
AsyncWebSocket ws("/ws"); 

// Przykładowe dane silnika
float current1, current2, current3;
float voltage1, voltage2, voltage3;
float temperature;

// Funkcja obsługi komunikacji WebSocket
void onWebSocketEvent(AsyncWebSocket *server, AsyncWebSocketClient *client, 
                      AwsEventType type, void *arg, uint8_t *data, size_t len) {
    if (type == WS_EVT_CONNECT) {
        Serial.printf("Nowe połączenie WebSocket: ID %u\n", client->id());
    } 
    else if (type == WS_EVT_DISCONNECT) {
        Serial.printf("Rozłączono klienta: ID %u\n", client->id());
    } 
    else if (type == WS_EVT_DATA) {
        String message = String((char*)data).substring(0, len);
        Serial.printf("Odebrano: %s\n", message.c_str());

        if (message.startsWith("SET_SPEED:")) {
            int speed = message.substring(10).toInt();
            Serial.printf("Ustawiono prędkość: %d\n", speed);
            // Tu kod do sterowania silnikiem
        }
    }
}

void sendData() {
     // Symulacja danych
    current1 = random(100, 500) / 10.0;
    current2 = random(100, 500) / 10.0;
    current3 = random(100, 500) / 10.0;
    voltage1 = random(200, 240) / 1.0;
    voltage2 = random(200, 240) / 1.0;
    voltage3 = random(200, 240) / 1.0;
    temperature = random(20, 60) / 1.0;

    // Bufor na 7 floatów (7x4 bajty = 28 bajtów)
    uint8_t buffer[28];
    memcpy(buffer, &current1, 4);
    memcpy(buffer + 4, &current2, 4);
    memcpy(buffer + 8, &current3, 4);
    memcpy(buffer + 12, &voltage1, 4);
    memcpy(buffer + 16, &voltage2, 4);
    memcpy(buffer + 20, &voltage3, 4);
    memcpy(buffer + 24, &temperature, 4);

    // Wysyłanie binarne do wszystkich klientów
    ws.binaryAll(buffer, sizeof(buffer)); 
}

void setup() {
    Serial.begin(115200);

    WiFi.mode(WIFI_STA);
    WiFi.disconnect();   // upewnij się, że ESP nie jest już „podłączone” do czegokolwiek
    delay(100);


    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(1000);
        Serial.print(".");
    }
    Serial.println("\nPołączono z WiFi");


    ws.onEvent(onWebSocketEvent);
    server.addHandler(&ws);
    server.begin();
    Serial.println("Serwer WebSocket uruchomiony!");

    Serial.print("Adres IP: ");
    Serial.println(WiFi.localIP());
}

void loop() {
    sendData();
    delay(300);
}