# SIAT – Sistema Inteligente Adaptativo de Tráfego para Corredores Urbanos

Sistema de controle semafórico adaptativo baseado em visão computacional e Inteligência Artificial, desenvolvido para otimizar a mobilidade urbana em corredores viários críticos.

## 📍 Sobre o projeto

O SIAT é uma solução de mobilidade urbana inteligente aplicada à cidade de **Sorocaba–SP**, com área piloto na **Avenida Dom Aguirre**, especificamente no cruzamento localizado na **Ponte Salomão Pavlovsky** — um dos principais corredores estruturais do município.

O sistema identifica a demanda veicular em tempo real e ajusta dinamicamente os tempos de sinalização semafórica, reduzindo congestionamentos e melhorando o fluxo de tráfego sem intervenção humana.

## 🎯 Objetivo

Substituir o controle semafórico de tempo fixo por um modelo **adaptativo**, capaz de:
- Identificar a demanda veicular em cada via do cruzamento em tempo real
- Ajustar dinamicamente o tempo de abertura/fechamento dos semáforos
- Reduzir congestionamentos em corredores estruturais de alto fluxo

## 🏗️ Arquitetura do sistema

| Componente | Tecnologia |
|---|---|
| Aquisição de imagens | Câmeras **ESP32-CAM** |
| Processamento computacional | **Python** |
| Visão computacional | **OpenCV** |
| Detecção e contagem de veículos | Algoritmos da família **YOLO** |

### Fluxo de funcionamento
1. As câmeras ESP32-CAM capturam imagens do cruzamento em tempo real
2. As imagens são processadas em Python utilizando OpenCV
3. Os algoritmos YOLO detectam e contam os veículos presentes em cada via
4. Com base na contagem, o sistema calcula e ajusta dinamicamente os tempos do semáforo

## 🛠️ Tecnologias utilizadas

![Python](https://img.shields.io/badge/-Python-3776AB?style=flat-square&logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/-OpenCV-5C3EE8?style=flat-square&logo=opencv&logoColor=white)
![YOLO](https://img.shields.io/badge/-YOLO-00FFFF?style=flat-square&logo=yolo&logoColor=black)
![ESP32](https://img.shields.io/badge/-ESP32--CAM-E7352C?style=flat-square&logo=espressif&logoColor=white)

## 📦 Estrutura do repositório

```
siat/
├── hardware/          # Firmware e configurações da ESP32-CAM
├── vision/            # Scripts de processamento de imagem (OpenCV + YOLO)
├── control/           # Lógica de controle e ajuste do tempo semafórico
├── docs/              # Documentação e relatórios do projeto
└── README.md
```

## 🚀 Como executar

```bash
# Clone o repositório
git clone https://github.com/SEU_USUARIO/siat.git
cd siat

# Instale as dependências
pip install -r requirements.txt

# Execute o módulo de detecção
python vision/detect.py
```

## 👥 Equipe

Projeto desenvolvido em grupo como parte da graduação em Engenharia da Computação.
