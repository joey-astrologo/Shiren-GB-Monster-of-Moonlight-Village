/* Browser counterpart of wrap_en/textlayout/dialogue_preview. Generated font and
 * source contracts come from prose_editor.py; differential checks use Python oracles. */
export const EDIT_FORMAT = "shiren-prose-edits-v1";
const FREE = new Set(["br", "brk", "end"]);
const TOKEN = /^<((?:\$[0-9a-fA-F]{2})|(?:[A-Za-z][A-Za-z0-9]*(?::[0-9a-fA-F]{2})*))>/;
export const MAX_TEXT = 40000;

export function tokenize(text, data) {
  const result = [];
  for (let i = 0; i < text.length;) {
    if (text[i] === "<") {
      const match = text.slice(i).match(TOKEN);
      if (!match) throw new Error("Malformed control token. Use the required tokens shown below.");
      const raw = match[0], parts = match[1].split(":"), name = parts[0];
      const escape = name.startsWith("$");
      const code = escape ? parseInt(name.slice(1), 16) : data.rules.controls[name];
      if (code === undefined) throw new Error(`Unknown token ${raw}.`);
      const args = parts.slice(1).map(value => parseInt(value, 16));
      if (!escape && args.length !== (data.rules.arity[code] || 0)) {
        throw new Error(`${raw} has the wrong argument count for this dialogue.`);
      }
      result.push({raw, name, code, args, escape, control: true});
      i += raw.length;
    } else {
      const char = String.fromCodePoint(text.codePointAt(i));
      const glyph = data.font.glyphs[char];
      if (!glyph) throw new Error(`The current game font has no glyph for ${JSON.stringify(char)}.`);
      result.push({raw: char, code: glyph.code, args: [], control: false});
      i += char.length;
    }
  }
  return result;
}

export function encode(text, data) {
  return tokenize(text, data).flatMap(token => [token.code, ...token.args]);
}

function cost(table, code) { return table[code] || 0; }

export function measureBytes(bytes, data) {
  let advance = 0, extent = 0, cells = 0;
  const operations = [];
  const glyphs = new Map(Object.entries(data.font.glyphs).map(([char, glyph]) => [glyph.code, {char, ...glyph}]));
  for (let i = 0; i < bytes.length; i++) {
    const code = bytes[i];
    if (code >= 0xE0 && code <= 0xF4) {
      const value = cost(data.rules.pixelCosts, code);
      const [width, ink] = Array.isArray(value) ? value : [value, value];
      if (ink) {
        extent = Math.max(extent, advance + ink);
        operations.push({x: advance, width: ink, substitution: true, code});
      }
      advance += width;
      cells += cost(data.rules.sourceCosts, code);
      i += data.rules.arity[code] || 0;
    } else if (!data.rules.combining.includes(code)) {
      const glyph = glyphs.get(code);
      const width = glyph ? glyph.advance : 8, ink = glyph ? glyph.ink : 8;
      extent = Math.max(extent, advance + ink);
      operations.push({x: advance, width: ink, char: glyph?.char, code});
      advance += width;
      cells++;
    }
  }
  // Mirrors dialogue_preview.buffer_bytes, including control/argument staging.
  const buffer = bytes.length + bytes.reduce((n, code) => n + cost(data.rules.sourceCosts, code), 0);
  return {advance, extent, cells, buffer, operations};
}

export function measure(text, data) { return measureBytes(encode(text, data), data); }

function draftCells(text, data) {
  return tokenize(text, data).reduce((total, token) => total +
    (token.control ? (data.rules.sourceCosts[token.code] ?? (token.escape ? 1 : 0)) : 1), 0);
}

function wrapSegment(segment, first, record, data) {
  const lines = [];
  let current = null;
  for (const word of segment.split(" ").filter(Boolean)) {
    const indent = first && !lines.length ? record.sourceIndent : " ";
    const candidate = current === null ? word : current + " " + word;
    if (current !== null && draftCells(indent + candidate, data) <= data.rules.glyphLimit &&
        measure(indent + candidate, data).extent <= data.rules.pixelLimit) {
      current = candidate;
      continue;
    }
    if (current !== null) lines.push(current);
    current = word;
  }
  if (current !== null) lines.push(current);
  return lines;
}

export function wrapDraft(record, text, data) {
  const pages = [];
  let autoSplit = false;
  for (const page of text.split("<brk>")) {
    const lines = [];
    page.split("<br>").forEach((segment, index) => {
      segment = segment.trim();
      if (!segment) return;
      lines.push(...wrapSegment(segment, !pages.length && !lines.length && index === 0, record, data));
    });
    if (!lines.length) continue;
    const count = Math.ceil(lines.length / data.rules.linesPerBox);
    if (count > 1) autoSplit = true;
    const size = Math.floor(lines.length / count), extra = lines.length % count;
    let offset = 0;
    for (let box = 0; box < count; box++) {
      const length = size + (box < extra ? 1 : 0);
      pages.push(lines.slice(offset, offset + length));
      offset += length;
    }
  }
  let compiled = pages.map((lines, page) => lines.map((line, row) =>
    (page || row ? " " : "") + line).join("<br>")).join("<end><brk>");
  if (record.terminalSuffix) {
    if (!compiled.endsWith(record.terminalSuffix)) throw new Error("Keep the source's terminal effect controls at the end.");
    compiled = compiled.slice(0, -record.terminalSuffix.length) + "<end>" + record.terminalSuffix;
  }
  return {compiled, autoSplit};
}

export function renderLines(record, compiled, data) {
  if (compiled.includes("<$81>")) compiled = compiled.replaceAll("<br> ", "<br>  ");
  const bytes = encode(record.sourceIndent + compiled, data);
  const lines = [];
  let current = [], box = 0, row = 0;
  const append = () => lines.push({box, row, bytes: current, ...measureBytes(current, data)});
  for (let i = 0; i < bytes.length; i++) {
    const code = bytes[i];
    if (code === 0xEE || code === 0xEF) {
      append(); current = [];
      if (code === 0xEE) { box++; row = 0; } else row++;
    } else {
      current.push(code);
      if (code >= 0xE0 && code <= 0xF4) {
        const count = data.rules.arity[code] || 0;
        current.push(...bytes.slice(i + 1, i + 1 + count));
        i += count;
      }
    }
  }
  append();
  return lines;
}

export function validateDraft(record, text, data) {
  const errors = [], warnings = [];
  let compiled = record.current, lines = [], autoSplit = false;
  try {
    if (text.length > MAX_TEXT) throw new Error("This entry exceeds the editor's 40,000-character limit.");
    if (!record.editable && text !== record.draft) throw new Error("Structured dialogue is read-only in this proof of concept.");
    if (!text.trim()) throw new Error("A translation cannot be empty.");
    if (/[\t\r\n]/.test(text)) throw new Error("Use <br> or <brk> instead of literal tabs or newlines.");
    if (text !== text.trim()) throw new Error("Remove outer spaces; the wrapper supplies the native indent.");
    const tokens = tokenize(text.startsWith("=") ? text.slice(1) : text, data);
    if (record.editable) {
      if (text.startsWith("=")) throw new Error("Ordinary prose cannot become a verbatim row.");
      if (text.includes("<end>")) throw new Error("Use <brk> for a page break; the wrapper places <end>.");
    }
    const significant = tokens.filter(token => token.control && !FREE.has(token.name)).map(token => token.raw);
    if (JSON.stringify(significant) !== JSON.stringify(record.sequence)) {
      throw new Error("Keep the required controls, arguments and raw bytes in their original order.");
    }
    if (text !== record.draft) ({compiled, autoSplit} = wrapDraft(record, text, data));
    const finalTokens = tokenize(compiled, data);
    const counts = {};
    for (const token of finalTokens) {
      if (token.control && !token.escape && !FREE.has(token.name)) {
        const key = token.raw.slice(1, -1); counts[key] = (counts[key] || 0) + 1;
      }
    }
    for (const key of new Set([...Object.keys(counts), ...Object.keys(record.significant)])) {
      if ((counts[key] || 0) !== (record.significant[key] || 0)) errors.push(`Required source token <${key}> has a different count or argument.`);
    }
    if (record.sourceHasEnd && !compiled.includes("<end>")) errors.push("The source's end/wait control is missing. Preserve a meaningful page boundary.");
    if (!record.sourceTrailingEnd && compiled.trimEnd().endsWith("<end>")) errors.push("A trailing <end> would repeat the final box.");
    if (!record.sourceHasEnd && /<end>(?:<brk>)+\s*$/.test(compiled)) errors.push("An added terminal <end><brk> would create an empty final box.");
    if (/<end>(?!(?:<[^>]+>)*$|<brk>)/.test(compiled)) errors.push("Printable dialogue resumes after <end> without a page boundary.");
    if (record.sequence[0]?.startsWith("<cEC:") && !compiled.startsWith(record.sequence[0])) errors.push("Keep the source's <cEC:xx> prefix first.");
    if (encode(compiled, data).some(code => data.rules.dteCodes.includes(code))) errors.push("A raw byte collides with compression codes.");
    lines = renderLines(record, compiled, data);
    for (const line of lines) {
      const label = `Box ${line.box + 1}, line ${line.row + 1}`;
      if (line.cells > data.rules.glyphLimit) errors.push(`${label}: ${line.cells} glyphs exceeds ${data.rules.glyphLimit}.`);
      if (line.extent > data.rules.pixelLimit) errors.push(`${label}: ${line.extent}px exceeds ${data.rules.pixelLimit}px.`);
      if (line.row >= data.rules.linesPerBox) errors.push(`${label}: only ${data.rules.linesPerBox} lines fit in a box.`);
      if (line.buffer >= data.rules.bufferLimit) errors.push(`${label}: staged data exceeds the cleared buffer.`);
    }
    const unresolved = finalTokens.some(token => data.rules.sourceCosts[token.code] && token.name !== "name");
    if (unresolved) warnings.push("Contains a runtime value measured at its minimum size. Check longer values in the project.");
    if (autoSplit) warnings.push("Wrapped into extra boxes. Review the pacing in the preview.");
  } catch (error) { errors.push(error.message); }
  return {valid: !errors.length, errors: [...new Set(errors)], warnings, compiled, lines, autoSplit};
}

export function exportEdits(data, edits) {
  const selected = data.records.filter(row => edits[row.loc] !== undefined && edits[row.loc] !== row.draft);
  if (!selected.length) throw new Error("There are no changed entries to download.");
  const lines = [`# format\t${EDIT_FORMAT}`, `# revision\t${data.revision}`, `# rules\t${data.rulesRevision}`];
  for (const row of selected) {
    if (!row.editable || !validateDraft(row, edits[row.loc], data).valid) throw new Error(`${row.loc}: fix validation errors before downloading.`);
    lines.push(`# base\t${row.loc}\t${row.base}`);
  }
  lines.push("# loc\tenglish");
  for (const row of selected) lines.push(`${row.loc}\t${edits[row.loc]}`);
  return lines.join("\n") + "\n";
}

export function importEdits(text, data, existing = {}) {
  if (new TextEncoder().encode(text).length > 2_000_000) throw new Error("This TSV is larger than 2 MB.");
  const metadata = new Map(), bases = new Map(), incoming = new Map();
  for (const [index, line] of text.replace(/^\uFEFF/, "").split(/\r?\n/).entries()) {
    if (!line) continue;
    if (line.startsWith("# ")) {
      const fields = line.slice(2).split("\t");
      if (fields[0] === "base" && fields.length === 3) {
        if (bases.has(fields[1])) throw new Error(`Line ${index + 1}: duplicate base address.`);
        bases.set(fields[1], fields[2]);
      } else if (["format", "revision", "rules"].includes(fields[0]) && fields.length === 2) {
        if (metadata.has(fields[0])) throw new Error(`Line ${index + 1}: duplicate metadata.`);
        metadata.set(fields[0], fields[1]);
      }
      continue;
    }
    if (line.startsWith("#")) continue;
    const fields = line.split("\t");
    if (fields.length !== 2 || !/^\d+:\$[0-9A-F]{4}$/.test(fields[0])) throw new Error(`Line ${index + 1}: expected loc and prose, separated by one tab.`);
    if (incoming.has(fields[0])) throw new Error(`Line ${index + 1}: duplicate address.`);
    incoming.set(fields[0], fields[1]);
  }
  if (metadata.get("format") !== EDIT_FORMAT || metadata.get("rules") !== data.rulesRevision ||
      !incoming.size || incoming.size !== bases.size || [...bases.keys()].some(key => !incoming.has(key))) {
    throw new Error("Use a changes TSV from this editor with the current rules and base hashes.");
  }
  const records = new Map(data.records.map(row => [row.loc, row]));
  const result = {...existing};
  for (const [loc, value] of incoming) {
    const row = records.get(loc);
    if (!row || !row.editable || bases.get(loc) !== row.base) throw new Error(`${loc}: unknown, read-only, or changed in the project since export.`);
    if (!validateDraft(row, value, data).valid) throw new Error(`${loc}: the imported translation fails validation.`);
    if (existing[loc] !== undefined && existing[loc] !== value && existing[loc] !== row.draft) {
      throw new Error(`${loc}: this import conflicts with your saved edit. Download or reset that entry first.`);
    }
    if (value === row.draft) delete result[loc]; else result[loc] = value;
  }
  return result;
}

export async function sha256(text) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(bytes)].map(byte => byte.toString(16).padStart(2, "0")).join("");
}

export async function importJapanese(text, data) {
  if (new TextEncoder().encode(text).length > 2_000_000) throw new Error("Source TSV is larger than 2 MB.");
  const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/);
  const header = lines.shift().split("\t"), locIndex = header.indexOf("loc"), jpIndex = header.indexOf("jp");
  if (locIndex < 0 || jpIndex < 0) throw new Error("Choose the extracted script.tsv with loc and jp columns.");
  const source = new Map();
  for (const line of lines) {
    if (!line) continue;
    const fields = line.split("\t");
    if (fields.length !== header.length || source.has(fields[locIndex])) throw new Error("The source has malformed or duplicate rows.");
    source.set(fields[locIndex], fields[jpIndex]);
  }
  const result = {};
  await Promise.all(data.records.map(async row => {
    const jp = source.get(row.loc);
    if (jp === undefined || await sha256(jp) !== row.sourceHash) throw new Error(`${row.loc}: Japanese source does not match this catalogue.`);
    result[row.loc] = jp;
  }));
  return result;
}
