from __future__ import annotations

from datetime import date, datetime
from html import escape

from src.store import get_weekend_history, get_latest_learning_opportunities
from src.holidays import holiday_dates, workdays_affected
from src.budget import REMOTE_WORK_DAYS, ANNUAL_LEAVE_DAYS, estimate_allocation


WEEKDAYS = ['lun.', 'mar.', 'mié.', 'jue.', 'vie.', 'sáb.', 'dom.']
MONTHS = ['ene.', 'feb.', 'mar.', 'abr.', 'may.', 'jun.', 'jul.', 'ago.', 'sep.', 'oct.', 'nov.', 'dic.']


def _fmt_day(value):
    d = date.fromisoformat(value) if isinstance(value, str) else value
    return f'{WEEKDAYS[d.weekday()]} {d.day} {MONTHS[d.month-1]} {d.year}'


def _price(value):
    return '—' if value is None else f'{value:.0f} €'


def _time(value):
    value = value or '—'
    suffix = ' +1' if '+1' in value else ''
    clean = value.replace('+1', '').strip()
    for fmt in ('%I:%M %p', '%H:%M'):
        try:
            return datetime.strptime(clean.upper(), fmt).strftime('%H:%M') + suffix
        except ValueError:
            pass
    return escape(value)


def _trend_label(current, historical_min, observation_count=0):
    if current is None:
        return 'Precio incompleto'
    if observation_count < 5 or historical_min is None or historical_min <= 0:
        return 'Histórico insuficiente'
    ratio = current / historical_min
    if ratio <= 1.03:
        return 'Cerca del mínimo observado'
    if ratio <= 1.08:
        return 'Hasta un 8 % sobre el mínimo'
    return 'Por encima del mínimo observado'


def _flight(row):
    url = escape(row.get('source_url') or '#', quote=True)
    return (f"{escape(row['origin'])}→{escape(row['destination'])} · "
            f"{escape(row.get('airline') or '—')} · "
            f"{_time(row.get('outbound_departure'))}–{_time(row.get('outbound_arrival'))} · "
            f"{_price(row.get('price'))} "
            f'<a href="{url}">Consultar precio</a>')


def _leg(rows, diagnostics, leg_date, outbound):
    if rows:
        return '<br>'.join(_flight(r) for r in sorted(rows, key=lambda r: r['price'])[:2])
    keys = [(airport, 'BCN', leg_date) if outbound else ('BCN', airport, leg_date)
            for airport in ['AMS', 'RTM']]
    if any(diagnostics.get(key) == 'failed' for key in keys):
        return 'Consulta fallida: disponibilidad sin verificar'
    if all(diagnostics.get(key) == 'filtered_empty' for key in keys):
        return 'Sin opciones que cumplan los filtros'
    return 'Sin resultados verificados'


def build_html_report(run_date, rows, pairs=None, diagnostics=None):
    diagnostics = diagnostics or {}
    pairs = sorted(set(pairs or [(r['outbound'], r['inbound']) for r in rows]))
    trips = []
    for outbound, inbound in pairs:
        selected = [r for r in rows if (r['outbound'], r['inbound']) == (outbound, inbound)]
        out = [r for r in selected if r['leg_type'] == 'outbound']
        inc = [r for r in selected if r['leg_type'] == 'inbound']
        total = min(r['price'] for r in out) + min(r['price'] for r in inc) if out and inc else None
        # One observation per run date; exclude future records and incomplete totals.
        history = {h['run_date']: h for h in get_weekend_history(outbound, inbound)
                   if h['run_date'] <= str(run_date) and h['best_combo'] is not None}
        valid = sorted(history.values(), key=lambda h: h['run_date'])
        previous = [h for h in valid if h['run_date'] < str(run_date)]
        minimum = min((h['best_combo'] for h in valid), default=None)
        delta = total - previous[-1]['best_combo'] if total is not None and previous else None
        trips.append(dict(outbound=outbound, inbound=inbound, out=out, inc=inc,
                          total=total, delta=delta, minimum=minimum, count=len(valid)))

    def card(trip, detail=False):
        t = trip
        change = f" · cambio {t['delta']:+.0f} €" if t['delta'] is not None else ''
        body = (f"<b>{_fmt_day(t['outbound'])} → {_fmt_day(t['inbound'])}: {_price(t['total'])}</b>{change}"
                f"<p>Ida: {_leg(t['out'], diagnostics, t['outbound'], True)}<br>"
                f"Vuelta: {_leg(t['inc'], diagnostics, t['inbound'], False)}</p>")
        holidays = holiday_dates(t['outbound'], t['inbound'])
        if holidays:
            affected = workdays_affected(t['outbound'], t['inbound'])
            body += (f"<p>{(t['inbound']-t['outbound']).days} noches · "
                     f"{affected} días laborables afectados · festivos NCIA: "
                     + ', '.join(_fmt_day(d) for d in holidays) + '</p>')
        allocation = estimate_allocation(t['outbound'], t['inbound'])
        if allocation:
            body += '<p><small>Reparto orientativo por viaje: '
            body += '; '.join(f"{year}: {a['remote']} teletrabajo + {a['leave']} vacaciones"
                              for year, a in allocation.items())
            body += '</small></p>'
        if detail:
            body += (f"<small>{_trend_label(t['total'], t['minimum'], t['count'])} · "
                     f"mínimo {_price(t['minimum'])} · {t['count']} días con precio completo</small>")
        return f'<div style="padding:12px 0;border-bottom:1px solid #ddd">{body}</div>'

    html = (f'<html><body style="font-family:Arial,sans-serif;font-size:14px;line-height:1.5;'
            f'max-width:680px;margin:auto;padding:16px;color:#222">'
            f'<h2>Vuelos Países Bajos ↔ Barcelona</h2><p>{_fmt_day(run_date)} · {len(trips)} combinaciones</p>'
            '<p>Vuelos directos. Jueves y domingo desde las 16:00; viernes y lunes todo el día. '
            'Los festivos NCIA permiten ampliar fechas y horarios. Vueling y Transavia; KLM también en oportunidades lejanas vía AMS. '
            'Precios observados: confirmar tarifa y equipaje antes de reservar. '
            'El total suma dos billetes de ida y puede combinar AMS y RTM.</p>')
    html += (f'<p>Presupuesto anual: {REMOTE_WORK_DAYS} días de teletrabajo desde España y '
             f'{ANNUAL_LEAVE_DAYS} de vacaciones. Cupos completos confirmados para 2027; días arrastrados aún sin cuantificar. '
             'Los repartos son alternativas; no se suman automáticamente entre viajes.</p>')
    failed = sum(status == 'failed' for status in diagnostics.values())
    if failed:
        html += f'<p><b>{failed} consultas fallidas.</b> El informe tiene cobertura parcial.</p>'
    complete = sorted([t for t in trips if t['total'] is not None], key=lambda t: t['total'])
    html += '<h3>Tres opciones más económicas</h3>'
    html += ''.join(card(t, True) for t in complete[:3]) or '<p>Sin combinaciones completas verificadas.</p>'
    drops = sorted([t for t in complete if t['delta'] is not None and t['delta'] <= -20], key=lambda t: t['delta'])
    if drops:
        html += '<h3>Bajadas de al menos 20 €</h3>' + ''.join(card(t) for t in drops[:3])
    bridges = [t for t in complete if holiday_dates(t['outbound'], t['inbound'])]
    if bridges:
        bridges.sort(key=lambda t: (workdays_affected(t['outbound'], t['inbound']),
                                    -(t['inbound']-t['outbound']).days, t['total']))
        html += '<h3>Más tiempo en España con festivos NCIA</h3>'
        html += '<p>Días laborables afectados: estimación conservadora desde el día posterior a la ida hasta la vuelta. El reparto prioriza teletrabajo para conservar vacaciones y requiere saldo disponible.</p>'
        html += ''.join(card(t) for t in bridges[:6])
    html += '<h3>Próximas fechas</h3>' + ''.join(card(t, True) for t in trips)
    opportunities = [o for o in get_latest_learning_opportunities(limit=10)
                     if o['run_date'] == str(run_date) and o['outbound'] >= str(run_date)][:3]
    if opportunities:
        html += '<h3>Tres oportunidades a largo plazo</h3>'
        for item in opportunities:
            html += f"<p><b>{_fmt_day(item['outbound'])} → {_fmt_day(item['inbound'])}: {_price(item['best_combo'])}</b><br>"
            for leg in ['outbound', 'inbound']:
                row = dict(origin=item.get(f'{leg}_origin') or '—', destination=item.get(f'{leg}_destination') or '—',
                           airline=item.get(f'{leg}_airline'), outbound_departure=item.get(f'{leg}_departure_time'),
                           outbound_arrival=item.get(f'{leg}_arrival_time'), price=item.get(f'best_{leg}'),
                           source_url=item.get(f'{leg}_source_url'))
                html += _flight(row) + '<br>'
            html += '</p>'
    return html + '</body></html>'
