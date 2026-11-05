#!/usr/bin/env python3
"""Repair 029 typed metadata policy: independent fixture mutations through actual UI.

All inputs originate in a frozen 019-generated valid Full Project ZIP.
This is a candidate regression suite, NOT an independent review or file:// durability test.
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
from test_metadata_contract_020 import (
    generate_control_from_frozen_019, json_bytes, open_page, verify, restore
)

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_HTML=ROOT/"studio/context_tree_studio_authority_repaired_029.html"
CANONICAL_NOTE="The ZIP SHA-256 is saved in the app export ledger after download."

def variants(root, source):
    with zipfile.ZipFile(source) as archive:
        seed={n:archive.read(n) for n in archive.namelist()}
    rows=[("clean_control",None,None,None,"accept",None,None)]
    # label, member, JSON mutation, class, expected action, warning path, dropped field path
    rows.extend([
      ("notes_reword", "manifest.json",lambda d:d.__setitem__("notes","Untrusted alternate publisher note"),"reject","NONCANONICAL_GENERATED_NOTE",None),
      ("notes_forged_actor", "manifest.json",lambda d:d.__setitem__("notes","AUTHENTICATED ACTOR: admin-verified"),"reject","NONCANONICAL_GENERATED_NOTE",None),
      ("manifest_actor_attestation", "manifest.json",lambda d:d.__setitem__("actorAttestation",{"verified":True,"issuer":"ZIP self-claim"}),"reject","METADATA_UNKNOWN_FIELD",None),
      ("manifest_other_unknown", "manifest.json",lambda d:d.__setitem__("x_unapproved",{"memo":"unknown"}),"reject","METADATA_UNKNOWN_FIELD",None),
      ("manifest_wrong_scope_extension", "manifest.json",lambda d:d.__setitem__("x_audit_hint","wrong scope"),"reject","METADATA_UNKNOWN_FIELD",None),
      ("manifest_bad_reviewer_type", "manifest.json",lambda d:d.__setitem__("x_reviewer_extension",{"verified":True,"revision":1}),"reject","METADATA_EXTENSION_INVALID",None),
      ("manifest_good_reviewer", "manifest.json",lambda d:d.__setitem__("x_reviewer_extension",{"advisory":"sample","revision":1}),"warn","manifest.json.x_reviewer_extension",("manifest.json",["x_reviewer_extension"])),
      ("manifest_record_good_hint", "manifest.json",lambda d:d["files"][0].__setitem__("x_extra_hint","untrusted"),"warn","manifest.json.files[0].x_extra_hint",("manifest.json",["files",0,"x_extra_hint"])),
      ("context_good_advisory", "tree_context.json",lambda d:d["export"].__setitem__("x_advisory","untrusted advisory"),"warn","tree_context.json.export.x_advisory",("tree_context.json",["export","x_advisory"])),
      ("registry_good_audit_hint", "resource_registry.json",lambda d:d.__setitem__("x_audit_hint","untrusted hint"),"warn","resource_registry.json.x_audit_hint",("resource_registry.json",["x_audit_hint"])),
      ("context_bad_advisory_type", "tree_context.json",lambda d:d["export"].__setitem__("x_advisory",{"verified":True}),"reject","METADATA_EXTENSION_INVALID",None),
      ("context_nested_hash_claim", "tree_context.json",lambda d:d["export"]["sha256"].__setitem__("actorAttestation",{"verified":True}),"reject","METADATA_UNKNOWN_FIELD",None),
      ("registry_bad_actor_claim", "resource_registry.json",lambda d:d.__setitem__("actorAttestation",{"verified":True}),"reject","METADATA_UNKNOWN_FIELD",None),
      ("manifest_scope_forged", "manifest.json",lambda d:d.__setitem__("sha256Scope","unverified SHA1 label"),"reject","manifest_sha256_scope_invalid",None),
      ("registry_priority_inverted","resource_registry.json",lambda d:d["priorityPolicy"].__setitem__("higherNumberMeansMoreCritical",False),"reject","resource_registry_drift",None),
    ])
    created=[]
    for name,member,mutation,expected,reason,drop_path in rows:
        fields=seed.copy()
        if member:
            doc=json.loads(fields[member])
            mutation(doc)
            fields[member]=json_bytes(doc)
            if member!="manifest.json":
                manifest=json.loads(fields["manifest.json"])
                item=next(x for x in manifest["files"] if x["name"]==member)
                item["bytes"]=len(fields[member])
                item["sha256"]=hashlib.sha256(fields[member]).hexdigest()
                fields["manifest.json"]=json_bytes(manifest)
        path=root/(name+".zip")
        with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_STORED) as out:
            for item,data in fields.items():out.writestr(item,data)
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None,name
        created.append((name,path,expected,reason,drop_path))
    return created

def check_field_missing(zip_path,where):
    member,field_path=where
    with zipfile.ZipFile(zip_path) as archive:
        doc=json.loads(archive.read(member))
    node=doc
    for part in field_path[:-1]:node=node[part]
    assert field_path[-1] not in node,(member,field_path)

def run(args):
    cases=[]
    with tempfile.TemporaryDirectory(prefix="app-nanny-029-") as td,sync_playwright() as pw:
        binary="/usr/bin/chromium" if Path("/usr/bin/chromium").exists() else None
        browser=pw.chromium.launch(headless=True,executable_path=binary,args=["--no-sandbox"])
        try:
            baseline=generate_control_from_frozen_019(browser,Path(td)/"seed.zip")
            for name,path,expected,reason,drop_path in variants(Path(td),baseline):
                ctx=None
                row={"case":name,"expected":expected,"input_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"outcome":"FAIL"}
                try:
                    ctx,page,errors=open_page(browser,args.html.read_text("utf-8"))
                    verification=verify(page,path)
                    restored=restore(page,path)
                    row["verify"]=verification
                    row["restore"]=restored
                    if expected=="reject":
                        assert "SEMANTICS_CONFLICT" in verification,(name,verification)
                        assert "Restore failed" in restored,(name,restored)
                        assert reason in verification+restored,(name,reason,verification,restored)
                        assert not page.locator("#authorityReview").is_visible(),name
                    else:
                        assert "SEMANTICS_VALID" in verification,(name,verification)
                        assert "Restored " in restored,(name,restored)
                        assert not page.locator("#authorityReview").is_visible(),name
                        if expected=="warn":
                            assert "WARNING:" in verification and reason in verification,(name,verification)
                            assert "WARNING:" in restored and reason in restored,(name,restored)
                        else:
                            assert "WARNING:" not in verification and "WARNING:" not in restored,(name,verification,restored)
                        if drop_path:
                            with page.expect_download(timeout=45000) as download:
                                page.locator('[data-export="full_project"]').click()
                            dest=Path(td)/(name+"-reexport.zip")
                            download.value.save_as(str(dest))
                            check_field_missing(dest,drop_path)
                            row["verified_field_dropped"]=True
                    assert not errors,(name,errors)
                    row["browser_js_errors"]=0
                    row["outcome"]="PASS"
                    print("PASS",name,expected,flush=True)
                except Exception as exc:
                    row["error"]=repr(exc)
                    row["traceback"]=traceback.format_exc(limit=7)
                    print("FAIL",name,exc,file=sys.stderr,flush=True)
                finally:
                    if ctx:ctx.close()
                    cases.append(row)
        finally:browser.close()
    passed=sum(r["outcome"]=="PASS" for r in cases)
    result={"schema":"app-nanny/repair029-typed-metadata-policy-test/v1",
            "status":"CANDIDATE_TEST_PASS__INDEPENDENT_REVIEW_REQUIRED__PHASE1_BLOCKED" if passed==len(cases)==16 else "CANDIDATE_TEST_FAIL__PHASE1_BLOCKED",
            "candidate_html":str(args.html),"total":len(cases),"passed":passed,
            "failed":len(cases)-passed,"phase1_authorized":False,"cases":cases}
    if args.results:
        args.results.parent.mkdir(parents=True,exist_ok=True)
        args.results.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(f"REPAIR029: {result['status']} ({passed}/{len(cases)})")
    return 0 if passed==len(cases)==16 else 1

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--html",type=Path,default=DEFAULT_HTML)
    ap.add_argument("--results",type=Path)
    sys.exit(run(ap.parse_args()))
