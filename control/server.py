# ====== CONTROL: servidor Flask — recebe fotos, conta carros e envia ao ESP32 dos LEDs a RAZÃO de carros
# de cada via. Quem calcula o tempo e controla o semáforo é o ESP32, que devolve ao servidor os tempos
# de verde que calculou (para o dashboard mostrar). Este servidor não calcula tempo nem cuida de horário. ======

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
from datetime import datetime

from deteccao import contar_carros  # vem de siat/vision/deteccao.py

# ====== CONFIGURAÇÃO INICIAL ======
app = Flask(__name__)

# Libera acesso das rotas de dados para o dashboard React, que roda em outra porta/origem
# (ex: http://localhost:3000). Sem isso, o navegador bloqueia o fetch() por política de CORS
# caso o dashboard não esteja passando pelo proxy do Vite.
CORS(app, resources={r"/dados/*": {"origins": "*"}})

contagem_vias = {"via1": 0, "via2": 0}
IP_ESP32_LEDS = "http://192.168.0.101"

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

    # Uma linha por cálculo feito pelo ESP32: os tempos de verde que ele devolveu ao servidor
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
        requests.post(f"{IP_ESP32_LEDS}/razao", json=payload, timeout=2)
        print(f"[ESP32] razão enviada -> via1: {razao_via1:.2f} | via2: {razao_via2:.2f}")
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


# ====== ROTA: recebe do ESP32 dos LEDs os tempos de verde que ele calculou ======
@app.route('/tempos', methods=['POST'])
def registrar_tempos():
    dados = request.get_json(silent=True)

    try:
        tempo_via1 = int(dados["tempo_via1"])
        tempo_via2 = int(dados["tempo_via2"])
    except (KeyError, TypeError, ValueError):
        return "Dados inválidos", 400

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

    print(f"[ESP32] tempos de verde recebidos -> via1: {tempo_via1}s | via2: {tempo_via2}s")
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


# ====== INICIALIZAÇÃO DO SERVIDOR ======
if __name__ == '__main__':
    os.makedirs(DEBUG_DIR, exist_ok=True)
    iniciar_banco()
    app.run(host='0.0.0.0', port=5000, debug=True)



    # A interface gráfica (dashboard React) é um projeto separado que roda com "bun dev" e
    # consome as rotas /dados/... daqui através de um proxy configurado no vite.config.ts dele.
    # Este servidor Flask não serve nenhuma página HTML — só a API JSON.


# COMANDOS ÚTEIS (rode a partir de qualquer pasta, os caminhos internos já se ajustam sozinhos):
# NO WINDOWS LEMBRE DE RODAR "curl.exe ..." para funcionar
# No WINDOWS LEMBRE DE ESTAR DENTRO DO DIRETÓRIO CORRETO "siat" PARA OS COMANDOS
#
# cd "C:\Users\brito\OneDrive\Área de Trabalho\Faculdade\siat"
# dir tests
# curl.exe -X POST -H "Content-Type: image/jpeg" --data-binary "@tests/teste.jpg" http://localhost:5000/upload/via2
#
#
#
    # UPLOAD:    curl -X POST -H "Content-Type: image/jpeg" --data-binary "@tests/teste.jpg" http://localhost:5000/upload/via1
    #            curl -X POST -H "Content-Type: image/jpeg" --data-binary "@tests/trafego.jpg" http://localhost:5000/upload/via2

    # VER DADOS: curl http://localhost:5000/dados/deteccoes
    #            curl http://localhost:5000/dados/tempos
    #
    # PARA RODAR:
    #   (VENV): source venv/bin/activate

    #   a partir da raiz do projeto (siat/):  python control/server.py
    #   ou de dentro de control/:             python server.py
    #
    #   DASHBOARD(REACT):   cd ~/Área\ de\ trabalho/semaforo-inteligente/dashboard
    #                       bun dev
    #
    #
    #
#
#
#TERMINAL 1:
#    cd "C:\Users\brito\OneDrive\Área de Trabalho\Faculdade\siat"
#  venv\Scripts\Activate.ps1
#   python control/server.py
#
#
#TERMINAL 2:
#
#   cd "C:\Users\brito\OneDrive\Área de Trabalho\Faculdade\siat\dashboard"
#   bun dev
#
#
#   python control\exportar_excel.py