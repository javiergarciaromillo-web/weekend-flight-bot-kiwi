"""Descriptive price learning from real, timestamped eligible fare quotes.

Context comparisons are by identical weekday pattern, holiday status and
booking-horizon bucket, aggregated by *independent travel week* to avoid
overweighting daily repeats. A genuine optimum booking lead-time requires
matured travel-date trajectories, never today's unseen future prices.
No external fuel figures are fabricated or imputed.
"""
from collections import defaultdict
from datetime import date
from statistics import median

from src.decisions import FILTER_VERSION
from src.family import weekend_of

# Booking lead-time intervals: [first, last], in days ahead of outbound.
LEAD_BUCKETS = (
    (0, 13), (14, 27), (28, 41), (42, 55), (56, 83),
    (84, 111), (112, 167), (168, 223), (224, 300),
)
MIN_CONTEXT_WEEKENDS = 6
MIN_MATURE_WEEKENDS = 8


def _date(value):
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def lead_bucket(days):
    for first, last in LEAD_BUCKETS:
        if first <= days <= last:
            return (first, last)
    return None


def _month_gap(a, b):
    gap = abs(a - b)
    return min(gap, 12 - gap)


def _valid_records(records, as_of):
    cutoff = _date(as_of)
    for row in records:
        try:
            quote_day = _date(row['run_date'])
            outbound = _date(row['outbound'])
            inbound = _date(row['inbound'])
            price = float(row['price'])
            if (not row.get('coverage_complete')
                    or row.get('filter_version') != FILTER_VERSION
                    or quote_day >= cutoff or quote_day >= outbound
                    or outbound >= inbound or price <= 0
                    or lead_bucket((outbound - quote_day).days) is None):
                continue
            yield dict(quoted=quote_day, out=outbound, back=inbound,
                       weekend=weekend_of(outbound), price=price,
                       holiday=bool(row.get('holiday', False)),
                       bucket=lead_bucket((outbound-quote_day).days))
        except (KeyError, TypeError, ValueError, OverflowError):
            continue


def comparable_price(outbound, inbound, price, holiday, records, as_of):
    """Market-level price context, not a projection of a future price.

    Exact stay weekday pattern and same holiday class are mandatory. First
    try nearby travel months, then fall back to all months *explicitly*
    without falsely claiming seasonality is adjusted. Never use the
    candidate's own date or future quotes as its benchmark.
    """
    out = _date(outbound)
    back = _date(inbound)
    bucket = lead_bucket((out - _date(as_of)).days)
    if price is None or bucket is None or price <= 0:
        return None
    choices = []
    for record in _valid_records(records, as_of):
        if (record['bucket'] != bucket
                or record['out'].weekday() != out.weekday()
                or record['back'].weekday() != back.weekday()
                or record['holiday'] != bool(holiday)
                or record['weekend'] == weekend_of(out)
                or (record['back']-record['out']).days != (back-out).days):
            continue
        choices.append(record)

    for seasonal in (True, False):
        grouped = defaultdict(list)
        for record in choices:
            if seasonal and _month_gap(record['out'].month, out.month) > 1:
                continue
            grouped[record['weekend']].append(record['price'])
        if len(grouped) < MIN_CONTEXT_WEEKENDS:
            continue
        peers = sorted(median(prices) for prices in grouped.values())
        reference = median(peers)
        below = sum(v <= price for v in peers)
        return {
            'reference': round(reference, 2),
            'vs_reference_pct': round((price/reference-1)*100, 1),
            'percentile': round(100*below/len(peers)),
            'independent_weekends': len(peers),
            'lead_days': bucket,
            'seasonally_matched': seasonal,
            'context': ('fechas de meses cercanos' if seasonal else
                        'todos los meses; estacionalidad no calibrada'),
            'favourable': price <= sorted(peers)[max(0, (len(peers)-1)//4)],
        }
    return None


def booking_window_evidence(records, as_of, min_weekends=MIN_MATURE_WEEKENDS):
    """Learn only from *already departed* trips with 3+ observed lead bins.

    Paired comparisons prevent apparent optima caused by different target
    weekends falling in different booking-horizon buckets. Regret is
    relative to the *observed* minimum, not the unknowable market minimum.
    """
    as_of = _date(as_of)
    routes = defaultdict(lambda: defaultdict(list))
    for item in _valid_records(records, as_of):
        if item['out'] >= as_of:
            continue
        key = (item['out'], item['back'])
        routes[key][item['bucket']].append(item['price'])
    eligible = []
    for key, bins in routes.items():
        if len(bins) < 3:
            continue
        eligible.append((key, {band: median(values) for band, values in bins.items()}))
    # Only lead-time bins supported by >=min_weekends independent, matured
    # journeys can be compared. No claims before sufficient complete journeys.
    if len(eligible) < min_weekends:
        return dict(status='insufficient', mature_trips=len(eligible),
                    minimum_needed=min_weekends, bands=[])
    penalties = defaultdict(list)
    for _, bins in eligible:
        minimum = min(bins.values())
        for band, value in bins.items():
            penalties[band].append(100 * (value/minimum - 1))
    bands = []
    for band, deviations in penalties.items():
        if len(deviations) < min_weekends:
            continue
        bands.append(dict(range_days=band, journeys=len(deviations),
                          median_above_observed_best_pct=round(median(deviations), 1)))
    bands.sort(key=lambda r: (r['median_above_observed_best_pct'], -r['journeys']))
    if len(bands) < 2:
        return dict(status='insufficient', mature_trips=len(eligible),
                    minimum_needed=min_weekends, bands=bands)
    return dict(status='observational', mature_trips=len(eligible),
                minimum_needed=min_weekends, bands=bands)


def market_movement(records, as_of, min_weekends=6):
    """Broad directional indicator from SAME-itinerary prices across last days.

    Does not attribute the direction to fuel, politics, seasonality or fares
    that were not observed. Balances by travel weekend.
    """
    today = _date(as_of)
    recent = defaultdict(list)
    previous = defaultdict(list)
    for row in _valid_records(records, today):
        age = (today-row['quoted']).days
        if age <= 3:
            recent[(row['out'], row['back'])].append(row['price'])
        elif 4 <= age <= 10:
            previous[(row['out'], row['back'])].append(row['price'])
    diffs = defaultdict(list)
    for key in recent.keys() & previous.keys():
        before, after = median(previous[key]), median(recent[key])
        if before > 0:
            diffs[weekend_of(key[0])].append(100*(after/before-1))
    if len(diffs) < min_weekends:
        return None
    return dict(weekends=len(diffs),
                median_change_pct=round(median(median(v) for v in diffs.values()), 1),
                period='últimos 3 días frente a los 4–10 días anteriores')
