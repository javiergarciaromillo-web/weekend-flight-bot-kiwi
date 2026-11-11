"""Optional private KAIROS Site bridge. Existing email, queries and SQLite remain authoritative."""
import argparse
from datetime import date, datetime, timezone
import hashlib
from html import escape
import json
import os
from pathlib import Path
import sqlite3
import urllib.request

SITE = 'https://puente-viajes-javier.javiergarciaromillo.chatgpt.site'
FEEDBACK_PATH = Path('data/puente-feedback.json')

def validate_feedback(data):
    from src.travel_plan import ALL_STATES
    if not isinstance(data,dict): raise ValueError('Invalid feedback')
    for day,state in data.get('weekends',{}).items():
        if date.fromisoformat(day).weekday()!=5 or state not in ALL_STATES: raise ValueError('Invalid weekend')
    for key,c in data.get('choices',{}).items():
        a,b=key.split('|')
        if date.fromisoformat(a)>=date.fromisoformat(b) or c.get('action') not in ('Comprar ahora','Vigilar','Descartar'): raise ValueError('Invalid choice')
        if not isinstance(c.get('notes',''),str) or len(c.get('notes',''))>4000: raise ValueError('Invalid notes')
        t=c.get('threshold')
        if t is not None and (type(t) not in (int,float) or not 0<=t<=100000): raise ValueError('Invalid threshold')
    return data

def local_feedback():
    try: return validate_feedback(json.loads(FEEDBACK_PATH.read_text())) if FEEDBACK_PATH.exists() else {}
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        print('[WARN] Invalid KAIROS feedback ignored; original bot continues.')
        return {}

def apply_feedback(plan, feedback):
    validate_feedback(feedback)
    return {**plan,'weekends':{**plan.get('weekends',{}),**feedback.get('weekends',{})}}

def feedback_html(feedback):
    if not feedback.get('choices') and not feedback.get('weekends'): return ''
    parts=['<section><h2>Tus decisiones en KAIROS</h2><p>Preferencias personales; comprar ahora no equivale a una reserva. Umbrales de tarifa ida y vuelta, sin extras desconocidos.</p>']
    for key,c in sorted(feedback.get('choices',{}).items()):
        parts.append(f'<p><b>{escape(key.replace("|"," → "))}: {escape(c["action"])}</b>')
        if c.get('threshold') is not None: parts.append(f' · Umbral: {c["threshold"]:.2f} €')
        parts.append(f'<br>{escape(c.get("notes",""))}</p>')
    for day,state in sorted(feedback.get('weekends',{}).items()): parts.append(f'<p>{escape(day)}: {escape(state)}</p>')
    return ''.join(parts)+'</section>'

def _request(path,payload=None):
    token=os.environ.get('PUENTE_SITE_TOKEN')
    if not token: raise RuntimeError('Missing Site token')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs): return None
    req=urllib.request.Request(SITE+path,headers={'OAI-Sites-Authorization':'Bearer '+token,'X-Puente-Service-Key':token,'Content-Type':'application/json'},data=None if payload is None else json.dumps(payload,ensure_ascii=False,default=str).encode())
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=45) as r: return json.load(r)

def pull():
    FEEDBACK_PATH.unlink(missing_ok=True)
    if not os.environ.get('PUENTE_SITE_TOKEN'):
        print('[INFO] KAIROS not configured; original bot unchanged.');return
    state=_request('/api/bridge')
    feedback=validate_feedback(state.get('feedback') or {})
    FEEDBACK_PATH.parent.mkdir(parents=True,exist_ok=True)
    FEEDBACK_PATH.write_text(json.dumps(feedback,ensure_ascii=False))
    print('[INFO] KAIROS preferences loaded; revision',state.get('feedbackVersion',0))

def build_bundle(report,db_path=Path('data/prices.db')):
    from src.market_learning import comparable_price,booking_window_evidence,market_movement
    from src.budget import trip_work_dates,assess_remote_plan,annual_tt_outlook,projected_annual_tt
    from src.family import weekend_of
    from src.holidays import holiday_dates
    from src.planner import allowed_pair
    from src.decisions import FILTER_VERSION,POLICY_VERSION
    with sqlite3.connect(db_path) as conn:
        conn.row_factory=sqlite3.Row
        history=[dict(r) for r in conn.execute('SELECT * FROM booking_decisions ORDER BY run_date,outbound,inbound')]
    as_of=date.fromisoformat(report['run_date'])
    past=[h for h in history if h['run_date']<str(as_of) and h['filter_version']==FILTER_VERSION and h['coverage_complete'] and h['price'] is not None]
    decisions={(d['outbound'],d['inbound']):d for d in report.get('decisions',[])}
    trips=[];outlook=annual_tt_outlook(report.get('family_plan',{}))
    for a,b in report['pairs']:
        out,inc=date.fromisoformat(a),date.fromisoformat(b)
        if not allowed_pair(out,inc): continue
        rows=[r for r in report['flights'] if r['outbound']==a and r['inbound']==b]
        legs={k:[{f:v for f,v in r.items() if f not in ('raw_text','page_title')} for r in rows if r['leg_type']==k] for k in ('outbound','inbound')}
        fare=sum(min(r['price'] for r in legs[k]) for k in legs) if all(legs.values()) else None
        trip=dict(outbound=out,inbound=inc,out=legs['outbound'],inc=legs['inbound'])
        days,notes=trip_work_dates(trip);holiday=bool(holiday_dates(out,inc))
        trips.append(dict(id=a+'|'+b,outbound=a,inbound=b,fare=fare,total=None,extras_status='unknown',legs=legs,decision=decisions.get((a,b)),market=comparable_price(out,inc,fare,holiday,past,as_of),booking_window=booking_window_evidence(past,as_of,travel_month=out.month,weekday_pattern=(out.weekday(),inc.weekday()),holiday=holiday),tt=assess_remote_plan(days),workdates=[str(d) for d in days],tt_notes=notes,annual=projected_annual_tt(days,[weekend_of(out)],outlook),weekend=str(weekend_of(out)),holiday=holiday))
    rid=str(os.environ.get('GITHUB_RUN_ID') or 'backfill-'+report['run_date'])+'-'+str(os.environ.get('GITHUB_RUN_ATTEMPT','1'))
    meta={k:v for k,v in report.items() if k not in ('flights','decisions')}
    meta.update(run_id=rid,source_repository='javiergarciaromillo-web/weekend-flight-bot-kiwi',source_commit=os.environ.get('GITHUB_SHA'),imported_at=datetime.now(timezone.utc).isoformat(),policy_version=POLICY_VERSION,filter_version=FILTER_VERSION,market_movement=market_movement(past,as_of),annual_outlook=outlook,feedback_revision=local_feedback().get('revision',0),fuel={'status':'unknown','note':'Sin serie de combustible validada.'})
    return dict(meta=meta,trips=trips,history=history)

def upload_bundle(bundle):
    rid=bundle['meta']['run_id']
    for kind in ('trips','history'):
        values=bundle[kind]
        for i in range(0,len(values),40): _request('/api/bridge',{'kind':kind,'run_id':rid,'items':values[i:i+40]})
    _request('/api/bridge',{'kind':'commit','run_id':rid,'meta':bundle['meta'],'trip_count':len(bundle['trips']),'history_count':len(bundle['history']),'digest':hashlib.sha256(json.dumps(bundle,sort_keys=True,default=str).encode()).hexdigest()})
    print('[INFO] KAIROS synchronized:',len(bundle['trips']),'journeys;',len(bundle['history']),'historical decisions.')

def push():
    if not os.environ.get('PUENTE_SITE_TOKEN'):
        print('[INFO] KAIROS not configured; email and DB unchanged.');return
    path=Path('data/report/report.json')
    if not path.exists(): raise RuntimeError('No current report')
    upload_bundle(build_bundle(json.loads(path.read_text())))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['pull','push']);args=p.parse_args()
    try: (pull if args.operation=='pull' else push)()
    except Exception as exc:
        print('[WARN] KAIROS synchronization failed:',type(exc).__name__,'. Email bot remains independent.')
        raise SystemExit(1)
