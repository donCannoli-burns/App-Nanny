#!/usr/bin/env python3
"""Repair 022: strict editable scaffold admission, rejecting duplicates before state changes.

Only disposable about:blank Chromium with isolated localStorage mock. Original
Repair 021 HTML is a byte-pinned negative-control input, not modified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'studio/context_tree_studio_authority_repaired_021.html'
CAND=ROOT/'studio/context_tree_studio_authority_repaired_022.html'
BASE_SHA='535cb3917c4e4a1892271ba1f35dd2ca5618c5892e5a74bc132564d1563c5e04'

CONTROL={"schema":"context-tree/scaffold-v1","project":{"name":"Canonical Green","goal":"Check preservation"},"tree":[{"name":"main.go","kind":"file","core":True}]}
def raw_control(): return json.dumps(CONTROL,indent=2,ensure_ascii=False)

def variants():
    c=raw_control()
    assert c.count('"name": "Canonical Green"') == 1
    assert c.count('"schema": "context-tree/scaffold-v1"') == 1
    return {
      'project_name_old_then_new':c.replace('"name": "Canonical Green"','"name": "Untrusted First", "name": "Canonical Green"',1),
      'project_name_new_then_old':c.replace('"name": "Canonical Green"','"name": "Canonical Green", "name": "Untrusted Second"',1),
      'project_name_identical':c.replace('"name": "Canonical Green"','"name": "Canonical Green", "name": "Canonical Green"',1),
      'project_name_unicode_escaped':c.replace('"name": "Canonical Green"','"n\\u0061me": "Untrusted Unicode", "name": "Canonical Green"',1),
      'scaffold_schema_old_then_new':c.replace('"schema": "context-tree/scaffold-v1"','"schema": "fake-schema", "schema": "context-tree/scaffold-v1"',1),
      'scaffold_schema_new_then_old':c.replace('"schema": "context-tree/scaffold-v1"','"schema": "context-tree/scaffold-v1", "schema": "fake-schema"',1),
      'tree_node_name_duplicate':c.replace('"name": "main.go"','"name": "other.go", "name": "main.go"',1),
      'tree_node_kind_duplicate':c.replace('"kind": "file"','"kind": "folder", "kind": "file"',1),
      'tree_nested_metadata_duplicate':c.replace('"goal": "Check preservation"','"goal": "Contradictory", "goal": "Check preservation"',1),
      'deep_nested_array_key':c.replace('"core": true','"core": false, "core": true',1),
      'escaped_unicode_surrogate':c.replace('"name": "Canonical Green"','"\\ud83d\\udc31": 1, "🐱": 2, "name": "Canonical Green"',1),
      'invalid_escape':c.replace('"name": "Canonical Green"','"name": "\\q"',1),
      'broken_json':c[:-1],
    }

def page_for(browser,html):
    ctx=browser.new_context(accept_downloads=True)
    p=ctx.new_page();errors=[]
    p.on('pageerror',lambda e:errors.append(str(e)))
    p.evaluate("""() => {const db={};Object.defineProperty(window,'localStorage',{configurable:true,value:{
      getItem:k=>Object.prototype.hasOwnProperty.call(db,k)?db[k]:null,
      setItem:(k,v)=>{db[k]=String(v)}, removeItem:k=>{delete db[k]}}});}""")
    p.set_content(html,wait_until='load')
    p.on('dialog',lambda d:d.accept())
    return ctx,p,errors

def import_scaffold(p,s):
    p.locator('#jsonInput').fill(s)
    p.locator('[data-action="generate"]').click()
    return p.locator('#status').inner_text()

def full_project_export(p,out):
    with p.expect_download(timeout=30000) as d:
        p.locator('[data-export="full_project"]').click()
    d.value.save_as(str(out))
    p.locator('#verifyFile').set_input_files(str(out))
    p.wait_for_function("() => document.querySelector('#verifyResult').textContent.includes('SEMANTICS_')",timeout=30000)
    return p.locator('#verifyResult').inner_text()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--html',type=Path,default=CAND);ap.add_argument('--results',type=Path);args=ap.parse_args()
    assert hashlib.sha256(BASE.read_bytes()).hexdigest()==BASE_SHA,'Frozen Repair 021 source changed'
    source=args.html.read_text('utf8'); cases=[]
    with sync_playwright() as pw, tempfile.TemporaryDirectory(prefix='app-nanny-022-') as tmp:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
        # Reproduce R021-I01 on the *unchanged* original app.
        ctx,p,errors=page_for(browser,BASE.read_text('utf8'))
        contradiction=variants()['project_name_old_then_new']
        status=import_scaffold(p,contradiction)
        assert 'SEMANTICS_VALID' in status,('baseline unexpectedly rejected',status)
        assert p.locator('#projectBadge').inner_text()=='Canonical Green'
        from playwright.sync_api import TimeoutError as PwTimeout
        try:
            with p.expect_download(timeout=1000):
                p.locator('[data-export="full_project"]').click()
        except PwTimeout:
            pass
        else:
            raise AssertionError('Original Repair 021 unexpectedly downloaded ambiguous ZIP')
        assert 'duplicate' in p.locator('#status').inner_text().lower(),p.locator('#status').inner_text()
        assert not errors,errors
        cases.append({'case':'baseline_failure_reproduced','result':'accepted scaffold; export rejected'})
        print('PASS baseline R021-I01 reproduced',flush=True)
        ctx.close()

        # Clean success control must export to internally verifiable ZIP.
        ctx,p,errors=page_for(browser,source)
        assert 'SEMANTICS_VALID' in import_scaffold(p,raw_control())
        control_out=Path(tmp)/'clean.zip'
        assert 'SEMANTICS_VALID' in full_project_export(p,control_out)
        assert not errors,errors
        cases.append({'case':'clean_scaffold_roundtrip','result':'SEMANTICS_VALID'})
        print('PASS clean scaffold -> Full Project ZIP -> verify',flush=True)
        ctx.close()

        for name,raw in variants().items():
            ctx,p,errors=page_for(browser,source)
            assert 'SEMANTICS_VALID' in import_scaffold(p,raw_control()),name
            original=p.locator('#projectBadge').inner_text()
            original_nodes=p.locator('#treeStatus').inner_text()
            before_release=p.locator('#versionBadge').inner_text()
            status=import_scaffold(p,raw)
            assert 'Import failed:' in status,(name,status)
            assert 'SEMANTICS_CONFLICT' in status or name in ('invalid_escape','broken_json'),(name,status)
            assert p.locator('#jsonInput').input_value()==raw,('raw bytes overwritten',name)
            assert p.locator('#projectBadge').inner_text()==original,('project changed',name)
            assert p.locator('#treeStatus').inner_text()==original_nodes,('nodes changed',name)
            assert p.locator('#versionBadge').inner_text()==before_release,('release changed',name)
            assert not errors,(name,errors)
            cases.append({'case':name,'result':'rejected; original project and editable input preserved'})
            print('PASS',name,'rejected without state mutation',flush=True)
            if name in ('project_name_old_then_new','scaffold_schema_old_then_new','tree_node_name_duplicate'):
                out=Path(tmp)/(name+'.zip')
                assert 'SEMANTICS_VALID' in full_project_export(p,out),name
                cases.append({'case':name+'_export_still_valid','result':'SEMANTICS_VALID'})
                print('PASS',name,'existing state still backs up',flush=True)
            ctx.close()

        # File selection also populates the same textarea + Generate gate.
        raw=variants()['project_name_unicode_escaped']
        ctx,p,errors=page_for(browser,source)
        initial_badge=p.locator('#projectBadge').inner_text()
        p.locator('#scaffoldFile').set_input_files({'name':'ambiguous.json','mimeType':'application/json','buffer':raw.encode('utf8')})
        p.wait_for_function('() => document.querySelector("#jsonInput").value.includes("\\u0061")')
        status_before=p.locator('#status').inner_text()
        assert 'Loaded' in status_before,status_before
        status=p.locator('[data-action="generate"]').click()
        status=p.locator('#status').inner_text()
        assert 'SEMANTICS_CONFLICT' in status,status
        assert p.locator('#jsonInput').input_value()==raw
        assert p.locator('#projectBadge').inner_text()==initial_badge
        assert not errors,errors
        cases.append({'case':'uploaded_scaffold_path','result':'rejected; raw input retained'})
        print('PASS uploaded scaffold uses strict Generate gate',flush=True)
        ctx.close()

        # Duplicate names across distinct object scopes are not duplicate keys.
        valid=raw_control().replace('"name": "main.go",','"name": "main.go",',1)
        obj=json.loads(valid);obj['tree'].append({'name':'README.md','kind':'file'})
        ctx,p,errors=page_for(browser,source)
        assert 'SEMANTICS_VALID' in import_scaffold(p,json.dumps(obj,indent=2))
        assert 'SEMANTICS_VALID' in full_project_export(p,Path(tmp)/'two-distinct-objects.zip')
        assert not errors,errors
        cases.append({'case':'same_key_in_distinct_objects','result':'SEMANTICS_VALID'})
        print('PASS same member name in distinct object scopes accepted',flush=True)
        ctx.close();browser.close()
    if args.results:
        args.results.parent.mkdir(parents=True,exist_ok=True)
        args.results.write_text(json.dumps({'gate':'LOCAL_REPAIR_CANDIDATE_PASS__INDEPENDENT_REAUDIT_REQUIRED__PHASE1_BLOCKED','checks':len(cases),'cases':cases},indent=2)+'\n')
    print('PASS %d/%d checks' % (len(cases),len(cases)),flush=True)

if __name__=='__main__': main()
