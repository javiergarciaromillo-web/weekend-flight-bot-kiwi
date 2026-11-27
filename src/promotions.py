"""Campaign eligibility and observed fare drops are independent evidence.

Never attribute a dynamic fare to Black Friday merely because it fell.
Only dated, manually verified official campaign terms enter the catalogue.
No campaign changes searches, buy decisions, totals or email delivery.
"""
from datetime import date, timedelta
from html import escape
import json
from math import isfinite
from pathlib import Path
from statistics import median

from src.decisions import FILTER_VERSION

CATALOGUE = Path(__file__).resolve().parents[1] / 'config' / 'promotions.json'


def active_campaigns(as_of):
    day = str(as_of)
    return [c for c in json.loads(CATALOGUE.read_text())
            if c['verified_at'] <= day and c['booking_from'] <= day <= c['booking_until']]


def promotion_signal(trip, history, as_of, campaigns=None):
    day = str(as_of)
    campaigns = active_campaigns(day) if campaigns is None else campaigns
    fare = trip.get('fare')
    if (not isinstance(fare, (int, float)) or not isfinite(fare) or fare <= 0
            or str(trip['outbound']) <= day):
        return None
    matches = []
    for campaign in campaigns:
        if not (campaign['verified_at'] <= day and campaign['booking_from'] <= day <= campaign['booking_until']):
            continue
        if not campaign.get('travel_from') or not campaign.get('travel_until'):
            continue
        legs = []
        for kind, rows in trip.get('legs', {}).items():
            travel_day = str(trip['outbound'] if kind == 'outbound' else trip['inbound'])
            if not campaign['travel_from'] <= travel_day <= campaign['travel_until']:
                continue
            for row in rows:
                if (row.get('airline') == campaign['provider']
                        and [row.get('origin'), row.get('destination')] in campaign['routes']):
                    legs.append(dict(kind=kind, origin=row['origin'], destination=row['destination'], price=row.get('price')))
        if legs:
            matches.append(dict(campaign=campaign, legs=legs))
    # Exclude all campaign-era observations from a pre-campaign reference.
    # Outside an active campaign use a rolling 30-day same-date reference.
    anchor = min([c['booking_from'] for c in campaigns], default=day)
    lower = str(date.fromisoformat(anchor) - timedelta(days=30))
    daily = {}
    for row in history:
        price = row.get('price')
        if (str(row.get('outbound')) == str(trip['outbound'])
                and str(row.get('inbound')) == str(trip['inbound'])
                and row.get('filter_version') == FILTER_VERSION
                and row.get('coverage_complete')
                and lower <= str(row.get('run_date', '')) < anchor
                and str(row['run_date']) < day
                and isinstance(price, (int, float)) and isfinite(price) and price > 0):
            daily[str(row['run_date'])] = price
    reference = median(daily.values()) if len(daily) >= 3 else None
    saving = round(reference - fare, 2) if reference is not None else None
    drop = saving is not None and saving >= max(20, reference * .15)
    if not matches and not drop:
        return None
    return dict(campaigns=matches, drop=drop, reference=reference, saving=saving,
                sample_days=len(daily), baseline_before=anchor,
                attribution='unknown', observed_at=day)


def render_promotions(run_date, trips, history):
    campaigns = active_campaigns(run_date)
    if not campaigns:
        return ''
    parts = ['<section><h2>Campañas y bajadas verificables</h2>',
             '<p>Ruta en campaña no garantiza tarifa promocional. Las bajadas comparan '
             'la misma pareja de fechas y filtros, pero el vuelo más barato puede cambiar. '
             'Equipaje y extras desconocidos. Prime no equivale a BF.</p>']
    for campaign in campaigns:
        parts.append(f'<p><a href="{escape(campaign["source"], quote=True)}">{escape(campaign["name"])}</a>'
                     f' · reservas hasta {campaign["booking_until"]}. {escape(campaign["note"])}</p>')
    return ''.join(parts) + '</section>'
