import {validateRow, validateAll, exportEdits, importEdits, verifySources} from "./rules.js";
import {controlReferenceURL} from "../controls/links.js";
const output = document.querySelector("#results"); let passed = 0;
function check(condition, label) {if (!condition) throw Error(label); passed++;}
function rejects(fn, label) {let failed = false; try {fn();} catch {failed = true;} check(failed, label);}
const normalize = lines => lines.map(l => ({box: l.box, row: l.row, extent: l.extent, cells: l.cells, buffer: l.buffer}));
const canonical = value => JSON.stringify(value, (_, v) => v && typeof v === "object" && !Array.isArray(v) ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)) : v);
const equal = (a, b) => canonical(a) === canonical(b);
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function frameReady(frame) {
  for (let i = 0; i < 250; i++) {if (frame.contentDocument?.body.dataset.ready === "true") return frame.contentDocument; await pause(100);}
  throw Error("Workbench iframe did not initialize: " + frame.contentDocument?.querySelector("#notice")?.textContent);
}
async function navigate(frame, url) {
  await new Promise(resolve => {frame.addEventListener("load", resolve, {once: true}); frame.src = url;});
  return frameReady(frame);
}
async function run() {
  const [data, oracle, source, opening] = await Promise.all([fetch("catalog.json").then(r => r.json()), fetch("checks-oracle.json").then(r => r.json()), fetch("../data/script.tsv").then(r => r.text()), fetch("../data/intro.tsv").then(r => r.text())]);
  check(data.revision === oracle.revision, "Regenerate the Python/browser oracle");
  await verifySources(data, source, opening); passed++;
  const referenceURL = new URL("../controls/", location.href);
  const reference = new DOMParser().parseFromString(await fetch(referenceURL).then(r => r.text()), "text/html");
  const tokens = new Set([...Object.keys(data.rules.controls).map(name => `<${name}>`), "<page>", "<$FF>", "<$B6>",
    ...data.records.flatMap(row => row.controls)]);
  for (const token of tokens) {
    const url = new URL(controlReferenceURL(token));
    check(url.pathname === referenceURL.pathname && !!reference.getElementById(url.hash.slice(1)), `Missing control explanation: ${token}`);
  }
  for (const link of reference.querySelectorAll('a[href^="#"]')) check(!!reference.getElementById(link.hash.slice(1)), `Broken reference section: ${link.hash}`);
  for (const [s, o] of [[source + source.split("\n")[1] + "\n", opening], [source, opening.replace("Mother: My child...", "Mother: My child...").replace("ははおや", "異なる")], ["", opening]]) {
    let failed = false; try {await verifySources(data, s, o);} catch {failed = true;} check(failed, "Corrupt/missing source rejected");
  }
  const rows = new Map(data.records.map(r => [r.key, r]));
  const initial = validateAll(data);
  for (const [key, result] of initial) {
    check(result.valid, `${key}: baseline rejected: ${result.errors.join("; ")}`);
    check(equal(normalize(result.lines), oracle.baseline[key]), `${key}: baseline metrics differ\n${JSON.stringify(normalize(result.lines))}\n${JSON.stringify(oracle.baseline[key])}`);
  }
  for (const fixture of oracle.cases) {
    const result = validateRow(rows.get(fixture.key), fixture.text, data);
    check(result.valid === fixture.valid, `${fixture.key} ${fixture.label}: valid ${result.valid}, Python ${fixture.valid}: ${result.errors.join("; ")}`);
    // For rejected text the two parsers can reject at different stages. Metrics must
    // agree whenever both engines reach layout, and always for accepted text.
    if (result.lines.length && fixture.lines.length || fixture.valid) check(equal(normalize(result.lines), fixture.lines), `${fixture.key} ${fixture.label}: metrics differ`);
  }
  for (const fixture of oracle.batches) {
    const invalid = [...validateAll(data, fixture.edits)].filter(([, r]) => !r.valid).map(([key]) => key).sort();
    check(equal(invalid, fixture.invalid), `${fixture.label}: affected entries differ\n${JSON.stringify(invalid)}\n${JSON.stringify(fixture.invalid)}`);
  }
  const merged = importEdits(oracle.validTSV, data);
  check(equal(merged, oracle.validEdits), "Python TSV imports in the browser");
  const exported = exportEdits(data, merged);
  check(equal(importEdits(exported, data), merged), "Browser TSV round trip");
  rejects(() => importEdits(exported.replace(data.rulesRevision, "0".repeat(64)), data), "Stale rules accepted");
  rejects(() => importEdits(exported + "30:$7EC6\tBad\n", data), "Duplicate address accepted");
  rejects(() => importEdits(exported, data, {"30:$7EC6": "Old"}), "Conflicting saved edit overwritten");
  rejects(() => exportEdits(data, {"30:$7EC6": "W".repeat(50)}), "Overflow exported");
  rejects(() => exportEdits(data, {"11:$55C6": "W".repeat(22)}), "Invalid shared consumer exported");
  const storage = "shiren-workbenches-v1", original = localStorage.getItem(storage), frames = [];
  try {
    localStorage.removeItem(storage);
    const frame = document.createElement("iframe"); frame.style.cssText = "width:1440px;height:1100px;border:0"; frames.push(frame); document.body.append(frame); frame.src = "./?subject=verbs";
    let doc = await frameReady(frame);
    check(doc.querySelector("#title").textContent === "Item actions", "Workbench route title");
    check(doc.querySelectorAll("#subjects a").length === data.subjects.length, "All workbenches in navigation");
    check(doc.querySelector(".control-guide-link a")?.href === referenceURL.href, "Workbench links to the control reference under the project path");
    const input = doc.querySelector('[data-key="30:$7EC6"] textarea'); check(!!input, "Verb editor present");
    input.value = "Use"; input.dispatchEvent(new Event("input", {bubbles: true})); await pause(1000);
    check(!doc.querySelector("#export").disabled, "Valid edit enables download");
    check(JSON.parse(localStorage.getItem(storage)).edits['30:$7EC6'] === "Use", "Draft saved");
    input.value = "W".repeat(50); input.dispatchEvent(new Event("input", {bubbles: true})); await pause(1000);
    check(doc.querySelector("#export").disabled && !doc.querySelector("#global-issues").hidden, "Invalid edit blocks download");
    doc = await navigate(frame, "./?subject=verbs&reload=1");
    check(doc.querySelector('[data-key="30:$7EC6"] textarea').value === "W".repeat(50), "Invalid draft survives reload");
    const file = new File([oracle.validTSV], "edits.tsv", {type: "text/tab-separated-values"}), transfer = new DataTransfer(); transfer.items.add(file);
    const upload = doc.querySelector("#file"); upload.files = transfer.files; upload.dispatchEvent(new Event("change", {bubbles: true})); await pause(1000);
    check(doc.querySelector("#notice").textContent.includes("conflicts"), "Import conflict is shown without overwriting");
    doc = await navigate(frame, "./?subject=choices");
    const control = doc.querySelector(".required a");
    check(control?.href === controlReferenceURL(control?.textContent || "") && control?.target === "_blank" && control?.rel === "noopener", "Required control opens its explanation in a separate tab");
    localStorage.removeItem(storage); doc = await navigate(frame, "./?subject=cinematic&fresh=1");
    check(doc.querySelectorAll("textarea").length === 10, "Cinematic page size");
    const sourceText = doc.querySelector('[data-key="intro_01"] .jp').textContent;
    check(sourceText === rows.get("intro_01").jp, "Cinematic Japanese loaded");
    frame.style.width = "390px"; await pause(300);
    check(doc.documentElement.scrollWidth <= doc.documentElement.clientWidth, "Mobile layout overflows horizontally");
    localStorage.setItem(storage, JSON.stringify({rules: "old", edits: {"30:$7EC6": "Keep me"}}));
    doc = await navigate(frame, "./?subject=items&stale=1");
    check(!doc.querySelector("#recovery").hidden && [...doc.querySelectorAll("textarea")].every(e => e.disabled), "Stale draft enters recovery without overwrite");
    check(JSON.parse(localStorage.getItem(storage)).edits['30:$7EC6'] === "Keep me", "Stale edit retained");
    await new Promise(resolve => {frame.addEventListener("load", resolve, {once: true}); frame.src = referenceURL.href;});
    doc = frame.contentDocument;
    check(doc.querySelector("h1")?.textContent === "Control code reference", "Control reference loads in the staged site");
    check(doc.documentElement.scrollWidth <= doc.documentElement.clientWidth, "Mobile control reference overflows horizontally");
  } finally {frames.forEach(f => f.remove()); if (original === null) localStorage.removeItem(storage); else localStorage.setItem(storage, original);}
  output.textContent = `${passed} checks passed.\nCoverage, Python metrics, controls, bank arity, pixels, source scanners, buffers, shared dependencies, TSVs, browser drafts, control reference links and mobile layout checked.`;
  output.dataset.status = "passed";
}
run().catch(error => {output.textContent = `${passed} checks passed before failure.\n${error.stack}`; output.dataset.status = "failed";});
