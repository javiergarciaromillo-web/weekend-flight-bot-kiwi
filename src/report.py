from __future__ import annotations

from datetime import date, datetime
from html import escape

from src.family import build_coverage, join_opportunities, render_coverage
from src.store import get_weekend_history, get_latest_learning_opportunities
from src.holidays import holiday_dates, workdays_affected
from src.budget import REMOTE_WORK_DAYS, ANNUAL_LEAVE_DAYS, estimate_allocation
from src.planner import allowed_pair, FILTER_HISTORY_START


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


def _horizon_radar(tracking, daily_saturdays=()):
    """Historical long-range observations; never imply a stale quote is live."""
    daily = set(daily_saturdays)
    future = [t for t in tracking if t['weekend'] not in daily]
    if not future:
        return ''
    html = ('<h2 style="font-size:18px">Radar de precios a largo plazo</h2>'
            '<p>Seguimiento hasta unos 10 meses. Fechas lejanas: comprobación '
            'periódica, no diaria. Cada precio indica cuándo se observó; '
            'no equivale a una tarifa disponible hoy.</p>')
    current_month = None
    for item in future:
        saturday = item['weekend']
        month = saturday.strftime('%Y-%m')
        if month != current_month:
            html += f'<h3 style="font-size:14px;margin:14px 0 4px">{month}</h3>'
            current_month = month
        date_label = saturday.strftime('%d/%m')
        if not item['checked_at']:
            status = 'Primera comprobación pendiente'
        elif item['best_price'] is None:
            status = f'Sin precio completo verificado (consulta {escape(str(item["checked_at"]))})'
        else:
            status = (f'{_price(item["best_price"])}'
                      f' · visto el {escape(str(item["checked_at"]))}'
                      f' · {escape(str(item["outbound"]))} → {escape(str(item["inbound"]))}')
        html += (f'<p style="margin:4px 0;font-size:12px">'
                 f'<b>Finde {date_label}:</b> {status}</p>')
    return html


def build_html_report(run_date, rows, pairs=None, diagnostics=None, decisions=None,
                      family_plan=None, horizon_tracking=None, daily_saturdays=()):
    diagnostics = diagnostics or {}
    decisions = decisions or {}
    pairs = sorted(pair for pair in set(pairs or [(r['outbound'], r['inbound']) for r in rows])
                   if allowed_pair(*pair))
    trips = []
    for outbound, inbound in pairs:
        selected = [r for r in rows if (r['outbound'], r['inbound']) == (outbound, inbound)]
        out = [r for r in selected if r['leg_type'] == 'outbound']
        inc = [r for r in selected if r['leg_type'] == 'inbound']
        total = min(r['price'] for r in out) + min(r['price'] for r in inc) if out and inc else None
        # One observation per run date; exclude future records and incomplete totals.
        history = {h['run_date']: h for h in get_weekend_history(outbound, inbound)
                   if str(FILTER_HISTORY_START) <= h['run_date'] <= str(run_date)
                   and h['best_combo'] is not None}
        valid = sorted(history.values(), key=lambda h: h['run_date'])
        previous = [h for h in valid if h['run_date'] < str(run_date)]
        minimum = min((h['best_combo'] for h in valid), default=None)
        delta = total - previous[-1]['best_combo'] if total is not None and previous else None
        trips.append(dict(outbound=outbound, inbound=inbound, out=out, inc=inc,
                          total=total, delta=delta, minimum=minimum, count=len(valid)))

    def compact_date(value):
        return f"{WEEKDAYS[value.weekday()]} {value.day} {MONTHS[value.month-1]}"

    def date_range(t):
        start = compact_date(t['outbound'])
        if t['outbound'].year != t['inbound'].year:
            start += f" {t['outbound'].year}"
        return f"{start} → {compact_date(t['inbound'])} {t['inbound'].year}"

    def flight_line(row):
        url = escape(row.get('source_url') or '#', quote=True)
        return (f"{escape(row['origin'])}→{escape(row['destination'])} "
                f"{_time(row.get('outbound_departure'))}–{_time(row.get('outbound_arrival'))} "
                f'<span style="color:#64748b">{escape(row.get("airline") or "—")}</span> '
                f'<a href="{url}" style="color:#2563eb">{_price(row.get("price"))}</a>')

    def leg_lines(trip, outbound):
        choices = sorted(trip['out' if outbound else 'inc'], key=lambda r: r['price'])[:2]
        if not choices:
            return _leg([], diagnostics, trip['outbound' if outbound else 'inbound'], outbound)
        # Keep the alternative, with less emphasis than the cheapest leg.
        return flight_line(choices[0]) + (
            '<br><span style="color:#64748b;font-size:11px">Alternativa: '
            + flight_line(choices[1]) + '</span>' if len(choices) > 1 else '')

    def table(items):
        result = ('<table role="table" width="100%" cellpadding="0" cellspacing="0" '
                  'style="border-collapse:collapse;font-size:12px;line-height:1.5">'
                  '<tr class="table-head" style="background:#eef2f6;text-align:left">'
                  '<th style="padding:10px">Fechas y estancia</th>'
                  '<th style="padding:10px">Vuelos · precio por trayecto</th>'
                  '<th style="padding:10px;text-align:right">Total</th></tr>')
        month = None
        for t in items:
            current = (t['outbound'].year, t['outbound'].month)
            if current != month:
                result += (f'<tr><td colspan="3" style="padding:12px 10px 6px;color:#475569;'
                           f'font-weight:bold">{MONTHS[current[1]-1].upper()} {current[0]}</td></tr>')
                month = current
            nights = (t['inbound']-t['outbound']).days
            affected = workdays_affected(t['outbound'], t['inbound'])
            holidays = holiday_dates(t['outbound'], t['inbound'])
            meta = f'{nights} noches · {affected} laborables'
            if holidays:
                meta += f'<br><span style="color:#9a6700">{len(holidays)} festivos NCIA</span>'
            if t['out'] and t['inc']:
                out = min(t['out'], key=lambda r: r['price'])
                inc = min(t['inc'], key=lambda r: r['price'])
                if out['origin'] != inc['destination']:
                    meta += '<br><span style="color:#9a6700">Aeropuertos distintos</span>'
            allocation = estimate_allocation(t['outbound'], t['inbound'])
            if allocation:
                meta += '<br>' + '; '.join(
                    f"{year}: {a['remote']} TT / {a['leave']} vac."
                    for year, a in allocation.items())
            decision = decisions.get((t['outbound'], t['inbound']))
            if any(w['state'] in ('booked', 'covered', 'skipped', 'outside') and t['outbound'] <= w['weekend'] < t['inbound'] for w in coverage):
                decision = None
            if decision:
                meta += (f'<br><b>{escape(decision["action"])}</b>'
                         f'<br>Revisar: {escape(decision["review_on"])}'
                         f'<br>Límite: {escape(decision["deadline"])}'
                         f'<br>{escape(decision["reason"])}')
            total = _price(t['total'])
            if t['total'] is None:
                total += '<br><small>Incompleto</small>'
            if t['delta'] is not None:
                color = '#15803d' if t['delta'] < 0 else '#64748b'
                total += f'<br><span style="color:{color};font-size:11px">{t["delta"]:+.0f} €</span>'
            if t['count'] >= 5:
                total += (f'<br><span style="font-size:10px;color:#64748b">'
                          f'Mín. {_price(t["minimum"])} · {t["count"]} observaciones</span>')
            result += (
                '<tr class="trip-row" style="border-bottom:1px solid #e2e8f0;vertical-align:top">'
                f'<td class="trip-date" style="padding:10px;min-width:95px"><b>{compact_date(t["outbound"])}<br>'
                f'→ {compact_date(t["inbound"])}'
                + (f' {t["inbound"].year}' if t['inbound'].year != t['outbound'].year else '')
                + '</b><br>'
                f'<span style="font-size:11px;color:#64748b">{meta}</span></td>'
                f'<td class="trip-flights" style="padding:10px"><b>Ida</b> · {leg_lines(t, True)}<br>'
                f'<b>Vuelta</b> · {leg_lines(t, False)}</td>'
                f'<td class="trip-total" style="padding:10px;text-align:right;white-space:nowrap"><b>{total}</b></td></tr>')
        return result + '</table>'

    complete = sorted([t for t in trips if t['total'] is not None], key=lambda t: t['total'])
    failed = [(key, status) for key, status in diagnostics.items() if status == 'failed']
    html = ('<html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<style>@media screen and (max-width:540px){'
            '.table-head{display:none}.trip-row{display:block;position:relative}'
            '.trip-date,.trip-flights{display:block!important;text-align:left}'
            '.trip-date{padding-right:90px!important}.trip-flights{padding-top:0!important}'
            '.trip-total{position:absolute;top:0;right:0}.trip-row td{box-sizing:border-box}'
            '}</style></head>'
            f'<body style="margin:0;padding:12px;background:#f3f5f8;color:#172033;'
            f'font-family:Arial,sans-serif;line-height:1.5">'
            '<div style="max-width:760px;margin:auto;background:white;padding:18px">'
            '<h1 style="font-size:23px;margin:0">Tus vuelos a Barcelona</h1>'
            f'<p style="color:#64748b;margin:4px 0 18px">{_fmt_day(run_date)} · '
            f'{len(complete)}/{len(trips)} viajes con precio completo</p>'
            '')
    coverage = build_coverage(trips, decisions, family_plan)
    html += render_coverage(coverage, join_opportunities(coverage, trips))
    if horizon_tracking:
        html += _horizon_radar(horizon_tracking, daily_saturdays)
    if decisions:
        html += ('<p style="padding:10px;background:#fff7ed"><b>Cuándo comprar</b><br>'
                 'Reglas iniciales de prudencia, todavía sin una ventana óptima aprendida: '
                 '21/42 días (normal/festivos) son topes provisionales para dejar de esperar, no fechas óptimas de compra. '
                 'Revisar como máximo cada 3 días. Cada fin de semana necesario debe quedar cubierto; si está caro, comparar horarios y aeropuertos dentro de esa semana. '
                 'El histórico compara la combinación más barata aceptable, que puede cambiar de vuelo. '
                 'Tarifas sin coste de traslados ni equipaje adicional.</p>')
    if not complete:
        html += '<p>Sin combinaciones completas verificadas.</p>'
    drops = sorted([t for t in complete if t['delta'] is not None and t['delta'] <= -20], key=lambda t: t['delta'])
    if drops:
        html += '<p style="color:#15803d"><b>Bajadas de al menos 20 €:</b> ' + '; '.join(
            f'{compact_date(t["outbound"])} → {compact_date(t["inbound"])}: {t["delta"]:+.0f} €'
            for t in drops[:3]) + '</p>'
    if failed:
        html += (f'<p style="padding:10px;background:#fff7ed;color:#9a3412">'
                 f'<b>{len(failed)} consultas pendientes de verificar: cobertura parcial.</b> '
                 'Los precios completos pueden existir por otro aeropuerto; no garantizan la opción más barata.</p>')

    bridges = [t for t in trips if holiday_dates(t['outbound'], t['inbound'])]
    ordinary = [t for t in trips if (t['inbound']-t['outbound']).days <= 4 and not holiday_dates(t['outbound'], t['inbound'])]
    if ordinary:
        html += '<h2 style="font-size:18px;margin-top:24px">Opciones para cubrir tus fines de semana</h2>' + table(ordinary)
    if bridges:
        ranked = sorted([t for t in bridges if t['total'] is not None], key=lambda t: (
            workdays_affected(t['outbound'], t['inbound']), -(t['inbound']-t['outbound']).days, t['total']))
        html += '<h2 style="font-size:18px;margin-top:24px">Estancias con festivos NCIA</h2>'
        if ranked:
            t = ranked[0]
            html += (f'<p><b>Destacada por aprovechar días libres:</b> '
                     f'{date_range(t)}, {(t["inbound"]-t["outbound"]).days} noches, '
                     f'{workdays_affected(t["outbound"], t["inbound"])} laborables, {_price(t["total"])}.</p>')
        html += table(bridges)

    opportunities = [o for o in get_latest_learning_opportunities(limit=100)
                     if o['run_date'] == str(run_date) and o['outbound'] >= str(run_date)
                     and allowed_pair(date.fromisoformat(o['outbound']), date.fromisoformat(o['inbound']))][:3]
    if opportunities:
        html += '<h2 style="font-size:18px;margin-top:24px">Precios a más largo plazo</h2>'
        for item in opportunities:
            html += (f'<p><b>{_fmt_day(item["outbound"])} → {_fmt_day(item["inbound"])} · '
                     f'{_price(item["best_combo"])}</b><br>')
            for leg in ['outbound', 'inbound']:
                row = dict(origin=item.get(f'{leg}_origin') or '—', destination=item.get(f'{leg}_destination') or '—',
                           airline=item.get(f'{leg}_airline'), outbound_departure=item.get(f'{leg}_departure_time'),
                           outbound_arrival=item.get(f'{leg}_arrival_time'), price=item.get(f'best_{leg}'),
                           source_url=item.get(f'{leg}_source_url'))
                html += flight_line(row) + '<br>'
            html += '</p>'

    if failed:
        html += '<h2 style="font-size:16px;margin-top:24px">Consultas sin verificar</h2><p style="font-size:12px">'
        html += '<br>'.join(f'{escape(o)}→{escape(d)} · {_fmt_day(day)}' for (o, d, day), _ in sorted(failed)) + '</p>'
    used_holidays = sorted({d for t in bridges for d in holiday_dates(t['outbound'], t['inbound'])})
    html += ('<div style="border-top:1px solid #e2e8f0;margin-top:24px;padding-top:12px;'
             'font-size:11px;color:#64748b"><b>Cómo leer el informe</b><br>'
             'Total = los dos trayectos más baratos mostrados; puede combinar AMS y RTM. '
             'Los enlaces en cada precio abren la búsqueda: confirmar tarifa y equipaje. '
             'Cambio de precio = comparación con la última observación anterior. '
             'El mínimo solo se muestra a partir de 5 días con precio completo.<br>'
             'Vuelos directos de Vueling y Transavia; KLM también en las opciones habituales vía AMS. '
             'Vigilancia 300 días: primeras 8 semanas familiares y próximas 8 semanas, diaria; '
             'de 9 a 20 semanas, tres veces por semana; fechas más lejanas, dos veces por semana. '
             'Los precios del radar incluyen fecha y pueden no seguir disponibles.<br>'
             'Viajes habituales jueves/viernes a domingo/lunes, con extensiones por festivos NCIA. '
             'Ida del jueves laborable desde las 17:00; viernes laborable antes de las 08:00 '
             'o después de las 15:30. '
             'Vuelta domingo desde las 16:00; lunes laborable con llegada a NL antes de las 09:00 '
             'o salida desde las 17:00. Los festivos NCIA permiten todos los horarios '
             'y desplazan la ventana al laborable adyacente.<br>'
             'Histórico comparable desde el 20 de octubre de 2026, con estos filtros.<br>'
             f'<b>Cupos 2027:</b> {REMOTE_WORK_DAYS} días de teletrabajo (TT) desde España y '
             f'{ANNUAL_LEAVE_DAYS} de vacaciones; arrastre pendiente de cuantificar. '
             'Los repartos por viaje son alternativas, no consumen saldo. '
             'El saldo disponible de 2026 no está verificado. '
             'Laborables: desde el día siguiente a la ida hasta la vuelta, inclusive; se supone trabajo antes de la ida.<br>')
    if used_holidays:
        html += '<b>Festivos NCIA utilizados:</b> ' + '; '.join(_fmt_day(d) for d in used_holidays) + '.<br>'
    return html + '</div></div></body></html>'
