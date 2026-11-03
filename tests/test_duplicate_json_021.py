#!/usr/bin/env python3
"""Repair 021. Mutate original JSON bytes, retain valid ZIP CRCs and SHA-256 member hashes.

All negative fixtures are made from the seed, never from the candidate app's state.
Usage: python test_duplicate_json_021.py [--html FILE] [--seed ZIP] [--results JSON]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile
from playwright.sync_api import sync_playwright

HERE=Path(__file__).resolve().parents[1]
BASE=HERE/'studio/context_tree_studio_authority_repaired_020.html'
CANDIDATE=HERE/'studio/context_tree_studio_authority_repaired_021.html'
BASE_SHA256='a98f0b7b001dd7b02506b8161a83748f65df573aebef6976b5077d13bbdda944'


def json_bytes(x): return (json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode('utf8')


def inject_before(text,anchor,key,value):
    assert text.count(anchor)>=1, (anchor,text.count(anchor))
    return text.replace(anchor,key+': '+json.dumps(value, ensure_ascii=False)+',\n  '+anchor,1)


def insert_after_project_id(s):
    import re
    return re.sub(r'("projectId":\s*"[^"]+"),', lambda m: m.group(1)+',\n  "projectId": "unrelated-project",',s,count=1)


def mutate(seed):
    members=dict(seed)
    variants={}
    def add(name, member, func):
        b=members[member]; x=func(b.decode('utf8')).encode('utf8')
        assert x!=b,(name,member)
        contents=members.copy(); contents[member]=x
        if member!='manifest.json':
            manifest=json.loads(members['manifest.json'])
            entry=next(f for f in manifest['files'] if f['name']==member)
            entry['sha256']=hashlib.sha256(x).hexdigest();entry['bytes']=len(x)
            contents['manifest.json']=json_bytes(manifest)
        variants[name]=(contents,member)
    add('project_id_conflicting_first','project_state.json',lambda s:inject_before(s,'"projectId":','"projectId"','unrelated-project'))
    add('project_id_escaped_equivalent','project_state.json',lambda s:inject_before(s,'"projectId":','"pro\\u006aectId"','unrelated-project'))
    add('project_id_conflicting_second','project_state.json',insert_after_project_id)
    add('manifest_scope_duplicate','manifest.json',lambda s:inject_before(s,'"sha256Scope":','"sha256Scope"','fake SHA-1 scope'))
    add('manifest_notes_same_value_duplicate','manifest.json',lambda s:inject_before(s,'"notes":','"notes"','some notes'))
    add('tree_export_algorithm_duplicate','tree_full.json',lambda s:inject_before(s,'"algorithm":','"algorithm"','MD5'))
    add('tree_context_scope_duplicate','tree_context.json',lambda s:inject_before(s,'"scope":','"scope"','anything'))
    add('planning_snapshot_revision_duplicate','planning_snapshot.json',lambda s:inject_before(s,'"revision":','"revision"',99999))
    add('planning_ledger_algorithm_duplicate','planning_ledger.json',lambda s:inject_before(s,'"algorithm":','"algorithm"','SHA-1'))
    add('registry_priority_duplicate','resource_registry.json',lambda s:inject_before(s,'"higherNumberMeansMoreCritical":','"higherNumberMeansMoreCritical"',False))
    add('registry_priority_unicode_escaped','resource_registry.json',lambda s:inject_before(s,'"higherNumberMeansMoreCritical":','"higherNumberMeansMoreCritic\\u0061l"',False))
    add('nested_array_object_duplicate','project_state.json',lambda s: s.replace('"nodes": [\n    {','"nodes": [\n    {\n      "name": "false-name",',1))
    add('templates_format_duplicate','templates.json',lambda s:inject_before(s,'"format":','"format"','fake-format'))
    add('tree_raw_nested_key_duplicate','tree_raw.json',lambda s:inject_before(s,'"project":','"project"',None))
    add('surrogate_pair_equivalent_nested','resource_registry.json',lambda s:s.replace('"priorityPolicy": {','"priorityPolicy": {\n    "\\ud83d\\udc31": 1,\n    "🐱": 2,',1))
    return variants


def zip_bytes(members,output):
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as z:
        for n,data in members.items():z.writestr(n,data)
    with zipfile.ZipFile(output) as z: assert z.testzip() is None


def browser_context(browser,html):
    ctx=browser.new_context(accept_downloads=True)
    p=ctx.new_page();errors=[]
    p.on('pageerror',lambda e:errors.append(str(e)))
    p.evaluate("""() => {const db={}; Object.defineProperty(window,'localStorage',
       {configurable:true,value:{getItem:k=>Object.prototype.hasOwnProperty.call(db,k)?db[k]:null,
       setItem:(k,v)=>{db[k]=String(v)},removeItem:k=>{delete db[k]}}});}""")
    p.set_content(html,wait_until='load')
    p.on('dialog',lambda d:d.accept())
    return ctx,p,errors


def verify(page,path):
    page.locator('#verifyFile').set_input_files(str(path))
    page.wait_for_function("() => !document.querySelector('#verifyResult').textContent.includes('Checking ')",timeout=18000)
    return page.locator('#verifyResult').inner_text()


def restore(page,path):
    before=page.locator('#projectBadge').inner_text()
    page.locator('#restoreFile').set_input_files(str(path))
    page.wait_for_function("() => {let t=document.querySelector('#status').textContent;return t.includes('failed') || t.includes('Restored ') || t.includes('Restore blocked') || t.includes('AUTHORITY')}",timeout=18000)
    return before,page.locator('#status').inner_text(),page.locator('#projectBadge').inner_text()


def main():
    arg=argparse.ArgumentParser();arg.add_argument('--html',type=Path,default=CANDIDATE);arg.add_argument('--results',type=Path,default=None)
    a=arg.parse_args()
    html=a.html.read_text('utf8')
    assert hashlib.sha256(BASE.read_bytes()).hexdigest()==BASE_SHA256,'Frozen Repair 020 source changed'
    checks=[]
    with tempfile.TemporaryDirectory(prefix='app-nanny-021-') as tmp:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
            clean=Path(tmp)/'control.zip'
            seed_ctx,seed_page,seed_errors=browser_context(browser,BASE.read_text('utf8'))
            seed_page.locator('[data-action=load-example]').click()
            seed_page.locator('[data-action=generate]').click()
            with seed_page.expect_download(timeout=30000) as seed_dl:
                seed_page.locator('[data-export=full_project]').click()
            seed_dl.value.save_as(str(clean))
            assert not seed_errors,seed_errors
            seed_ctx.close()
            with zipfile.ZipFile(clean) as z:seed={n:z.read(n) for n in z.namelist()}
            tests=mutate(seed)
            for title,contents,member in [('control',seed,None)]+[(name,files,member) for name,(files,member) in tests.items()]:
                path=Path(tmp)/(title+'.zip');zip_bytes(contents,path)
                ctx,p,errors=browser_context(browser,html)
                ver=verify(p,path)
                bad=title!='control'
                if bad:
                    assert 'SEMANTICS_CONFLICT' in ver and 'SEMANTICS_VALID' not in ver,(title,ver)
                else:assert 'SEMANTICS_VALID' in ver,ver
                before,status,after=restore(p,path)
                if bad:
                    assert ('Restore failed' in status or 'Restore blocked' in status), (title,status)
                    assert before==after,(title,before,after)
                else:
                    assert 'Restored ' in status,(title,status)
                    with p.expect_download(timeout=20000) as info:
                        p.locator('[data-export="full_project"]').click()
                    reexport=Path(tmp)/'roundtrip.zip';info.value.save_as(str(reexport))
                    assert 'SEMANTICS_VALID' in verify(p,reexport)
                    other,pp,ee=browser_context(browser,html)
                    assert 'Restored ' in restore(pp,reexport)[1]
                    assert not ee,ee
                    other.close()
                assert not errors,(title,errors)
                checks.append({'case':title,'member':member,'verify':ver,'restore':status,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'js_errors':errors})
                print('PASS',title,'verification: '+('REJECTED' if bad else 'SEMANTICS_VALID'),'restore: '+('REJECTED' if bad else 'SUCCESS'),flush=True)
                ctx.close()
            # Standalone JSON exports are subject to the same pre-parse admission gate.
            standalone=[
                ('planning_snapshot_control','planning_snapshot.json',None),
                ('planning_snapshot_escaped_revision_duplicate','planning_snapshot.json',lambda x:inject_before(x,'"revision":','"re\\u0076ision"',99999)),
                ('tree_full_control','tree_full.json',None),
                ('tree_full_export_hash_duplicate','tree_full.json',lambda x:inject_before(x,'"algorithm":','"algorithm"','MD5')),
                ('project_state_restore_duplicate','project_state.json',lambda x:inject_before(x,'"projectId":','"projectId"','other-project')),
            ]
            for title,member,mutator in standalone:
                data=seed[member]
                if mutator is not None:data=mutator(data.decode('utf8')).encode('utf8')
                path=Path(tmp)/(title+'.json');path.write_bytes(data)
                ctx,p,errors=browser_context(browser,html)
                if member!='project_state.json':
                    result=verify(p,path)
                    if mutator is None:assert 'SEMANTICS_VALID' in result,(title,result)
                    else:assert 'SEMANTICS_CONFLICT' in result and 'SEMANTICS_VALID' not in result,(title,result)
                else:result='NO_STANDALONE_CHECKSUM'
                if mutator is not None:
                    before,status,after=restore(p,path)
                    assert ('Restore failed' in status or 'Restore blocked' in status),(title,status)
                    assert before==after,(title,before,after)
                else:status='verification-control'
                assert not errors,(title,errors)
                checks.append({'case':title,'member':member,'verify':result,'restore':status,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'js_errors':errors})
                print('PASS standalone',title,flush=True)
                ctx.close()
            browser.close()
    if a.results:
        a.results.parent.mkdir(parents=True,exist_ok=True)
        a.results.write_text(json.dumps({'gate':'LOCAL_PASS__INDEPENDENT_AUDIT_REQUIRED','checks':len(checks),'results':checks},indent=2)+'\n')
    print(f'PASS {len(checks)}/{len(checks)}',flush=True)

if __name__=='__main__': main()
