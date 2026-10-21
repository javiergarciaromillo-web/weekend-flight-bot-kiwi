"""Weekly family coverage and conditional two-weekend stays.

No booking/exception is inferred from a price search. Date keys are Saturdays.
"""
import json
from datetime import date, timedelta
from html import escape
from pathlib import Path

from src.holidays import workdays_affected, outbound_dates_for_weekend, inbound_dates_for_weekend
from src.travel_plan import ALL_STATES, NO_TRAVEL_STATES, forecast_config
from src.budget import (estimate_allocation, trip_work_dates, assess_remote_plan,
                        REMOTE_WORK_DAYS, MAX_CONSECUTIVE_REMOTE_DAYS,
                        annual_tt_outlook, projected_annual_tt,
                        projected_selection_tt)


STATES = ALL_STATES
LABELS = {'pending': 'Pendiente de comprar', 'booked': 'Comprado',
          'skipped': 'Excepción: no viajar', 'covered': 'Cubierto por estancia',
          'vacation': 'Vacaciones: sin vuelo semanal',
          'holiday_break': 'Cierre NCIA: sin vuelo semanal',
          'visiting_nl': 'Familia en Países Bajos: sin vuelo semanal',
          'unknown': 'Reserva sin verificar'}


def load_plan(path=Path('config/family_plan.json')):
    plan = json.loads(path.read_text()) if path.exists() else {}
    for key in ('required_from', 'required_until'):
        if plan.get(key):
            date.fromisoformat(plan[key])
    if plan.get('required_from') and plan.get('required_until') and plan['required_from'] > plan['required_until']:
        raise ValueError('Family coverage dates are reversed')
    forecast_config(plan)  # Fail early on invalid long-range assumptions.
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
    annual_outlook = annual_tt_outlook(plan)
    for week, choices in sorted(groups.items()):
        key = str(week)
        in_period = (not plan.get('required_from') or key >= plan['required_from']) and (not plan.get('required_until') or key <= plan['required_until'])
        state = plan.get('weekends', {}).get(key, 'unknown') if in_period else 'outside'
        # Prefer standard-approval-compatible trips over a cheaper itinerary
        # requiring more than five consecutive days of remote work.
        def risk_key(t):
            dates, _ = trip_work_dates(t)
            streak = assess_remote_plan(dates)['requires_special_authorisation']
            annual = projected_annual_tt(dates, [week], annual_outlook)
            cap_risk = bool(annual and annual['exceeds_cap'])
            return (streak or cap_risk, streak, cap_risk, t['total'])

        available = sorted((t for t in choices if t['total'] is not None),
                           key=risk_key)
        best = available[0] if available else None
        result.append(dict(weekend=week, state=state, choices=choices, best=best,
                           period_confirmed=bool(plan.get('required_from')),
                           decision=decisions.get((best['outbound'], best['inbound']), {}) if best else {}))
    return result


def join_opportunities(coverage, trips, annual_outlook=None):
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
            joined_dates, joined_notes = trip_work_dates(trip)
            separate_days = [d for w in (first, second)
                             for d in trip_work_dates(w['best'])[0]]
            extra = len(joined_dates) - len(separate_days)
            assessment = assess_remote_plan(joined_dates)
            annual_projection = projected_annual_tt(
                joined_dates, [first['weekend'], second['weekend']], annual_outlook)
            result.append(dict(first=first['weekend'], second=second['weekend'], trip=trip,
                               saving=saving, extra_workdays=extra,
                               joined_tt=len(joined_dates), separate_tt=len(separate_days),
                               joined_dates=joined_dates, joined_notes=joined_notes,
                               longest_streak=assessment['longest_consecutive_tt'],
                               needs_special_authorisation=assessment['requires_special_authorisation'],
                               annual_projection=annual_projection,
                               allocation=estimate_allocation(
                                   trip['outbound'], trip['inbound'], workdates=joined_dates)))
    # One suggestion per adjacent pair; alternatives can overlap and must not be summed.
    best = {}
    for item in sorted(result, key=lambda i: (
            i['needs_special_authorisation'] or bool(i['annual_projection'] and
                                                    i['annual_projection']['exceeds_cap']),
            i['needs_special_authorisation'], -i['saving'], i['extra_workdays'])):
        best.setdefault(item['first'], item)
    return list(best.values())



def _day(day):
    labels = ['lun.', 'mar.', 'mié.', 'jue.', 'vie.', 'sáb.', 'dom.']
    return f'{labels[day.weekday()]} {day.day:02d}/{day.month:02d}'


def _flight_details(trip, leg):
    from datetime import datetime
    rows = trip.get('out' if leg == 'Ida' else 'inc') or []
    if not rows:
        return f'<span style="color:#64748b">{leg}: horario sin verificar</span>'
    row = min(rows, key=lambda r: r['price'])
    url = escape(row.get('source_url') or '#', quote=True)
    times = []
    for key in ('outbound_departure', 'outbound_arrival'):
        value = str(row.get(key) or '—')
        formatted = value
        for fmt in ('%I:%M %p', '%H:%M'):
            try:
                formatted = datetime.strptime(value.replace('+1', '').strip(), fmt).strftime('%H:%M')
                if '+1' in value:
                    formatted += ' (+1)'
                break
            except ValueError:
                continue
        times.append(escape(formatted))
    route = f"{escape(str(row['origin']))} → {escape(str(row['destination']))}"
    carrier = escape(str(row.get('airline') or '—'))
    return (f'<b>{leg}</b> · {route} · {carrier} · '
            f'<b>{times[0]}–{times[1]}</b> · '
            f'<a href="{url}" style="color:#2563eb">{row["price"]:.0f} €</a>')


def _tt_details(trip):
    dates, notes = trip_work_dates(trip)
    if not dates:
        return 'TT estimado: 0 días', notes
    return ('TT/permiso a prever: ' + ', '.join(_day(day) for day in dates), notes)


def render_coverage(coverage, joins, annual_outlook=None):
    """Email-friendly weekly cards with dated flights and requested TT dates.

    All working-day estimates are conditional: they are NOT approved TT/leave.
    """
    html = ('<h2 style="font-size:19px;margin:20px 0 6px">Próximos fines de semana con tu familia</h2>'
            '<p style="font-size:12px;color:#64748b;margin:4px 0 12px">'
            'Cada fin de semana se compara por separado. Los vuelos indicados son '
            'los más baratos de cada trayecto; confirma tarifa y condiciones. '
            'Los días TT son orientativos, no permisos aprobados.</p>')
    if annual_outlook:
        overview = annual_outlook
        margin = overview['margin']
        tone = '#9a3412' if margin <= 3 else '#475569'
        html += (f'<p style="font-size:12px;border-left:3px solid #64748b;'
                 f'padding:8px 11px;margin:10px 0;color:{tone}">'
                 f'<b>Cupo anual de TT {overview["year"]}: {REMOTE_WORK_DAYS} días.</b> '
                 f'Escenario de referencia (un viernes TT por fin de semana salvo festivos): '
                 f'<b>{overview["baseline_tt"]} días</b> para '
                 f'{overview["weekends"]} fines de semana · margen teórico '
                 f'{margin:+d} días. No es el consumo real ni el saldo restante; '
                 f'faltan las reservas, vacaciones y TT ya aprobados. '
                 f'Máximo ordinario: {MAX_CONSECUTIVE_REMOTE_DAYS} jornadas TT '
                 'seguidas; superar ese límite exige autorización especial.</p>')
        selected_forecast = projected_selection_tt(coverage, overview)
        if selected_forecast and selected_forecast['priced_weeks']:
            future = selected_forecast['projected']
            warning = (f'<b style="color:#9a3412">ATENCIÓN: {future}/'
                       f'{REMOTE_WORK_DAYS} TT en este escenario. '
                       'Conviene reducir los TT de alguna alternativa o reservar '
                       'vacaciones, porque el cupo teórico se supera.</b>'
                       if selected_forecast['exceeds_cap']
                       else f'<b>{future}/{REMOTE_WORK_DAYS} TT</b> en este escenario.')
            html += (f'<p style="font-size:12px;border-left:3px solid #94a3b8;'
                     f'padding:8px 11px;margin:8px 0">'
                     f'Sustituyendo por las mejores alternativas de '
                     f'{selected_forecast["priced_weeks"]} fines de semana comprobados: '
                     + warning +
                     ' Es una proyección, no un calendario reservado.</p>')
    if not coverage or not all(w['period_confirmed'] for w in coverage):
        html += ('<p><b>Inicio de la rutina familiar pendiente de confirmar.</b> '
                 'Planificación provisional; no implica que debas comprar todas las fechas.</p>')
    last_month = None
    for week in coverage:
        state, best, decision = week['state'], week['best'], week['decision']
        if state == 'outside':
            continue
        saturday = week['weekend']
        month = (saturday.year, saturday.month)
        if month != last_month:
            name = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'][month[1]-1]
            html += (f'<h3 style="font-size:15px;color:#334155;border-bottom:2px solid #94a3b8;'
                     f'padding:14px 0 5px;margin:18px 0 8px">{name.upper()} {month[0]}</h3>')
            last_month = month
        label = escape(LABELS[state])
        html += (f'<div style="border:1px solid #dbe2ea;border-radius:6px;'
                 f'padding:12px;margin:0 0 12px;background:#fff">'
                 f'<div style="font-size:15px;margin-bottom:6px"><b>Fin de semana {_day(saturday)}</b>'
                 f' <span style="font-size:11px;color:#64748b">· {label}</span></div>')
        if state in ('booked', 'covered', 'skipped', 'vacation', 'visiting_nl', 'holiday_break'):
            html += '<p style="font-size:12px">Sin recomendación de nueva compra.</p></div>'
            continue
        if not best:
            html += '<p>Sin precio completo verificado para este fin de semana.</p></div>'
            continue
        best_assessment = assess_remote_plan(trip_work_dates(best)[0])
        def option_risk(option):
            dates = trip_work_dates(option)[0]
            a = assess_remote_plan(dates)
            year_projection = projected_annual_tt(dates, [saturday], annual_outlook)
            return (a['requires_special_authorisation'] or
                    bool(year_projection and year_projection['exceeds_cap']))
        best_label = ('Opción viable priorizada' if any(
            option_risk(t) for t in week['choices'] if t['total'] is not None)
            else 'Opción más barata')
        html += (f'<div style="margin:2px 0 8px;font-size:13px">'
                 f'<b>{best_label}: {best["total"]:.0f} €</b>'
                 f' · {_day(best["outbound"])} → {_day(best["inbound"])}</div>')
        if decision:
            html += (f'<div style="font-size:11px;color:#475569;margin-bottom:8px">'
                     f'{escape(decision.get("action", "REVISAR"))}'
                     f' · Revisar: {escape(str(decision.get("review_on", "—")))}'
                     f' · Límite provisional: {escape(str(decision.get("deadline", "—")))}</div>')
        if state == 'unknown':
            html += ('<p style="font-size:11px;color:#64748b;margin:4px 0">'
                     'Reserva aún sin verificar: confirma si ya tienes billetes.</p>')
        ordered = sorted(week['choices'],
                         key=lambda t: (t['total'] is None, option_risk(t),
                                        t['total'] or 0, t['outbound'], t['inbound']))
        for index, choice in enumerate(ordered):
            highlighted = index == 0 and choice['total'] is not None
            chosen_tt_dates = trip_work_dates(choice)[0]
            status = assess_remote_plan(chosen_tt_dates)
            annual_scenario = projected_annual_tt(chosen_tt_dates, [saturday], annual_outlook)
            heading = ('OPCIÓN PRIORITARIA' if highlighted else
                       'REQUIERE AUTORIZACIÓN ESPECIAL' if status['requires_special_authorisation']
                       else 'SUPERA CUPO EN ESCENARIO ANUAL' if
                       annual_scenario and annual_scenario['exceeds_cap']
                       else 'Alternativa')
            border = '2px solid #cbd5e1' if highlighted else '1px solid #edf1f5'
            datestr = f'{_day(choice["outbound"])} → {_day(choice["inbound"])}'
            amount = f'{choice["total"]:.0f} €' if choice['total'] is not None else 'Sin precio completo'
            html += (f'<div style="border-top:{border};padding:8px 0 7px">'
                     f'<div style="font-size:12px"><b>{heading}</b> · {datestr} '
                     f'· <b>{amount}</b></div>')
            html += ('<div style="font-size:12px;line-height:1.6;padding-left:8px">'
                     + _flight_details(choice, 'Ida') + '<br>'
                     + _flight_details(choice, 'Vuelta') + '</div>')
            dates_line, notes = _tt_details(choice)
            html += f'<div style="font-size:11px;color:#475569;padding-left:8px">{escape(dates_line)}</div>'
            html += (f'<div style="font-size:11px;color:#475569;padding-left:8px">'
                     f'{status["tt_days"]} TT estimados · '
                     f'racha máxima {status["longest_consecutive_tt"]}/'
                     f'{MAX_CONSECUTIVE_REMOTE_DAYS} jornadas TT · '
                     f'cupo anual {REMOTE_WORK_DAYS} días (compartido entre viajes)</div>')
            if status['requires_special_authorisation']:
                html += ('<div style="font-size:11px;color:#9a3412;padding-left:8px">'
                         '<b>No prioritaria:</b> más de cinco jornadas TT seguidas; '
                         'solo con autorización especial o reorganizando con vacaciones.</div>')
            if annual_scenario:
                note = ' · EXCESO TEÓRICO' if annual_scenario['exceeds_cap'] else ''
                html += (f'<div style="font-size:11px;color:#475569;padding-left:8px">'
                         f'Proyección 2027 si el resto de fines de semana sigue el '
                         f'escenario base: <b>{annual_scenario["projected"]}/'
                         f'{REMOTE_WORK_DAYS} TT</b>{note}. No es saldo real.</div>')
                if annual_scenario['exceeds_cap']:
                    html += ('<div style="font-size:11px;color:#9a3412;padding-left:8px">'
                             '<b>No prioritaria:</b> supera 46 TT en el escenario '
                             'anual; elegir menos TT o combinar con vacaciones.</div>')
            if notes:
                html += ('<div style="font-size:10px;color:#64748b;padding-left:8px">'
                         + ' '.join(escape(note) for note in notes) + '</div>')
            html += '</div>'
        html += '</div>'

    if joins:
        html += ('<h2 style="font-size:18px;margin:24px 0 6px">Unir dos fines de semana</h2>'
                 '<p style="font-size:12px;color:#64748b">'
                 'Compara una estancia larga frente a dos viajes independientes. '
                 'TT extra = días estimados de trabajo desde España con la estancia '
                 'unida, menos los dos viajes separados (no es un saldo aprobado).</p>')
        for item in joins:
            trip = item['trip']
            allocations = '; '.join(
                f'{year}: {a["remote"]} TT / {a["leave"]} vacaciones'
                + (' (saldo sin verificar)' if not a['verified'] else '')
                + (f' / {a["uncovered"]} sin cubrir' if a['uncovered'] else '')
                for year, a in item['allocation'].items()
            )
            count = item['extra_workdays']
            count_label = f'+{count}' if count > 0 else str(count)
            special = item.get('needs_special_authorisation', False)
            annual_join = item.get('annual_projection')
            warning = ('<br><b style="color:#9a3412">NO PRIORITARIA: '
                       'requiere autorización especial por superar '
                       'cinco jornadas TT consecutivas, '
                       'o sustituir alguna jornada por vacaciones.</b>'
                       if special else '<br><b>Dentro del límite ordinario '
                       'de cinco jornadas TT consecutivas.</b>')
            tt_dates = ', '.join(_day(day) for day in item['joined_dates'])
            html += (f'<div style="border:1px solid #dbe2ea;border-radius:6px;'
                     f'padding:11px;margin:10px 0">'
                     f'<b>{_day(trip["outbound"])} → {_day(trip["inbound"])} · '
                     f'{trip["total"]:.0f} €</b><br>'
                     f'<span style="font-size:12px">Cubre los fines de semana '
                     f'{_day(item["first"])} y {_day(item["second"])} · '
                     f'ahorro observado {item["saving"]:.0f} € frente a dos viajes '
                     f'(evitas dos trayectos).</span><br>'
                     f'<span style="font-size:12px"><b>TT estimado:</b> '
                     f'dos viajes {item["separate_tt"]} días → estancia unida '
                     f'{item["joined_tt"]} días <b>({count_label} TT adicionales)</b></span><br>'
                     f'<span style="font-size:11px;color:#475569">Días de TT/permiso en '
                     f'la estancia unida: {escape(tt_dates) if tt_dates else "ninguno"}. '
                     f'Asignación orientativa: {escape(allocations)}.</span>'
                     f'<br><span style="font-size:11px">Racha máxima: '
                     f'{item.get("longest_streak", "—")}/{MAX_CONSECUTIVE_REMOTE_DAYS} jornadas TT. '
                     f'Cupo anual compartido: {REMOTE_WORK_DAYS} días.</span>'
                     + warning
                     + (f'<br><b style="color:#9a3412">Exceso teórico de cupo anual: '
                        f'{annual_join["projected"]}/{REMOTE_WORK_DAYS} TT'
                        f'. Evitar como opción ordinaria o utilizar vacaciones.</b>'
                        if annual_join and annual_join['exceeds_cap'] else '')
                     + '</div>')
        html += ('<p style="font-size:11px;color:#64748b">'
                 'Alternativas que pueden solaparse: no sumes ahorros ni días TT. '
                 'Las salidas tempranas del viernes pueden requerir TT o permiso parcial. '
                 'Para estancias largas habría que coordinar TT/vacaciones y presencia en NL.</p>')
    return html
