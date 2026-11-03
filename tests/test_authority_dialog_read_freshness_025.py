#!/usr/bin/env python3
"""Repair 025: authority-dialog/file-picker task-capture ordering tests.

Test the exact Repair 024 predecessor as a negative control, then exercise
the new candidate's authority-dialog settlement and stale read fencing.
All file reads are controlled promises; no native file:// durability claims.
"""
import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "studio/context_tree_studio_authority_repaired_024.html"
CANDIDATE = ROOT / "studio/context_tree_studio_authority_repaired_025.html"
PARENT_SHA256 = "6b07827b9806515a2704c65db2788c4339664c24be995b6bac019ccd6583d0c6"


def scaffold(name):
    return json.dumps({
        "schema": "context-tree/scaffold-v1",
        "project": {"name": name, "goal": "Verify dialog/reader ordering"},
        "tree": [{"name": "main.go", "kind": "file", "core": True}],
    }, ensure_ascii=False, indent=2)


A, B, ORIGINAL = scaffold("Import Candidate A"), scaffold("File B"), scaffold("Original Project")


def open_page(browser, html):
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("dialog", lambda dialog: dialog.accept())
    page.evaluate("""() => {
      const database={}, pending=[];
      Object.defineProperty(window,'localStorage',{configurable:true,value:{
        getItem:key=>Object.prototype.hasOwnProperty.call(database,key)?database[key]:null,
        setItem:(key,value)=>{database[key]=String(value)},
        removeItem:key=>{delete database[key]}
      }});
      const realRead=File.prototype.arrayBuffer;
      window.readController={
        pending:()=>pending.filter(x=>!x.done).map(x=>x.name),
        resolve:(name,raw)=>{
          const read=pending.find(x=>x.name===name&&!x.done);
          if(!read)throw Error('No pending read '+name);
          read.done=true;read.resolve(Uint8Array.from(raw).buffer);
        },
        reject:(name,reason)=>{
          const read=pending.find(x=>x.name===name&&!x.done);
          if(!read)throw Error('No pending read '+name);
          read.done=true;read.reject(Error(reason));
        }
      };
      File.prototype.arrayBuffer=function(){
        if(!this.name.endsWith('.json'))return realRead.call(this);
        return new Promise((resolve,reject)=>pending.push({
          name:this.name,resolve,reject,done:false
        }));
      };
    }""")
    page.set_content(html, wait_until="load")
    return context, page, errors


def settle(page):
    page.evaluate("() => new Promise(resolve => setTimeout(resolve, 0))")


def input_text(page):
    return page.locator("#jsonInput").input_value()


def import_original(page):
    page.locator("#jsonInput").fill(ORIGINAL)
    page.locator('[data-action="generate"]').click()
    assert "SEMANTICS_VALID" in page.locator("#status").inner_text()
    assert page.locator("#projectBadge").inner_text() == "Original Project"


def start_read(page, name="file-b.json", payload=B):
    page.locator("#scaffoldFile").set_input_files({
        "name": name,
        "mimeType": "application/json",
        "buffer": payload.encode("utf-8"),
    })
    page.wait_for_function("(n) => window.readController.pending().includes(n)", arg=name)
    assert page.locator("#scaffoldFile").input_value() == ""


def complete(page, name="file-b.json", payload=B, raw=None):
    bytes_ = list(payload.encode("utf-8") if raw is None else raw)
    page.evaluate("([n,b]) => window.readController.resolve(n,b)", [name, bytes_])
    settle(page)


def fail(page, name="file-b.json", message="OLD_IO_FAILURE"):
    page.evaluate("([n,m]) => window.readController.reject(n,m)", [name, message])
    settle(page)


def begin_authority_decision(page, raw=A):
    page.locator("#jsonInput").fill(raw)
    page.locator('[data-action="generate"]').click()
    assert page.locator("#authorityReview").is_visible(), page.locator("#status").inner_text()
    assert "UNRESOLVED_IDENTITY_CONFLICT" in page.locator("#status").inner_text()


def accept(page):
    page.locator("#authorityReason").fill("Human reviewed and accepted the imported scaffold.")
    page.locator("#authorityAccept").click()
    assert not page.locator("#authorityReview").is_visible()
    assert "SEMANTICS_VALID" in page.locator("#status").inner_text()


def cancel(page):
    page.locator("#authorityCancel").click()
    assert not page.locator("#authorityReview").is_visible()
    assert "Cancelled:" in page.locator("#status").inner_text()


def verify_export(page, path, project_name):
    with page.expect_download(timeout=45000) as dl:
        page.locator('[data-export="full_project"]').click()
    dl.value.save_as(str(path))
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        raw = json.loads(archive.read("tree_raw.json"))
        assert raw["project"]["name"] == project_name, (project_name, raw["project"]["name"])
    page.locator("#verifyFile").set_input_files(str(path))
    page.wait_for_function("() => document.querySelector('#verifyResult').textContent.includes('SEMANTICS_')", timeout=35000)
    assert "SEMANTICS_VALID" in page.locator("#verifyResult").inner_text()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path, default=CANDIDATE)
    parser.add_argument("--results", type=Path)
    args = parser.parse_args()
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA256, "Parent source mismatch"
    parent_html = PARENT.read_text(encoding="utf-8")
    current_html = args.html.read_text(encoding="utf-8")
    checks = []

    with sync_playwright() as pw, tempfile.TemporaryDirectory(prefix="app-nanny-025-") as temp:
        chrome = "/usr/bin/chromium" if Path("/usr/bin/chromium").exists() else None
        browser = pw.chromium.launch(headless=True, executable_path=chrome, args=["--no-sandbox"])

        def case(name, fn, html=current_html):
            context, page, errors = open_page(browser, html)
            try:
                fn(page)
                assert not errors, (name, errors)
            finally:
                context.close()
            checks.append(name)
            print("PASS", name, flush=True)

        def prior_failure(page):
            import_original(page)
            page.locator("#jsonInput").fill(A)
            start_read(page)
            page.locator('[data-action="generate"]').click()
            assert page.locator("#authorityReview").is_visible()
            complete(page)
            assert input_text(page) == B, "Parent no longer reproduces stale file overwrite"
            accept(page)
            assert page.locator("#projectBadge").inner_text() == "Import Candidate A"
            assert input_text(page) == B
            verify_export(page, Path(temp) / "parent-mismatch.zip", "Import Candidate A")
        case("exact_repair024_authority_mismatch_reproduced", prior_failure, parent_html)

        def approve_late_success(page):
            import_original(page)
            page.locator("#jsonInput").fill(A)
            start_read(page)
            page.locator('[data-action="generate"]').click()
            assert page.locator("#authorityReview").is_visible()
            before = page.locator("#status").inner_text()
            complete(page)
            assert input_text(page) == A
            assert page.locator("#status").inner_text() == before
            accept(page)
            assert page.locator("#projectBadge").inner_text() == "Import Candidate A"
            assert input_text(page) == A
            verify_export(page, Path(temp) / "approve.zip", "Import Candidate A")
        case("approve_ignores_pre_generate_completion_and_export_consistent", approve_late_success)

        def cancel_late_success(page):
            import_original(page)
            page.locator("#jsonInput").fill(A)
            start_read(page)
            page.locator('[data-action="generate"]').click()
            complete(page)
            assert input_text(page) == A
            cancel(page)
            assert page.locator("#projectBadge").inner_text() == "Original Project"
            assert input_text(page) == A
            verify_export(page, Path(temp) / "cancel.zip", "Original Project")
        case("cancel_ignores_pre_generate_completion_preserves_original", cancel_late_success)

        def accept_then_old_completion(page):
            import_original(page)
            page.locator("#jsonInput").fill(A)
            start_read(page)
            page.locator('[data-action="generate"]').click()
            accept(page)
            before = page.locator("#status").inner_text()
            complete(page)
            assert input_text(page) == A
            assert page.locator("#status").inner_text() == before
            assert page.locator("#projectBadge").inner_text() == "Import Candidate A"
        case("accept_before_old_read_settles", accept_then_old_completion)

        def cancel_then_old_completion(page):
            import_original(page)
            page.locator("#jsonInput").fill(A)
            start_read(page)
            page.locator('[data-action="generate"]').click()
            cancel(page)
            before = page.locator("#status").inner_text()
            complete(page)
            assert input_text(page) == A
            assert page.locator("#status").inner_text() == before
            assert page.locator("#projectBadge").inner_text() == "Original Project"
        case("cancel_before_old_read_settles", cancel_then_old_completion)

        def file_finishes_before_generate(page):
            import_original(page)
            start_read(page)
            complete(page)
            assert input_text(page) == B
            page.locator('[data-action="generate"]').click()
            assert page.locator("#authorityReview").is_visible()
            accept(page)
            assert page.locator("#projectBadge").inner_text() == "File B"
            assert input_text(page) == B
            verify_export(page, Path(temp) / "B-first.zip", "File B")
        case("settled_file_is_legitimate_generate_input", file_finishes_before_generate)

        def modal_started_read_finishes_inside(page):
            import_original(page)
            begin_authority_decision(page)
            start_read(page, "inside.json")
            before = page.locator("#status").inner_text()
            complete(page, "inside.json")
            assert input_text(page) == A
            assert page.locator("#status").inner_text() == before
            accept(page)
            assert input_text(page) == A
        case("read_started_during_dialog_cannot_edit_before_accept", modal_started_read_finishes_inside)

        def modal_started_read_finishes_after_accept(page):
            import_original(page)
            begin_authority_decision(page)
            start_read(page, "inside.json")
            accept(page)
            before = page.locator("#status").inner_text()
            complete(page, "inside.json")
            assert input_text(page) == A
            assert page.locator("#status").inner_text() == before
        case("read_started_during_dialog_cannot_edit_after_accept", modal_started_read_finishes_after_accept)

        def modal_started_read_finishes_after_cancel(page):
            import_original(page)
            begin_authority_decision(page)
            start_read(page, "inside.json")
            cancel(page)
            before = page.locator("#status").inner_text()
            complete(page, "inside.json")
            assert input_text(page) == A
            assert page.locator("#status").inner_text() == before
            assert page.locator("#projectBadge").inner_text() == "Original Project"
        case("read_started_during_dialog_cannot_edit_after_cancel", modal_started_read_finishes_after_cancel)

        def stale_io_error(page):
            import_original(page)
            page.locator("#jsonInput").fill(A)
            start_read(page)
            page.locator('[data-action="generate"]').click()
            before = page.locator("#status").inner_text()
            fail(page)
            assert page.locator("#status").inner_text() == before
            assert input_text(page) == A
            cancel(page)
        case("stale_io_failure_does_not_replace_dialog_status", stale_io_error)

        def stale_utf8_error(page):
            import_original(page)
            page.locator("#jsonInput").fill(A)
            start_read(page)
            page.locator('[data-action="generate"]').click()
            before = page.locator("#status").inner_text()
            complete(page, raw=b"\xff")
            assert page.locator("#status").inner_text() == before
            assert input_text(page) == A
            cancel(page)
        case("stale_invalid_utf8_does_not_replace_dialog_status", stale_utf8_error)

        def fresh_selection_after_cancel(page):
            import_original(page)
            begin_authority_decision(page)
            cancel(page)
            start_read(page, "fresh.json")
            complete(page, "fresh.json")
            assert input_text(page) == B
            page.locator('[data-action="generate"]').click()
            assert page.locator("#authorityReview").is_visible()
            accept(page)
            assert page.locator("#projectBadge").inner_text() == "File B"
        case("fresh_selection_after_cancel_is_permitted", fresh_selection_after_cancel)

        def fresh_selection_after_accept(page):
            import_original(page)
            begin_authority_decision(page)
            accept(page)
            start_read(page, "fresh.json")
            complete(page, "fresh.json")
            assert input_text(page) == B
            page.locator('[data-action="generate"]').click()
            assert page.locator("#authorityReview").is_visible()
            accept(page)
            assert page.locator("#projectBadge").inner_text() == "File B"
        case("fresh_selection_after_accept_is_permitted", fresh_selection_after_accept)

        browser.close()

    result = {"status": "LOCAL_CANDIDATE_PASS__INDEPENDENT_REAUDIT_REQUIRED__PHASE1_BLOCKED",
              "cases": checks, "count": len(checks)}
    if args.results:
        args.results.parent.mkdir(parents=True, exist_ok=True)
        args.results.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("PASS %d/%d" % (len(checks), len(checks)), flush=True)


if __name__ == "__main__":
    main()
