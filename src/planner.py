from datetime import date, timedelta


def generate_weekend_pairs(start_date: date, weeks: int):
    pairs = []

    for i in range(weeks * 7):
        d = start_date + timedelta(days=i)

        if d.weekday() not in [3, 4]:
            continue

        sunday = d + timedelta(days=(6 - d.weekday()))
        monday = sunday + timedelta(days=1)

        pairs.append((d, sunday))
        pairs.append((d, monday))

    return pairs
