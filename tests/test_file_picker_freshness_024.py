#!/usr/bin/env python3
"""Repair 024: deterministic out-of-order file selection/editor/project race tests.
Run against the exact SHA-pinned Repair 023 and the new candidate, without disk persistence.
"""
import argparse,hashlib,json,tempfile,zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'studio/context_tree_studio_authority_repaired_023.html'
DEFAULT=ROOT/'studio/context_tree_studio_authority_repaired_024.html'
BASE_SHA='f4bde89f4efd585fc406f020d659b2eda5990b41ed1e62e9837aa08f3ffd2b73'

def scaffold(name):
    return json.dumps({'schema':'context-tree/scaffold-v1','project':{'name':name,'goal':'Freshness test'},'tree':[{'name':'main.go','kind':'file','core':True}]},indent=2,ensure_ascii=False)

def make_page(browser,html):
    ctx=browser.new_context(accept_downloads=True);p=ctx.new_page();errors=[]
    p.on('pageerror',lambda e:errors.append(str(e)))
    p.on('dialog',lambda d:d.accept())
    p.evaluate('''() => {
      const db={},pending=[];
      Object.defineProperty(window,'localStorage',{configurable:true,value:{
        getItem:k=>Object.prototype.hasOwnProperty.call(db,k)?db[k]:null,
        setItem:(k,v)=>{db[k]=String(v)},removeItem:k=>{delete db[k]}}});
      const original=File.prototype.arrayBuffer;
      window.readController={
        names:()=>pending.filter(x=>!x.done).map(x=>x.name),
        resolve:(name,bytes)=>{const r=pending.find(x=>x.name===name&&!x.done);if(!r)throw Error('Missing '+name);r.done=true;r.resolve(Uint8Array.from(bytes).buffer)},
        reject:(name,msg)=>{const r=pending.find(x=>x.name===name&&!x.done);if(!r)throw Error('Missing '+name);r.done=true;r.reject(Error(msg))}
      };
      File.prototype.arrayBuffer=function(){
        if(!this.name.endsWith('.json'))return original.call(this);
        return new Promise((resolve,reject)=>pending.push({name:this.name,resolve,reject,done:false}));
      };
    }''')
    p.set_content(html,wait_until='load')
    return ctx,p,errors

def select(p,name,text):
    p.locator('#scaffoldFile').set_input_files({'name':name,'mimeType':'application/json','buffer':text.encode('utf-8')})
    p.wait_for_function('(x)=>readController.names().includes(x)',arg=name)
    assert p.locator('#scaffoldFile').input_value()==''

def complete(p,name,text,raw=None):
    p.evaluate('([n,b])=>readController.resolve(n,b)',[name,list(text.encode('utf-8') if raw is None else raw)])
    p.evaluate('()=>new Promise(resolve=>queueMicrotask(resolve))')

def reject(p,name,reason):
    p.evaluate('([n,x])=>readController.reject(n,x)',[name,reason])
    p.evaluate('()=>new Promise(resolve=>queueMicrotask(resolve))')

def edit(p,s):p.locator('#jsonInput').fill(s)
def value(p):return p.locator('#jsonInput').input_value()
def status(p):return p.locator('#status').inner_text()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--html',type=Path,default=DEFAULT);parser.add_argument('--results',type=Path);a=parser.parse_args()
    assert hashlib.sha256(BASE.read_bytes()).hexdigest()==BASE_SHA,'Repair 023 baseline changed'
    original=BASE.read_text();candidate=a.html.read_text();checks=[]
    A,B=scaffold('Older A'),scaffold('Newest B')
    with sync_playwright() as pw,tempfile.TemporaryDirectory(prefix='app-nanny-024-') as t:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
        def check(name,steps,html=candidate):
            c,p,errors=make_page(browser,html)
            try:steps(p)
            finally:c.close()
            assert not errors,(name,errors)
            checks.append(name);print('PASS',name,flush=True)
        def baseline(p):
            select(p,'A.json',A);select(p,'B.json',B)
            complete(p,'B.json',B);assert value(p)==B
            complete(p,'A.json',A);assert value(p)==A
        check('repair023_stale_read_reproduced',baseline,original)
        def latest(p):
            select(p,'A.json',A);select(p,'B.json',B)
            complete(p,'B.json',B);assert value(p)==B
            before=status(p);complete(p,'A.json',A);assert value(p)==B and status(p)==before
            p.locator('[data-action="generate"]').click()
            assert 'SEMANTICS_VALID' in status(p) and p.locator('#projectBadge').inner_text()=='Newest B'
            with p.expect_download(timeout=30000) as dl:p.locator('[data-export="full_project"]').click()
            z=Path(t)/'latest.zip';dl.value.save_as(str(z))
            with zipfile.ZipFile(z) as f:
                assert f.testzip() is None
                assert json.loads(f.read('tree_raw.json'))['project']['name']=='Newest B'
            p.locator('#verifyFile').set_input_files(str(z))
            p.wait_for_function("()=>document.querySelector('#verifyResult').textContent.includes('SEMANTICS_')")
            assert 'SEMANTICS_VALID' in p.locator('#verifyResult').inner_text()
        check('B_then_A_latest_selection_wins_and_export_valid',latest)
        def older_first(p):
            edit(p,'UNCHANGED');select(p,'A.json',A);select(p,'B.json',B)
            complete(p,'A.json',A);assert value(p)=='UNCHANGED'
            complete(p,'B.json',B);assert value(p)==B
        check('A_finishes_first_ignored',older_first)
        def manual(p):
            edit(p,'BEFORE');select(p,'A.json',A);edit(p,'MANUAL')
            complete(p,'A.json',A);assert value(p)=='MANUAL'
        check('manual_edit_cancels_read',manual)
        def edit_back(p):
            edit(p,'SAME');select(p,'A.json',A);edit(p,'OTHER');edit(p,'SAME')
            complete(p,'A.json',A);assert value(p)=='SAME'
        check('manual_edit_then_same_value_still_cancels',edit_back)
        def demo(p):
            select(p,'A.json',A);p.locator('[data-action="load-example"]').click()
            before=value(p);complete(p,'A.json',A);assert value(p)==before
        check('demo_load_cancels_read',demo)
        def project(p):
            select(p,'A.json',A);edit(p,scaffold('Replacement'))
            p.locator('[data-action="generate"]').click()
            assert 'SEMANTICS_VALID' in status(p)
            before=value(p);complete(p,'A.json',A)
            assert value(p)==before and p.locator('#projectBadge').inner_text()=='Replacement'
        check('project_transition_cancels_read',project)
        def stale_error(p):
            select(p,'old.json',A);select(p,'new.json',B)
            complete(p,'new.json',B);before=status(p)
            reject(p,'old.json','STALE_ERROR');assert value(p)==B and status(p)==before
        check('stale_error_ignored',stale_error)
        def stale_decode_error(p):
            select(p,'old.json',A);select(p,'new.json',B)
            complete(p,'new.json',B);before=status(p)
            complete(p,'old.json',A,raw=b'\xff');assert value(p)==B and status(p)==before
        check('stale_invalid_utf8_error_ignored',stale_decode_error)
        def fresh_invalid(p):
            edit(p,'PRESERVED');select(p,'bad.json',A);complete(p,'bad.json',A,raw=b'\xff')
            p.wait_for_function("()=>document.querySelector('#status').textContent.includes('Invalid UTF-8')")
            assert value(p)=='PRESERVED'
        check('current_invalid_utf8_rejected',fresh_invalid)
        def fresh_error(p):
            edit(p,'PRESERVED');select(p,'bad.json',A);reject(p,'bad.json','IO_FAILURE')
            p.wait_for_function("()=>document.querySelector('#status').textContent.includes('IO_FAILURE')")
            assert value(p)=='PRESERVED'
        check('current_read_error_visible',fresh_error)
        def error_after_edit(p):
            edit(p,'BEFORE');select(p,'A.json',A);edit(p,'MANUAL');before=status(p)
            reject(p,'A.json','OLD_ERROR');assert value(p)=='MANUAL' and status(p)==before
        check('stale_error_after_manual_edit_ignored',error_after_edit)
        def cancel_selection(p):
            edit(p,'KEEP');select(p,'A.json',A)
            p.locator('#scaffoldFile').set_input_files([])
            complete(p,'A.json',A);assert value(p)=='KEEP'
        check('cleared_selection_invalidates_read',cancel_selection)
        def unicode(p):
            text=scaffold('Café 🌍');select(p,'good.json',text)
            complete(p,'good.json',text);assert value(p)==text
            p.locator('[data-action="generate"]').click()
            assert 'SEMANTICS_VALID' in status(p)
        check('unicode_valid_after_fencing',unicode)
        def bom(p):
            text=scaffold('BOM');select(p,'bom.json',text)
            complete(p,'bom.json',text,raw=b'\xef\xbb\xbf'+text.encode())
            assert value(p)==text
        check('bom_policy_preserved',bom)
        browser.close()
    if a.results:
        a.results.parent.mkdir(parents=True,exist_ok=True)
        a.results.write_text(json.dumps({'status':'LOCAL_PASS__INDEPENDENT_REAUDIT_REQUIRED__PHASE1_BLOCKED','checks':len(checks),'cases':checks},indent=2)+'\n')
    print(f'PASS {len(checks)}/{len(checks)}',flush=True)
if __name__=='__main__':main()
