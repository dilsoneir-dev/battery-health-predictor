# Battery Health Predictor & 3D Degradation Diagnostics (Dell G15)

Análise preditiva, extracao de dados e modelagem de degradacao da bateria do notebook Dell G15.

## Funcionalidades
- Parsing automatico de relatorios nativos (`powercfg /batteryreport`).
- Regressao Linear Preditiva de degradacao da saude da bateria (SoH).
- Modelagem 3D do impacto de Temperatura, Carga na Tomada (AC) e Ciclos.
- Integracao com dados do Dell ePSA via `config.json`.