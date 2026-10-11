# Weekend Flight Bot

Informe diario de vuelos directos entre AMS/RTM y BCN, con histórico SQLite y envío por Gmail SMTP.

## Búsqueda y filtros actuales

- Próximas siete semanas, omitiendo los primeros siete días.
- Ida jueves desde las 16:00 o viernes a cualquier hora.
- Vuelta domingo desde las 16:00 o lunes a cualquier hora.
- Vueling y Transavia; el muestreo lejano también admite KLM en rutas con AMS.
- Cada ruta y fecha se consulta una sola vez por lote. El muestreo lejano usa otro lote porque admite otras aerolíneas.
- Un fallo de consulta o una página sin bloques reconocibles significa disponibilidad sin verificar. Una página con vuelos reconocidos, todos descartados, significa sin opciones que cumplan los filtros.

El informe abre con las tres combinaciones operativas más económicas, destaca bajadas de al menos 20 € y muestra un resumen por combinación con hasta dos opciones por trayecto. Termina con tres oportunidades lejanas observadas ese día. El total suma billetes de ida independientes y puede combinar aeropuertos.

Las valoraciones describen la distancia al mínimo observado; no predicen precios ni recomiendan comprar. Se necesitan al menos cinco fechas con precio completo para valorar el histórico. Las ejecuciones repetidas sustituyen la observación del mismo día.

## Ejecución local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python -m unittest discover -s tests -v
python -m src.main
```

La ejecución principal realiza búsquedas reales y envía un correo. Necesita `GMAIL_SMTP_USER`, `GMAIL_SMTP_APP_PASSWORD` y `EMAIL_TO`; configurar estos valores como secretos de GitHub Actions. No incluir credenciales en archivos del repositorio.

El flujo diario guarda `data/prices.db` en caché y como artefacto, y conserva páginas de diagnóstico en `debug/`. El flujo de pruebas de las propuestas de cambios usa datos simulados y no envía correos ni consulta precios.

## Límites

La extracción depende del formato de Google Flights. Los precios y equipaje deben confirmarse en la consulta enlazada. No existe aún detección automática de reservas compradas, cálculo de traslados/equipaje, prioridad personalizada de horarios ni supresión del correo diario por ausencia de cambios. `config/routes.yaml` pertenece a la versión anterior; los filtros activos están en `src/scrapers/google_flights_ui.py` y los horizontes en `src/main.py` y `src/learning.py`.

## Puentes NCIA

`src/holidays.py` recoge las fechas oficiales NCIA de La Haya de 2026 y 2027 facilitadas por el usuario. Incluye los días sustitutorios y el cierre navideño; no añade festivos nacionales que NCIA no haya publicado. La búsqueda operativa añade puentes para los próximos 180 días y muestrea hasta seis opciones por bloque (de cero a cinco días laborables afectados), priorizando la duración. No es una búsqueda exhaustiva de todas las fechas posibles.

El informe destaca noches en España, festivos y días laborables afectados. Esta última cifra cuenta conservadoramente las fechas laborables posteriores a la ida y hasta la vuelta; presupone trabajar antes de la salida de tarde y no da por autorizado el teletrabajo o las vacaciones. Un regreso temprano puede requerir menos permiso del indicado. Se mantienen los horarios ordinarios; en un festivo publicado se permite volar todo el día. El calendario posterior a 2027 está pendiente de publicación.

## Presupuesto anual

Se consideran 46 días de teletrabajo desde España y 30 días de vacaciones por año. El reparto orientativo prioriza teletrabajo y separa años naturales; no afirma que el saldo esté disponible. El consumo real y las reservas aún no están registrados. `estimate_allocation` acepta saldos restantes por año para calcular necesidades sin cubrir. Las alternativas de viaje se muestran individualmente y no constituyen un plan anual acumulado ni descuentan días automáticamente.

El usuario confirma los cupos completos para 2027: 46 días de teletrabajo y 30 de vacaciones. Los días adicionales arrastrados desde 2026 están pendientes de cuantificar y no se incluyen. El saldo de 2026 continúa sin verificar.
