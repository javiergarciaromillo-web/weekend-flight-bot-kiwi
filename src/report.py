from __future__ import annotations

from collections import defaultdict


def build_html_report(run_date, rows):
    grouped = defaultdict(list)

    for r in rows:
        grouped[(r["outbound"], r["inbound"])].append(r)

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background:#f5f6f7; color:#222; margin:0; padding:20px;">
        <div style="max-width:900px; margin:0 auto; background:#fff; border:1px solid #ddd;">
          <div style="padding:16px 20px; border-bottom:1px solid #e5e5e5;">
            <div style="font-size:12px; color:#666;">Weekend Flight Bot</div>
            <div style="font-size:22px; font-weight:700; margin-top:4px;">Daily flight report</div>
            <div style="font-size:13px; color:#666; margin-top:6px;">Run date: {run_date.isoformat()}</div>
          </div>
    """

    if not rows:
        html += """
          <div style="padding:20px;">
            <div style="font-size:18px; font-weight:700;">No flights found</div>
            <div style="margin-top:8px; color:#666;">Review the debug artifacts from GitHub Actions.</div>
          </div>
        """
    else:
        for (outbound, inbound), items in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
            items = sorted(items, key=lambda x: x["price"])
            best = items[0]

            html += f"""
              <div style="padding:18px 20px; border-top:1px solid #ececec; background:#fafafa;">
                <div style="font-size:18px; font-weight:700;">
                  {best['origin']} → BCN | {outbound.isoformat()} → {inbound.isoformat()}
                </div>
                <div style="margin-top:6px; font-size:14px; color:#444;">
                  Best price: <strong>{best['price']:.2f} EUR</strong>
                </div>
              </div>
            """

            for idx, item in enumerate(items[:3], start=1):
                html += f"""
                  <div style="padding:14px 20px; border-top:1px solid #f0f0f0;">
                    <div style="font-size:14px; font-weight:700;">
                      {idx}) {item.get('airline', 'Unknown')} — {item['price']:.2f} EUR
                    </div>
                    <div style="margin-top:6px; font-size:13px; color:#333;">
                      OUT {item.get('outbound_departure', 'N/A')} - {item.get('outbound_arrival', 'N/A')}
                    </div>
                    <div style="margin-top:4px; font-size:12px; color:#666;">
                      {item.get('page_title', '')}
                    </div>
                    <div style="margin-top:4px; font-size:12px;">
                      <a href="{item.get('source_url', '#')}">Open result</a>
                    </div>
                  </div>
                """

    html += """
        </div>
      </body>
    </html>
    """

    return html
