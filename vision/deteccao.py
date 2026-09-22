# ====== VISION: detecção e contagem de veículos com YOLO ======
# Este módulo cuida só da parte de "olhar pra imagem e contar carros".
# Ele não sabe nada sobre Flask, banco de dados ou ESP32 — isso fica em control/.

import cv2
import numpy as np
from ultralytics import YOLO

modelo = YOLO('yolov8n.pt')  # baixa automaticamente na primeira execução

# Classes do dataset COCO que nos interessam (veículos)
CLASSES_VEICULOS = {2: "carro", 3: "moto", 5: "onibus", 7: "caminhao"}


def contar_carros(imagem_bytes):
    """Recebe os bytes de uma imagem JPEG e devolve:
       - a quantidade de veículos detectados
       - uma cópia da imagem com as caixas desenhadas (para debug)
    """
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
