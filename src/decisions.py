"""Transparent risk policy, not a learned optimal booking window.

Only past, complete observations under the same policy may inform a decision.
The deadline is a configurable risk preference, never a price forecast.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

POLICY_VERSION = '2026-10-20-holiday-windows-v3'
FILTER_VERSION = '2026-10-20'


@dataclass(frozen=True)
class BookingPolicy:
    ordinary_deadline_days: int = 21
    holiday_deadline_days: int = 42
    review_days: int = 3
    min_history_days: int = 7
    meaningful_saving_eur: float = 20
    meaningful_saving_fraction: float = .08


def recommend(run_date, outbound, price, history, *, holiday=False,
              coverage_complete=True, policy=None):
    policy = policy or BookingPolicy()
    deadline = outbound - timedelta(days=(policy.holiday_deadline_days if holiday
                                          else policy.ordinary_deadline_days))
    prior = {str(h['run_date']): float(h['price']) for h in history
             if FILTER_VERSION <= str(h['run_date']) < str(run_date)
             and h.get('price') is not None and h['price'] > 0
             and h.get('coverage_complete')
             and h.get('filter_version') == FILTER_VERSION}
    result = dict(policy_version=POLICY_VERSION, deadline=str(deadline),
                  review_on=str(min(run_date + timedelta(days=policy.review_days),
                                    max(run_date, deadline))),
                  history_days=len(prior), confidence='Regla prudente; no predicción',
                  historical_median=None, saving_vs_median=None)
    if outbound <= run_date:
        action, reason = 'REVISAR', 'Fecha de salida alcanzada; comprobar disponibilidad directamente.'
    elif price is None or not coverage_complete:
        action, reason = 'VERIFICAR', 'Cobertura incompleta: verificar precios antes de decidir.'
        result['review_on'] = str(run_date)
    elif run_date >= deadline:
        action, reason = 'CERRAR DECISIÓN', ('Límite prudente alcanzado para cubrir esta semana: reservar una opción '
                                            'aceptable dentro del mismo fin de semana; no seguir esperando una bajada.')
    elif len(prior) >= policy.min_history_days:
        baseline = median(prior.values())
        saving = baseline - price
        result.update(historical_median=baseline, saving_vs_median=round(saving, 2))
        if saving >= max(policy.meaningful_saving_eur, baseline * policy.meaningful_saving_fraction):
            action, reason = 'CONSIDERAR COMPRA', (f'{saving:.0f} € por debajo de la mediana observada '
                                                  'para estas fechas; no garantiza el mínimo futuro.')
        else:
            action, reason = 'ESPERAR CON LÍMITE', 'Sin ahorro destacado frente a tu histórico; revisar en la fecha indicada.'
    else:
        action, reason = 'OBSERVAR', 'Aún faltan días comparables para valorar el precio; mantener la fecha límite.'
    result.update(action=action, reason=reason)
    return result


def backtest(records, policy=None):
    """Walk forward independently for each pair; no future inputs to recommend().

Requires complete trajectories near departure; returns descriptive regret only,
not a probability or an estimate of the optimum. Alternatives may overlap.
"""
    grouped = {}
    for row in records:
        if row.get('filter_version') == FILTER_VERSION and row.get('coverage_complete') and row.get('price') is not None:
            grouped.setdefault((row['outbound'], row['inbound']), {})[row['run_date']] = row
    outcomes = []
    for (outbound, inbound), daily in sorted(grouped.items()):
        departure = date.fromisoformat(outbound)
        series = sorted(daily.values(), key=lambda r: r['run_date'])
        if len(series) < 7 or (departure - date.fromisoformat(series[-1]['run_date'])).days not in range(1, 8):
            continue
        past, selected = [], None
        for row in series:
            decision = recommend(date.fromisoformat(row['run_date']), departure, row['price'], past,
                                 holiday=row.get('holiday', False), policy=policy)
            if selected is None and decision['action'] in ('CONSIDERAR COMPRA', 'CERRAR DECISIÓN'):
                selected = row
            past.append(row)
        if selected:
            later = [r['price'] for r in series if r['run_date'] >= selected['run_date']]
            outcomes.append(dict(outbound=outbound, inbound=inbound, buy_date=selected['run_date'],
                                 price=selected['price'], observed_regret=selected['price']-min(later),
                                 versus_last=selected['price']-series[-1]['price'],
                                 observation_days=len(series)))
    return outcomes
