# weekend-flight-bot

Bot diario para monitorizar vuelos de fin de semana entre AMS/RTM y BCN.

## Qué hace esta versión
- Genera combinaciones de fechas para las próximas 5 semanas
- Filtra por:
  - jueves o viernes de ida
  - domingo o lunes de vuelta
  - salida a partir de las 16:00
  - Vueling / Transavia
- Guarda histórico en SQLite
- Envía un email HTML diario

## Setup local

### 1. Crear entorno virtual
```bash
python -m venv .venv
