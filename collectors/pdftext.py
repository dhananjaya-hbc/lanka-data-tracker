"""Minimal PDF text extraction (standard library only).

Reads FlateDecode content streams and maps glyph codes back to text with the
fonts' ToUnicode tables. Enough for the text-based tables in NDCU and SLTDA
reports; it does not do OCR, so tables embedded as images yield nothing.
"""

import re
import zlib


def _streams(pdf):
    for m in re.finditer(rb"stream\r?\n", pdf):
        end = pdf.find(b"endstream", m.end())
        if end < 0:
            continue
        try:
            yield zlib.decompress(pdf[m.end():end].rstrip(b"\r\n"))
        except zlib.error:
            continue


def _unicode_map(streams):
    cmap = {}
    for data in streams:
        for block in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
            for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
                cmap[src.upper()] = bytes.fromhex(dst.decode()).decode("utf-16-be", "ignore")
        for block in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
            for lo, hi, dst in re.findall(
                    rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
                width, start, base = len(lo), int(lo, 16), int(dst, 16)
                for k in range(int(hi, 16) - start + 1):
                    cmap[b"%0*X" % (width, start + k)] = chr(base + k)
    return cmap


def pdf_cells(pdf):
    """Return the PDF's text as a list of cells. Within a content stream,
    fragments of one cell are drawn back to back and cells are separated by a
    whitespace-only string, which is how the NDCU tables are laid out."""
    streams = list(_streams(pdf))
    cmap = _unicode_map(streams)
    cells, current = [], ""
    token = re.compile(rb"<([0-9A-Fa-f]+)>|\(((?:\\.|[^\\)])*)\)")
    for data in streams:
        if b"Tj" not in data and b"TJ" not in data:
            continue
        for m in token.finditer(data):
            if m.group(1) is not None:
                h = m.group(1).upper()
                piece = "".join(cmap.get(h[i:i + 4], "") for i in range(0, len(h), 4))
            else:
                piece = re.sub(r"\\(.)", r"\1", m.group(2).decode("latin-1"))
            if piece.strip():
                current += piece
            elif current:
                cells.append(current.strip())
                current = ""
    if current:
        cells.append(current.strip())
    return cells
