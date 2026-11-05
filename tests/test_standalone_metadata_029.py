#!/usr/bin/env python3
"""Repair 029: standalone verified-JSON admission and Restore modal warning replay.

Uses a frozen Repair 019 producer for standalone JSON controls and a frozen
Repair 027 producer for a genuine human-authority Restore conflict.
"""
import argparse
import hashlib
import json
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright
from test_metadata_contract_020 import generate_control_from_frozen_019, open_page, verify, restore
from test_cross_operation_async_028 import (
    OLD, OLD_SHA, page as page_with_concurrency_instrumentation,
    conflict_zip, original, restore_dialog, accept, modal, status
)

ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/"studio/context_tree_studio_authority_repaired_029.html"

def bytes_json(obj):
    return (json.dumps(obj,indent=2,ensure_ascii=False)+"\n").encode("utf-8")

def mutated_document(original_bytes,change):
    doc=json.loads(original_bytes)
    change(doc)
    return bytes_json(doc)

def update_zip_member(zip_bytes,member,change):
    with zipfile.ZipFile(__import__("io").BytesIO(zip_bytes)) as archive:
        records={name:archive.read(name) for name in archive.namelist()}
    records[member]=mutated_document(records[member],change)
    if member!="manifest.json":
        manifest=json.loads(records["manifest.json"])
        rec=next(x for x in manifest["files"] if x["name"]==member)
        rec["bytes"]=len(records[member])
        rec["sha256"]=hashlib.sha256(records[member]).hexdigest()
        records["manifest.json"]=bytes_json(manifest)
    out=__import__("io").BytesIO()
    with zipfile.ZipFile(out,mode="w",compression=zipfile.ZIP_STORED) as z:
        for name,data in records.items():z.writestr(name,data)
    return out.getvalue()

def case(results,name,fn):
    row={"name":name,"outcome":"FAIL"}
    try:
        fn(row)
        row["outcome"]="PASS"
        print("PASS",name,flush=True)
    except Exception as exc:
        row["error"]=repr(exc)
        row["traceback"]=traceback.format_exc(limit=7)
        print("FAIL",name,exc,file=sys.stderr,flush=True)
    results.append(row)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--html",type=Path,default=HTML)
    ap.add_argument("--results",type=Path)
    args=ap.parse_args()
    assert hashlib.sha256(OLD.read_bytes()).hexdigest()==OLD_SHA
    src=args.html.read_text("utf-8")
    result=[]
    with tempfile.TemporaryDirectory(prefix="app-nanny-029-standalone-") as td,sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path="/usr/bin/chromium",args=["--no-sandbox"])
        try:
            seed_path=generate_control_from_frozen_019(browser,Path(td)/"baseline.zip")
            with zipfile.ZipFile(seed_path) as archive:
                documents={n:archive.read(n) for n in ("tree_full.json","planning_snapshot.json","planning_ledger.json")}

            def check_json(name,member,change,expect,token,do_restore=True):
                def run(row):
                    ctx=None
                    try:
                        ctx,p,errors=open_page(browser,src)
                        data=mutated_document(documents[member],change)
                        path=Path(td)/(name+".json")
                        path.write_bytes(data)
                        verified=verify(p,path)
                        row["verify"]=verified
                        if expect=="accept":
                            assert "SEMANTICS_VALID" in verified,(name,verified)
                            assert "WARNING:" not in verified,verified
                        elif expect=="warn":
                            assert "SEMANTICS_VALID" in verified,(name,verified)
                            assert "WARNING:" in verified and token in verified,(name,verified)
                        else:
                            assert "SEMANTICS_CONFLICT" in verified,(name,verified)
                            assert token in verified,(name,verified)
                        if do_restore:
                            restored=restore(p,path)
                            row["restore"]=restored
                            if expect=="reject":
                                assert "Restore failed" in restored and token in restored,(name,restored)
                            else:
                                assert "Restored " in restored,(name,restored)
                                if expect=="warn":
                                    assert "WARNING:" in restored and token in restored,(name,restored)
                                    with p.expect_download(timeout=40000) as dl:
                                        p.locator('[data-export="full_project"]').click()
                                    dest=Path(td)/(name+"-reexport.zip")
                                    dl.value.save_as(str(dest))
                                    with zipfile.ZipFile(dest) as z:
                                        exporter=json.loads(z.read("tree_full.json"))["export"]
                                        assert "x_advisory" not in exporter,exporter
                                else:
                                    assert "WARNING:" not in restored,restored
                        assert not errors,(name,errors)
                    finally:
                        if ctx:ctx.close()
                case(result,name,run)

            check_json("standalone_tree_full_clean","tree_full.json",lambda d:None,"accept",None)
            check_json("standalone_tree_full_advisory","tree_full.json",
                       lambda d:d["export"].__setitem__("x_advisory","harmless extension"),
                       "warn","standalone.json.export.x_advisory")
            check_json("standalone_tree_full_actor_claim","tree_full.json",
                       lambda d:d["export"].__setitem__("actorAttestation",{"verified":True}),
                       "reject","METADATA_UNKNOWN_FIELD")
            check_json("standalone_tree_full_bad_extension_type","tree_full.json",
                       lambda d:d["export"].__setitem__("x_advisory",{"verified":True}),
                       "reject","METADATA_EXTENSION_INVALID")
            check_json("standalone_snapshot_actor_claim","planning_snapshot.json",
                       lambda d:d.__setitem__("actorAttestation",{"verified":True}),
                       "reject","METADATA_UNKNOWN_FIELD",False)
            check_json("standalone_ledger_actor_claim","planning_ledger.json",
                       lambda d:d.__setitem__("actorAttestation",{"verified":True}),
                       "reject","METADATA_UNKNOWN_FIELD",False)

            def modal_warning(row):
                fixture=conflict_zip(browser,OLD.read_text("utf-8"),Path(td)/"conflict.zip")
                data=update_zip_member(fixture,"resource_registry.json",
                                       lambda d:d.__setitem__("x_audit_hint","untrusted advisory"))
                ctx=None
                try:
                    ctx,p,errors,_=page_with_concurrency_instrumentation(browser,src)
                    original(p)
                    restore_dialog(p,data)
                    token="resource_registry.json.x_audit_hint"
                    assert modal(p) and "WARNING:" in status(p) and token in status(p),status(p)
                    assert "WARNING:" in p.locator("#authorityExplain").inner_text()
                    accept(p)
                    assert not modal(p),status(p)
                    assert "Restored" in status(p) and "WARNING:" in status(p) and token in status(p),status(p)
                    with p.expect_download(timeout=45000) as dl:
                        p.locator('[data-export="full_project"]').click()
                    dest=Path(td)/"modal-reexport.zip"
                    dl.value.save_as(str(dest))
                    with zipfile.ZipFile(dest) as z:
                        registry=json.loads(z.read("resource_registry.json"))
                        assert "x_audit_hint" not in registry,registry
                    assert not errors,errors
                    row["restore"]=status(p)
                finally:
                    if ctx:ctx.close()
            case(result,"restore_origin_modal_warning_visible_before_and_after_accept",modal_warning)
        finally:
            browser.close()
    passed=sum(r["outcome"]=="PASS" for r in result)
    overall={"schema":"app-nanny/repair029-standalone-and-modal/v1",
        "status":"CANDIDATE_TEST_PASS__INDEPENDENT_REVIEW_REQUIRED__PHASE1_BLOCKED" if passed==len(result)==7 else "CANDIDATE_TEST_FAIL__PHASE1_BLOCKED",
        "total":len(result),"passed":passed,"failed":len(result)-passed,
        "phase1_authorized":False,"cases":result}
    if args.results:
        args.results.write_text(json.dumps(overall,indent=2)+"\n")
    print(f"REPAIR029-STANDALONE: {overall['status']} ({passed}/{len(result)})")
    return 0 if passed==7 else 1

if __name__=="__main__":
    sys.exit(main())
