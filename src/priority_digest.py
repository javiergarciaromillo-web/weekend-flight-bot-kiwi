"""Decision-first email digest for weekly family flights.

Quote age and forecast uncertainty are explicit. The digest does not infer
bookings, claim optimal purchase dates, or use a nationwide holiday calendar.
"""
from collections import defaultdict
from datetime import date, timedelta
from html import escape

from src.holidays import HOLIDAYS
from src.family import weekend_of
from src.budget import trip_work_dates, assess_remote_plan

NON_TRAVEL = {'booked', 'covered', 'skipped', 'vacation', 'visiting_nl', 'holiday_break', 'outside'}
WEEKDAY = ('lun.', 'mar.', 'mié.', 'jue.', 'vie.', 'sáb.', 'dom.')


def _day(d):
    return f'{WEEKDAY[d.weekday()]} {d.day:02d}/{d.month:02d}'


def holiday_weekend(day):
    """Associate Friday/Thursday with following Saturday and Mon-Wed with prior one."""
    if day.weekday() in (3, 4):
        return day + timedelta(days=5 - day.weekday())
    return day - timedelta(days=(day.weekday() - 5) % 7)


def _family_holiday_weekends(run_date, tracked, plan):
    """Show NCIA holiday weeks even if their live search is scheduled later."""
    tracking = {r['weekend']: r for r in tracked or []}
    start = date.fromisoformat(plan.get('required_from', '2027-01-01'))
    end = date.fromisoformat(plan['required_until']) if plan.get('required_until') else date(2027, 12, 31)
    groups = defaultdict(list)
    for day in sorted(HOLIDAYS):
        if day.year != 2027 or day < run_date or day < start - timedelta(days=4) or day > end + timedelta(days=4):
            continue
        # Christmas closure is handled as a block; it is not a normal weekly ticket.
        if day.month == 12 and day.day >= 23:
            continue
        sat = holiday_weekend(day)
        if sat < start - timedelta(days=4) or sat > end:
            continue
        if plan.get('weekends', {}).get(str(sat)) in NON_TRAVEL:
            continue
        groups[sat].append(day)
    return [(sat, days, tracking.get(sat)) for sat, days in sorted(groups.items())]


def _link_to_trip(trip):
    """Links to original observed fare search, not a fabricated booking URL."""
    if not trip:
        return ''
    best = [min(trip[leg], key=lambda r: r['price']) for leg in ('out', 'inc') if trip.get(leg)]
    links = [r.get('source_url') for r in best if r.get('source_url')]
    if not links:
        return ''
    return f' · <a href="{escape(links[0], quote=True)}">Ver vuelo de ida</a>'


def render_priority_digest(run_date, coverage, trips, decisions,
                           tracking=None, family_plan=None):
    """Three decision groups, followed by a strategic NCIA holiday watch."""
    plan = family_plan or {}
    active = [w for w in coverage if w['state'] not in NON_TRAVEL]
    active_sats = {w['weekend'] for w in active}
    signals = []
    for w in active:
        best = w.get('best')
        d = w.get('decision') or {}
        if not best:
            continue
        if d.get('action') in ('CONSIDERAR COMPRA', 'CERRAR DECISIÓN'):
            signals.append((0 if d['action'] == 'CERRAR DECISIÓN' else 1,
                            w['weekend'], w, d))
    signals.sort(key=lambda x: (x[0], x[1]))

    drop_by_week = {}
    for trip in trips:
        if (trip['total'] is None or trip['delta'] is None
                or trip.get('count', 0) < 2):
            continue
        sat = weekend_of(trip['outbound'])
        if sat not in active_sats or trip['delta'] >= 0:
            continue
        previous = trip['total'] - trip['delta']
        if previous <= 0:
            continue
        fraction = -trip['delta'] / previous
        if -trip['delta'] < 20 or fraction < .15:
            continue
        candidate = (fraction, -trip['delta'], trip)
        if sat not in drop_by_week or candidate[:2] > drop_by_week[sat][:2]:
            drop_by_week[sat] = candidate
    drops = sorted(drop_by_week.values(), key=lambda x: (-x[1], -x[0]))[:3]

    deadline_items = []
    for w in active:
        d = w.get('decision') or {}
        if not w.get('best') or not d.get('deadline'):
            continue
        deadline = date.fromisoformat(d['deadline'])
        if run_date <= deadline <= run_date + timedelta(days=42):
            deadline_items.append((deadline, w))
    deadline_items.sort(key=lambda x: x[0])

    html = ('<section style="border:1px solid #ccd5df;border-radius:8px;'
            'padding:14px;margin:4px 0 18px;background:#f8fafc">'
            '<h2 style="font-size:18px;margin:0 0 5px">Lo importante hoy</h2>'
            '<p style="font-size:11px;color:#475569;margin:0 0 12px">'
            'Oportunidades por fin de semana, no una clasificación global que sustituya '
            'otros viajes. Las reservas siguen sin confirmar hasta que las registres.</p>')

    html += '<h3 style="font-size:14px;margin:12px 0 5px">Decisiones de compra</h3>'
    if not signals:
        html += '<p style="font-size:12px;margin:2px 0">Sin señales de compra justificadas por ahora.</p>'
    for _, sat, w, d in signals[:3]:
        best = w['best']
        tt = trip_work_dates(best)[0]
        label = 'LÍMITE PRUDENTE' if d['action'] == 'CERRAR DECISIÓN' else 'PRECIO FAVORABLE'
        html += (f'<p style="font-size:12px;margin:7px 0"><b>{label} · fin de semana {_day(sat)}</b>'
                 f'<br>{_day(best["outbound"])} → {_day(best["inbound"])} · '
                 f'<b>{best["total"]:.0f} €</b> · {len(tt)} TT estimados. '
                 f'{escape(d.get("reason", ""))}</p>')
        if w['state'] == 'unknown':
            html += '<p style="font-size:11px;color:#92400e">Confirmar antes si el viaje es necesario o ya está reservado.</p>'

    html += '<h3 style="font-size:14px;margin:14px 0 5px">Mayores bajadas verificables</h3>'
    if not drops:
        html += '<p style="font-size:12px;margin:2px 0">Sin bajadas de al menos 20 € y 15 % frente a la última observación comparable.</p>'
    for fraction, amount, trip in drops:
        html += (f'<p style="font-size:12px;margin:7px 0"><b>↓ {amount:.0f} € '
                 f'({fraction:.0%}) · fin de semana {_day(weekend_of(trip["outbound"]))}</b>'
                 f'<br>{_day(trip["outbound"])} → {_day(trip["inbound"])} · '
                 f'<b>{trip["total"]:.0f} €</b>'
                 f'{_link_to_trip(trip)}</p>')
    html += ('<p style="font-size:10px;color:#64748b;margin:3px 0">'
             'Bajadas sobre la misma pareja de fechas; el vuelo concreto más barato '
             'puede haber cambiado. No son mínimos históricos garantizados.</p>')

    html += '<h3 style="font-size:14px;margin:14px 0 5px">Decisiones próximas</h3>'
    if not deadline_items:
        html += '<p style="font-size:12px;margin:2px 0">Sin límites prudentes de compra en los próximos 42 días.</p>'
    for deadline, w in deadline_items[:3]:
        html += (f'<p style="font-size:12px;margin:5px 0">'
                 f'<b>{_day(w["weekend"])}</b> · límite provisional '
                 f'{_day(deadline)} · {_price(w["best"]["total"])}'
                 f' · {escape(w["decision"].get("action", "REVISAR"))}</p>')

    html += '</section>'
    html += ('<section style="margin:18px 0;padding:0">'
             '<h2 style="font-size:18px;margin:0 0 6px">Festivos NCIA: planificar antes</h2>'
             '<p style="font-size:11px;color:#475569;margin:2px 0 9px">'
             'Calendario oficial suministrado para 2027: 16 festivos. '
             'Los precios antiguos del radar no son cotizaciones de hoy. '
             'Confirmar necesidad del viaje antes de reservar.</p>')

    for sat, days, quote in _family_holiday_weekends(run_date, tracking, plan)[:8]:
        names = ', '.join(_day(d) for d in days)
        price = 'Sin precio completo observado'
        if quote and quote['best_price'] is not None:
            observed_at = str(quote.get('checked_at') or 'fecha sin confirmar')
            price = f'{_price(quote["best_price"])} · observado {escape(observed_at)}'
            if observed_at == str(run_date):
                price = f'{_price(quote["best_price"])} · comprobado hoy'
        html += (f'<div style="border-bottom:1px solid #e2e8f0;padding:7px 0;font-size:12px">'
                 f'<b>Fin de semana {_day(sat)}</b> · festivos {names}<br>'
                 f'{price} · <b>PRIORIDAD DE PLANIFICACIÓN</b></div>')

    if run_date <= date(2027, 12, 23):
        html += ('<p style="font-size:12px;margin:10px 0"><b>Cierre navideño:</b> '
                 '23–31 diciembre de 2027 · periodo especial, '
                 'no debe tratarse como viaje semanal ordinario.</p>')
    html += ('<p style="font-size:10px;color:#64748b">'
             'Los festivos no consumen teletrabajo ni vacaciones; '
             'los días laborables intermedios sí requieren planificación. '
             'No se recomienda comprar solo por ser festivo.</p></section>')
    return html


def _price(amount):
    return '—' if amount is None else f'{amount:.0f} €'
