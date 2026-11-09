import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src.puente import apply_feedback,validate_feedback,feedback_html,pull,push,local_feedback,upload_bundle

class BridgeTests(unittest.TestCase):
 def test_no_feedback_keeps_plan_and_email(self):
  plan={'required_from':'2027-02-01','weekends':{'2027-12-25':'holiday_break'}}
  self.assertEqual(apply_feedback(plan,{}),plan);self.assertEqual(feedback_html({}),'')
 def test_buy_intent_never_marks_booking(self):
  self.assertEqual(apply_feedback({'weekends':{}},{'choices':{'2027-02-04|2027-02-07':{'action':'Comprar ahora'}}}),{'weekends':{}})
 def test_dated_states_preserve_others(self):
  self.assertEqual(apply_feedback({'weekends':{'2027-12-25':'holiday_break'}},{'weekends':{'2027-02-06':'visiting_nl'}})['weekends'],{'2027-12-25':'holiday_break','2027-02-06':'visiting_nl'})
 def test_invalid_feedback_rejected(self):
  for f in [{'weekends':{'2027-02-05':'booked'}},{'choices':{'bad':{'action':'Vigilar'}}},{'choices':{'2027-02-04|2027-02-07':{'action':'Vigilar','threshold':-1}}}]:
   with self.assertRaises(ValueError):validate_feedback(f)
 def test_html_is_escaped(self):
  self.assertIn('&lt;script&gt;',feedback_html({'choices':{'2027-02-04|2027-02-07':{'action':'Vigilar','notes':'<script>'}}}))
 @patch.dict(os.environ,{},clear=True)
 @patch('src.puente._request')
 def test_missing_secret_no_network(self,request):
  with tempfile.TemporaryDirectory() as d,patch('src.puente.FEEDBACK_PATH',Path(d)/'f.json'):
   pull();push();request.assert_not_called()
 def test_corrupt_feedback_falls_back(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'f.json';p.write_text('{bad')
   with patch('src.puente.FEEDBACK_PATH',p):self.assertEqual(local_feedback(),{})
 @patch.dict(os.environ,{'PUENTE_SITE_TOKEN':'test'})
 @patch('src.puente._request',side_effect=TimeoutError)
 def test_failed_pull_clears_stale_data(self,request):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'f.json';p.write_text('{}')
   with patch('src.puente.FEEDBACK_PATH',p):
    with self.assertRaises(TimeoutError):pull()
    self.assertFalse(p.exists())
 @patch('src.puente._request',side_effect=TimeoutError)
 @patch('src.emailer.send_email_html')
 def test_push_failure_cannot_send_email(self,email,request):
  with self.assertRaises(TimeoutError):upload_bundle({'meta':{'run_id':'test'},'trips':[{}],'history':[]})
  email.assert_not_called();self.assertEqual(request.call_count,1)
 @patch('src.puente._request')
 def test_commit_follows_all_rows(self,request):
  upload_bundle({'meta':{'run_id':'test'},'trips':[{'id':str(i)} for i in range(45)],'history':[{}]})
  self.assertEqual([c.args[1]['kind'] for c in request.call_args_list],['trips','trips','history','commit'])
  self.assertEqual(request.call_args.args[1]['trip_count'],45)
 def test_workflow_keeps_mail_and_backups(self):
  import yaml
  steps=yaml.safe_load(Path('.github/workflows/daily_report.yml').read_text())['jobs']['run-bot']['steps'];names=[s['name'] for s in steps]
  self.assertLess(names.index('Run bot'),names.index('Sync Puente after email (optional)'))
  for n in ['Read Puente preferences (optional)','Sync Puente after email (optional)']:self.assertTrue(steps[names.index(n)]['continue-on-error'])
  for n in ['Save historical DB cache','Upload DB','Upload report and observations']:self.assertIn('always()',steps[names.index(n)]['if'])
  self.assertEqual(steps[names.index('Run bot')]['run'].strip(),'python -m src.main')
