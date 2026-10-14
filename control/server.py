# ====== CONTROL: servidor Flask — recebe fotos, conta carros e envia ao ESP32 dos LEDs a RAZÃO de carros
# de cada via. Quem calcula o tempo e controla o semáforo é o ESP32, que devolve ao servidor os tempos
# de verde de cada ciclo e avisa periodicamente que está conectado (o dashboard mostra tudo isso).
# Este servidor não calcula tempo nem cuida de horário. ======

import sys
import os

# BASE_DIR = pasta onde este arquivo (server.py) está, não importa de onde você rodou o comando
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Adiciona a pasta vision/ (irmã de control/) ao caminho de busca de módulos do Python,
# assim "from deteccao import contar_carros" funciona sem precisar instalar nada como pacote
sys.path.append(os.path.join(BASE_DIR, "..", "vision"))

from flask import Flask, request, jsonify
from flask_cors import CORS
import cv2
import requests
import sqlite3
from datetime import datetime, timedelta

from deteccao import contar_carros  # vem de siat/vision/deteccao.py

# ====== CONFIGURAÇÃO INICIAL ======
app = Flask(__name__)

# Libera acesso das rotas de dados para o dashboard React, que roda em outra porta/origem
# (ex: http://localhost:3000). Sem isso, o navegador bloqueia o fetch() por política de CORS
# caso o dashboard não esteja passando pelo proxy do Vite.
CORS(app, resources={r"/dados/*": {"origins": "*"}})

contagem_vias = {"via1": 0, "via2": 0}
IP_ESP32_LEDS = "http://192.168.0.101"

# ---- Conexão do ESP32 dos semáforos ----
# O servidor considera o ESP32 conectado se houve algum contato (nos dois sentidos) recentemente.
# O ESP32 avisa a cada 10 s; passados 30 s sem nenhum contato, ele aparece como desconectado.
LIMITE_DESCONEXAO_SEGUNDOS = 30
status_esp32 = {"ultimo_contato": None, "ip": None}

# Caminhos ancorados em BASE_DIR: funcionam igual rodando "python server.py" de dentro
# de control/, ou "python control/server.py" da raiz do projeto (siat/)
DB_PATH = os.path.join(BASE_DIR, "semaforo.db")
DEBUG_DIR = os.path.join(BASE_DIR, "debug")


# ====== BANCO DE DADOS ======
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def iniciar_banco():
    conn = get_db()
    cursor = conn.cursor()

    # Uma linha por foto processada: o que a câmera viu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deteccoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            via TEXT NOT NULL,
            quantidade_carros INTEGER NOT NULL,
            imagem_debug TEXT,
            timestamp TEXT NOT NULL
        )
    """)

    # Uma linha por CICLO do semáforo: os tempos de verde que o ESP32 aplicou e devolveu ao servidor
    # (mesma estrutura de antes, então bancos já existentes continuam compatíveis)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tempos_calculados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tempo_via1 INTEGER NOT NULL,
            tempo_via2 INTEGER NOT NULL,
            carros_via1 INTEGER,
            carros_via2 INTEGER,
            enviado_com_sucesso INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ====== CONEXÃO DO ESP32 ======
def marcar_contato_esp32(ip=None):
    status_esp32["ultimo_contato"] = datetime.now()
    if ip:
        status_esp32["ip"] = ip


# ====== ENVIO DA RAZÃO PARA O ESP32 (quem calcula o tempo é o ESP32) ======
def enviar_razao_ao_esp32():
    total = contagem_vias["via1"] + contagem_vias["via2"]

    if total == 0:
        # Nenhum carro nas duas vias: manda 0 e 0 (o ESP32 entende como "sem movimento")
        razao_via1 = 0.0
        razao_via2 = 0.0
    else:
        razao_via1 = contagem_vias["via1"] / total
        razao_via2 = contagem_vias["via2"] / total

    payload = {"razao_via1": razao_via1, "razao_via2": razao_via2}

    try:
        resposta = requests.post(f"{IP_ESP32_LEDS}/razao", json=payload, timeout=2)
        if resposta.status_code == 200:
            marcar_contato_esp32()  # o ESP32 respondeu: está conectado
            print(f"[ESP32] razão enviada -> via1: {razao_via1:.2f} | via2: {razao_via2:.2f}")
        else:
            print(f"ESP32 recusou a razão (código {resposta.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar razão para o ESP32: {e}")


# ====== ROTA: recebe a foto do ESP32-CAM ======
@app.route('/upload/<via>', methods=['POST'])
def upload(via):
    imagem_bytes = request.data
    if len(imagem_bytes) == 0:
        return "Imagem vazia", 400

    n_carros, imagem_debug = contar_carros(imagem_bytes)
    contagem_vias[via] = n_carros

    timestamp = datetime.now().strftime("%H%M%S")
    nome_arquivo = os.path.join(DEBUG_DIR, f"{via}_{timestamp}.jpg")
    cv2.imwrite(nome_arquivo, imagem_debug)

    conn = get_db()
    conn.execute(
        "INSERT INTO deteccoes (via, quantidade_carros, imagem_debug, timestamp) VALUES (?, ?, ?, ?)",
        (via, n_carros, nome_arquivo, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()

    print(f"[{via}] {n_carros} carro(s) detectado(s)")
    enviar_razao_ao_esp32()
    return "OK", 200


# ====== ROTA: aviso periódico do ESP32 dos LEDs ("estou conectado") ======
@app.route('/status', methods=['POST'])
def receber_status():
    marcar_contato_esp32(request.remote_addr)
    return "OK", 200


# ====== ROTA: recebe do ESP32 dos LEDs os tempos de verde do ciclo que ele iniciou ======
@app.route('/tempos', methods=['POST'])
def registrar_tempos():
    dados = request.get_json(silent=True)

    try:
        tempo_via1 = int(dados["tempo_via1"])
        tempo_via2 = int(dados["tempo_via2"])
    except (KeyError, TypeError, ValueError):
        return "Dados inválidos", 400

    marcar_contato_esp32(request.remote_addr)

    # O ESP32 só conhece a razão, não a quantidade de carros. A contagem gravada junto com os
    # tempos é a que o próprio servidor tem da câmera neste momento (a que gerou essa razão).
    conn = get_db()
    conn.execute(
        """INSERT INTO tempos_calculados
           (tempo_via1, tempo_via2, carros_via1, carros_via2, enviado_com_sucesso, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (tempo_via1, tempo_via2, contagem_vias["via1"], contagem_vias["via2"],
         1, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()

    print(f"[ESP32] ciclo iniciado -> verde via1: {tempo_via1}s | via2: {tempo_via2}s")
    return "OK", 200


# ====== ROTAS DE CONSULTA AO BANCO ======
@app.route('/dados/deteccoes', methods=['GET'])
def listar_deteccoes():
    conn = get_db()
    linhas = conn.execute("SELECT * FROM deteccoes ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    return jsonify([dict(l) for l in linhas])


@app.route('/dados/tempos', methods=['GET'])
def listar_tempos():
    conn = get_db()
    linhas = conn.execute("SELECT * FROM tempos_calculados ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    return jsonify([dict(l) for l in linhas])


@app.route('/dados/status', methods=['GET'])
def status_dos_semaforos():
    ultimo = status_esp32["ultimo_contato"]

    if ultimo is None:
        segundos = None
        conectado = False
    else:
        segundos = int((datetime.now() - ultimo).total_seconds())
        conectado = segundos <= LIMITE_DESCONEXAO_SEGUNDOS

    return jsonify({
        "conectado": conectado,
        "segundos_desde_contato": segundos,
        "ultimo_contato": ultimo.isoformat(timespec="seconds") if ultimo else None,
        "ip": status_esp32["ip"],
        "limite_segundos": LIMITE_DESCONEXAO_SEGUNDOS,
    })


@app.route('/dados/por-hora', methods=['GET'])
def listar_por_hora():
    # Resumo das últimas 24 h, uma linha por hora:
    #  - carros detectados em cada via e a RAZÃO de cada via (carros da via / total de carros)
    #  - segundos em que o verde de cada via ficou aberto (soma dos ciclos daquela hora)
    desde = (datetime.now() - timedelta(hours=24)).isoformat(timespec="seconds")

    conn = get_db()
    fluxo = conn.execute(
        """SELECT substr(timestamp, 1, 13) AS hora,
                  SUM(CASE WHEN via = 'via1' THEN quantidade_carros ELSE 0 END) AS carros_via1,
                  SUM(CASE WHEN via = 'via2' THEN quantidade_carros ELSE 0 END) AS carros_via2
           FROM deteccoes WHERE timestamp >= ? GROUP BY hora""",
        (desde,)
    ).fetchall()
    aberto = conn.execute(
        """SELECT substr(timestamp, 1, 13) AS hora,
                  SUM(tempo_via1) AS aberto_via1,
                  SUM(tempo_via2) AS aberto_via2
           FROM tempos_calculados WHERE timestamp >= ? GROUP BY hora""",
        (desde,)
    ).fetchall()
    conn.close()

    # "hora" tem o formato 2026-10-14T15 (data + hora cheia)
    horas = {}

    def obter_hora(hora):
        return horas.setdefault(hora, {
            "hora": hora,
            "carros_via1": 0, "carros_via2": 0,
            "aberto_via1": 0, "aberto_via2": 0,
        })

    for linha in fluxo:
        item = obter_hora(linha["hora"])
        item["carros_via1"] = linha["carros_via1"]
        item["carros_via2"] = linha["carros_via2"]

    for linha in aberto:
        item = obter_hora(linha["hora"])
        item["aberto_via1"] = linha["aberto_via1"]
        item["aberto_via2"] = linha["aberto_via2"]

    resultado = []
    for hora in sorted(horas):
        item = horas[hora]
        total = item["carros_via1"] + item["carros_via2"]
        item["razao_via1"] = item["carros_via1"] / total if total else 0
        item["razao_via2"] = item["carros_via2"] / total if total else 0
        resultado.append(item)

    return jsonify(resultado)


# ====== INICIALIZAÇÃO DO SERVIDOR ======
if __name__ == '__main__':
    os.makedirs(DEBUG_DIR, exist_ok=True)
    iniciar_banco()
    app.run(host='0.0.0.0', port=5000, debug=True)


# ANTES DE COMEÇAR DENTRO DA PASTA:
#   Remove-Item control\semaforo.db
#
# TESTE1 - SERVIDOR(dois terminais):
#       cd "C:\Users\brito\OneDrive\Área de Trabalho\Faculdade\siat"
#       venv\Scripts\Activate.ps1
#       python control/server.py
#
#
#       curl.exe -X POST -H "Content-Type: image/jpeg" --data-binary "@tests/teste.jpg" http://localhost:5000/upload/via1
#       curl.exe -X POST -H "Content-Type: image/jpeg" --data-binary "@tests/trafego.jpg" http://localhost:5000/upload/via2
#       curl.exe http://localhost:5000/dados/deteccoes
#       curl.exe http://localhost:5000/dados/por-hora
#
# TESTE2 - DASHBOARD:
#       cd dashboard
#       bun dev
#
# TESTE3 - SIMULE O ESP32 ATIVO:
#       python -c "import requests; print(requests.post('http://localhost:5000/status').status_code)"
#       python -c "import requests; print(requests.post('http://localhost:5000/tempos', json={'tempo_via1':32,'tempo_via2':17}).status_code)"