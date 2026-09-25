# ====== CONTROL: servidor Flask — recebe fotos, calcula tempos, envia pro ESP32 dos LEDs ======

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
CORS(app, resources={r"/dados/*": {"origins": "*"}, r"/horario": {"origins": "*"}})

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deteccoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            via TEXT NOT NULL,
            quantidade_carros INTEGER NOT NULL,
            imagem_debug TEXT,
            timestamp TEXT NOT NULL
        )
    """)

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sincronizacoes_horario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_solicitante TEXT,
            hora_enviada TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ====== CÁLCULO DE TEMPO ======
def calcular_tempos():
    total = contagem_vias["via1"] + contagem_vias["via2"]
    if total == 0:
        tempos = {"via1": 15, "via2": 15}
    else:
        proporcao1 = contagem_vias["via1"] / total
        tempo_via1 = max(10, min(40, int(10 + proporcao1 * 30)))
        tempo_via2 = max(10, min(40, int(10 + (1 - proporcao1) * 30)))
        tempos = {"via1": tempo_via1, "via2": tempo_via2}

    sucesso = True
    try:
        requests.post(f"{IP_ESP32_LEDS}/tempos", json=tempos, timeout=2)
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar tempos para o ESP32: {e}")
        sucesso = False

    conn = get_db()
    conn.execute(
        """INSERT INTO tempos_calculados
           (tempo_via1, tempo_via2, carros_via1, carros_via2, enviado_com_sucesso, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (tempos["via1"], tempos["via2"], contagem_vias["via1"], contagem_vias["via2"],
         int(sucesso), datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()


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
    calcular_tempos()
    return "OK", 200


# ====== ROTA: horário (fonte da verdade do tempo) ======
@app.route('/horario', methods=['GET'])
def horario():
    agora = datetime.now()
    hora_texto = agora.strftime("%H:%M:%S")

    conn = get_db()
    conn.execute(
        "INSERT INTO sincronizacoes_horario (ip_solicitante, hora_enviada, timestamp) VALUES (?, ?, ?)",
        (request.remote_addr, hora_texto, agora.isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()

    return jsonify({
        "hora": hora_texto,
        "data": agora.strftime("%d/%m/%Y"),
        "timestamp": int(agora.timestamp())
    })


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


@app.route('/dados/sincronizacoes', methods=['GET'])
def listar_sincronizacoes():
    conn = get_db()
    linhas = conn.execute("SELECT * FROM sincronizacoes_horario ORDER BY id DESC LIMIT 100").fetchall()
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
    # HORARIO:   curl http://localhost:5000/horario
    
    # UPLOAD:    curl -X POST -H "Content-Type: image/jpeg" --data-binary "@tests/teste.jpg" http://localhost:5000/upload/via1
    #            curl -X POST -H "Content-Type: image/jpeg" --data-binary "@tests/trafego.jpg" http://localhost:5000/upload/via2
    
    # VER DADOS: curl http://localhost:5000/dados/deteccoes
    #            curl http://localhost:5000/dados/tempos
    #            curl http://localhost:5000/dados/sincronizacoes
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
