// ===================================================================
// FIRMWARE DO ESP32 DOS LEDS — controla o semáforo E sincroniza
// o horário com o servidor (notebook) periodicamente
// ===================================================================

#include <WiFi.h>            // Para conectar na rede Wi-Fi
#include <WebServer.h>       // Para este ESP32 também "escutar" mensagens (recebe os tempos)
#include <HTTPClient.h>      // Para este ESP32 "perguntar" coisas para o servidor (buscar o horário)
#include <ArduinoJson.h>     // Para entender o formato JSON

WebServer server(80);   // Mini servidor deste ESP32, na porta 80

// ---------- CONFIGURAÇÕES QUE VOCÊ PRECISA AJUSTAR ----------
const char* ssid = "SEU_WIFI";
const char* password = "SUA_SENHA";
const char* horarioUrl = "http://192.168.0.47:5000/horario"; // IP do seu notebook/servidor
// ---------------------------------------------------------------

// ---------- PINOS DOS LEDS — ajuste conforme sua montagem física ----------
const int ledVerdeVia1    = 25;
const int ledAmareloVia1  = 26;
const int ledVermelhoVia1 = 27;

const int ledVerdeVia2    = 32;
const int ledAmareloVia2  = 33;
const int ledVermelhoVia2 = 14;
// ---------------------------------------------------------------------------

// Tempos de verde de cada via (começam em 15s, o servidor atualiza depois)
int tempoVia1 = 15;
int tempoVia2 = 15;

// Variáveis que guardam o horário sincronizado com o servidor
int horaAtual = 0;
int minutoAtual = 0;
int segundoAtual = 0;

// Controla de quanto em quanto tempo o ESP32 vai buscar o horário de novo
unsigned long ultimaSincronizacao = 0;
const unsigned long INTERVALO_SINCRONIZACAO = 60000; // 60000 ms = 1 minuto

// ===================================================================
// FUNÇÃO: recebe os novos tempos calculados pelo servidor Python
// ===================================================================
void handleTempos() {
  StaticJsonDocument<200> doc;
  DeserializationError erro = deserializeJson(doc, server.arg("plain"));

  if (!erro) {
    tempoVia1 = doc["via1"];
    tempoVia2 = doc["via2"];
    Serial.printf("Novos tempos recebidos -> Via1: %ds | Via2: %ds\n", tempoVia1, tempoVia2);
    server.send(200, "text/plain", "Tempos atualizados com sucesso");
  } else {
    Serial.println("Erro ao interpretar os dados recebidos");
    server.send(400, "text/plain", "Erro nos dados enviados");
  }
}

// ===================================================================
// FUNÇÃO: pergunta ao servidor (notebook) que horas são agora
// ===================================================================
void sincronizarHorario() {
  HTTPClient http;
  http.begin(horarioUrl);

  int httpCode = http.GET();  // Pede a informação (GET = "me dá o horário")

  if (httpCode == 200) {
    String resposta = http.getString();

    StaticJsonDocument<200> doc;
    DeserializationError erro = deserializeJson(doc, resposta);

    if (!erro) {
      String horaTexto = doc["hora"];  // ex: "14:35:22"

      horaAtual = horaTexto.substring(0, 2).toInt();
      minutoAtual = horaTexto.substring(3, 5).toInt();
      segundoAtual = horaTexto.substring(6, 8).toInt();

      Serial.printf("Horario sincronizado: %02d:%02d:%02d\n", horaAtual, minutoAtual, segundoAtual);
    } else {
      Serial.println("Erro ao interpretar o horario recebido");
    }
  } else {
    Serial.printf("Erro ao buscar horario (codigo %d) — servidor pode estar fora do ar\n", httpCode);
  }

  http.end();
}

// ===================================================================
// FUNÇÃO: executa um ciclo completo do semáforo
// ===================================================================
void cicloSemaforo() {
  // ---------- ETAPA 1: Via 1 verde, Via 2 vermelha ----------
  digitalWrite(ledVerdeVia1, HIGH);
  digitalWrite(ledVermelhoVia2, HIGH);
  delay(tempoVia1 * 1000);

  digitalWrite(ledVerdeVia1, LOW);
  digitalWrite(ledAmareloVia1, HIGH);
  delay(3000);
  digitalWrite(ledAmareloVia1, LOW);

  digitalWrite(ledVermelhoVia1, HIGH);
  digitalWrite(ledVermelhoVia2, LOW);

  // ---------- ETAPA 2: Via 2 verde, Via 1 vermelha ----------
  digitalWrite(ledVerdeVia2, HIGH);
  delay(tempoVia2 * 1000);

  digitalWrite(ledVerdeVia2, LOW);
  digitalWrite(ledAmareloVia2, HIGH);
  delay(3000);
  digitalWrite(ledAmareloVia2, LOW);

  digitalWrite(ledVermelhoVia2, HIGH);
  digitalWrite(ledVermelhoVia1, LOW);
}

// ===================================================================
// SETUP — roda uma única vez, quando o ESP32 liga
// ===================================================================
void setup() {
  Serial.begin(115200);

  pinMode(ledVerdeVia1, OUTPUT);
  pinMode(ledAmareloVia1, OUTPUT);
  pinMode(ledVermelhoVia1, OUTPUT);
  pinMode(ledVerdeVia2, OUTPUT);
  pinMode(ledAmareloVia2, OUTPUT);
  pinMode(ledVermelhoVia2, OUTPUT);

  WiFi.begin(ssid, password);
  Serial.print("Conectando ao Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Conectado! IP deste ESP32 (dos LEDs): ");
  Serial.println(WiFi.localIP());

  sincronizarHorario();
  ultimaSincronizacao = millis();

  server.on("/tempos", HTTP_POST, handleTempos);
  server.begin();
}

// ===================================================================
// LOOP — roda repetidamente, para sempre, enquanto o ESP32 estiver ligado
// ===================================================================
void loop() {
  server.handleClient();

  if (millis() - ultimaSincronizacao >= INTERVALO_SINCRONIZACAO) {
    sincronizarHorario();
    ultimaSincronizacao = millis();
  }

  cicloSemaforo();
}
