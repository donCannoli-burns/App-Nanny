#!/usr/bin/env python3
"""R026-I01: controlled asynchronous Restore crossing newer authority decisions.

Runs against exact frozen Repair 026 (negative controls) and repaired candidate.
Uses actual app-generated ZIP bytes, app's verifier, File.arrayBuffer deferrals,
real Generate / dialog controls, and isolated in-memory storage.
"""
import argparse, hashlib, json, tempfile, zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'studio/context_tree_studio_authority_repaired_026.html'
CANDIDATE = ROOT / 'studio/context_tree_studio_authority_repaired_027.html'
BASE_SHA = '0f3b37f2c0f8f1ec5d2046a5ee11fa73323b715161b6f065751363f9382f6a98'

def scaffold(name):
    return json.dumps({'schema':'context-tree/scaffold-v1','project':{'name':name,'goal':'Bounded restore transaction freshness test'},'tree':[{'name':'main.go','kind':'file','core':True}]})

ORIGINAL, A, C = [scaffold(x) for x in ('Original Project', 'Import Candidate A', 'Restore Candidate C')]

def context(browser, html):
    c=browser.new_context(accept_downloads=True)
    p=c.new_page()
    errors=[]
    p.on('pageerror', lambda e: errors.append(str(e)))
    p.on('dialog',lambda d:d.accept())
    p.evaluate("""() => {
      const db={};
      Object.defineProperty(window,'localStorage',{configurable:true,value:{
        getItem:k=>Object.prototype.hasOwnProperty.call(db,k)?db[k]:null,
        setItem:(k,v)=>{db[k]=String(v)},removeItem:k=>{delete db[k]}
      }});
      const nativeRead=File.prototype.arrayBuffer,waiters=[];
      window.restoreRead={
        pending:()=>waiters.filter(x=>!x.done).map(x=>x.name),
        resolve:(name,bytes)=>{const x=waiters.find(x=>x.name===name&&!x.done);if(!x)throw Error('No read '+name);x.done=true;x.resolve(Uint8Array.from(bytes).buffer)},
        reject:(name,reason)=>{const x=waiters.find(x=>x.name===name&&!x.done);if(!x)throw Error('No read '+name);x.done=true;x.reject(Error(reason))},
      };
      File.prototype.arrayBuffer=function(){
        if(!this.name.startsWith('held-'))return nativeRead.call(this);
        return new Promise((resolve,reject)=>waiters.push({name:this.name,resolve,reject,done:false}));
      };
    }""")
    p.set_content(html,wait_until='load')
    return c,p,errors

def badge(p):return p.locator('#projectBadge').inner_text()
def editor(p):return json.loads(p.locator('#jsonInput').input_value())['project']['name']
def status(p):return p.locator('#status').inner_text()
def settle(p):p.evaluate('() => new Promise(r=>setTimeout(r,0))')
def generate(p,content):
    p.locator('#jsonInput').fill(content)
    p.locator('[data-action=generate]').click()

def create_fixture(browser, html, path):
    ctx,p,errors=context(browser,html)
    try:
        generate(p,C)
        assert badge(p)=='Restore Candidate C' and 'SEMANTICS_VALID' in status(p),status(p)
        with p.expect_download(timeout=45000) as dl:p.locator('[data-export=full_project]').click()
        dl.value.save_as(str(path))
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            assert json.loads(z.read('project_state.json'))['project']['name']=='Restore Candidate C'
        assert not errors, errors
    finally:ctx.close()
    return path.read_bytes()

def setup_original(p):
    generate(p,ORIGINAL)
    assert badge(p)=='Original Project' and 'SEMANTICS_VALID' in status(p)

def dialog_A(p):
    generate(p,A)
    assert p.locator('#authorityReview').is_visible() and 'UNRESOLVED' in status(p), status(p)

def accept_A(p):
    p.locator('#authorityReason').fill('Human accepted candidate A, superseding pending restore')
    p.locator('#authorityAccept').click()
    assert not p.locator('#authorityReview').is_visible()
    assert badge(p)=='Import Candidate A', (badge(p),status(p))

def cancel_A(p):
    p.locator('#authorityCancel').click()
    assert not p.locator('#authorityReview').is_visible()

def start_restore(p, czip, name='held-c.zip'):
    p.locator('#restoreFile').set_input_files({'name':name,'mimeType':'application/zip','buffer':czip})
    p.wait_for_function('(n) => window.restoreRead.pending().includes(n)',arg=name,timeout=10000)
    assert p.locator('#restoreFile').input_value()==''

def finish_restore(p, czip,name='held-c.zip'):
    p.evaluate('([n,b])=>window.restoreRead.resolve(n,b)', [name,list(czip)])
    p.wait_for_timeout(250)

def fail_restore(p,name='held-c.zip'):
    p.evaluate('n=>window.restoreRead.reject(n,"HELD_RESTORE_IO_FAILURE")',name)
    settle(p)

def run_case(browser, html, label, fn, rows):
    ctx,p,errors=context(browser,html)
    try:
        fn(p)
        assert not errors,(label,errors)
    finally:ctx.close()
    rows.append(label)
    print('PASS',label,flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--html',type=Path,default=CANDIDATE)
    parser.add_argument('--results',type=Path)
    parser.add_argument('--baseline-only',action='store_true')
    args=parser.parse_args()
    assert hashlib.sha256(BASE.read_bytes()).hexdigest()==BASE_SHA
    base=BASE.read_text(encoding='utf-8')
    candidate=args.html.read_text(encoding='utf-8') if not args.baseline_only else base
    results=[]
    with tempfile.TemporaryDirectory(prefix='appnanny027-') as temp, sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        czip=create_fixture(browser,base,Path(temp)/'valid-C.zip')
        def baseline_after_accept(p):
            setup_original(p);start_restore(p,czip);dialog_A(p);accept_A(p)
            finish_restore(p,czip)
            assert badge(p)=='Restore Candidate C' and editor(p)=='Restore Candidate C',(badge(p),editor(p),status(p))
        run_case(browser,base,'negative_exact026_restore_commits_after_A_accept',baseline_after_accept,results)
        def baseline_during_dialog(p):
            setup_original(p);start_restore(p,czip);dialog_A(p)
            finish_restore(p,czip)
            assert badge(p)=='Restore Candidate C' and p.locator('#authorityReview').is_visible(),(badge(p),status(p))
        run_case(browser,base,'negative_exact026_restore_commits_during_A_dialog',baseline_during_dialog,results)
        def baseline_failed_status(p):
            setup_original(p);start_restore(p,czip);dialog_A(p)
            fail_restore(p)
            assert 'HELD_RESTORE_IO_FAILURE' in status(p) and p.locator('#authorityReview').is_visible(),status(p)
        run_case(browser,base,'negative_exact026_stale_failure_overwrites_dialog_status',baseline_failed_status,results)
        if not args.baseline_only:
            def finishes_before_generate(p):
                setup_original(p);start_restore(p,czip);finish_restore(p,czip)
                assert badge(p)=='Restore Candidate C' and editor(p)=='Restore Candidate C',status(p)
                dialog_A(p);cancel_A(p);assert badge(p)=='Restore Candidate C'
            run_case(browser,candidate,'legitimate_restore_before_generate_allowed',finishes_before_generate,results)
            def during_dialog(p):
                setup_original(p);start_restore(p,czip);dialog_A(p);before=status(p)
                finish_restore(p,czip)
                assert badge(p)=='Original Project' and editor(p)=='Import Candidate A'
                assert status(p)==before and p.locator('#authorityReview').is_visible()
                accept_A(p);assert badge(p)=='Import Candidate A'
            run_case(browser,candidate,'stale_restore_cannot_commit_or_change_status_during_A_dialog',during_dialog,results)
            def after_accept(p):
                setup_original(p);start_restore(p,czip);dialog_A(p);accept_A(p);before=status(p)
                finish_restore(p,czip)
                assert badge(p)=='Import Candidate A' and editor(p)=='Import Candidate A'
                assert status(p)==before
            run_case(browser,candidate,'stale_restore_cannot_supersede_accepted_A',after_accept,results)
            def after_cancel(p):
                setup_original(p);start_restore(p,czip);dialog_A(p);cancel_A(p);before=status(p)
                finish_restore(p,czip)
                assert badge(p)=='Original Project' and editor(p)=='Import Candidate A'
                assert status(p)==before
            run_case(browser,candidate,'stale_restore_cannot_supersede_cancelled_A_decision',after_cancel,results)
            def stale_failure(p):
                setup_original(p);start_restore(p,czip);dialog_A(p);before=status(p)
                fail_restore(p)
                assert p.locator('#authorityReview').is_visible() and status(p)==before
                accept_A(p);assert badge(p)=='Import Candidate A'
            run_case(browser,candidate,'stale_read_failure_cannot_mask_authority_status',stale_failure,results)
            def fresh_failure(p):
                setup_original(p);start_restore(p,czip);fail_restore(p)
                assert 'HELD_RESTORE_IO_FAILURE' in status(p)
                assert badge(p)=='Original Project'
            run_case(browser,candidate,'fresh_restore_io_failure_remains_visible',fresh_failure,results)
            def successive_restores(p):
                setup_original(p)
                start_restore(p,czip,'held-old.zip');start_restore(p,czip,'held-new.zip')
                finish_restore(p,czip,'held-old.zip')
                assert badge(p)=='Original Project'
                finish_restore(p,czip,'held-new.zip')
                assert badge(p)=='Restore Candidate C' and editor(p)=='Restore Candidate C'
            run_case(browser,candidate,'newer_restore_selection_supersedes_previous_restore',successive_restores,results)
            def stale_invalid_zip(p):
                setup_original(p);start_restore(p,b'invalid','held-bad.zip');dialog_A(p);before=status(p)
                finish_restore(p,b'invalid','held-bad.zip')
                assert status(p)==before and p.locator('#authorityReview').is_visible()
            run_case(browser,candidate,'stale_malformed_zip_error_cannot_mask_authority',stale_invalid_zip,results)
            def during_modal_new_restore(p):
                setup_original(p);dialog_A(p);before=status(p)
                # Simulate out-of-band change dispatch; pending modal is not an authorizing surface.
                p.locator('#restoreFile').set_input_files({'name':'held-modal.zip','mimeType':'application/zip','buffer':czip})
                settle(p)
                assert p.evaluate('window.restoreRead.pending().length')==0
                assert status(p)==before and badge(p)=='Original Project'
                cancel_A(p)
            run_case(browser,candidate,'restore_start_during_modal_cannot_claim_authority',during_modal_new_restore,results)
            def timer_only_autosave(p):
                setup_original(p);start_restore(p,czip)
                # Previous Generate queued an autosave. It must not make an
                # otherwise unchanged, validated restore unavailable.
                p.wait_for_timeout(500)
                finish_restore(p,czip)
                assert badge(p)=='Restore Candidate C' and editor(p)=='Restore Candidate C'
            run_case(browser,candidate,'timer_only_autosave_does_not_block_valid_restore',timer_only_autosave,results)
            def edit_then_revert(p):
                setup_original(p);start_restore(p,czip)
                p.locator('#jsonInput').fill(A)
                p.locator('#jsonInput').fill(ORIGINAL)
                before=status(p);finish_restore(p,czip)
                assert badge(p)=='Original Project' and editor(p)=='Original Project' and status(p)==before
            run_case(browser,candidate,'editor_edit_and_revert_invalidates_restore',edit_then_revert,results)
            def in_place_project_edit(p):
                setup_original(p);start_restore(p,czip)
                p.locator('#proj-goal').fill('Newer human goal must not be overwritten')
                before=status(p);finish_restore(p,czip)
                assert badge(p)=='Original Project' and status(p)==before
                assert p.locator('#proj-goal').input_value()=='Newer human goal must not be overwritten'
            run_case(browser,candidate,'in_place_project_edit_invalidates_restore',in_place_project_edit,results)
            def saved_state_json(p):
                setup_original(p)
                with zipfile.ZipFile(Path(temp)/'valid-C.zip') as z:
                    payload=z.read('project_state.json')
                start_restore(p,payload,'held-state.json')
                finish_restore(p,payload,'held-state.json')
                assert badge(p)=='Restore Candidate C' and editor(p)=='Restore Candidate C'
            run_case(browser,candidate,'valid_canonical_state_json_restore_allowed',saved_state_json,results)
        browser.close()
    payload={'cases':results,'passed':len(results),'status':'LOCAL_CANDIDATE_PASS__INDEPENDENT_REAUDIT_REQUIRED__PHASE1_BLOCKED'}
    if args.results:args.results.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(f'PASS {len(results)}/{len(results)}',flush=True)
if __name__=='__main__':main()
