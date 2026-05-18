# Proyecto 6 — Análisis Empírico del Costo Criptográfico TLS

## Descripción

Este proyecto realiza un análisis empírico reproducible del costo criptográfico observable asociado a conexiones HTTPS/TLS.

El experimento compara dos escenarios:

- Sesiones efímeras o cortas: cada request abre una nueva conexión.
- Sesiones persistentes o largas: varios requests reutilizan una conexión TLS.

El objetivo es evaluar si el costo criptográfico del handshake TLS se percibe más en sesiones cortas y si se amortiza en sesiones largas.

El proyecto mide:

- Tiempo DNS.
- Tiempo TCP.
- Tiempo de handshake TLS.
- Tiempo HTTP.
- Tiempo total observable.
- Tiempo CPU.
- Bytes enviados y recibidos.
- Ahorro por reutilización de sesión.
- Correlaciones y covarianzas entre métricas.

---

# Estructura esperada

```text
TLS 1.3 Final/
│
├── Códigos/
│   ├── run_final.py
│   ├── analyze_final.py
│   └── combine_final_csvs.py
│
├── data/
│   └── final_tls13/
│
├── results/
│   ├── final_tls13/
│   └── final_combined/
│
└── README.md
```

---

# Requisitos

Python 3.10 o superior.

Dependencias:

```bash
pandas
matplotlib
```

---

# Linux / Ubuntu / WSL

Entrar a la carpeta del proyecto:

```bash
cd "/mnt/c/Users/mauri/Downloads/TLS 1.3 Final"
```

Crear entorno virtual si no existe:

```bash
python3 -m venv .venv
```

Activar entorno virtual:

```bash
source .venv/bin/activate
```

Instalar dependencias:

```bash
python3 -m pip install pandas matplotlib
```

Prueba rápida:

```bash
python3 "Códigos/run_final.py" --repetitions 2 --sizes 1,3 --timeout 10 --delay 0.15
```

Analizar prueba:

```bash
python3 "Códigos/analyze_final.py" --input latest
```

Ejecutar experimento completo:

```bash
python3 "Códigos/run_final.py" --repetitions 15 --sizes 1,3,5,10,20,50,100 --timeout 10 --delay 0.15
```

Analizar experimento completo:

```bash
python3 "Códigos/analyze_final.py" --input latest
```

Combinar todos los CSV:

```bash
python3 "Códigos/combine_final_csvs.py"
```

Abrir resultados desde WSL:

```bash
explorer.exe results
```

---

# macOS

Entrar a la carpeta:

```bash
cd "/ruta/a/TLS 1.3 Final"
```

Crear entorno virtual:

```bash
python3 -m venv .venv
```

Activar entorno:

```bash
source .venv/bin/activate
```

Instalar dependencias:

```bash
python3 -m pip install pandas matplotlib
```

Ejecutar prueba rápida:

```bash
python3 "Códigos/run_final.py" --repetitions 2 --sizes 1,3 --timeout 10 --delay 0.15
```

Analizar prueba:

```bash
python3 "Códigos/analyze_final.py" --input latest
```

Ejecutar experimento completo:

```bash
python3 "Códigos/run_final.py" --repetitions 15 --sizes 1,3,5,10,20,50,100 --timeout 10 --delay 0.15
```

Analizar resultados:

```bash
python3 "Códigos/analyze_final.py" --input latest
```

Combinar CSVs:

```bash
python3 "Códigos/combine_final_csvs.py"
```

Abrir resultados:

```bash
open results
```

---

# Windows PowerShell

Entrar a la carpeta del proyecto:

```powershell
cd "C:\Users\mauri\Downloads\TLS 1.3 Final"
```

Crear entorno virtual:

```powershell
python -m venv .venv
```

Activar entorno virtual:

```powershell
.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la activación:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Volver a activar:

```powershell
.venv\Scripts\Activate.ps1
```

Instalar dependencias:

```powershell
python -m pip install pandas matplotlib
```

Ejecutar prueba rápida:

```powershell
python "Códigos\run_final.py" --repetitions 2 --sizes 1,3 --timeout 10 --delay 0.15
```

Analizar prueba:

```powershell
python "Códigos\analyze_final.py" --input latest
```

Ejecutar experimento completo:

```powershell
python "Códigos\run_final.py" --repetitions 15 --sizes 1,3,5,10,20,50,100 --timeout 10 --delay 0.15
```

Analizar resultados:

```powershell
python "Códigos\analyze_final.py" --input latest
```

Combinar CSVs:

```powershell
python "Códigos\combine_final_csvs.py"
```

Abrir resultados:

```powershell
start results
```

---

# Qué hace cada script

## run_final.py

Ejecuta el experimento principal.

Este script:

- Realiza conexiones HTTPS reales.
- Fuerza TLS 1.3 estricto.
- Ejecuta sesiones cortas y sesiones largas.
- Mide DNS, TCP, TLS, HTTP, wall time y CPU time.
- Guarda resultados por sesión y por request.

Archivos generados:

```text
data/final_tls13/raw_results_final_tls13_*.csv
data/final_tls13/request_log_final_tls13_*.csv
```

---

## analyze_final.py

Analiza una ejecución específica del experimento.

Este script:

- Lee el CSV más reciente o uno indicado manualmente.
- Calcula medias, medianas, desviaciones estándar e intervalos de confianza.
- Calcula ahorro entre sesión corta y sesión larga.
- Calcula correlaciones y covarianzas.
- Genera gráficas del experimento.
- Escribe una conclusión automática.

Comando:

```bash
python3 "Códigos/analyze_final.py" --input latest
```

Resultados principales:

```text
results/final_tls13/final_global_summary.csv
results/final_tls13/final_global_comparison.csv
results/final_tls13/final_target_correlations.csv
results/final_tls13/final_conclusion.txt
```

---

## combine_final_csvs.py

Combina varias ejecuciones independientes.

Este script:

- Carga todos los CSV de `data/final_tls13/`.
- Une varias corridas.
- Recalcula estadísticas globales.
- Calcula correlaciones y covarianzas globales.
- Genera gráficas combinadas.
- Produce un reporte general.

Comando:

```bash
python3 "Códigos/combine_final_csvs.py"
```

Resultados principales:

```text
results/final_combined/combined_raw_results.csv
results/final_combined/combined_summary.csv
results/final_combined/combined_comparison.csv
results/final_combined/combined_covariance_matrix.csv
results/final_combined/combined_correlation_matrix.csv
results/final_combined/combined_target_correlations.csv
results/final_combined/combined_report.txt
```

---

# Parámetros principales

## --repetitions

Número de repeticiones por escenario.

Ejemplo:

```bash
--repetitions 15
```

---

## --sizes

Número de requests evaluados por sesión.

Ejemplo:

```bash
--sizes 1,3,5,10,20,50,100
```

---

## --timeout

Tiempo máximo de espera por conexión.

Ejemplo:

```bash
--timeout 10
```

---

## --delay

Pausa entre requests.

Ejemplo:

```bash
--delay 0.15
```

---

# Flujo completo recomendado

## Linux / WSL / macOS

```bash
cd "/mnt/c/Users/mauri/Downloads/TLS 1.3 Final"
source .venv/bin/activate
python3 -m pip install pandas matplotlib
python3 "Códigos/run_final.py" --repetitions 2 --sizes 1,3 --timeout 10 --delay 0.15
python3 "Códigos/analyze_final.py" --input latest
python3 "Códigos/run_final.py" --repetitions 15 --sizes 1,3,5,10,20,50,100 --timeout 10 --delay 0.15
python3 "Códigos/analyze_final.py" --input latest
python3 "Códigos/combine_final_csvs.py"
```

## Windows PowerShell

```powershell
cd "C:\Users\mauri\Downloads\TLS 1.3 Final"
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install pandas matplotlib
python "Códigos\run_final.py" --repetitions 2 --sizes 1,3 --timeout 10 --delay 0.15
python "Códigos\analyze_final.py" --input latest
python "Códigos\run_final.py" --repetitions 15 --sizes 1,3,5,10,20,50,100 --timeout 10 --delay 0.15
python "Códigos\analyze_final.py" --input latest
python "Códigos\combine_final_csvs.py"
```

---

# Interpretación esperada

Teóricamente, se espera que:

- Las sesiones cortas tengan mayor costo acumulado.
- Las sesiones largas reduzcan el costo total.
- El handshake TLS sea más relevante en sesiones efímeras.
- El costo TLS se amortice en sesiones persistentes.
- La diferencia sea más clara cuando aumenta el número de requests.

En términos simples:

```text
sesión corta = muchos handshakes TLS
sesión larga = un handshake TLS reutilizado
```

Si los resultados muestran menor tiempo total, menor CPU y menor costo TLS por request en sesiones largas, entonces el experimento confirma que la reutilización de conexión reduce el costo criptográfico observable.

---

# Notas importantes

Los resultados pueden variar entre Windows, macOS y Linux porque dependen de:

- Red local.
- Sistema operativo.
- Implementación TLS.
- Estado del servidor.
- Latencia temporal.
- Carga del equipo.

---

# Reproducibilidad

El proyecto es reproducible porque:

- Los parámetros se controlan desde terminal.
- Los resultados se guardan en CSV.
- Se generan gráficas automáticamente.
- Se pueden repetir varias corridas.
- Se pueden combinar múltiples CSVs para análisis global.

Para aumentar robustez:

```bash
python3 "Códigos/run_final.py" --repetitions 15 --sizes 1,3,5,10,20,50,100 --timeout 10 --delay 0.15
```

Luego combinar:

```bash
python3 "Códigos/combine_final_csvs.py"
```
