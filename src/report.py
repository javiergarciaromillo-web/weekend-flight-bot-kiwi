def _build_long_range_opportunities() -> str:
    opportunities = get_latest_learning_opportunities(limit=10)

    if not opportunities:
        return ""

    html = """
      <div style="margin:12px; border:1px solid #dcdcdc; border-radius:10px; overflow:hidden;">
        <div style="padding:12px 14px; background:#fafafa; border-bottom:1px solid #ececec;">
          <div style="font-size:18px; font-weight:700;">Long-range opportunities</div>
          <div style="font-size:12px; color:#666; margin-top:4px;">
            Cheapest sampled future weekends at 30–150 days ahead. KLM is allowed here only for AMS.
          </div>
        </div>
    """

    for item in opportunities:
        outbound_link = item.get("outbound_source_url") or "#"
        inbound_link = item.get("inbound_source_url") or "#"

        html += f"""
          <div style="padding:12px 14px; border-bottom:1px solid #f1f1f1;">
            <div style="font-size:14px; font-weight:700;">
              {item['outbound']} → {item['inbound']} |
              {item['pattern']} |
              {item['days_to_departure']} days out |
              Combo: {_fmt_price_compact(item['best_combo'])}
            </div>

            <div style="margin-top:8px; display:grid; grid-template-columns:1fr 1fr; gap:10px;">
              <div style="padding:8px 10px; border:1px solid #ececec; border-radius:8px; background:#fff;">
                <div style="font-size:12px; font-weight:700;">Outbound</div>
                <div style="margin-top:4px; font-size:12px;">
                  {item.get('outbound_origin') or '—'}→{item.get('outbound_destination') or '—'} |
                  {item.get('outbound_airline') or '—'} |
                  {item.get('outbound_departure_time') or '—'}-{item.get('outbound_arrival_time') or '—'} |
                  {_fmt_price_compact(item.get('best_outbound'))}
                </div>
                <div style="margin-top:4px; font-size:11px;">
                  <a href="{outbound_link}">Abrir ida</a>
                </div>
              </div>

              <div style="padding:8px 10px; border:1px solid #ececec; border-radius:8px; background:#fff;">
                <div style="font-size:12px; font-weight:700;">Inbound</div>
                <div style="margin-top:4px; font-size:12px;">
                  {item.get('inbound_origin') or '—'}→{item.get('inbound_destination') or '—'} |
                  {item.get('inbound_airline') or '—'} |
                  {item.get('inbound_departure_time') or '—'}-{item.get('inbound_arrival_time') or '—'} |
                  {_fmt_price_compact(item.get('best_inbound'))}
                </div>
                <div style="margin-top:4px; font-size:11px;">
                  <a href="{inbound_link}">Abrir vuelta</a>
                </div>
              </div>
            </div>
          </div>
        """

    html += "</div>"
    return html
