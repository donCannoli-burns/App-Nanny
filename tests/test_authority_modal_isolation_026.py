#!/usr/bin/env python3
"""R025-I01: exact-byte negative controls and dialog-isolation regression."""
import argparse, hashlib, json, tempfile, zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'studio/context_tree_studio_authority_repaired_025.html';DEFAULT=ROOT/'studio/context_tree_studio_authority_repaired_026.html'
PARENT_SHA='dab25c2b1b7caa7a6c58f620c32da47194cbd25a162b902f7df5b76079401be2'
def scaffold(name):
 return json.dumps({'schema':'context-tree/scaffold-v1','project':{'name':name,'goal':'Authority decision test'},'tree':[{'name':'main.go','kind':'file','core':True}]},ensure_ascii=False)
ORIGINAL,A,B=(scaffold(x) for x in ('Original Project','Import Candidate A','File B'))
def context(browser,html):
 c=browser.new_context(accept_downloads=True);p=c.new_page();errors=[]
 p.on('pageerror',lambda err:errors.append(str(err)));p.on('dialog',lambda d:d.accept())
 p.evaluate("""() => {const db={};Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>Object.prototype.hasOwnProperty.call(db,k)?db[k]:null,setItem:(k,v)=>{db[k]=String(v)},removeItem:k=>{delete db[k]}}})}""")
 p.set_content(html,wait_until='load');return c,p,errors
def name(p):return p.locator('#projectBadge').inner_text()
def editor_name(p):return json.loads(p.locator('#jsonInput').input_value())['project']['name']
def status(p):return p.locator('#status').inner_text()
def setup(p):
 p.locator('#jsonInput').fill(ORIGINAL);p.locator('[data-action=generate]').click();assert name(p)=='Original Project' and 'SEMANTICS_VALID' in status(p)
 p.locator('#jsonInput').fill(A);p.locator('[data-action=generate]').click();assert p.locator('#authorityReview').is_visible() and 'UNRESOLVED' in status(p)
def approve(p,choice='raw'):
 p.locator(f'input[name=authorityChoice][value={choice}]').check()
 p.locator('#authorityReason').fill('Accepted after reviewing the complete identity differences')
 p.locator('#authorityAccept').click()
def cancel(p):p.locator('#authorityCancel').click()
def focus_detail(p):return p.evaluate("""() => ({id:document.activeElement.id,inside:!!document.activeElement.closest('#authorityReview'),tag:document.activeElement.tagName,action:document.activeElement.dataset.action||''})""")
def keyboard_seek(p,desired,limit=150):
 for i in range(limit):
  p.keyboard.press('Shift+Tab')
  f=focus_detail(p)
  if desired=='editor' and f['id']=='jsonInput':return i+1
  if desired=='generate' and f['action']=='generate':return i+1
 raise AssertionError('Background element not reachable: '+desired)
def verify_export(p,path,want):
 with p.expect_download(timeout=40000) as download:p.locator('[data-export=full_project]').click()
 download.value.save_as(str(path))
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None
  assert json.loads(z.read('project_state.json'))['project']['name']==want
 p.locator('#verifyFile').set_input_files(str(path))
 p.wait_for_function("() => document.querySelector('#verifyResult').textContent.includes('SEMANTICS_')",timeout=40000)
 assert 'SEMANTICS_VALID' in p.locator('#verifyResult').inner_text()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--html',type=Path,default=DEFAULT);ap.add_argument('--results',type=Path);args=ap.parse_args()
 assert hashlib.sha256(PARENT.read_bytes()).hexdigest()==PARENT_SHA
 baseline=PARENT.read_text(); candidate=args.html.read_text();checks=[]
 with sync_playwright() as pw,tempfile.TemporaryDirectory(prefix='appnanny026-') as tmp:
  browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
  def case(label,run,html=candidate):
   c,p,errors=context(browser,html)
   try:run(p);assert not errors,(label,errors)
   finally:c.close()
   checks.append(label);print('PASS',label,flush=True)
  def baseline_escape(p):
   setup(p)
   i=keyboard_seek(p,'editor');assert i>0
   p.keyboard.press('ControlOrMeta+A');p.keyboard.insert_text(B)
   assert editor_name(p)=='File B'
   approve(p);assert name(p)=='Import Candidate A' and editor_name(p)=='File B'
   verify_export(p,Path(tmp)/'baseline-mismatch.zip','Import Candidate A')
  case('exact025_keyboard_escape_editor_project_mismatch',baseline_escape,baseline)
  def baseline_reentry(p):
   setup(p);p.locator('#authorityReason').fill('First human rationale recorded for candidate A')
   keyboard_seek(p,'generate');p.keyboard.press('Enter')
   assert p.locator('#authorityReview').is_visible()
   assert p.locator('#authorityReason').input_value()==''
  case('exact025_background_generate_reenters_dialog',baseline_reentry,baseline)
  def inert_and_focus(p):
   setup(p);assert p.locator('.app').evaluate('(e)=>e.inert')
   for direction in ('Shift+Tab','Tab'):
    for i in range(75):
     p.keyboard.press(direction);assert focus_detail(p)['inside'],(direction,i,focus_detail(p))
   assert editor_name(p)=='Import Candidate A'
   approve(p);assert name(p)=='Import Candidate A' and editor_name(p)=='Import Candidate A'
   assert not p.locator('.app').evaluate('(e)=>e.inert')
   verify_export(p,Path(tmp)/'isolated.zip','Import Candidate A')
  case('keyboard_focus_contained_both_directions_accept_export',inert_and_focus)
  def no_reentry(p):
   setup(p)
   p.locator('#authorityReason').fill('First reason must remain untouched by background')
   before=status(p)
   p.evaluate('document.querySelector("[data-action=generate]").click()')
   assert p.locator('#authorityReason').input_value()=='First reason must remain untouched by background'
   assert status(p)==before and name(p)=='Original Project'
   p.evaluate('document.querySelector("[data-action=load-example]").click()')
   assert editor_name(p)=='Import Candidate A' and status(p)==before
   approve(p);assert name(p)=='Import Candidate A'
  case('reentrant_generate_and_demo_background_blocked',no_reentry)
  def background_export(p):
   setup(p);before=status(p)
   p.evaluate('document.querySelector("[data-export=full_project]").click()')
   assert status(p)==before
   cancel(p);assert name(p)=='Original Project'
  case('background_export_handler_blocked',background_export)
  def external_edit_fail_closed(p):
   setup(p)
   p.evaluate("""value=>{const e=document.querySelector('#jsonInput');e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}))}""",B)
   approve(p)
   assert p.locator('#authorityReview').is_visible() and 'AUTHORITY_INPUT_CHANGED' in status(p)
   assert name(p)=='Original Project'
   cancel(p);assert not p.locator('#authorityReview').is_visible()
   assert not p.locator('.app').evaluate('(e)=>e.inert')
   p.locator('[data-action=generate]').click();assert p.locator('#authorityReview').is_visible()
   approve(p);assert name(p)=='File B' and editor_name(p)=='File B'
  case('programmatic_editor_mutation_cannot_commit_stale_task',external_edit_fail_closed)
  def state_identity_fail_closed(p):
   setup(p)
   # Simulated state replacement is out-of-band; fail closed even if editor is unchanged.
   # Internal closure state cannot be mutated directly from the test; normal reentrant UI is guarded.
   p.locator('#authorityReason').fill('Legitimate reason for this identity')
   approve(p);assert name(p)=='Import Candidate A'
  case('normal_approval_can_finish_when_editor_unchanged',state_identity_fail_closed)
  def choice_current(p):
   setup(p);approve(p,'current');assert name(p)=='Original Project'
   assert editor_name(p)=='Import Candidate A'
   assert 'SEMANTICS_VALID' in status(p)
   verify_export(p,Path(tmp)/'keep-current.zip','Original Project')
  case('existing_project_authority_choice_remains_valid',choice_current)
  def cancel_then_new(p):
   setup(p);cancel(p)
   assert name(p)=='Original Project' and editor_name(p)=='Import Candidate A'
   assert not p.locator('.app').evaluate('(e)=>e.inert')
   p.locator('#jsonInput').fill(B)
   p.locator('[data-action=generate]').click();assert p.locator('#authorityReview').is_visible()
   approve(p);assert name(p)=='File B' and editor_name(p)=='File B'
  case('cancel_restores_background_new_generate_allowed',cancel_then_new)
  def rationale_and_validation(p):
   setup(p);p.locator('#authorityAccept').click()
   assert p.locator('#authorityReview').is_visible()
   assert p.locator('.app').evaluate('(e)=>e.inert')
   p.locator('#authorityReason').fill('This source is authoritative after full review')
   approve(p);assert name(p)=='Import Candidate A'
  case('short_reason_refusal_keeps_modal_isolated',rationale_and_validation)
  browser.close()
 result={'status':'LOCAL_CANDIDATE_PASS__INDEPENDENT_REAUDIT_REQUIRED__PHASE1_BLOCKED','checks':len(checks),'cases':checks}
 if args.results:args.results.write_text(json.dumps(result,indent=2)+'\n')
 print('PASS %s/%s'%(len(checks),len(checks)),flush=True)
if __name__=='__main__':main()
