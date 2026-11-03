#!/usr/bin/env python3
"""Repair 020: deterministic, hash-valid ZIP mutations against source read from this Git tree.

No network, no production repo writes, no native file:// persistence claim.
Usage: python tests/test_metadata_contract_020.py
       python tests/test_metadata_contract_020.py --html studio/context_tree_studio_authority_repaired_020.html
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "studio" / "context_tree_studio_authority_repaired_019.html"
BASELINE_SHA256 = "8b41c0096ebbbc4f920b1f059ea908d9b0aded5d6c6f01cdedeec77e77c14674"

def json_bytes(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def fixture_variants(root, seed_path):
    with zipfile.ZipFile(seed_path) as archive:
        seed = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(seed["manifest.json"])
    prior_version = ("Version: " + manifest["version"]).encode("utf-8")
    assert seed["README.txt"].count(prior_version) == 1

    variants = {"control": seed_path}
    def make(tag, name, fn, raw=False):
        members = seed.copy()
        if raw:
            members[name] = fn(members[name])
        else:
            doc = json.loads(members[name])
            fn(doc)
            members[name] = json_bytes(doc)
        if name != "manifest.json":
            manifest = json.loads(members["manifest.json"])
            record = next(rec for rec in manifest["files"] if rec["name"] == name)
            record["bytes"] = len(members[name])
            record["sha256"] = hashlib.sha256(members[name]).hexdigest()
            members["manifest.json"] = json_bytes(manifest)
        path = root / (tag + ".zip")
        with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_STORED) as archive:
            for key, value in members.items():
                archive.writestr(key, value)
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
        variants[tag] = path

    make("manifest_scope_forged", "manifest.json", lambda d: d.__setitem__("sha256Scope", "SHA-1 digest of unrelated bytes"))
    make("tree_full_hash_algorithm_forged", "tree_full.json", lambda d: d["export"]["sha256"].__setitem__("algorithm", "MD5"))
    make("snapshot_hash_algorithm_forged", "planning_snapshot.json", lambda d: d["contentHash"].__setitem__("algorithm", "MD5"))
    make("planning_ledger_hash_scope_forged", "planning_ledger.json", lambda d: d["sha256"].__setitem__("scope", "unchecked unrelated payload"))
    make("registry_priority_policy_inverted", "resource_registry.json", lambda d: d["priorityPolicy"].__setitem__("higherNumberMeansMoreCritical", False))
    make("registry_format_invalid", "resource_registry.json", lambda d: d.__setitem__("format", "fake-resource-registry/not-supported"))
    make("readme_version_forged", "README.txt", lambda b: b.replace(prior_version, b"Version: V999.999.999.999"), raw=True)
    make("readme_claims_unsafe_changes", "README.txt", lambda b: b.replace(b"No filesystem changes are performed.", b"This tool modifies the original repository."), raw=True)
    make("tree_context_hash_scope_forged", "tree_context.json", lambda d: d["export"]["sha256"].__setitem__("scope", "unrelated content"))
    make("resource_priority_labels_changed", "resource_registry.json", lambda d: d["priorityPolicy"].__setitem__("10", "optional"))
    make("manifest_scope_missing", "manifest.json", lambda d: d.pop("sha256Scope"))
    make("readme_content_added", "README.txt", lambda b: b + b"New unsupported restore promise.\n", raw=True)
    make("planning_snapshot_scope_missing", "planning_snapshot.json", lambda d: d["contentHash"].pop("scope"))
    return variants


def generate_control_from_frozen_019(browser, seed_path):
    baseline = BASELINE.read_bytes()
    assert hashlib.sha256(baseline).hexdigest() == BASELINE_SHA256, "Repair 019 baseline changed"
    ctx, page, errors = open_page(browser, baseline.decode("utf-8"))
    page.on("dialog", lambda dialog: dialog.accept())
    page.locator('[data-action="load-example"]').click()
    page.locator('[data-action="generate"]').click()
    assert "SEMANTICS_VALID" in page.locator("#status").inner_text()
    with page.expect_download(timeout=45000) as info:
        page.locator('[data-export="full_project"]').click()
    info.value.save_as(str(seed_path))
    assert not errors, errors
    ctx.close()
    with zipfile.ZipFile(seed_path) as archive:
        assert archive.testzip() is None
    return seed_path


def open_page(browser, html):
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    # about:blank denies native storage. A deliberately isolated in-memory key-value
    # store makes the browser test meaningful without asserting file:// durability.
    page.evaluate("""() => {const db={}; Object.defineProperty(window,'localStorage',
       {configurable:true,value:{getItem:k=>Object.prototype.hasOwnProperty.call(db,k)?db[k]:null,
        setItem:(k,v)=>{db[k]=String(v)},removeItem:k=>{delete db[k]}}});}""")
    page.set_content(html, wait_until="load")
    return context, page, errors


def verify(page, path):
    page.locator("#verifyFile").set_input_files(str(path))
    page.wait_for_function("""() => {const t=document.querySelector('#verifyResult').textContent;
       return t.includes('SEMANTICS_') || t.includes('VERIFICATION FAILED');}""", timeout=30000)
    return page.locator("#verifyResult").inner_text()


def restore(page, path):
    page.locator("#restoreFile").set_input_files(str(path))
    page.wait_for_function("""() => {const t=document.querySelector('#status').textContent;
       return t.includes('Restore failed') || t.includes('Restored ') || t.includes('Restore blocked') || t.includes('AUTHORITY');}""", timeout=30000)
    return page.locator("#status").inner_text()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", type=Path, default=ROOT / "studio" / "context_tree_studio_authority_repaired_020.html")
    ap.add_argument("--json", type=Path, default=None, help="Write complete evidence to JSON")
    args = ap.parse_args()
    html = args.html.read_text(encoding="utf8")
    results = []
    with tempfile.TemporaryDirectory(prefix="app-nanny-020-") as tmp:
        with sync_playwright() as pw:
            binary = "/usr/bin/chromium" if Path("/usr/bin/chromium").exists() else None
            browser = pw.chromium.launch(headless=True, executable_path=binary, args=["--no-sandbox"])
            seed = generate_control_from_frozen_019(browser, Path(tmp) / "control.zip")
            variants = fixture_variants(Path(tmp), seed)
            for name, fixture in variants.items():
                ctx, page, js_errors = open_page(browser, html)
                message = verify(page, fixture)
                expected = "SEMANTICS_VALID" if name == "control" else "SEMANTICS_CONFLICT"
                assert expected in message, f"{name}: expected {expected}, got {message}"
                assert not js_errors, f"{name}: browser exceptions {js_errors}"
                before_badge = page.locator("#projectBadge").inner_text()
                restore_status = restore(page, fixture)
                if name == "control":
                    assert "Restored " in restore_status, (name,restore_status)
                    assert "No project" not in page.locator("#projectBadge").inner_text()
                    # A successful restore must produce a self-verifying, portable re-export.
                    with page.expect_download(timeout=40000) as download_info:
                        page.locator('[data-export="full_project"]').click()
                    download = download_info.value
                    reexport_path = Path(tmp) / "roundtrip.zip"
                    download.save_as(str(reexport_path))
                    assert "SEMANTICS_VALID" in verify(page,reexport_path)
                    # It must also restore into a new session.
                    other, fresh, other_errors = open_page(browser, html)
                    assert "Restored " in restore(fresh, reexport_path)
                    assert not other_errors
                    other.close()
                else:
                    assert "Restore failed" in restore_status, (name,restore_status)
                    assert page.locator("#projectBadge").inner_text() == before_badge, (name,page.locator("#projectBadge").inner_text())
                row = {"case":name,"sha256":hashlib.sha256(fixture.read_bytes()).hexdigest(),
                       "verification":expected,"restore":"success" if name=="control" else "rejected",
                       "browser_errors":len(js_errors)}
                results.append(row)
                print(f"PASS {name}: {expected}; restore {row['restore']}",flush=True)
                ctx.close()
            browser.close()
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"status":"PASS", "checks":len(results), "cases":results}, indent=2)+"\n")
    print(f"PASS {len(results)}/{len(results)} cases; source={args.html}")


if __name__=="__main__":
    main()
