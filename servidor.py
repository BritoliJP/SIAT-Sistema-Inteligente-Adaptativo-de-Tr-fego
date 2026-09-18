# ====== 1. IMPORTS ======
from flask import Flask, request, jsonify
import cv2
import numpy as np
import requests
import os
import sqlite3
from datetime import datetime
from ultralytics import YOLO

# ====== 2. CONFIGURAÇÃO INICIAL (roda uma vez, quando o servidor liga) ======
app = Flask(__name__)

modelo = YOLO('yolov8n.pt')  # baixa automaticamente na primeira execução

# Classes do dataset COCO que nos interessam (veículos)
CLASSES_VEICULOS = {2: "carro", 3: "moto", 5: "onibus", 7: "caminhao"}

contagem_vias = {"via1": 0, "via2": 0}
IP_ESP32_LEDS = "http://192.168.0.101"

DB_PATH = "semaforo.db"


# ====== 2.1 BANCO DE DADOS ======
def get_db():
    # check_same_thread=False porque o Flask pode atender requisições em threads diferentes
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def iniciar_banco():
    conn = get_db()
    cursor = conn.cursor()

    # Dados que o ESP32-CAM envia para o servidor (fotos -> contagem de carros)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deteccoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            via TEXT NOT NULL,
            quantidade_carros INTEGER NOT NULL,
            imagem_debug TEXT,
            timestamp TEXT NOT NULL
        )
    """)

    # Dados que o servidor calcula e envia de volta para o ESP32 dos LEDs
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

    # Cada vez que o ESP32 dos LEDs pede o horário ao servidor
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


# ====== 3. FUNÇÃO DE DETECÇÃO (só é executada quando chamada) ======
def contar_carros(imagem_bytes):
    img_array = np.frombuffer(imagem_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    resultados = modelo(img, conf=0.4, verbose=False, device='cpu')[0]

    contador = 0
    img_debug = img.copy()

    for box in resultados.boxes:
        classe_id = int(box.cls[0])
        if classe_id in CLASSES_VEICULOS:
            contador += 1
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            nome = CLASSES_VEICULOS[classe_id]
            confianca = float(box.conf[0])
            cv2.rectangle(img_debug, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img_debug, f"{nome} {confianca:.2f}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    return contador, img_debug


# ====== 4. FUNÇÃO DE CÁLCULO DE TEMPO (só é executada quando chamada) ======
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

    # Grava no banco o que foi calculado e se chegou a ser enviado com sucesso
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


# ====== 5. ROTA HTTP (só é executada quando o ESP32-CAM faz o POST) ======
@app.route('/upload/<via>', methods=['POST'])
def upload(via):
    imagem_bytes = request.data
    if len(imagem_bytes) == 0:
        return "Imagem vazia", 400

    n_carros, imagem_debug = contar_carros(imagem_bytes)
    contagem_vias[via] = n_carros

    timestamp = datetime.now().strftime("%H%M%S")
    nome_arquivo = f"debug/{via}_{timestamp}.jpg"
    cv2.imwrite(nome_arquivo, imagem_debug)

    # Grava no banco a detecção recebida da câmera
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


# ====== 6. HORÁRIO (o servidor/notebook vira a "fonte da verdade" do tempo) ======
@app.route('/horario', methods=['GET'])
def horario():
    agora = datetime.now()
    hora_texto = agora.strftime("%H:%M:%S")

    # Grava no banco que alguém (o ESP32 dos LEDs) pediu o horário
    conn = get_db()
    conn.execute(
        "INSERT INTO sincronizacoes_horario (ip_solicitante, hora_enviada, timestamp) VALUES (?, ?, ?)",
        (request.remote_addr, hora_texto, agora.isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()

    return jsonify({
        "hora": hora_texto,                      # ex: "14:35:22"
        "data": agora.strftime("%d/%m/%Y"),      # ex: "15/09/2026"
        "timestamp": int(agora.timestamp())      # número único representando o momento exato
    })


# ====== 6.1 ROTAS PARA CONSULTAR O BANCO (úteis pra ver os dados sem abrir o SQLite manualmente) ======
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


# ====== 7. INICIALIZAÇÃO DO SERVIDOR (só roda se o arquivo for executado diretamente) ======
if __name__ == '__main__':
    os.makedirs("debug", exist_ok=True)
    iniciar_banco()
    app.run(host='0.0.0.0', port=5000, debug=True)


# COMANDOS ÚTEIS NO SERVIDOR:
    # --HORARIO:  curl http://localhost:5000/horario
    # --IA:       curl -X POST -H "Content-Type: image/jpeg" --data-binary "@fototeste.jpg" http://localhost:5000/upload/via1
    # --Detecções:             curl http://localhost:5000/dados/deteccoes
    # --Decisão do servidor:   curl http://localhost:5000/dados/tempos
    # --EspLED_Pede_horarios:  curl http://localhost:5000/dados/sincronizacoes
    # --Exportar dados em excel: python exportar_excel.py

# COMANDOS DO AMBIENTE VIRTUAL:
    # --Ambiente virtual [venv]: source venv/bin/activate
    # --Desativação: deactivate

