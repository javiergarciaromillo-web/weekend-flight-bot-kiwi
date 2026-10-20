"""Weekly family coverage and conditional two-weekend stays.

No booking/exception is inferred from a price search. Date keys are Saturdays.
"""
import json
from datetime import date, timedelta
from html import escape
from pathlib import Path

from src.holidays import workdays_affected, outbound_dates_for_weekend, inbound_dates_for_weekend
from src.budget import estimate_allocation


STATES = {'pending', 'booked', 'skipped', 'covered', 'unknown'}
LABELS = {'pending': 'Pendiente de comprar', 'booked': 'Comprado',
          'skipped': 'Excepción: no viajar', 'covered': 'Cubierto por estancia',
          'unknown': 'Reserva sin verificar'}


def load_plan(path=Path('config/family_plan.json')):
    plan = json.loads(path.read_text()) if path.exists() else {}
    for key in ('required_from', 'required_until'):
        if plan.get(key):
            date.fromisoformat(plan[key])
    if plan.get('required_from') and plan.get('required_until') and plan['required_from'] > plan['required_until']:
        raise ValueError('Family coverage dates are reversed')
    for saturday, status in plan.get('weekends', {}).items():
        if date.fromisoformat(saturday).weekday() != 5 or status not in STATES:
            raise ValueError('Weekend state must use a Saturday and an explicit supported status')
    return plan


def weekend_of(outbound):
    return outbound + timedelta(days=(5-outbound.weekday()) % 7)


def joined_pairs(weekly_pairs):
    """Only combine adjacent weekends; existing leg queries can be reused."""
    groups = {}
    for out, inc in weekly_pairs:
        groups.setdefault(weekend_of(out), []).append((out, inc))
    return sorted({(first[0], second[1]) for week, choices in groups.items()
                   for first in choices for second in groups.get(week+timedelta(days=7), [])})


def build_coverage(trips, decisions, plan=None):
    plan = plan or {}
    groups = {}
    for trip in trips:
        out, inc = trip['outbound'], trip['inbound']
        saturday = weekend_of(out)
        # Holiday extensions are still alternatives for this same family weekend.
        # Joined two-weekend stays must not replace individual-week coverage.
        if out not in outbound_dates_for_weekend(saturday) or inc not in inbound_dates_for_weekend(saturday):
            continue
        groups.setdefault(saturday, []).append(trip)
    result = []
    for week, choices in sorted(groups.items()):
        key = str(week)
        in_period = (not plan.get('required_from') or key >= plan['required_from']) and (not plan.get('required_until') or key <= plan['required_until'])
        state = plan.get('weekends', {}).get(key, 'unknown') if in_period else 'outside'
        available = sorted((t for t in choices if t['total'] is not None), key=lambda t: t['total'])
        best = available[0] if available else None
        result.append(dict(weekend=week, state=state, choices=choices, best=best,
                           period_confirmed=bool(plan.get('required_from')),
                           decision=decisions.get((best['outbound'], best['inbound']), {}) if best else {}))
    return result


def join_opportunities(coverage, trips):
    """Compare complete two-weekend prices against two separate cheapest trips.

Only alternatives, never cumulatively reserved or deducted from annual balances.
"""
    by_week = {w['weekend']: w for w in coverage}
    result = []
    for first in coverage:
        second = by_week.get(first['weekend']+timedelta(days=7))
        if not second or any(w['state'] not in ('pending', 'unknown') or not w['best'] for w in (first, second)):
            continue
        candidates = [t for t in trips if t['total'] is not None
                      and t['outbound'] in outbound_dates_for_weekend(first['weekend'])
                      and t['inbound'] in inbound_dates_for_weekend(second['weekend'])]
        for trip in candidates:
            separate = first['best']['total'] + second['best']['total']
            saving = separate - trip['total']
            if saving <= 0:
                continue
            extra = workdays_affected(trip['outbound'], trip['inbound']) - sum(
                workdays_affected(w['best']['outbound'], w['best']['inbound']) for w in (first, second))
            result.append(dict(first=first['weekend'], second=second['weekend'], trip=trip,
                               saving=saving, extra_workdays=extra,
                               allocation=estimate_allocation(trip['outbound'], trip['inbound'])))
    # One suggestion per adjacent pair; alternatives can overlap and must not be summed.
    best = {}
    for item in sorted(result, key=lambda i: (-i['saving'], i['extra_workdays'])):
        best.setdefault(item['first'], item)
    return list(best.values())


def render_coverage(coverage, joins):
    html = ('<h2 style="font-size:18px">Fines de semana con tu familia</h2>'
            '<p>Cada semana se planifica por separado: una barata no sustituye a otra. '
            'Las reservas y excepciones solo se marcan con confirmación.</p>')
    if not coverage or not all(w['period_confirmed'] for w in coverage):
        html += '<p><b>Inicio de la rutina familiar pendiente de confirmar.</b> Planificación provisional; no implica que debas comprar todas estas fechas.</p>'
    monthly = {}
    for week in coverage:
        state, best, decision = week['state'], week['best'], week['decision']
        if state == 'outside':
            continue
        label = LABELS[state]
        html += f'<div style="border-bottom:1px solid #e2e8f0;padding:10px 0"><b>{week["weekend"].isoformat()} · {label}</b>'
        if state in ('booked', 'covered', 'skipped'):
            html += '<br>Sin recomendación de nueva compra.</div>'
            continue
        bucket = monthly.setdefault(str(week['weekend'])[:7], dict(total=0, priced=0, weeks=0))
        bucket['weeks'] += 1
        if best:
            bucket['total'] += best['total']; bucket['priced'] += 1
            action = decision.get('action', 'REVISAR OPCIONES')
            html += (f'<br>Desde {best["total"]:.0f} € · {best["outbound"]} → {best["inbound"]}'
                     f'<br>{escape(action)}')
            if state == 'unknown':
                html += ' (antes, verificar si ya tienes billetes)'
            if decision:
                html += f' · revisar {escape(decision["review_on"])} · límite provisional {escape(decision["deadline"])}'
            html += '<br>Alternativas de esta semana: ' + '; '.join(
                f'{t["outbound"]} → {t["inbound"]}: {t["total"]:.0f} €' if t['total'] is not None
                else f'{t["outbound"]} → {t["inbound"]}: sin precio completo' for t in week['choices'])
        else:
            html += '<br><b>Sin precio completo: verificar esta semana; no sustituirla por otra.</b>'
        html += '</div>'
    html += '<h3>Presupuesto orientativo por mes</h3>'
    for month, bucket in sorted(monthly.items()):
        html += (f'<p>{month}: {bucket["total"]:.0f} € para {bucket["priced"]}/{bucket["weeks"]} fines de semana '
                 'pendientes o sin verificar, con precio observado.</p>')
    html += '<p>Estimación con viajes separados, agrupada por sábado; no es gasto contratado. Excluye billetes ya comprados, traslados y extras. Puede haber cobertura de búsqueda parcial.</p>'
    if joins:
        html += '<h3>Unir dos fines de semana</h3>'
        for item in joins:
            trip = item['trip']
            allocations = '; '.join(f'{year}: {a["remote"]} TT / {a["leave"]} vacaciones'
                                     + (' (saldo sin verificar)' if not a['verified'] else '')
                                     + (f' / {a["uncovered"]} días sin cubrir' if a['uncovered'] else '')
                                     for year, a in item['allocation'].items())
            html += (f'<p><b>{trip["outbound"]} → {trip["inbound"]}: {trip["total"]:.0f} €</b><br>'
                     f'Cubre los fines de semana {item["first"]} y {item["second"]}; '
                     f'ahorro observado de {item["saving"]:.0f} € frente a dos viajes separados, evitando dos trayectos.<br>'
                     f'{item["extra_workdays"]} laborables adicionales a organizar; {allocations}.</p>')
        html += ('<p>Solo si puedes permanecer en España entre ambos fines de semana y no tienes ya esos vuelos comprados. '
                 'Requiere confirmar teletrabajo/vacaciones y presencia en NL. Alternativas solapadas: no sumar sus ahorros ni sus cupos. '
                 'El cálculo de laborables supone trabajar antes de la ida; una salida temprana puede requerir otro día.</p>')
    return html
