def build_html_report(run_date, rows):

    html = f"<h2>Flight report {run_date}</h2>"

    if not rows:
        html += "<p>No flights found.</p>"
        return html

    for r in rows:
        html += f"""
        <p>
        {r['origin']} → BCN<br>
        {r['outbound']} → {r['inbound']}<br>
        {r['price']} €<br>
        {r.get('page_title', '')}<br>
        <a href="{r.get('source_url', '#')}">open result</a>
        </p>
        """

    return html
