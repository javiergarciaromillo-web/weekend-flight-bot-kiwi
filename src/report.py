from __future__ import annotations

from collections import defaultdict


def build_html_report(run_date, rows):
    grouped = defaultdict(list)

    for row in rows:
        grouped[(row["outbound"], row["inbound"])].append(row)

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background:#f5f6f7; color:#222; margin:0; padding:20px;">
        <div style="max-width:950px; margin:0 auto; background:#fff; border:1px solid #ddd;">
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
          </div>
        """
        html += "</div></body></html>"
        return html

    for (weekend_outbound, weekend_inbound), items in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
        html += f"""
          <div style="padding:18px 20px; border-top:1px solid #d9d9d9; background:#fafafa;">
            <div style="font-size:20px; font-weight:700;">
              Weekend block: {weekend_outbound.isoformat()} → {weekend_inbound.isoformat()}
            </div>
          </div>
        """

        outbound_items = [
            x for x in items
            if x.get("leg_type") == "outbound"
        ]
        inbound_items = [
            x for x in items
            if x.get("leg_type") == "inbound"
        ]

        outbound_grouped = defaultdict(list)
        inbound_grouped = defaultdict(list)

        for row in outbound_items:
            outbound_grouped[(row["origin"], row["destination"], row["leg_date"])].append(row)

        for row in inbound_items:
            inbound_grouped[(row["origin"], row["destination"], row["leg_date"])].append(row)

        html += """
          <div style="padding:16px 20px; border-top:1px solid #ececec;">
            <div style="font-size:18px; font-weight:700;">Outbound options</div>
            <div style="font-size:13px; color:#666; margin-top:4px;">
              Separate one-way options to compose manually
            </div>
          </div>
        """

        if outbound_grouped:
            for (origin, destination, leg_date), group_rows in sorted(outbound_grouped.items(), key=lambda x: (x[0][2], x[0][0])):
                group_rows = sorted(group_rows, key=lambda r: (r["price"], r["outbound_departure"]))
                best = group_rows[0]

                html += f"""
                  <div style="padding:14px 20px; border-top:1px solid #f0f0f0;">
                    <div style="font-size:17px; font-weight:700;">
                      {origin} → {destination} | {leg_date.isoformat()}
                    </div>
                    <div style="margin-top:6px; font-size:14px; color:#444;">
                      Best one-way price: <strong>{best['price']:.2f} EUR</strong>
                    </div>
                """

                for idx, item in enumerate(group_rows[:3], start=1):
                    html += f"""
                      <div style="margin-top:12px; padding-top:10px; border-top:1px dashed #ddd;">
                        <div style="font-size:15px; font-weight:700;">
                          {idx}) {item.get('airline', 'Unknown')} — {item['price']:.2f} EUR
                        </div>
                        <div style="margin-top:4px; font-size:13px; color:#333;">
                          {origin} → {destination}
                        </div>
                        <div style="margin-top:4px; font-size:13px; color:#333;">
                          DEP {item.get('outbound_departure', 'N/A')} | ARR {item.get('outbound_arrival', 'N/A')}
                        </div>
                        <div style="margin-top:4px; font-size:13px; color:#333;">
                          Flight no: {item.get('outbound_flight_no', 'N/A')}
                        </div>
                        <div style="margin-top:4px; font-size:12px; color:#666;">
                          {item.get('page_title', '')}
                        </div>
                        <div style="margin-top:4px; font-size:12px;">
                          <a href="{item.get('source_url', '#')}">Open result</a>
                        </div>
                      </div>
                    """

                html += "</div>"
        else:
            html += """
              <div style="padding:14px 20px; border-top:1px solid #f0f0f0;">
                <div style="font-size:14px; color:#666;">No outbound options found.</div>
              </div>
            """

        html += """
          <div style="padding:16px 20px; border-top:1px solid #ececec;">
            <div style="font-size:18px; font-weight:700;">Inbound options</div>
            <div style="font-size:13px; color:#666; margin-top:4px;">
              Separate one-way options to compose manually
            </div>
          </div>
        """

        if inbound_grouped:
            for (origin, destination, leg_date), group_rows in sorted(inbound_grouped.items(), key=lambda x: (x[0][2], x[0][1])):
                group_rows = sorted(group_rows, key=lambda r: (r["price"], r["outbound_departure"]))
                best = group_rows[0]

                html += f"""
                  <div style="padding:14px 20px; border-top:1px solid #f0f0f0;">
                    <div style="font-size:17px; font-weight:700;">
                      {origin} → {destination} | {leg_date.isoformat()}
                    </div>
                    <div style="margin-top:6px; font-size:14px; color:#444;">
                      Best one-way price: <strong>{best['price']:.2f} EUR</strong>
                    </div>
                """

                for idx, item in enumerate(group_rows[:3], start=1):
                    html += f"""
                      <div style="margin-top:12px; padding-top:10px; border-top:1px dashed #ddd;">
                        <div style="font-size:15px; font-weight:700;">
                          {idx}) {item.get('airline', 'Unknown')} — {item['price']:.2f} EUR
                        </div>
                        <div style="margin-top:4px; font-size:13px; color:#333;">
                          {origin} → {destination}
                        </div>
                        <div style="margin-top:4px; font-size:13px; color:#333;">
                          DEP {item.get('outbound_departure', 'N/A')} | ARR {item.get('outbound_arrival', 'N/A')}
                        </div>
                        <div style="margin-top:4px; font-size:13px; color:#333;">
                          Flight no: {item.get('outbound_flight_no', 'N/A')}
                        </div>
                        <div style="margin-top:4px; font-size:12px; color:#666;">
                          {item.get('page_title', '')}
                        </div>
                        <div style="margin-top:4px; font-size:12px;">
                          <a href="{item.get('source_url', '#')}">Open result</a>
                        </div>
                      </div>
                    """

                html += "</div>"
        else:
            html += """
              <div style="padding:14px 20px; border-top:1px solid #f0f0f0;">
                <div style="font-size:14px; color:#666;">No inbound options found.</div>
              </div>
            """

    html += """
        </div>
      </body>
    </html>
    """

    return html
