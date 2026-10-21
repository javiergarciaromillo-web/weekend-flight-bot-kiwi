# Weekend Flight Bot

Informe diario de vuelos directos entre AMS/RTM y BCN, con histórico SQLite y envío por Gmail SMTP.

## Búsqueda y filtros actuales

- **Horizonte de seguimiento de 300 días (~10 meses)**, limitado al inicio de la rutina familiar si todavía no ha empezado. Todas las semanas quedan en el radar, pero no se consultan todas a diario.
- **Seguimiento diario** de las primeras 8 semanas familiares (incluso antes de febrero de 2027) y de los fines de semana a <=8 semanas vista; **tres comprobaciones semanales** entre 9 y 20 semanas y **dos semanales** de 21 semanas hasta el final del horizonte.
- El reparto por días de la semana es determinista y escalonado por fin de semana. Los precios que no se han comprobado hoy se etiquetan como históricos con fecha, nunca como ofertas actuales.
- Viajes semanales anclados en el sábado: normalmente ida jueves/viernes y vuelta domingo/lunes.
- Ida en jueves laborable desde las 17:00; viernes laborable antes de las 08:00 o desde las 15:30. Resto de días laborables, después de las 17:00.
- Vuelta el domingo desde las 16:00. El lunes laborable se permite aterrizar en NL antes de las 09:00 o salir de BCN desde las 17:00.
- **Festivos NCIA**: salida y regreso a cualquier hora del día festivo; si el viernes y días anteriores son consecutivamente festivos, añadir el laborable inmediatamente anterior desde las 17:00. Si el lunes y días siguientes son festivos, añadir el primer laborable siguiente con llegada antes de las 09:00 o salida desde las 17:00. Se siguen buscando opciones de viaje más corto. Viernes–domingo se admite si el viernes es festivo (se excluye en fines de semana ordinarios).
- La generación de fechas, filtrado de vuelos, muestreo lejano e informe familiar comparten estas reglas. No se puntúan transporte al aeropuerto ni conexiones terrestres; AMS y RTM no reciben prioridades distintas.
- Vueling y Transavia; KLM también en búsquedas habituales y lejanas en rutas con AMS.
- Cada ruta y fecha se consulta una sola vez por ejecución. El aprendizaje lejano reutiliza los resultados operativos; no abre una segunda sesión de Google Flights para repetir consultas. Las estancias con festivos lejanos solo se consultan cuando toca comprobar una semana afectada.
- Un fallo de consulta o una página sin bloques reconocibles significa disponibilidad sin verificar. Una página con vuelos reconocidos, todos descartados, significa sin opciones que cumplan los filtros.

El informe comienza con los ocho fines de semana de seguimiento diario, agrupados por mes y fin de semana. Cada alternativa muestra ida y vuelta con aeropuerto, aerolínea, hora de salida/llegada y precio; indica las fechas de TT/permiso orientativas. Los lunes con llegada antes de las 09:00 no consumen TT en el modelo; el viernes de salida antes de las 08:00 puede requerir TT o permiso parcial. La comparación de estancias de dos fines de semana muestra claramente TT separado, TT unido y diferencia neta. El radar lejano presenta cada fin de semana bajo su mes, con último precio observado y fecha de consulta (o primera comprobación pendiente, sin inferir que no hay vuelos). Las oportunidades lejanas se agrupan por meses y por fin de semana, evitando duplicados. El presupuesto mensual está al final y muestra fines de semana con precio observado sobre todos los fines de semana del mes incluidos en el horizonte; un subtotal parcial no se presenta como presupuesto mensual completo. El histórico de precios de los fines de semana individuales excluye estancias que unen dos fines de semana. Las tablas detalladas se limitan a fechas cercanas para evitar correos excesivamente largos.

Las valoraciones describen la distancia al mínimo observado; no predicen precios ni recomiendan comprar. Se necesitan al menos cinco fechas con precio completo para valorar el histórico. Las ejecuciones repetidas sustituyen la observación del mismo día. El histórico comparable empieza el 20 de octubre de 2026, al incorporar ventanas desplazadas por festivos: las observaciones anteriores se conservan, pero no se usan para calcular mínimos o bajadas con estos filtros.

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

También publica el artefacto `flight-report`: `report.html` contiene el correo exacto y `report.json` las observaciones y estados de las consultas (esquema versión 1), para revisarlos desde el chat. Las tablas separan escapadas y estancias con festivos sin duplicar viajes, mantienen dos opciones por trayecto y se adaptan a pantallas pequeñas. Un resultado con escalas o de otra aerolínea es una consulta válida que no cumple los filtros, no un fallo de disponibilidad. Las consultas realmente no verificadas se detallan al final. Los registros de Python se publican sin buffering para seguir el progreso.

Las consultas fallidas se reintentan en dos pasadas al final del lote (máximo tres intentos por ruta/fecha, con pausas de 2 y 5 segundos entre pasadas). Los resultados válidos que no cumplen los filtros no se reintentan. Los precios lejanos se guardan a partir de la misma búsqueda; no hay segunda consulta paralela para completar resultados fallidos. Solo se muestran como sin verificar los fallos que persistan tras la recuperación. Los reintentos pueden alargar la ejecución y no garantizan que Google Flights responda.

## Límites

La extracción depende del formato de Google Flights. Los precios y equipaje deben confirmarse en la consulta enlazada. No existe aún detección automática de reservas compradas, cálculo de traslados/equipaje, prioridad personalizada de horarios ni supresión del correo diario por ausencia de cambios. `config/routes.yaml` pertenece a la versión anterior; los filtros activos están en `src/scrapers/google_flights_ui.py` y los horizontes en `src/main.py` y `src/learning.py`.

## Puentes NCIA

`src/holidays.py` recoge las fechas oficiales NCIA de La Haya de 2026 y 2027 facilitadas por el usuario. Incluye los días sustitutorios y el cierre navideño; no añade festivos nacionales que NCIA no haya publicado. La búsqueda añade puentes dentro de los 300 días vigilados y muestrea hasta seis opciones por bloque (de cero a cinco días laborables afectados), priorizando la duración. No es una búsqueda exhaustiva de todas las fechas posibles.

El informe destaca noches en España, festivos y días laborables afectados. Esta última cifra cuenta conservadoramente las fechas laborables posteriores a la ida y hasta la vuelta; presupone trabajar antes de la salida de tarde y no da por autorizado el teletrabajo o las vacaciones. Un regreso temprano puede requerir menos permiso del indicado. Los festivos NCIA habilitan todas las horas en su fecha, y las ventanas laborales se desplazan automáticamente a los días adyacentes; se conservan opciones cortas y puentes. Se conservan las estancias largas que incluyan festivos. El calendario posterior a 2027 está pendiente de publicación.

## Presupuesto anual

Se consideran 46 días de teletrabajo desde España y 30 días de vacaciones por año. El reparto orientativo prioriza teletrabajo y separa años naturales; no afirma que el saldo esté disponible. El consumo real y las reservas aún no están registrados. `estimate_allocation` acepta saldos restantes por año para calcular necesidades sin cubrir. Las alternativas de viaje se muestran individualmente y no constituyen un plan anual acumulado ni descuentan días automáticamente.

El usuario confirma los cupos completos para 2027: 46 días de teletrabajo y 30 de vacaciones. Los días adicionales arrastrados desde 2026 están pendientes de cuantificar y no se incluyen. El saldo de 2026 continúa sin verificar.

## Weekly family travel: preparation phase

The objective is to cover each necessary weekend with family in Spain, not select occasional cheap trips. The report records a daily decision for each date alternative and presents a chronological weekend coverage view. It retains the
existing NCIA holidays, 46 TT / 30 leave allowance for 2027, unknown 2026 balance,
and all existing flight filters. No booking is automatic.

Initial **risk rules**, not learned optimum booking windows:

- Review within three days, never after the decision deadline.
- Close the decision 21 days before ordinary weekly travel, 42 before trips containing an
  NCIA holiday. At that point choose an acceptable fare or change the trip; this
  does not imply that any current fare is good.
- Consider buying early only after seven distinct prior days with complete
  comparable coverage, when the current basket costs at least €20 and 8% less
  than its historical median. These thresholds are policy choices.
- Incomplete/failed searches require verification and cannot generate a buy
  signal. Historical savings compare the cheapest eligible **basket**, whose
  flights can change. No probability of future savings is claimed.

`BookingPolicy` in `src/decisions.py` makes these provisional settings explicit.
The full report still presents vacation/TT usage separately so a low fare does
not hide workday costs. Transport and baggage costs are not yet available and
are **not** included in the fare or replaced with invented estimates.

### Evidence collected from activation onward

Additive SQLite tables retain all returned eligible flight observations (both
operational and long-range), query outcomes and decisions with filter/policy
versions. Repeated legs across trip combinations count once per day. Same-day
reruns replace queried scopes. This is a daily snapshot, not an intraday series.
The existing cheapest-price tables remain intact. Remote fare observations are persisted into the existing learning and detailed-flight tables, without a separate scraper run.

Flight identity currently uses airline, route, departure date and normalized
scheduled departure/arrival times: the scraper returns `N/A` for flight numbers.
Schedule changes split these proxy identities. A missing flight in a failed
search is not evidence of being sold out. Legacy data cannot reconstruct all
individual flights; comparable basket history starts 12 October 2026 but the
new coverage-verified decision series starts only on activation.

### Validation before learned recommendations

Run `python -m src.evaluate_decisions data/prices.db` for read-only walk-forward
policy evaluation. Decisions receive only strictly earlier complete observations.
Only trajectories with at least seven days and an observation within seven days
before departure are included. Output reports chosen date, observed later regret
and difference from the last observed fare; it is not an optimum or success rate.
No evaluation is claimed until production data is available and trips mature. Twice/thrice-weekly samples may miss transient promotions and are not full daily coverage.

Next modelling stages require: continuous cohorts from first search through
purchase cutoff; explicit fare/baggage comparability; enough **distinct departed
flights**, segmented by season, direction, carrier and weekday; then rolling
held-out evaluation against fixed 21/42-day and buy-first-seen baselines. Report
coverage and sample size, avoid treating overlapping alternatives as independent,
and enable finer airline/flight predictions only when evidence improves on the
simple baseline. Do not substitute US-wide purchase-window averages for NL–BCN.

This branch prepares the feature. Merging enables recording and the new report
on the existing scheduled run; no additional run or email is needed for testing.


### Weekly coverage and longer stays

The 300-day horizon begins at the later of today and the confirmed
family start date. The first eight family weekends are checked daily already
during the preparation phase; thereafter daily monitoring applies within
eight weeks, 3x weekly within 20 weeks and 2x weekly out to 300 days.
Each Saturday groups Thursday–Sunday, Thursday–Monday and Friday–Monday choices;
missing or expensive weeks remain visible instead of being replaced by cheaper
weeks. All weekends inside the horizon are listed in a dated historical-price radar. Unsampled weekends explicitly say that their initial check is pending.

`config/family_plan.json` records an optional `required_from`/`required_until`
period and a `weekends` mapping of Saturday ISO date to `pending`, `booked`,
`covered`, `skipped`, or `unknown`. The family routine starts on **1 February 2027**, confirmed by the user; the first
weekend to cover is **6–7 February**. Purchased flights and deliberate exceptions
have not been confirmed. Unknown is never
silently treated as unbooked. Outside-period, purchased, already covered and
skipped weeks receive no new purchase instruction. This is explicit state input,
not automatic Gmail booking reconciliation; no reservation identifiers needed.

For adjacent weekends, query the combined outward/return date alternatives too.
These use existing leg dates and the scraper's per-leg query reuse, with normal
time/airline filters. Compare a continuous stay against the cheapest separate
trip for each weekend. Show fare saving, two avoided legs, additional workdays
and annual TT/leave allocation. Suggestions require approval of presence and
remote-work/leave arrangements. They do not consume balances or presume existing
tickets can be refunded. Overlapping suggestions are alternatives, not additive.

Monthly totals group Saturdays sampled **on that run** and sum the cheapest separate trips for pending
or unverified weeks only, with priced/total counts; the long-range radar is a separate dated record. They are neither spending
records nor full trip cost: purchased trips, extras and ground transfers are
excluded. Weekly detail retains airline/airport/timetable choices. Labour-day
estimates assume work before departure and conservatively count working return
days; early Friday flights may require another day.

The 21/42-day rules remain explicitly provisional **stop-waiting limits**, not a
recommendation to wait until those dates. Validate and replace them using weekly
coverage outcomes; airline/flight-specific learned timing remains future work.
