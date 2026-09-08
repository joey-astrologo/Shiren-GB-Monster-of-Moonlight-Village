import {validateDraft, wrapDraft, renderLines, measure, exportEdits, importEdits, importJapanese} from "./rules.js";

const result = document.querySelector("#results"), frame = document.querySelector("#app");
const STORAGE = "shiren-prose-studio-v1";
const saved = localStorage.getItem(STORAGE);
let checks = 0;
function assert(ok, label) { checks++; if (!ok) throw new Error(label); }
function equal(actual, expected, label) { assert(JSON.stringify(actual) === JSON.stringify(expected), `${label}\nActual: ${JSON.stringify(actual)}\nExpected: ${JSON.stringify(expected)}`); }
function rejects(action, label) { let rejected = false; try { action(); } catch { rejected = true; } assert(rejected, label); }
async function rejectsAsync(action, label) { let rejected = false; try { await action(); } catch { rejected = true; } assert(rejected, label); }
async function until(predicate, label) {
  for (let i = 0; i < 400; i++) {
    if (predicate()) return;
    await new Promise(resolve => setTimeout(resolve, 25));
  }
  throw new Error("Timed out: " + label);
}
const cleanLines = lines => lines.map(({box, row, advance, extent, cells, buffer}) => ({box, row, advance, extent, cells, buffer}));

try {
  const [data, oracle] = await Promise.all([fetch("catalog.json").then(r => r.json()), fetch("test-oracle.json").then(r => { if (!r.ok) throw new Error("Generate the Python oracle and serve with --test."); return r.json(); })]);
  assert(oracle.revision === data.revision, "Oracle revision matches catalogue");
  const byLoc = new Map(data.records.map(row => [row.loc, row]));
  for (const expected of oracle.baseline) {
    const row = byLoc.get(expected.loc), check = validateDraft(row, row.draft, data);
    assert(check.valid, `${row.loc}: accepted baseline rejected: ${check.errors}`);
    equal(check.compiled, expected.compiled, row.loc + " accepted layout preserved");
    equal(cleanLines(check.lines), expected.lines, row.loc + " baseline Python geometry");
  }
  for (const expected of oracle.wrapping) {
    const row = byLoc.get(expected.loc), actual = wrapDraft(row, row.draft, data);
    equal(actual.compiled, expected.compiled, row.loc + " Python wrapper parity");
    equal(cleanLines(renderLines(row, actual.compiled, data)), expected.lines, row.loc + " rewrapped Python geometry");
  }
  for (const sample of oracle.metrics) {
    const actual = measure(sample.text, data);
    equal([actual.advance, actual.extent, actual.cells], [sample.advance, sample.extent, sample.cells], "Metric edge: " + sample.text);
  }
  const {loc, text, tsv} = oracle.validEdit, row = byLoc.get(loc);
  assert(validateDraft(row, text, data).valid, "Edited row fits");
  equal(importEdits(exportEdits(data, {[loc]: text}), data), {[loc]: text}, "TSV round trip");
  equal(importEdits(tsv.replaceAll("\n", "\r\n"), data), {[loc]: text}, "CRLF TSV import");
  const downloaded = exportEdits(data, {[loc]: text, [data.records[0].loc]: data.records[0].draft});
  assert(downloaded.split("\n").filter(line => line && !line.startsWith("#")).length === 1, "Export contains only changed rows");
  rejects(() => exportEdits(data, {}), "Empty export blocked");
  rejects(() => importEdits(tsv + `${loc}\t${text}\n`, data), "Duplicate TSV address blocked");
  rejects(() => importEdits(tsv.replace(row.base, "0".repeat(64)), data), "Stale row blocked");
  rejects(() => importEdits(tsv.replace(data.rulesRevision, "0".repeat(64)), data), "Stale rules blocked");
  rejects(() => importEdits(tsv, data, {[loc]: "Keyaki: Hello!"}), "Conflicting browser edit blocked");
  for (const value of ["", "é", "A".repeat(40), "Hello\tthere", "Hello\nthere", "<bad>", "<name", "=Hello", "Hello<end>", " Hello", "Hello ", "Hello<$EA>", "<script>alert(1)</script>"]) {
    assert(!validateDraft(row, value, data).valid, "Invalid text rejected: " + JSON.stringify(value));
    rejects(() => exportEdits(data, {[loc]: value}), "Invalid export blocked");
  }
  const named = byLoc.get("14:$51D3");
  assert(!validateDraft(named, named.draft.replace("<name>", "Shiren"), data).valid, "Required player token protected");
  const selected = data.records.find(row => row.editable && row.draft.includes("<cE3:05>"));
  assert(!validateDraft(selected, selected.draft.replace("<cE3:05>", "<cE3:04>"), data).valid, "Selector argument protected");
  const locked = data.records.find(row => !row.editable);
  assert(!validateDraft(locked, "Edited", data).valid, "Structured text protected");
  const sourceText = await fetch("../data/script.tsv").then(r => { if (!r.ok) throw new Error("Bundled source TSV is missing."); return r.text(); });
  const source = await importJapanese(sourceText, data);
  assert(Object.keys(source).length === 480, "Japanese source matched");
  await rejectsAsync(() => importJapanese(sourceText.replace(source[loc], "Wrong source"), data), "Wrong source rejected");

  // Exercise the actual editor: edit, validation, Blob download, reload and file input.
  localStorage.removeItem(STORAGE);
  frame.src = "index.html";
  await until(() => frame.contentDocument?.body.dataset.ready === "true", "initial editor load");
  let doc = frame.contentDocument, win = frame.contentWindow;
  assert(doc.querySelector("#source-status").textContent.includes("loaded"), "Bundled Japanese loads without file import");
  assert(doc.querySelector("#source-description").textContent.includes("included script"), "Included source identified in the UI");
  assert(doc.querySelector('.source-actions a[download]').href === new URL("../data/script.tsv", location.href).href, "Original TSV download uses project-relative URL");
  assert(doc.querySelector(`[data-loc="${loc}"] .jp`).textContent.includes(source[loc].split("<")[0]), "Japanese displayed beside its matching entry");
  let input = doc.querySelector(`[data-loc="${loc}"] textarea`);
  assert(!!input, "Prose is editable");
  input.value = "é"; input.dispatchEvent(new win.Event("input", {bubbles: true}));
  assert(doc.querySelector("#export-edits").disabled && doc.querySelector("#error-count").textContent === "1", "Invalid UI draft blocks download");
  input.value = text; input.dispatchEvent(new win.Event("input", {bubbles: true}));
  assert(!doc.querySelector("#export-edits").disabled && doc.querySelector("#error-count").textContent === "0", "Corrected UI draft enables download");
  assert(JSON.parse(localStorage.getItem(STORAGE)).edits[loc] === text, "Autosave contains edit");
  let blob;
  const createURL = win.URL.createObjectURL.bind(win.URL);
  win.URL.createObjectURL = value => { blob = value; return createURL(value); };
  doc.querySelector("#export-edits").click();
  assert(!!blob, "Download creates a file Blob");
  equal(importEdits(await blob.text(), data), {[loc]: text}, "Downloaded file contains the UI edit");
  frame.src = "index.html?reload=1";
  await until(() => frame.contentWindow.location.search === "?reload=1" && frame.contentDocument?.body.dataset.ready === "true", "reload saved draft");
  doc = frame.contentDocument; win = frame.contentWindow;
  assert(doc.querySelector(`[data-loc="${loc}"] textarea`).value === text, "Draft survives reload");
  assert(doc.querySelector("#source-status").textContent.includes("loaded"), "Japanese reloads automatically on a later visit");
  const search = doc.querySelector("#search");
  search.value = loc; search.dispatchEvent(new win.Event("input", {bubbles: true}));
  assert(doc.querySelectorAll(".record").length === 1, "Search finds exact address");
  doc.querySelector('[data-filter="edited"]').click();
  assert(doc.querySelectorAll(".record").length === 1, "Edited filter works");
  localStorage.removeItem(STORAGE);
  frame.src = "index.html?import=1";
  await until(() => frame.contentWindow.location.search === "?import=1" && frame.contentDocument?.body.dataset.ready === "true", "fresh import page");
  doc = frame.contentDocument; win = frame.contentWindow;
  const transfer = new win.DataTransfer(); transfer.items.add(new win.File([tsv], "changes.tsv", {type: "text/tab-separated-values"}));
  const fileInput = doc.querySelector("#edits-file"); fileInput.files = transfer.files;
  fileInput.dispatchEvent(new win.Event("change", {bubbles: true}));
  await until(() => doc.querySelector("#edited-count").textContent === "1", "file input import");
  assert(doc.querySelector(`[data-loc="${loc}"] textarea`).value === text, "File-input import fills draft");
  frame.style.width = "390px";
  await new Promise(resolve => setTimeout(resolve, 100));
  const viewport = doc.documentElement.clientWidth;
  const overflow = [...doc.querySelectorAll("body *")].filter(element => element.getBoundingClientRect().right > viewport + 1 &&
    !element.closest("#events") && getComputedStyle(element).position !== "fixed").slice(0, 8).map(element => element.className);
  assert(doc.documentElement.scrollWidth <= viewport, `Mobile horizontal overflow: viewport ${viewport}, page ${doc.documentElement.scrollWidth}, elements ${overflow}`);
  assert(win.matchMedia("(max-width: 760px)").matches, "Mobile media query applies");
  assert(win.getComputedStyle(doc.querySelector(".record-body")).gridTemplateColumns.split(" ").length === 1, "Mobile source and translation stack");
  assert(win.getComputedStyle(doc.querySelector("#rules-mobile")).display !== "none", "Mobile guide remains accessible");
  // Simulate a missing or mismatched bundled file, then recover using the file input.
  const appHTML = await fetch("index.html").then(r => r.text());
  for (const [status, payload] of [[404, "Missing source"], [200, sourceText.replace(source[loc], "Wrong source")]]) {
    const stub = `<base href="${new URL("./", location.href).href}"><script>
      const originalFetch = window.fetch.bind(window);
      window.fetch = (url, options) => url === "../data/script.tsv"
        ? Promise.resolve(new Response(${JSON.stringify(payload).replaceAll("<", "\\u003c")}, {status: ${status}}))
        : originalFetch(url, options);
      <\/script>`;
    frame.srcdoc = appHTML.replace("<head>", "<head>" + stub);
    await until(() => frame.contentWindow.location.href === "about:srcdoc" && frame.contentDocument?.body.dataset.ready === "true" &&
      frame.contentDocument.querySelector("#source-status").textContent === "Japanese source unavailable", "source failure state");
    doc = frame.contentDocument; win = frame.contentWindow;
    assert(!doc.querySelector("#import-source").disabled, "Missing/mismatched source offers manual recovery");
    assert(!doc.querySelector("#notice").hidden && !doc.querySelector('.jp').textContent.includes(source[loc].split("<")[0]), "Invalid source is reported without displaying it");
    const sourceTransfer = new win.DataTransfer();
    sourceTransfer.items.add(new win.File([sourceText], "script.tsv", {type: "text/tab-separated-values"}));
    const sourceInput = doc.querySelector("#source-file"); sourceInput.files = sourceTransfer.files;
    sourceInput.dispatchEvent(new win.Event("change", {bubbles: true}));
    await until(() => doc.querySelector("#source-status").textContent.includes("loaded"), "manual source recovery");
    assert(doc.querySelector(`[data-loc="${loc}"] .jp`).textContent.includes(source[loc].split("<")[0]), "Matching local source restores Japanese");
  }
  frame.removeAttribute("srcdoc");
  // Catalogue drift must preserve recovery data and prevent accidental overwrite.
  const stale = JSON.stringify({rules: "old", edits: {[loc]: "An older saved translation"}, bases: {}});
  localStorage.setItem(STORAGE, stale);
  frame.src = "index.html?stale=1";
  await until(() => frame.contentWindow.location.search === "?stale=1" && frame.contentDocument?.body.dataset.ready === "true", "stale draft page");
  doc = frame.contentDocument; win = frame.contentWindow;
  assert(!doc.querySelector("#recovery").hidden, "Stale drafts offer recovery");
  input = doc.querySelector(`[data-loc="${loc}"] textarea`); input.value = text;
  input.dispatchEvent(new win.Event("input", {bubbles: true}));
  assert(localStorage.getItem(STORAGE) === stale && doc.querySelector("#export-edits").disabled, "Stale draft is not overwritten");
  result.textContent = JSON.stringify({status: "PASS", checks, baseline: oracle.baseline.length, wrapped: oracle.wrapping.length,
    coverage: "Python geometry/wrapper parity, TSV round trip/rejection, source integrity, edit/download/reload/import/recovery UI"}, null, 2);
  document.body.dataset.status = "pass";
} catch (error) {
  result.textContent = JSON.stringify({status: "FAIL", checks, error: error.stack}, null, 2);
  document.body.dataset.status = "fail";
} finally {
  frame.removeAttribute("srcdoc");
  frame.src = "about:blank";
  if (saved === null) localStorage.removeItem(STORAGE); else localStorage.setItem(STORAGE, saved);
}
