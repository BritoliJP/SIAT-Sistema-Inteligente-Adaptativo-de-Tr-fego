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
| Servidor / API | **Flask** |
| Armazenamento de dados | **SQLite** |
| Controle do semáforo | **ESP32** (LEDs), via HTTP/JSON |
| Interface gráfica | **React** (TanStack Start), consumindo a API em tempo real |

### Fluxo de funcionamento
1. As câmeras ESP32-CAM capturam imagens do cruzamento em tempo real
2. As imagens são enviadas via HTTP para o servidor Flask, onde são processadas em Python utilizando OpenCV
3. Os algoritmos YOLO detectam e contam os veículos presentes em cada via
4. Com base na contagem, o servidor Flask calcula os novos tempos de verde e os envia ao ESP32 responsável pelos LEDs, que ajusta o semáforo dinamicamente
5. Cada detecção, tempo calculado e sincronização de horário é registrado em um banco de dados SQLite
6. O dashboard web (React) consome os dados do servidor em tempo real, exibindo os tempos de verde e a contagem de veículos em gráficos e indicadores

## 🛠️ Tecnologias utilizadas

![Python](https://img.shields.io/badge/-Python-3776AB?style=flat-square&logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/-OpenCV-5C3EE8?style=flat-square&logo=opencv&logoColor=white)
![YOLO](https://img.shields.io/badge/-YOLO-00FFFF?style=flat-square&logo=yolo&logoColor=black)
![ESP32](https://img.shields.io/badge/-ESP32--CAM-E7352C?style=flat-square&logo=espressif&logoColor=white)
![Flask](https://img.shields.io/badge/-Flask-000000?style=flat-square&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/-SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![React](https://img.shields.io/badge/-React-61DAFB?style=flat-square&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/-TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)

## 📦 Estrutura do repositório

```
siat/
├── control/                # Lógica de controle e ajuste do tempo semafórico
├── dashboard/             # Página WEB
├── debug/                 # Resultado do YOLO
├── docs/                  # Documentação e relatórios do projeto   
├── hardware/esp32_leds    # Firmware e configurações da ESP32-CAM
├── tests/                 # Imagens para testes
├── vision/                # Scripts de processamento de imagem (OpenCV + YOLO)
└── README.md
```

## ✅ Pré-requisitos
 
Antes de começar, tenha instalado na máquina:
 
- **Python 3.10+** com `pip`
- **Git**
- **Bun** (gerenciador de pacotes usado pelo dashboard) — veja como instalar no passo 4
## 🚀 Como executar
 
### 1. Clonar o repositório
 
```bash
git clone https://github.com/SEU_USUARIO/siat.git
cd siat
```
 
### 2. Criar e ativar um ambiente virtual Python
 
Distribuições Linux recentes (Debian/Ubuntu) bloqueiam a instalação de pacotes Python diretamente no sistema — por isso, use um ambiente virtual:
 
```bash
python3 -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows (PowerShell)
```
 
### 3. Instalar as dependências do backend
 
```bash
pip install -r requirements.txt
```
 
### 4. Rodar o servidor Flask (backend)
 
```bash
python control/server.py
```
 
O servidor sobe em `http://localhost:5000` e cria automaticamente o banco `semaforo.db` e a pasta `control/debug/` na primeira execução.
 
**Testar se está funcionando:**
```bash
curl http://localhost:5000/horario
curl -X POST -H "Content-Type: image/jpeg" --data-binary "@tests/foto_teste.jpg" http://localhost:5000/upload/via1
curl http://localhost:5000/dados/deteccoes
```
 
### 5. Instalar o Bun (necessário só na primeira vez, para o dashboard)
 
```bash
curl -fsSL https://bun.sh/install | bash
source ~/.bashrc   # ou reabra o terminal
bun --version      # confirma que instalou
```
 
### 6. Rodar o dashboard (interface gráfica)
 
Em um **novo terminal**, com o Flask do passo 4 ainda rodando:
 
```bash
cd dashboard
bun install
bun dev
```
 
Acesse o endereço mostrado no terminal (geralmente `http://localhost:3000`). O dashboard consome os dados reais do Flask através de um proxy já configurado em `dashboard/vite.config.ts` — não é necessário nenhum ajuste adicional.
 
### 7. Firmware do ESP32 (hardware)
 
O arquivo `hardware/esp32_leds/esp32_leds.ino` deve ser aberto na Arduino IDE (ou PlatformIO). Antes de gravar na placa, ajuste no início do arquivo:
 
```cpp
const char* ssid = "SEU_WIFI";
const char* password = "SUA_SENHA";
const char* horarioUrl = "http://IP_DO_SERVIDOR:5000/horario";
```
 
Substitua `IP_DO_SERVIDOR` pelo endereço IP da máquina onde o `control/server.py` está rodando na rede local (não use `localhost`, pois o ESP32 é um dispositivo separado).
 
## 📊 Exportar dados para Excel
 
Com o servidor já tendo recebido algumas detecções:
```bash
python control/exportar_excel.py
```
Gera um arquivo `.xlsx` com 3 abas (Detecções, Tempos Calculados, Sincronizações de Horário).

## 👥 Equipe

Projeto desenvolvido em grupo como parte da graduação em Engenharia da Computação.
