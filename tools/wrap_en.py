#!/usr/bin/env python3
"""Wrap drafted English prose into composer lines, so a translator writes sentences.

THE HOLE THIS CLOSES. `dialogue_preview.py` tells you a line is too long AFTER you have
written it; nothing turned prose into lines in the first place. For session 5's 323
village/story strings that is the whole job -- every one of them needs `<br>` at the right
places, the ROM's leading-space indent on continuation lines, a box closed every three
lines, and `<end>` before each `<brk>`. Done by hand that is 323 chances to lose a
character off the end of a line, and `line_too_long` only catches the ones that overrun.

WHAT YOU WRITE, AND WHAT THIS WRITES. The draft is `loc <TAB> english`, and the English is
sentences with NO layout in them at all:

    14:$4C7B    Yoshizota: Right here.
    14:$4C67    Koppa: Where is Orochi?

You may still place `<brk>` yourself where the pacing wants a page, and `<br>` where a line
break is content rather than wrapping (a menu's `>Yes` / `No`). Everything else -- the
wrapping, the indent, the `<end>`s, and splitting a page that ran past three lines -- is
this file's job.

WHY THE INDENT COUNTS. Every line of the shipped Japanese except the first begins with a
space (`13:$6B40`'s rows are drawn from column 0, so the space is authored, not padding).
`dialogue_preview` charges both its source glyph and its real approved-font advance, because the
screen does. A continuation line therefore has one fewer of the 30 staged glyphs and a
few fewer of the 144 painted pixels than the first line.

THE FIRST LINE'S INDENT IS NOT YOURS. `dialogue_preview.main` prepends a space when the
JAPANESE string started with one, and `build.py` does the same, so writing one here would
double it. This file never emits a leading space on the string's first line.

CURRENT PROPORTIONAL POLICY. A composer line may stage 30 glyphs and owns 144 painted
pixels. This wrapper checks both with the approved font. Unknown runtime
values such as `<var>` are charged their narrowest possible contribution; the settled
`<name>` producer reserves all six player-name glyphs and their widest approved pixels.
The old universal 14/16-cell reservations were fixed-width guesses and no longer shorten
prose automatically. `fontaudit.py` still reports unknown-value risk for review. A word that
cannot fit a line even alone is placed anyway and reported; that is the caller's cue to
reword, not the wrapper's to truncate.

    tools/wrap_en.py draft.tsv                  wrapped rows on stdout
    tools/wrap_en.py draft.tsv --apply          merge them into script/en.tsv
    tools/wrap_en.py draft.tsv --preview        draw every box it produced
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codec                                                        # noqa: E402
import dialogue_preview as dialogue                                 # noqa: E402
import dotfont                                                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Layout tokens the draft may contain. Everything else is content and is carried through
# untouched -- including the argument byte after `<mode1>`, which is a pause length and
# not a character. See docs/TEXT_REFERENCE.md section 7.
FORCED = {'br', 'brk'}


def cells_of(text, widths):
    """Cells `text` draws, by the same rule dialogue_preview.Line.cells uses.

    Counted on the token string rather than on encoded bytes so an unencodable draft still
    measures -- `build.encode_en` is what rejects a bad character, and it says so better.
    """
    n = 0
    pos = 0
    for m in codec.TOKEN_RE.finditer(text):
        n += len(text[pos:m.start()])
        tok = m.group(1)
        if tok.startswith('$'):
            n += widths.get(int(tok[1:], 16), 1)
        else:
            parts = tok.split(':')
            code = codec.REV_CONTROL.get(parts[0])
            if code is None:
                raise ValueError('unknown token <%s>' % tok)
            w = widths.get(code, 0)
            if isinstance(w, dict):                 # <cF0:xx>, keyed by its argument
                w = w.get(int(parts[1], 16), 0) if len(parts) > 1 else 0
            n += w
        pos = m.end()
    return n + len(text[pos:])


def _atoms(seg):
    """A segment -> its words. A token never splits, and a token glued to a word stays."""
    return [w for w in seg.split(' ') if w]


def wrap_segment(seg, width, first, widths, measure=None, pixel_limit=None):
    """One unbroken run of prose -> [line, ...], each already carrying its indent."""
    lines, cur = [], None

    def fits(candidate):
        if cells_of(candidate, widths) > width:
            return False
        if measure is not None and pixel_limit is not None:
            _advance, extent = measure(candidate)
            if extent > pixel_limit:
                return False
        return True

    for word in _atoms(seg):
        indent = '' if (first and not lines) else ' '
        cand = word if cur is None else cur + ' ' + word
        if cur is not None and fits(indent + cand):
            cur = cand
            continue
        if cur is not None:
            lines.append(cur)
        cur = word
    if cur is not None:
        lines.append(cur)
    return lines


def place_terminal_end(joined, suffix):
    """Preserve a source ``<end>`` immediately before terminal effect controls.

    ``<end><mode0>`` is a structural ending used by dialogue that hands control to a
    menu.  It is safe because every visible glyph precedes the wait.  By contrast, an
    arbitrary Japanese pause in the last box cannot be moved mechanically after English
    reflow: putting it before the last English word hid that word and produced an
    unchanged extra wait in play.  Those semantic pauses must be authored as ``<brk>`` in
    the prose draft instead.
    """
    if not suffix or not joined.endswith(suffix):
        raise ValueError('terminal control suffix %r was not preserved' % suffix)
    return joined[:-len(suffix)] + '<end>' + suffix


def wrap(text, width=dialogue.WIDTH, per_box=dialogue.LINES_PER_BOX, widths=None,
         want_end=True, terminal_end='', measure=None, pixel_limit=None):
    """Drafted prose -> the en.tsv string. -> (text, [(kind, detail), ...]).

    `<end>` IS A `WAIT HERE`, NOT A TERMINATOR, and the shipped Japanese settles both
    halves of that. Measured over all 820 bank-11/14 strings: every one of the 120 `<brk>`
    is preceded by `<end>` -- 120 of 120, no exceptions -- and NO string ends with one.
    The last box is closed by the `$FF` terminator, and only 23 of the 68 multi-box
    strings ask it to wait as well.

    The mechanism agrees: `$ED` sets `$CFC4` (13:$4155), and `13:$40B8` -- the only reader
    in the ROM -- tests it once with `and a` and calls the wait at `13:$5445`. So presence
    is what matters, not count. `want_end` puts one before every `<brk>`. A source ending
    such as ``<end><mode0>`` is preserved by `terminal_end`; ordinary last-box pauses are
    not guessed after reflow and belong as semantic ``<brk>`` markers in the draft.
    """
    # Production reserves the settled six-glyph player name. Other runtime producers are
    # still unknown here, so reserve only the one glyph they must emit; fontaudit owns the
    # separate warning about their larger actual values.
    widths = dialogue.production_widths() if widths is None else widths
    notes = []

    # Explicit page breaks first, then explicit line breaks inside each page. A `<br>` the
    # translator wrote is content, so it starts a line rather than joining one.
    pages = re.split(r'<brk>', text)
    out_pages, split = [], []
    for page_no, page in enumerate(pages, 1):
        lines = []
        for i, seg in enumerate(re.split(r'<br>', page)):
            seg = seg.strip()
            if not seg:
                continue
            first = not out_pages and not lines and i == 0
            lines.extend(wrap_segment(seg, width, first, widths, measure, pixel_limit))
        if not lines:
            continue
        # A box holds three rows and there is no fourth; overflow becomes another box.
        # Boxes are free (docs/TEXT_REFERENCE.md section 3a), so this is a pacing note, not a fault.
        #
        # BALANCED, not greedy. Cutting every third line leaves the remainder alone in a
        # box of its own -- four lines became 3+1, and a page that says only `one but me.`
        # reads like a mistake on a screen the player has to press A through. Same box
        # count, so it costs nothing: 4 -> 2+2, 5 -> 3+2, 7 -> 3+2+2.
        boxes = -(-len(lines) // per_box)
        if boxes > 1:
            split.append((page_no, len(lines), ' '.join(lines)[:60]))
        base, extra = divmod(len(lines), boxes)
        at = 0
        for b in range(boxes):
            n = base + (1 if b < extra else 0)
            out_pages.append(lines[at:at + n])
            at += n
    for page_i, n, sample in split:
        notes.append(('auto_split', 'page %d wrapped to %d lines and a box holds %d, so it '
                                    'was split -- author a <brk> instead: %r'
                                    % (page_i, n, per_box, sample)))

    body = []
    for p, lines in enumerate(out_pages):
        for i, ln in enumerate(lines):
            lead = '' if (p == 0 and i == 0) else ' '
            body.append(lead + ln)
            if i + 1 < len(lines):
                body.append('<br>')
        if p + 1 < len(out_pages):
            body.append('<end><brk>' if want_end else '<brk>')
    joined = ''.join(body)
    if terminal_end:
        joined = place_terminal_end(joined, terminal_end)

    over = [(p + 1, i + 1, cells_of((' ' if (p or i) else '') + ln, widths))
            for p, lines in enumerate(out_pages) for i, ln in enumerate(lines)
            if cells_of((' ' if (p or i) else '') + ln, widths) > width]
    for box, row, n in over:
        notes.append(('unwrappable', 'box %d line %d still needs %d of %d cells -- one word '
                                     'or token is too wide to break' % (box, row, n, width)))
    if measure is not None and pixel_limit is not None:
        for p, lines in enumerate(out_pages):
            for i, ln in enumerate(lines):
                shown = (' ' if (p or i) else '') + ln
                advance, extent = measure(shown)
                if extent > pixel_limit:
                    notes.append(('unwrappable',
                                  'box %d line %d advances %dpx and paints %dpx into a '
                                  '%dpx canvas -- one word or token is too wide to break'
                                  % (p + 1, i + 1, advance, extent, pixel_limit)))
    return joined, notes


# ---------------------------------------------------------------------------------------
def load_draft(path):
    rows = []
    for n, line in enumerate(open(path, encoding='utf-8'), 1):
        line = line.rstrip('\n')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if '\t' not in line:
            raise SystemExit('%s:%d: no tab -- draft rows are `loc <TAB> english`' % (path, n))
        loc, text = line.split('\t', 1)
        rows.append((loc.strip(), text.strip()))
    return rows


# A row whose text starts with this is LAYOUT, not prose, and is emitted byte for byte.
#
# The four choice prompts need it and show why. `<cEC:08>Will you...<br><$81>Yes<br> No`
# draws a menu: `<$81>` is the selection cursor and it occupies the indent column, so the
# option it marks must NOT be indented while the other one must. That is the opposite of
# the prose rule, and it is content rather than wrapping -- re-flowing it would move the
# cursor off its row. Same for the six `<cEC:04>X is asleep.<br> <br>` rows, whose two
# trailing blank lines clear the box.
VERBATIM = '='


def merge(pairs, en_path):
    """Rewrite en.tsv with `pairs` applied: replace a loc in place, append a new one."""
    lines = open(en_path, encoding='utf-8').read().split('\n')
    todo = dict(pairs)
    for i, line in enumerate(lines):
        if line.startswith('#') or '\t' not in line:
            continue
        k = line.split('\t', 1)[0].strip()
        if k in todo:
            lines[i] = '%s\t%s' % (k, todo.pop(k))
    if todo:
        tail = ['', '# ---- wrapped by tools/wrap_en.py ----']
        tail += ['%s\t%s' % (k, v) for k, v in pairs if k in todo]
        while lines and not lines[-1].strip():
            lines.pop()
        lines += tail + ['']
    open(en_path, 'w', encoding='utf-8').write('\n'.join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('draft')
    ap.add_argument('--apply', action='store_true', help='merge into script/en.tsv')
    ap.add_argument('--preview', action='store_true', help='draw the boxes')
    ap.add_argument('--en', default='script/en.tsv')
    args = ap.parse_args()

    strings = json.load(open(os.path.join(ROOT, 'script/script.json'),
                             encoding='utf-8'))['strings']
    by_loc = {r['loc']: r for r in strings}
    import build as B

    # Load the same current fixed CF0 fragments that build.py will insert, so a help-row
    # draft which uses one is wrapped against its real source and pixel contribution.
    trans = {}
    en_path = os.path.join(ROOT, args.en)
    if os.path.exists(en_path):
        for raw in open(en_path, encoding='utf-8'):
            if raw.startswith('#') or '\t' not in raw:
                continue
            loc, value = raw.split('\t', 1)
            if value.strip():
                trans[loc.strip()] = value.rstrip('\n')
    font = dotfont.load_approved()
    cf0_cells, cf0_text = dialogue.cf0_from_trans(trans, B.encode_en)
    cf0_data = {}
    for index, value in cf0_text.items():
        try:
            cf0_data[index] = B.encode_en(value, 11)
        except ValueError:
            pass                        # untranslated fragment uses native 8px fallback
    help_pixel_widths = dialogue.dot_help_widths(font, cf0_data)
    composer_pixel_widths = dialogue.dot_production_widths(font)

    out, bad = [], 0
    for loc, text in load_draft(args.draft):
        r = by_loc.get(loc)
        if r is None:
            print('%-11s !! no such string' % loc, file=sys.stderr)
            bad += 1
            continue
        width, per_box, _buf = dialogue.geometry_for(r)
        if text.startswith(VERBATIM):
            out.append((loc, text[len(VERBATIM):]))
            continue
        # Preserve only a structural source ending immediately before effect controls.
        # Moving an arbitrary Japanese last-box pause to the final English word caused
        # that word to disappear and left an unchanged extra wait on screen.
        want_end = True
        terminal = re.search(r'<end>((?:<[^>]+>)*)$', r['jp'])
        terminal_end = terminal.group(1) if terminal and terminal.group(1) else ''
        help_ = dialogue.is_help(r)
        widths = (dialogue.help_widths(cf0=cf0_cells) if help_
                  else dialogue.production_widths())
        pixel_widths = help_pixel_widths if help_ else composer_pixel_widths

        def measure(candidate, bank=r['bank'], controls=pixel_widths):
            data = B.encode_en(candidate, bank)
            return dialogue.dot_metrics(data, font, bank, controls)[:2]

        try:
            wrapped, notes = wrap(text, width, per_box, widths, want_end, terminal_end,
                                  measure=measure, pixel_limit=dialogue.LINE_PX)
        except ValueError as exc:
            print('%-11s !! %s' % (loc, exc), file=sys.stderr)
            bad += 1
            continue
        out.append((loc, wrapped))
        for kind, detail in notes:
            if kind == 'unwrappable':
                bad += 1
            print('%-11s -- %s: %s' % (loc, kind, detail), file=sys.stderr)

    if args.apply:
        merge(out, os.path.join(ROOT, args.en))
        print('applied %d rows to %s' % (len(out), args.en), file=sys.stderr)
    else:
        for loc, wrapped in out:
            print('%s\t%s' % (loc, wrapped))

    if args.preview:
        for loc, wrapped in out:
            r = by_loc[loc]
            width, per_box, buf = dialogue.geometry_for(r)
            widths = (dialogue.help_widths(cf0=cf0_cells)
                      if dialogue.is_help(r) else dialogue.production_widths())
            lead = bytes.fromhex(r['hex'])[:1] == b'\xb4'
            data = B.encode_en((' ' if lead else '') + wrapped, r['bank'])
            print('\n%s  (bank %d dialogue)' % (loc, r['bank']), file=sys.stderr)
            print(dialogue.preview(data, widths, width=width, per_box=per_box,
                                   bank=r['bank']), file=sys.stderr)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
