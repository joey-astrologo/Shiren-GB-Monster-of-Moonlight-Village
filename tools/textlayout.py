"""Source-derived text layout shared by insertion, preview, and wrapping."""
from latinfont import EN_CODES


def source_indent(source):
    """The builder retains one native leading space outside the authored English."""
    return ' ' if source[:1] == bytes((EN_CODES[' '],)) else ''


def renderer_text(text, source):
    """Return the text that is encoded, including native cursor/indent cells.

    Selector continuation rows need an 8px cursor slot. Two proportional spaces
    preserve that slot while the reviewed TSV keeps its single structural space.
    """
    if '<$81>' in text:
        text = text.replace('<br> ', '<br>  ')
    return source_indent(source) + text
