"""Extract PRD text for the requirements agent: .docx (paragraphs and tables in
document order, table rows as ' | '-separated cells), .md and .txt."""
from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx(path: Path) -> str:
    import defusedxml.ElementTree as ET  # the PRD is untrusted input: block entity expansion attacks
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    body = root.find(f"{W}body")
    out: list[str] = []

    def text_of(el) -> str:
        return html.unescape("".join(t.text or "" for t in el.iter(f"{W}t"))).strip()

    for child in body:
        if child.tag == f"{W}p":
            t = text_of(child)
            if t:
                out.append(t)
        elif child.tag == f"{W}tbl":
            out.append("")
            for row in child.iter(f"{W}tr"):
                cells = [text_of(c) for c in row.findall(f"{W}tc")]
                out.append(" | ".join(cells))
            out.append("")
    return "\n".join(out)


def extract(path: str | Path) -> str:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".docx":
        text = _docx(path)
    elif suffix in (".md", ".txt"):
        text = path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"unsupported PRD format {suffix}; use .docx, .md or .txt")
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
