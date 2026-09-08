import {validateAll, exportEdits, importEdits, verifySources, describeRules} from "./rules.js";
const $ = s => document.querySelector(s), STORAGE = "shiren-workbenches-v1", PAGE_SIZE = 10;
let data, records, results, edits = {}, subject, page = 0, stale = null, ready = false, timer;
const cards = new Map();
function node(tag, className, text) {const e = document.createElement(tag); if (className) e.className = className; if (text !== undefined) e.textContent = text; return e;}
function notify(text, error = false) {$("#notice").textContent = text; $("#notice").hidden = !text; $("#notice").className = `notice${error ? " error" : ""}`;}
function download(name, text, type = "text/tab-separated-values;charset=utf-8") {
  const url = URL.createObjectURL(new Blob([text], {type})), link = node("a"); link.href = url; link.download = name;
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function save() {
  if (stale || !ready) return;
  const bases = Object.fromEntries(Object.keys(edits).map(key => [key, records.get(key).base]));
  try {localStorage.setItem(STORAGE, JSON.stringify({rules: data.rulesRevision, revision: data.revision, bases, edits})); $("#save-state").textContent = "Saved on this device";}
  catch {$("#save-state").textContent = "Browser storage unavailable"; notify("This browser cannot save drafts. Keep this tab open and download your changes before leaving.", true);}
}
function restore() {
  let raw;
  try {
    raw = localStorage.getItem(STORAGE); if (!raw) return;
    const saved = JSON.parse(raw);
    if (!saved || saved.rules !== data.rulesRevision || typeof saved.edits !== "object" || !saved.edits || Array.isArray(saved.edits)) throw Error();
    for (const [key, text] of Object.entries(saved.edits)) {
      if (!records.get(key)?.editable || saved.bases?.[key] !== records.get(key).base || typeof text !== "string" || text.length > 40000) throw Error();
    }
    edits = {...saved.edits};
  } catch {
    if (raw) {stale = raw; $("#recovery").hidden = false; $("#recovery-message").textContent = "The saved draft has older rules, changed entries or unreadable data. Download a recovery copy before starting fresh.";}
    else {$("#save-state").textContent = "Browser storage unavailable"; notify("Browser storage is unavailable. Keep this tab open and download changes before leaving.", true);}
  }
}
function href(row) {return `?subject=${encodeURIComponent(row.subject)}#${encodeURIComponent(row.key)}`;}
function current(row) {return edits[row.key] ?? row.current;}
function updateCounts() {
  const changed = Object.keys(edits).filter(k => edits[k] !== records.get(k).current), invalid = [...results].filter(([, r]) => !r.valid);
  $("#changed-count").textContent = changed.length;
  $("#export").disabled = !ready || !!stale || !changed.length || !!invalid.length;
  $("#import").disabled = !ready || !!stale;
  const issues = $("#global-issues"); issues.replaceChildren(); issues.hidden = !invalid.length;
  if (invalid.length) {
    issues.append(node("p", "", `${invalid.length} entries need attention across the workbenches. Downloads are paused until these checks pass.`));
    const list = node("ul");
    for (const [key, result] of invalid.slice(0, 8)) {
      const row = records.get(key), li = node("li"), a = node("a", "", `${key} · ${data.subjects.find(s => s.id === row.subject).name}`); a.href = href(row);
      li.append(a, document.createTextNode(` — ${result.errors[0]}`)); list.append(li);
    }
    issues.append(list);
    if (invalid.length > 8) issues.append(node("p", "", "Use ‘Needs attention’ in each workbench to see the remaining entries."));
  }
}
function revalidate() {
  clearTimeout(timer); results = validateAll(data, edits); updateCounts();
  for (const [key, card] of cards) feedback(records.get(key), card);
}
function update(row, value) {
  if (value === row.current) delete edits[row.key]; else edits[row.key] = value;
  save(); $("#export").disabled = true; timer = setTimeout(revalidate, 180);
}
function preview(row, result, target) {
  target.replaceChildren();
  if (!result.lines.length) return;
  const pages = [...new Set(result.lines.map(l => l.box))];
  for (const box of pages.slice(0, 8)) {
    const lines = result.lines.filter(l => l.box === box), wrap = node("div", "preview-page"), shell = node("div", "game-box"), canvas = node("canvas");
    canvas.width = Math.max(152, row.profile.pixels || 152); canvas.height = Math.max(16, lines.length * 12 + 4);
    canvas.setAttribute("role", "img"); canvas.setAttribute("aria-label", `Measured game-font text, page ${box + 1}`);
    const ctx = canvas.getContext("2d"); ctx.fillStyle = "#dce5c6"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    lines.forEach((line, i) => {
      for (const op of line.operations || []) {
        if (op.substitution) {ctx.fillStyle = "#a2b18c"; ctx.fillRect(op.x, 3 + i * 12, op.width, 7); continue;}
        ctx.fillStyle = "#344b2b";
        if (op.glyph) op.glyph.rows.forEach((bits, y) => {for (let x = 0; x < 8; x++) if (bits & (0x80 >> x)) ctx.fillRect(op.x + x, 2 + i * 12 + y, 1, 1);});
        else {ctx.strokeStyle = "#758662"; ctx.strokeRect(op.x + .5, 2.5 + i * 12, 6, 6);}
      }
    });
    shell.append(canvas); wrap.append(node("small", "", `Page ${box + 1}`), shell);
    for (const line of lines) wrap.append(node("div", "page-metrics", `Line ${line.row + 1}: ${line.extent}px · ${line.cells} source glyphs`));
    target.append(wrap);
  }
  target.append(node("p", "preview-note", "This preview shows measured text. Shaded spans represent runtime substitutions. Cursor cells, surrounding interface graphics and shared tile ownership need a game check."));
}
function feedback(row, card) {
  const result = results.get(row.key), changed = current(row) !== row.current;
  card.classList.toggle("invalid", !result.valid); card.classList.toggle("edited", changed);
  card.querySelector(".badge").textContent = !row.editable ? "Reference" : !result.valid ? "Needs attention" : changed ? "Edited" : "Current";
  const target = card.querySelector(".feedback-messages"); target.replaceChildren();
  for (const [messages, className] of [[result.errors, "messages"], [result.warnings, "messages warnings"]]) {
    if (messages.length) {const ul = node("ul", className); for (const message of [...new Set(messages)]) ul.append(node("li", "", message)); target.append(ul);}
  }
  card.querySelector(".row-result").textContent = row.editable ? result.valid ? "Text checks pass" : "Review the issues below" : "Reference only";
  const details = card.querySelector(".preview"); if (details?.open) preview(row, result, details.querySelector(".preview-content"));
}
function makeCard(row, first) {
  const card = node("article", "record"); card.id = `entry-${row.key.replace(/[^a-z0-9]/gi, "-")}`; card.dataset.key = row.key;
  const top = node("div", "record-top"), meta = node("div", "record-meta"), link = node("a", "loc", row.key); link.href = href(row);
  top.append(node("div", "speaker", row.group)); meta.append(link, node("span", "badge")); top.append(meta);
  const body = node("div", "record-body"), left = node("div", "source-pane"), jp = node("div", "jp", row.jp.replaceAll("<br>", "<br>\n").replaceAll("<brk>", "<brk>\n\n")); jp.lang = "ja"; left.append(jp);
  const right = node("div", "edit-pane");
  if (row.editable) {
    const input = node("textarea", "editor"); input.value = current(row); input.rows = Math.min(6, Math.max(2, Math.ceil(current(row).length / 60)));
    input.spellcheck = false; input.maxLength = 40000; input.disabled = !!stale; input.setAttribute("aria-label", `Translation for ${row.key}`); input.setAttribute("aria-describedby", `${card.id}-feedback`);
    input.addEventListener("input", () => update(row, input.value));
    input.addEventListener("keydown", e => {if (e.key === "Enter") {e.preventDefault(); if (["descriptions", "cinematic"].includes(row.subject)) insert("<br>");}});
    function insert(token) {if (input.value.length - (input.selectionEnd - input.selectionStart) + token.length > 40000) return; input.setRangeText(token, input.selectionStart, input.selectionEnd, "end"); input.focus(); update(row, input.value);}
    const actions = node("div", "edit-tools"), inserts = node("div", "token-insert");
    if (["descriptions", "cinematic"].includes(row.subject)) {
      const br = node("button", "", "+ Line break"); br.disabled = !!stale; br.addEventListener("click", () => insert("<br>")); inserts.append(br);
    }
    const reset = node("button", "reset-row", "Reset entry"); reset.disabled = !!stale;
    reset.addEventListener("click", () => {if (current(row) !== row.current && !confirm("Restore this entry to the current project translation?")) return; input.value = row.current; update(row, row.current); revalidate();});
    actions.append(inserts, reset); right.append(input, actions);
    const reference = node("details", "reference"); reference.append(node("summary", "", "Current English reference"), node("p", "current", row.current)); right.append(reference);
  } else right.append(node("p", "current", row.current || "No approved translation."));
  const contract = node("p", "contract", describeRules(row)); right.append(contract);
  if (row.controls.length) {const required = node("div", "required", "Controls in order: "); for (const token of row.controls) required.append(node("code", "", token)); right.append(required);}
  if (row.spaces.some(pair => pair.some(Boolean))) right.append(node("p", "contract", "Leading and trailing spaces are structural and must remain in place. The native source indent is supplied separately."));
  const notes = node("details", "rules-detail"); notes.append(node("summary", "", "Source context"), node("p", "", row.refs.join(" · ") || "No extracted pointer references.")); right.append(notes);
  const messages = node("div", "feedback-messages"); messages.id = `${card.id}-feedback`; messages.setAttribute("aria-live", "polite");
  right.append(node("div", "row-result"), messages); body.append(left, right); card.append(top, body);
  if (row.editable) {const details = node("details", "preview"); details.open = first; details.append(node("summary", "", "Game-font text preview"), node("div", "preview-content")); details.addEventListener("toggle", () => {if (details.open) preview(row, results.get(row.key), details.querySelector(".preview-content"));}); card.append(details);}
  feedback(row, card); return card;
}
function filtered() {
  const query = $("#search").value.trim().toLocaleLowerCase(), group = $("#group").value, filter = $("#filter").value;
  return data.records.filter(r => r.subject === subject.id && (!group || r.group === group) && (!query || [r.key, r.jp, current(r), r.group].join(" ").toLocaleLowerCase().includes(query)) &&
    (filter !== "edited" || current(r) !== r.current) && (filter !== "errors" || !results.get(r.key).valid));
}
function render() {
  const visible = filtered(), pages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE)); page = Math.min(page, pages - 1); cards.clear();
  $("#records").replaceChildren(...visible.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).map((row, i) => {const card = makeCard(row, i === 0); cards.set(row.key, card); return card;}));
  $("#group-title").textContent = $("#group").value || "All groups"; $("#row-count").textContent = `${visible.length} entries`;
  $("#empty").hidden = !!visible.length; $("#page-status").textContent = `Page ${page + 1} of ${pages}`; $("#previous").disabled = page === 0; $("#next").disabled = page + 1 === pages;
}
function focusHash() {
  let key; try {key = decodeURIComponent(location.hash.slice(1));} catch {return;}
  const index = filtered().findIndex(r => r.key === key); if (index < 0) return;
  page = Math.floor(index / PAGE_SIZE); render(); cards.get(key)?.scrollIntoView({block: "start"});
}
async function initialize() {
  const response = await fetch("catalog.json"); if (!response.ok) throw Error("The workbench catalogue could not be loaded. Reload to retry."); data = await response.json();
  records = new Map(data.records.map(r => [r.key, r]));
  const requested = new URLSearchParams(location.search).get("subject") || "items";
  subject = data.subjects.find(s => s.id === requested);
  if (!subject) throw Error("Unknown workbench. Return to the home page to choose an editor.");
  if (subject.id === "prose") {location.replace("../prose/" + location.hash); return;}
  $("#title").textContent = subject.name; $("#description").textContent = subject.description; $("#crumb").textContent = subject.name.toUpperCase(); document.title = `${subject.name} · Shiren GB`;
  for (const s of data.subjects) {const a = node("a", s.id === subject.id ? "active" : "", s.name); a.href = s.id === "prose" ? "../prose/" : `?subject=${s.id}`; a.append(node("span", "", s.count)); if (s.id === subject.id) a.setAttribute("aria-current", "page"); $("#subjects").append(a);}
  $("#group").append(new Option("All groups", "")); for (const group of new Set(data.records.filter(r => r.subject === subject.id).map(r => r.group))) $("#group").append(new Option(group, group));
  const responses = await Promise.all([fetch("../data/script.tsv"), fetch("../data/intro.tsv")]);
  if (responses.some(r => !r.ok)) throw Error("The included source TSVs could not be loaded. Reload to retry; saved drafts are retained.");
  await verifySources(data, ...await Promise.all(responses.map(r => r.text())));
  $("#source-status").textContent = "Original Japanese loaded"; $("#source-description").textContent = `${data.extractedCount} script entries + ${data.cinematicCount} cinematic entries.`;
  ready = true; restore(); results = validateAll(data, edits); updateCounts(); render(); focusHash();
  $("#save-state").textContent = stale ? "Draft recovery required" : "Drafts stay on this device";
  document.body.dataset.ready = "true";
}
$("#search").addEventListener("input", () => {if (!ready) return; page = 0; render();});
for (const id of ["#group", "#filter"]) $(id).addEventListener("change", () => {if (!ready) return; page = 0; revalidate(); render();});
$("#previous").addEventListener("click", () => {if (!ready) return; page--; render();}); $("#next").addEventListener("click", () => {if (!ready) return; page++; render();});
$("#export").addEventListener("click", () => {try {revalidate(); download("shiren-workbench-edits.tsv", exportEdits(data, edits)); notify("Downloaded changes from all workbenches in this draft. Prose uses its separate download.");} catch (e) {notify(e.message, true);}});
$("#import").addEventListener("click", () => $("#file").click());
$("#file").addEventListener("change", async () => {try {const file = $("#file").files[0]; if (!file) return; if (file.size > 2_000_000) throw Error("TSV exceeds 2 MB."); edits = importEdits(await file.text(), data, edits); save(); revalidate(); render(); notify("Imported edits. Review any entries that need attention before downloading.");} catch (e) {notify(e.message, true);} finally {$("#file").value = "";}});
$("#recover").addEventListener("click", () => {download("shiren-workbench-recovery.json", stale, "application/json"); $("#fresh").disabled = false;});
$("#fresh").addEventListener("click", () => {if (!confirm("Start a new draft after saving the recovery download?")) return; stale = null; edits = {}; $("#recovery").hidden = true; save(); revalidate(); render();});
window.addEventListener("hashchange", focusHash);
window.addEventListener("storage", e => {
  if (e.key !== STORAGE || !ready || stale) return;
  stale = JSON.stringify({thisTab: {rules: data.rulesRevision, edits}, otherTab: e.newValue});
  $("#recovery").hidden = false; $("#recovery-message").textContent = "The shared draft changed in another tab. Reload to use that saved draft, or download a recovery copy of both versions before starting fresh."; updateCounts(); render();
});
initialize().catch(e => {notify(e.message, true); $("#source-status").textContent = "Loading failed"; $("#save-state").textContent = "Editing unavailable";});
