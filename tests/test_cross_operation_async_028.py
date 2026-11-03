#!/usr/bin/env python3
"""Repair 028: exact Repair 027 export/Restore concurrency negative controls."""
import argparse,hashlib,json,tempfile,zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'studio/context_tree_studio_authority_repaired_027.html'
NEW=ROOT/'studio/context_tree_studio_authority_repaired_028.html'
OLD_SHA='9985d4182d1b0835fcea640005fe1558ca161a4fc03729d94e9585d2c4fd2c7b'
def scaffold(name):
 return json.dumps({'schema':'context-tree/scaffold-v1','project':{'name':name,'goal':'Cross-operation Restore race'},'tree':[{'name':'main.go','kind':'file','core':True}]})
ORIG=scaffold('Original Project');C=scaffold('Restore Candidate C')
INJECT='''
const __sha028=sha256,__held028=[];
window.test028={arm:(mode='any')=>{window.__armed028=mode},pending:()=>__held028.length,
 release:()=>{const p=__held028.shift();if(!p)throw Error('No hash');p()},busy:()=>busy,
 mutate:goal=>{state.project.goal=goal}};
sha256=async function(...args){const b=args[0] instanceof Uint8Array?args[0]:new Uint8Array(args[0]);
 if(window.__armed028==='any'||(window.__armed028==='zip'&&b[0]===80&&b[1]===75)){
  window.__armed028=null;return await new Promise(resolve=>__held028.push(()=>__sha028(...args).then(resolve)))}
 return await __sha028(...args)};
'''
def page(browser,html):
 ctx=browser.new_context(accept_downloads=True);p=ctx.new_page();errors=[];downloads=[]
 p.on('pageerror',lambda e:errors.append(str(e)))
 p.on('download',lambda d:downloads.append(d.suggested_filename))
 p.on('dialog',lambda d:d.accept())
 p.evaluate('''() => {let d={};Object.defineProperty(window,'localStorage',{configurable:true,value:{
 getItem:k=>Object.prototype.hasOwnProperty.call(d,k)?d[k]:null,
 setItem:(k,v)=>{d[k]=String(v)},removeItem:k=>{delete d[k]}}})}''')
 assert html.count('init();\n})();')==1
 p.set_content(html.replace('init();\n})();',INJECT+'\ninit();\n})();'),wait_until='load')
 return ctx,p,errors,downloads
def status(p):return p.locator('#status').inner_text()
def ledger(p):return p.locator('#ledger').inner_text()
def modal(p):return p.locator('#authorityReview').is_visible()
def generate(p,s):p.locator('#jsonInput').fill(s);p.locator('[data-action=generate]').click()
def original(p):
 generate(p,ORIG)
 assert p.locator('#projectBadge').inner_text()=='Original Project' and 'SEMANTICS_VALID' in status(p)
def accept(p,choice='raw'):
 p.locator('input[name=authorityChoice][value='+choice+']').check()
 p.locator('#authorityReason').fill('Human approved the authoritative project definition after review.')
 p.locator('#authorityAccept').click(no_wait_after=True,timeout=10000)
def conflict_zip(browser,old,path):
 ctx,p,err,_=page(browser,old)
 try:
  original(p);generate(p,C);assert modal(p)
  accept(p,'current');assert not modal(p)
  with p.expect_download(timeout=40000) as d:p.locator('[data-export=full_project]').click()
  d.value.save_as(str(path))
  with zipfile.ZipFile(path) as z:
   assert z.testzip() is None
   st=json.loads(z.read('project_state.json'))
   assert st['project']['name']=='Original Project'
   assert json.loads(st['raw'])['project']['name']=='Restore Candidate C'
  assert not err,err
 finally:ctx.close()
 return path.read_bytes()
def start_export(p,kind,mode='any'):
 p.evaluate('(m)=>window.test028.arm(m)',mode)
 if kind=='ledger':p.locator('[data-action=download-ledger]').click()
 else:p.locator('[data-export='+kind+']').click()
 p.wait_for_function('()=>window.test028.pending()===1',timeout=30000)
def resume(p):
 p.evaluate('()=>window.test028.release()')
 p.wait_for_function('()=>window.test028.busy()===false',timeout=30000)
def restore_dialog(p,data):
 p.locator('#restoreFile').set_input_files({'name':'conflict.zip','mimeType':'application/zip','buffer':data})
 p.wait_for_function('()=>!document.querySelector("#authorityReview").classList.contains("hidden")',timeout=40000)
 assert 'UNRESOLVED_IDENTITY_CONFLICT' in status(p)
def main():
 a=argparse.ArgumentParser();a.add_argument('--html',type=Path,default=NEW);a.add_argument('--results',type=Path);args=a.parse_args()
 assert hashlib.sha256(OLD.read_bytes()).hexdigest()==OLD_SHA
 old=OLD.read_text();new=args.html.read_text();checks=[]
 with tempfile.TemporaryDirectory() as tmp,sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  fixture=conflict_zip(browser,old,Path(tmp)/'conflict.zip')
  def case(name,fn,source=new):
   ctx,p,errors,downloads=page(browser,source)
   try:fn(p,downloads);assert not errors,(name,errors)
   finally:ctx.close()
   checks.append(name);print('PASS',name,flush=True)
  for kind in ('tree_raw','ledger'):
   def negative_success(p,downloads):
    original(p);start_export(p,kind);restore_dialog(p,fixture);resume(p)
    assert modal(p) and status(p).startswith('Exported ') and kind in ledger(p) and downloads
   case('original027_'+kind+'_late_receipt_crosses_dialog',negative_success,old)
   def negative_failure(p,downloads):
    original(p);start_export(p,kind)
    p.locator('#proj-goal').fill('Newer human metadata')
    restore_dialog(p,fixture);resume(p)
    assert modal(p) and 'export failed:' in status(p).lower()
   case('original027_'+kind+'_late_error_masks_dialog',negative_failure,old)
   def guarded_success(p,downloads):
    original(p);start_export(p,kind);restore_dialog(p,fixture);before=status(p);resume(p)
    assert modal(p) and status(p)==before and ledger(p)=='No exports yet.' and not downloads
    accept(p);assert not modal(p) and 'Restored' in status(p)
   case('candidate_'+kind+'_stale_success_suppressed',guarded_success)
   def guarded_failure(p,downloads):
    original(p);start_export(p,kind)
    p.locator('#proj-goal').fill('Newer human metadata')
    restore_dialog(p,fixture);before=status(p);resume(p)
    assert modal(p) and status(p)==before and not downloads
   case('candidate_'+kind+'_stale_failure_suppressed',guarded_failure)
  def late_accepted(p,downloads):
   original(p);start_export(p,'tree_raw');restore_dialog(p,fixture)
   accept(p);before=status(p);resume(p)
   assert status(p)==before and not modal(p) and not downloads
  case('candidate_after_restore_accept_export_discarded',late_accepted)
  def late_cancelled(p,downloads):
   original(p);start_export(p,'ledger');restore_dialog(p,fixture)
   p.locator('#authorityCancel').click();before=status(p);resume(p)
   assert status(p)==before and not downloads
  case('candidate_after_restore_cancel_ledger_discarded',late_cancelled)
  def fresh_export(p,downloads):
   original(p);p.locator('[data-export=tree_raw]').click();p.wait_for_function('()=>document.querySelector("#ledger").textContent.includes("tree_raw")')
   assert len(downloads)==1
   restore_dialog(p,fixture);assert modal(p)
  case('candidate_export_completed_before_restore_permitted',fresh_export)
  def ordinary_failure(p,downloads):
   original(p);start_export(p,'tree_raw')
   p.locator('#proj-goal').fill('Different goal');resume(p)
   assert 'Export failed:' in status(p) and not downloads
  case('candidate_stale_export_without_dialog_shows_error',ordinary_failure)
  def restore_guard(p,downloads):
   original(p);restore_dialog(p,fixture)
   p.evaluate('()=>window.test028.mutate("Out of band changed goal")')
   accept(p)
   assert modal(p) and 'AUTHORITY_INPUT_CHANGED' in status(p)
   p.locator('#authorityCancel').click();restore_dialog(p,fixture)
   accept(p);assert not modal(p) and 'Restored' in status(p)
  case('candidate_restore_origin_task_rechecks_project_state',restore_guard)
  def provisional(p,downloads):
   original(p);start_export(p,'full_project','zip')
   restore_dialog(p,fixture);before=status(p);resume(p)
   assert status(p)==before and modal(p) and not downloads and ledger(p)=='No exports yet.'
   accept(p)
   assert modal(p) and 'AUTHORITY_INPUT_CHANGED' in status(p)
  case('candidate_full_zip_pending_receipt_rollback_requires_reauth',provisional)
  def ledger_after_cancel(p,downloads):
   original(p);restore_dialog(p,fixture)
   p.locator('#authorityCancel').click()
   p.locator('[data-action=download-ledger]').click()
   p.wait_for_function('()=>document.querySelector("#ledger").textContent.includes("export_ledger")')
   assert len(downloads)==1
  case('candidate_fresh_ledger_after_cancel_allowed',ledger_after_cancel)
  browser.close()
 data={'passed':len(checks),'cases':checks,'status':'LOCAL_CANDIDATE_PASS__INDEPENDENT_REAUDIT_REQUIRED__PHASE1_BLOCKED'}
 if args.results:args.results.write_text(json.dumps(data,indent=2)+'\n')
 print(f'PASS {len(checks)}/{len(checks)}',flush=True)
if __name__=='__main__':main()
