# 🔋 Battery Health Predictor & 3D Degradation Diagnostics (Dell G15)

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Data Science](https://img.shields.io/badge/Data%20Science-Scikit--Learn-orange)

Projeto desenvolvido em **Python** para analise preditiva e modelagem multidimensional da degradacao de baterias de ion de litio em notebook.

O sistema cruza relatorios nativos do sistema operacional (`powercfg /batteryreport`) com telemetrias pre-boot gravadas na BIOS do dispositivo (Dell ePSA), mapeando os principais vetores de desgaste.

---

## 📊 Metodologia Tecnica e Fundamentacao

A perda de capacidade das celulas de litio ocorre por estresse quimico, termico e eletrico. A metodologia deste projeto baseia-se em tres pilares principais:

### 1. Extracao e Parsing Nativos
* **HTML Scraping:** Leitura e estruturacao do historico de capacidade via `BeautifulSoup` a partir do relatorio do Windows (`battery-report.html`).
* **Telemetria de Firmware (ePSA):** Leitura de dados reais nao expostos pelo S.O. (como o contador exato de ciclos de carga e a data de fabricacao), traduzidas em `config.json`.
* **Sanitizacao Automatica de Dados:** Tratamento de privacidade que remove identificadores pessoais.

### 2. Projecao Temporal (Regressao Linear)
Utilizando a biblioteca `scikit-learn`, o algoritmo aplica **Regressao Linear** sobre o historico de *Full Charge Capacity* vs *Design Capacity* para calcular a taxa diaria de degradacao:

$$\text{Saúde (\%)} = f(\text{Dias de Uso})$$

A partir desse modelo, estima-se a data exata em que a bateria atingira o limite critico de **30% de capacidade residual**.

### 3. Modelagem Multidimensional de Estresse (Superficie 3D)
O desgaste de celulas de ion de litio segue equacoes empiricas derivadas do efeito Arrhenius (temperatura) e estresse de voltagem (estado de carga elevado continuo). O modelo 3D simula a perda de saúde ($S$) em funcao de:
* **Temperatura Operacional ($T$ em °C):** Degradacao nao linear acelerada acima de 45°C.
* **Tempo Conectado a Tomada ($AC$ em %):** Manutencao do estresse de tensao a 100% de carga.
* **Ciclos de Carga ($C$):** Desgaste mecanico por intercalacao de litio.

### 4. Otimizações Ativas

Foram realizadas as seguintes otimizações, as quais refletiram em melhoria da saúde da bateria:

* **Custom Charge Stop (85%):** Redução do estresse de alta tensão nas células.
* **Custom Charge Start (50%):** Eliminação de micro-recargas com a fonte conectada.
* **Connected Standby (Desativado):** Interrupção de drenagem silenciosa e aquecimento em repouso.
* **USB PowerShare (Desativado):** Corte do fornecimento contínuo de energia pelas portas USB com o sistema desligado.

---

## 📁 Estrutura do Repositorio

```text
battery-health-predictor/
├── Battery.py                       # Script principal de processamento e visualizacao
├── config.json                      # Arquivo de configuracao de hardware e limites
├── requirements.txt                 # Dependencias do projeto Python
├── README.md                        # Documentacao e fundamentacao da metodologia
├── battery-report-sample.html       # Relatorio de exemplo sanitizado (cross-platform)
├── battery_health_projection.png   # Grafico 1: Projecao temporal e parametros formais
└── battery_advanced_degradation.png  # Grafico 2: Superficie 3D de estresse e decomposicao
```

## 📄 Licenca

Este projeto esta sob a licenca MIT.
