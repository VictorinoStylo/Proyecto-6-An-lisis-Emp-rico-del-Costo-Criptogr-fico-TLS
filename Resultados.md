# Resultados

Los resultados obtenidos del experimento se encuentran dentro de la carpeta adjunta del proyecto. En ella se incluyen:

- CSVs con resultados por sesión y por request.
- Matrices de correlación y covarianza.
- Reportes automáticos generados por el análisis.
- Gráficas comparativas.
- Conclusiones automáticas del experimento.

El flujo experimental ejecutado puede observarse en las imágenes y archivos generados dentro de la carpeta `results/`.

## Resumen de los resultados obtenidos

El experimento fue ejecutado utilizando conexiones HTTPS reales con TLS 1.3 estricto sobre distintos servidores web reales:

- Google
- YouTube
- Wikipedia
- GitHub
- Python.org

Se evaluaron escenarios con:

```text
n = 1, 3, 5, 10, 20, 50 y 100 requests
15 repeticiones por escenario
```

Los resultados obtenidos muestran una diferencia clara entre sesiones cortas y sesiones largas.

Principales hallazgos:

- Las sesiones largas reducen significativamente el costo observable asociado al handshake TLS.
- El costo criptográfico se concentra principalmente en el establecimiento inicial de la conexión segura.
- En sesiones cortas, dicho costo se repite para cada request.
- En sesiones largas, el costo se amortiza mediante reutilización de conexión.

Resultados destacados reportados automáticamente por el análisis:

```text
Ahorro en tiempo total usando sesión larga: 55.71%
Ahorro en handshake TLS usando sesión larga: 98.92%
Ahorro en setup de conexión usando sesión larga: 98.83%
Ahorro en CPU usando sesión larga: 95.87%
```

Además, el análisis de correlación mostró que las variables más relacionadas con el costo TLS fueron:

- Tiempo total de setup de conexión.
- Tiempo TCP.
- Tiempo DNS.
- Tiempo CPU.
- Tiempo total observable.

Esto indica que el costo criptográfico no solo impacta el handshake TLS directamente, sino también el tiempo total percibido y el consumo computacional asociado a la conexión.

En términos generales, los resultados respaldan la hipótesis inicial del proyecto:

```text
El impacto del costo criptográfico se percibe más en sesiones efímeras que en sesiones persistentes.
```

También se observó que conforme aumenta el número de requests, las sesiones persistentes se vuelven considerablemente más eficientes debido a la amortización del costo inicial de autenticación TLS.
