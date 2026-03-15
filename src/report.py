def build_html_report(run_date, rows):

    html = f"<h2>Flight report {run_date}</h2>"

    for r in rows:

        html += f"""
        <p>
        {r['origin']} → BCN<br>
        {r['outbound']} → {r['inbound']}<br>
        {r['price']} €
        </p>
        """

    return html
