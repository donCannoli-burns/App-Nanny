#!/usr/bin/env python3
"""Repair 023: exact-byte UTF-8 admission on the scaffold file-picker path.

Original Repair 022 is SHA-pinned for the negative baseline. The application is
run only in disposable Chromium contexts with a synthetic, isolated localStorage.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'studio/context_tree_studio_authority_repaired_022.html'
CAND = ROOT / 'studio/context_tree_studio_authority_repaired_023.html'
BASE_SHA = '9cbeb950e2b4d3ccb1a4b6b0fc07faec41a1dc974d8ca8a5274268287daab3d8'


def scaffold(name='Canonical Green'):
    return json.dumps({'schema':'context-tree/scaffold-v1','project':{'name':name,'goal':'Preserve original bytes'},'tree':[{'name':'main.go','kind':'file','core':True}]},ensure_ascii=False,indent=2)


def page_for(browser,html):
    ctx=browser.new_context(accept_downloads=True)
    p=ctx.new_page();errors=[]
    p.on('pageerror',lambda e: errors.append(str(e)))
    p.evaluate('''() => {const db={};Object.defineProperty(window,'localStorage',{configurable:true,value:{
      getItem:k=>Object.prototype.hasOwnProperty.call(db,k)?db[k]:null,
      setItem:(k,v)=>{db[k]=String(v)},removeItem:k=>{delete db[k]}}});}''')
    p.set_content(html,wait_until='load')
    p.on('dialog',lambda d:d.accept())
    return ctx,p,errors


def load_file(page,raw,name):
    page.locator('#scaffoldFile').set_input_files({'name':name,'mimeType':'application/json','buffer':raw})
    page.wait_for_function('''() => {
       const t=document.querySelector('#status').textContent;
       return t.includes('Loaded ') || t.includes('Scaffold file rejected:');
    }''',timeout=20000)
    return page.locator('#status').inner_text()


def export_and_verify(page,output):
    with page.expect_download(timeout=40000) as dl:
        page.locator('[data-export="full_project"]').click()
    dl.value.save_as(str(output))
    page.locator('#verifyFile').set_input_files(str(output))
    page.wait_for_function("() => document.querySelector('#verifyResult').textContent.includes('SEMANTICS_')",timeout=40000)
    result=page.locator('#verifyResult').inner_text()
    assert 'SEMANTICS_VALID' in result,result
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        return json.loads(z.read('tree_raw.json'))


def invalid_utf8_variants():
    payload=scaffold('Bad X').encode('utf-8')
    assert payload.count(b'Bad X')==1
    raw=lambda b: payload.replace(b'Bad X',b'Bad '+b,1)
    return {
        'invalid_ff_byte':raw(b'\xff'),
        'unexpected_continuation':raw(b'\x80'),
        'truncated_two_byte':raw(b'\xc3'),
        'invalid_two_byte_sequence':raw(b'\xc3('),
        'truncated_three_byte':raw(b'\xe2\x82'),
        'overlong_two_byte':raw(b'\xc0\xaf'),
        'surrogate_encoded_utf8':raw(b'\xed\xa0\x80'),
        'out_of_range_scalar':raw(b'\xf4\x90\x80\x80'),
        'bom_then_invalid':b'\xef\xbb\xbf'+raw(b'\xff')
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--html',type=Path,default=CAND)
    parser.add_argument('--results',type=Path)
    args=parser.parse_args()
    assert hashlib.sha256(BASE.read_bytes()).hexdigest()==BASE_SHA,'Frozen 022 HTML differs'
    new_html=args.html.read_text('utf-8')
    recorded=[]
    with sync_playwright() as pw, tempfile.TemporaryDirectory(prefix='app-nanny-023-') as tmp:
        chromium='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None
        browser=pw.chromium.launch(headless=True,executable_path=chromium,args=['--no-sandbox'])
        # Confirm exact predecessor accepted the malformed disk bytes after
        # file.text() silently substituted the Unicode replacement character.
        base_ctx,base_page,base_errors=page_for(browser,BASE.read_text('utf-8'))
        data=invalid_utf8_variants()['invalid_ff_byte']
        status=load_file(base_page,data,'original-ff.json')
        assert status.startswith('Loaded '),status
        assert 'Bad \ufffd' in base_page.locator('#jsonInput').input_value()
        base_page.locator('[data-action="generate"]').click()
        status=base_page.locator('#status').inner_text()
        assert 'SEMANTICS_VALID' in status,status
        zip_out=Path(tmp)/'predecessor-proof.zip'
        doc=export_and_verify(base_page,zip_out)
        assert doc['project']['name']=='Bad \ufffd',doc['project']['name']
        assert not base_errors,base_errors
        recorded.append({'case':'r022_i01_reproduced_against_unchanged_022','result':'Lossy UTF-8 accepted; exported replacement character'})
        print('PASS original Repair 022 loss verified',flush=True)
        base_ctx.close()

        # Every invalid byte sequence must fail *before* the textarea is edited,
        # even when a valid existing project is present and backupable.
        for label,bytes_ in invalid_utf8_variants().items():
            ctx,page,errors=page_for(browser,new_html)
            page.locator('#jsonInput').fill(scaffold('Original Project'))
            page.locator('[data-action="generate"]').click()
            assert 'SEMANTICS_VALID' in page.locator('#status').inner_text()
            before_project=page.locator('#projectBadge').inner_text()
            before_version=page.locator('#versionBadge').inner_text()
            before_tree=page.locator('#treeStatus').inner_text()
            sentinel='{"unchanged":"my editable JSON"}'
            page.locator('#jsonInput').fill(sentinel)
            status=load_file(page,bytes_,label+'.json')
            assert 'Scaffold file rejected:' in status and 'Invalid UTF-8' in status,(label,status)
            assert page.locator('#jsonInput').input_value()==sentinel,(label,'editor changed')
            assert page.locator('#projectBadge').inner_text()==before_project,(label,'project changed')
            assert page.locator('#versionBadge').inner_text()==before_version,(label,'version changed')
            assert page.locator('#treeStatus').inner_text()==before_tree,(label,'tree changed')
            assert page.locator('#scaffoldFile').input_value()=='',(label,'file picker not reset')
            assert not errors,(label,errors)
            recorded.append({'case':label,'result':'REJECTED original byte stream; no state mutation'})
            print('PASS',label,'rejected before editor update',flush=True)
            if label=='invalid_ff_byte':
                doc=export_and_verify(page,Path(tmp)/'preserved-project.zip')
                assert doc['project']['name']=='Original Project'
                recorded.append({'case':'backup_after_rejected_invalid_file','result':'SEMANTICS_VALID; prior project retained'})
                print('PASS old project still exports after rejection',flush=True)
            ctx.close()

        # Valid UTF-8 bytes—including Unicode and literal U+FFFD—are admitted
        # unchanged. Literal U+FFFD is not evidence of an invalid byte stream.
        controls=[
            ('ascii_valid',scaffold('ASCII Clean').encode('utf-8'),'ASCII Clean'),
            ('unicode_valid',scaffold('Caf\u00e9 \U0001f30d').encode('utf-8'),'Caf\u00e9 \U0001f30d'),
            ('literal_replacement_character',scaffold('Valid \ufffd').encode('utf-8'),'Valid \ufffd'),
            ('utf8_bom_policy_unchanged',b'\xef\xbb\xbf'+scaffold('BOM Clean').encode('utf-8'),'BOM Clean')
        ]
        for label,bytes_,name in controls:
            ctx,page,errors=page_for(browser,new_html)
            status=load_file(page,bytes_,label+'.json')
            assert status.startswith('Loaded '),(label,status)
            expected=scaffold(name)
            assert page.locator('#jsonInput').input_value()==expected,(label,'unexpected decoded text')
            page.locator('[data-action="generate"]').click()
            status=page.locator('#status').inner_text()
            assert 'SEMANTICS_VALID' in status,(label,status)
            doc=export_and_verify(page,Path(tmp)/(label+'.zip'))
            assert doc['project']['name']==name,(label,doc['project']['name'])
            assert not errors,(label,errors)
            recorded.append({'case':label,'result':'Accepted exact valid UTF-8; full project SEMANTICS_VALID'})
            print('PASS',label,'valid bytes preserved and exported',flush=True)
            ctx.close()
        browser.close()
    if args.results:
        args.results.parent.mkdir(parents=True,exist_ok=True)
        args.results.write_text(json.dumps({'status':'LOCAL_PASS__INDEPENDENT_REAUDIT_REQUIRED__PHASE1_BLOCKED','checks':len(recorded),'results':recorded},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('PASS %d/%d cases' % (len(recorded),len(recorded)),flush=True)

if __name__=='__main__': main()
