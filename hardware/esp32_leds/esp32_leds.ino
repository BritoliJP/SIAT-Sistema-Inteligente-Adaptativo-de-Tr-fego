// ===================================================================
// FIRMWARE DO ESP32 DOS LEDS
//  - recebe do servidor a RAZÃO de carros de cada via (via1/total e via2/total)
//  - CALCULA aqui o tempo de verde de cada via
//  - controla os LEDs do semáforo (quando cada via abre e fecha)
//  - a cada ciclo, ENVIA ao servidor os tempos de verde que está aplicando
//  - a cada 10 s, AVISA o servidor que está conectado (o dashboard mostra esse status)
// O servidor não manda horário nem tempo: toda a decisão do semáforo é feita neste ESP32.
// ===================================================================

#include <WiFi.h>            // Para conectar na rede Wi-Fi
#include <WebServer.h>       // Para este ESP32 "escutar" mensagens (recebe a razão)
#include <HTTPClient.h>      // Para este ESP32 "falar" com o servidor (tempos e status)
#include <ArduinoJson.h>     // Para entender/montar o formato JSON

WebServer server(80);   // Mini servidor deste ESP32, na porta 80

// ---------- CONFIGURAÇÕES QUE VOCÊ PRECISA AJUSTAR ----------
const char* ssid = "SEU_WIFI";
const char* password = "SUA_SENHA";
const char* servidorUrl = "http://192.168.0.47:5000"; // IP do computador onde roda o server.py
// ---------------------------------------------------------------

// ---------- PINOS DOS LEDS — ajuste conforme sua montagem física ----------
const int ledVerdeVia1    = 25;
const int ledAmareloVia1  = 26;
const int ledVermelhoVia1 = 27;

const int ledVerdeVia2    = 32;
const int ledAmareloVia2  = 33;
const int ledVermelhoVia2 = 14;
// ---------------------------------------------------------------------------

// ---------- REGRAS DO CÁLCULO DE TEMPO ----------
const int TEMPO_MINIMO = 10;   // segundos de verde mínimo para qualquer via
const int TEMPO_MAXIMO = 40;   // segundos de verde máximo para qualquer via
const int TEMPO_PADRAO = 15;   // usado antes da 1ª razão chegar e quando não há carros
const unsigned long TEMPO_AMARELO = 3000;  // 3 s de amarelo (em milissegundos)
// ------------------------------------------------

// Tempos de verde CALCULADOS a partir da última razão recebida (em segundos)
int tempoVia1 = TEMPO_PADRAO;
int tempoVia2 = TEMPO_PADRAO;

// Tempos de verde do ciclo em andamento: são copiados dos de cima no início de cada ciclo
// e valem até o ciclo acabar. São esses que o servidor recebe, pois são os realmente aplicados.
int tempoCicloVia1 = TEMPO_PADRAO;
int tempoCicloVia2 = TEMPO_PADRAO;

// Quando fica true, o loop() envia os tempos do ciclo para o servidor
bool precisaEnviarTempos = false;

// Aviso periódico ao servidor ("estou conectado")
const unsigned long INTERVALO_STATUS = 10000;  // 10 s
unsigned long ultimoStatus = 0;

// ---------- ESTADOS DO SEMÁFORO (sem delay(), controlado pelo millis()) ----------
const int VERDE_VIA1   = 0;   // via 1 verde,    via 2 vermelha
const int AMARELO_VIA1 = 1;   // via 1 amarela,  via 2 vermelha
const int VERDE_VIA2   = 2;   // via 1 vermelha, via 2 verde
const int AMARELO_VIA2 = 3;   // via 1 vermelha, via 2 amarela

int estadoAtual = VERDE_VIA1;
unsigned long inicioEstado = 0;    // quando o estado atual começou
unsigned long duracaoEstado = 0;   // quanto tempo o estado atual deve durar (ms)

// ===================================================================
// FUNÇÃO: calcula o tempo de verde de cada via a partir da razão
// razao = carros da via / total de carros (um número de 0 a 1)
// ===================================================================
void calcularTempos(double razao1, double razao2) {
  // O servidor manda 0 e 0 quando não há nenhum carro nas duas vias
  if (razao1 + razao2 <= 0) {
    tempoVia1 = TEMPO_PADRAO;
    tempoVia2 = TEMPO_PADRAO;
    return;
  }

  // Tempo mínimo + uma parte proporcional à razão de cada via
  double faixa = TEMPO_MAXIMO - TEMPO_MINIMO;
  tempoVia1 = constrain((int)(TEMPO_MINIMO + razao1 * faixa), TEMPO_MINIMO, TEMPO_MAXIMO);
  tempoVia2 = constrain((int)(TEMPO_MINIMO + razao2 * faixa), TEMPO_MINIMO, TEMPO_MAXIMO);
}

// ===================================================================
// FUNÇÃO: recebe a razão de carros enviada pelo servidor Python
// Os tempos calculados passam a valer no início do PRÓXIMO ciclo do semáforo
// ===================================================================
void handleRazao() {
  StaticJsonDocument<200> doc;
  DeserializationError erro = deserializeJson(doc, server.arg("plain"));

  if (erro || doc["razao_via1"].isNull() || doc["razao_via2"].isNull()) {
    Serial.println("Erro ao interpretar a razao recebida");
    server.send(400, "text/plain", "Erro nos dados enviados");
    return;
  }

  double razao1 = doc["razao_via1"];
  double razao2 = doc["razao_via2"];

  if (razao1 < 0 || razao1 > 1 || razao2 < 0 || razao2 > 1) {
    Serial.println("Razao fora do intervalo de 0 a 1");
    server.send(400, "text/plain", "Razao fora do intervalo");
    return;
  }

  calcularTempos(razao1, razao2);

  Serial.printf("Razao recebida -> via1: %.2f | via2: %.2f\n", razao1, razao2);
  Serial.printf("Tempos calculados (valem no proximo ciclo) -> Via1: %ds | Via2: %ds\n", tempoVia1, tempoVia2);

  server.send(200, "text/plain", "Razao recebida");
}

// ===================================================================
// FUNÇÃO: faz um POST em JSON para o servidor e devolve o código HTTP
// Os dois tempos limite evitam que o semáforo fique parado por muito tempo
// caso o servidor esteja desligado
// ===================================================================
int postarJson(const char* rota, const String& corpo) {
  HTTPClient http;
  http.begin(String(servidorUrl) + rota);
  http.setConnectTimeout(2000);
  http.setTimeout(2000);
  http.addHeader("Content-Type", "application/json");

  int codigo = http.POST(corpo);

  http.end();
  return codigo;
}

// ===================================================================
// FUNÇÃO: envia ao servidor os tempos de verde do ciclo que acabou de começar
// ===================================================================
void enviarTemposAoServidor() {
  StaticJsonDocument<200> doc;
  doc["tempo_via1"] = tempoCicloVia1;
  doc["tempo_via2"] = tempoCicloVia2;

  String corpo;
  serializeJson(doc, corpo);

  int codigo = postarJson("/tempos", corpo);

  if (codigo == 200) {
    Serial.printf("Ciclo enviado ao servidor -> Via1: %ds | Via2: %ds\n", tempoCicloVia1, tempoCicloVia2);
  } else {
    Serial.printf("Erro ao enviar tempos ao servidor (codigo %d) — servidor pode estar fora do ar\n", codigo);
  }
}

// ===================================================================
// FUNÇÃO: avisa o servidor que este ESP32 está conectado
// ===================================================================
void enviarStatus() {
  int codigo = postarJson("/status", "{}");

  if (codigo != 200) {
    Serial.printf("Sem contato com o servidor (codigo %d)\n", codigo);
  }
}

// ===================================================================
// FUNÇÃO: entra em um estado do semáforo (acende os LEDs certos)
// ===================================================================
void aplicarEstado(int estado) {
  // Apaga tudo e depois acende só o que o estado pede
  digitalWrite(ledVerdeVia1, LOW);
  digitalWrite(ledAmareloVia1, LOW);
  digitalWrite(ledVermelhoVia1, LOW);
  digitalWrite(ledVerdeVia2, LOW);
  digitalWrite(ledAmareloVia2, LOW);
  digitalWrite(ledVermelhoVia2, LOW);

  switch (estado) {
    case VERDE_VIA1:
      // Início de um novo ciclo: trava os tempos das duas vias até o ciclo acabar
      // e pede o envio deles ao servidor
      tempoCicloVia1 = tempoVia1;
      tempoCicloVia2 = tempoVia2;
      precisaEnviarTempos = true;

      digitalWrite(ledVerdeVia1, HIGH);
      digitalWrite(ledVermelhoVia2, HIGH);
      duracaoEstado = (unsigned long)tempoCicloVia1 * 1000UL;
      break;

    case AMARELO_VIA1:
      digitalWrite(ledAmareloVia1, HIGH);
      digitalWrite(ledVermelhoVia2, HIGH);
      duracaoEstado = TEMPO_AMARELO;
      break;

    case VERDE_VIA2:
      digitalWrite(ledVermelhoVia1, HIGH);
      digitalWrite(ledVerdeVia2, HIGH);
      duracaoEstado = (unsigned long)tempoCicloVia2 * 1000UL;
      break;

    case AMARELO_VIA2:
      digitalWrite(ledVermelhoVia1, HIGH);
      digitalWrite(ledAmareloVia2, HIGH);
      duracaoEstado = TEMPO_AMARELO;
      break;
  }

  estadoAtual = estado;
  inicioEstado = millis();
}

// ===================================================================
// FUNÇÃO: avança o semáforo quando o tempo do estado atual acabou
// Não bloqueia: se ainda não deu o tempo, sai na hora e o loop() continua
// ===================================================================
void atualizarSemaforo() {
  if (millis() - inicioEstado < duracaoEstado) {
    return;  // ainda no mesmo estado
  }

  switch (estadoAtual) {
    case VERDE_VIA1:   aplicarEstado(AMARELO_VIA1); break;
    case AMARELO_VIA1: aplicarEstado(VERDE_VIA2);   break;
    case VERDE_VIA2:   aplicarEstado(AMARELO_VIA2); break;
    case AMARELO_VIA2: aplicarEstado(VERDE_VIA1);   break;
  }
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

  // Registra a rota que recebe a razão de carros do servidor
  server.on("/razao", HTTP_POST, handleRazao);
  server.begin();

  // Primeiro aviso ao servidor, antes de começar o ciclo
  enviarStatus();
  ultimoStatus = millis();

  // Começa o ciclo do semáforo
  aplicarEstado(VERDE_VIA1);
}

// ===================================================================
// LOOP — roda repetidamente, para sempre, enquanto o ESP32 estiver ligado
// Cada passada é rápida, então o ESP32 sempre consegue atender o servidor
// enquanto o semáforo segue funcionando
// ===================================================================
void loop() {
  server.handleClient();   // Fica de olho se chegou uma nova razão do servidor
  atualizarSemaforo();     // Avança verde/amarelo/vermelho quando o tempo acaba

  // Início de ciclo: informa ao servidor os tempos de verde que estão valendo
  if (precisaEnviarTempos) {
    precisaEnviarTempos = false;
    enviarTemposAoServidor();
  }

  // Aviso periódico: "estou conectado"
  if (millis() - ultimoStatus >= INTERVALO_STATUS) {
    ultimoStatus = millis();
    enviarStatus();
  }
}
