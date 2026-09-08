/* Navigation only: explanations do not change validation or saved-draft revisions. */
export function controlReferenceURL(token) {
  const name = token.match(/^<([^:>]+)/)?.[1].toLowerCase();
  const anchor = name === "$81" ? "cursor" : name === "$b6" ? "divider" :
    name === "$ff" ? "terminator" : !name || name.startsWith("$") ? "raw-bytes" : name;
  return new URL(`./#${anchor}`, import.meta.url).href;
}

export function controlReferenceLink(token) {
  const link = document.createElement("a"), code = document.createElement("code");
  code.textContent = token; link.append(code);
  link.href = controlReferenceURL(token); link.target = "_blank"; link.rel = "noopener";
  link.title = `Meaning of ${token} (opens in a new tab)`;
  link.setAttribute("aria-label", link.title);
  return link;
}
