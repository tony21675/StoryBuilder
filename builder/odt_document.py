from __future__ import annotations

import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


MIMETYPE = "application/vnd.oasis.opendocument.text"
NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
    "xml": "http://www.w3.org/XML/1998/namespace",
}
for prefix, uri in NS.items():
    if prefix != "xml":
        ET.register_namespace(prefix, uri)


def _q(prefix: str, name: str) -> str:
    return f"{{{NS[prefix]}}}{name}"


_MARKDOWN_PATTERN = re.compile(
    r"\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|(?<!\*)\*([^*\n]+?)\*(?!\*)"
)


def _markdown_runs(text: str):
    """Yield plain-text runs with their Markdown emphasis style."""
    source = str(text or "")
    cursor = 0
    for match in _MARKDOWN_PATTERN.finditer(source):
        if match.start() > cursor:
            yield source[cursor:match.start()], None
        if match.group(1) is not None:
            yield match.group(1), "bold_italic"
        elif match.group(2) is not None:
            yield match.group(2), "bold"
        else:
            yield match.group(3), "italic"
        cursor = match.end()
    if cursor < len(source):
        yield source[cursor:], None


def markdown_to_rich_text(markdown: str) -> tuple[str, list[tuple[int, int, str]]]:
    """Remove emphasis markers and return character ranges for actual text styling."""
    plain_parts: list[str] = []
    spans: list[tuple[int, int, str]] = []
    position = 0
    for value, style in _markdown_runs(markdown):
        if not value:
            continue
        plain_parts.append(value)
        end = position + len(value)
        if style:
            spans.append((position, end, style))
        position = end
    return "".join(plain_parts), spans


def _style_map(root: ET.Element, styles: dict[str, tuple[bool, bool]]) -> None:
    for style in root.iter(_q("style", "style")):
        name = style.get(_q("style", "name"), "")
        if not name:
            continue
        properties = style.find(_q("style", "text-properties"))
        if properties is None:
            continue
        weight = (properties.get(_q("fo", "font-weight")) or "").casefold()
        posture = (properties.get(_q("fo", "font-style")) or "").casefold()
        bold = weight in {"bold", "bolder", "700", "800", "900"}
        italic = posture in {"italic", "oblique"}
        previous = styles.get(name, (False, False))
        styles[name] = (previous[0] or bold, previous[1] or italic)


def _append_run(runs: list[tuple[str, bool, bool]], value: str, bold: bool, italic: bool) -> None:
    if not value:
        return
    if runs and runs[-1][1:] == (bold, italic):
        previous, _, _ = runs[-1]
        runs[-1] = (previous + value, bold, italic)
    else:
        runs.append((value, bold, italic))


def _read_inline_runs(
    element: ET.Element,
    styles: dict[str, tuple[bool, bool]],
    inherited_bold: bool = False,
    inherited_italic: bool = False,
) -> list[tuple[str, bool, bool]]:
    runs: list[tuple[str, bool, bool]] = []

    def visit(node: ET.Element, bold: bool, italic: bool) -> None:
        _append_run(runs, node.text or "", bold, italic)
        for child in list(node):
            child_bold, child_italic = bold, italic
            style_name = child.get(_q("text", "style-name"), "")
            style_bold, style_italic = styles.get(style_name, (False, False))
            child_bold = child_bold or style_bold
            child_italic = child_italic or style_italic

            if child.tag == _q("text", "s"):
                count_text = child.get(_q("text", "c"), "1")
                try:
                    count = max(1, min(10000, int(count_text)))
                except (TypeError, ValueError):
                    count = 1
                _append_run(runs, " " * count, child_bold, child_italic)
            elif child.tag == _q("text", "tab"):
                _append_run(runs, "\t", child_bold, child_italic)
            elif child.tag == _q("text", "line-break"):
                _append_run(runs, "\n", child_bold, child_italic)
            else:
                visit(child, child_bold, child_italic)
            _append_run(runs, child.tail or "", bold, italic)

    visit(element, inherited_bold, inherited_italic)
    return runs


def _runs_to_markdown(runs: list[tuple[str, bool, bool]]) -> str:
    parts: list[str] = []
    for value, bold, italic in runs:
        if bold and italic:
            marker = "***"
        elif bold:
            marker = "**"
        elif italic:
            marker = "*"
        else:
            marker = ""
        parts.append(f"{marker}{value}{marker}" if marker else value)
    return "".join(parts)


def read_odt_document(path: str | Path) -> str:
    """Read ODT paragraphs and preserve bold/italic runs as Markdown for editing."""
    source = Path(path).expanduser()
    try:
        with zipfile.ZipFile(source, "r") as archive:
            try:
                content_root = ET.fromstring(archive.read("content.xml"))
            except KeyError as exc:
                raise ValueError("The ODT file does not contain content.xml.") from exc
            styles: dict[str, tuple[bool, bool]] = {}
            _style_map(content_root, styles)
            try:
                styles_root = ET.fromstring(archive.read("styles.xml"))
            except KeyError:
                styles_root = None
            if styles_root is not None:
                _style_map(styles_root, styles)
    except zipfile.BadZipFile as exc:
        raise ValueError("This is not a valid LibreOffice ODT document.") from exc
    except ET.ParseError as exc:
        raise ValueError("The ODT document contains invalid XML.") from exc

    text_root = content_root.find(f".//{_q('office', 'text')}")
    if text_root is None:
        raise ValueError("The ODT document has no Writer text body.")

    paragraphs: list[str] = []
    for element in text_root.iter():
        if element.tag not in {_q("text", "p"), _q("text", "h")}:
            continue
        style_name = element.get(_q("text", "style-name"), "")
        bold, italic = styles.get(style_name, (False, False))
        value = _runs_to_markdown(
            _read_inline_runs(element, styles, bold, italic)
        )
        if element.tag == _q("text", "h"):
            value = "# " + value
        paragraphs.append(value)
    return "\n\n".join(paragraphs)


def _append_xml_text(parent: ET.Element, value: str) -> None:
    if not value:
        return
    if len(parent):
        last = parent[-1]
        last.tail = (last.tail or "") + value
    else:
        parent.text = (parent.text or "") + value
    parent.set(_q("xml", "space"), "preserve")


def _append_markdown_line(paragraph: ET.Element, line: str) -> None:
    style_names = {
        "bold": "SB_Bold",
        "italic": "SB_Italic",
        "bold_italic": "SB_BoldItalic",
    }
    for value, style in _markdown_runs(line):
        if not value:
            continue
        if style:
            span = ET.SubElement(
                paragraph,
                _q("text", "span"),
                {_q("text", "style-name"): style_names[style]},
            )
            span.set(_q("xml", "space"), "preserve")
            span.text = value
        else:
            _append_xml_text(paragraph, value)


def _build_content_xml(markdown: str) -> bytes:
    root = ET.Element(
        _q("office", "document-content"),
        {_q("office", "version"): "1.2"},
    )
    automatic = ET.SubElement(root, _q("office", "automatic-styles"))
    for name, weight, posture in (
        ("SB_Bold", "bold", None),
        ("SB_Italic", None, "italic"),
        ("SB_BoldItalic", "bold", "italic"),
    ):
        style = ET.SubElement(
            automatic,
            _q("style", "style"),
            {
                _q("style", "name"): name,
                _q("style", "family"): "text",
            },
        )
        properties = {}
        if weight:
            properties[_q("fo", "font-weight")] = weight
        if posture:
            properties[_q("fo", "font-style")] = posture
        ET.SubElement(style, _q("style", "text-properties"), properties)

    body = ET.SubElement(root, _q("office", "body"))
    office_text = ET.SubElement(body, _q("office", "text"))
    source = str(markdown or "")
    blocks = re.split(r"\n[ \t]*\n", source) if source else [""]
    for block in blocks:
        heading_match = re.match(r"^(#{1,6})[ \t]+(.*)$", block, flags=re.DOTALL)
        if heading_match:
            paragraph = ET.SubElement(
                office_text,
                _q("text", "h"),
                {_q("text", "outline-level"): str(len(heading_match.group(1)))},
            )
            block = heading_match.group(2)
        else:
            paragraph = ET.SubElement(
                office_text,
                _q("text", "p"),
                {_q("text", "style-name"): "SB_Paragraph"},
            )

        lines = block.split("\n")
        for index, line in enumerate(lines):
            if index:
                ET.SubElement(paragraph, _q("text", "line-break"))
            _append_markdown_line(paragraph, line)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _build_styles_xml() -> bytes:
    root = ET.Element(
        _q("office", "document-styles"),
        {_q("office", "version"): "1.2"},
    )
    styles = ET.SubElement(root, _q("office", "styles"))
    ET.SubElement(
        styles,
        _q("style", "default-style"),
        {_q("style", "family"): "paragraph"},
    )
    paragraph_style = ET.SubElement(
        styles,
        _q("style", "style"),
        {
            _q("style", "name"): "SB_Paragraph",
            _q("style", "family"): "paragraph",
        },
    )
    ET.SubElement(
        paragraph_style,
        _q("style", "paragraph-properties"),
        {
            _q("fo", "margin-bottom"): "0.12in",
            _q("fo", "line-height"): "120%",
        },
    )
    automatic = ET.SubElement(root, _q("office", "automatic-styles"))
    page_layout = ET.SubElement(
        automatic,
        _q("style", "page-layout"),
        {_q("style", "name"): "SB_Page"},
    )
    ET.SubElement(
        page_layout,
        _q("style", "page-layout-properties"),
        {
            _q("fo", "page-width"): "8.5in",
            _q("fo", "page-height"): "11in",
            _q("fo", "margin-top"): "1in",
            _q("fo", "margin-bottom"): "1in",
            _q("fo", "margin-left"): "1in",
            _q("fo", "margin-right"): "1in",
        },
    )
    master = ET.SubElement(root, _q("office", "master-styles"))
    ET.SubElement(
        master,
        _q("style", "master-page"),
        {
            _q("style", "name"): "Standard",
            _q("style", "page-layout-name"): "SB_Page",
        },
    )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _build_manifest_xml() -> bytes:
    root = ET.Element(
        _q("manifest", "manifest"),
        {_q("manifest", "version"): "1.2"},
    )
    ET.SubElement(
        root,
        _q("manifest", "file-entry"),
        {
            _q("manifest", "full-path"): "/",
            _q("manifest", "media-type"): MIMETYPE,
            _q("manifest", "version"): "1.2",
        },
    )
    for name, media_type in (
        ("content.xml", "text/xml"),
        ("styles.xml", "text/xml"),
    ):
        ET.SubElement(
            root,
            _q("manifest", "file-entry"),
            {
                _q("manifest", "full-path"): name,
                _q("manifest", "media-type"): media_type,
            },
        )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def save_odt_document(path: str | Path, markdown: str) -> Path:
    """Write a valid ODT file with real bold/italic character styles."""
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        with zipfile.ZipFile(temporary_path, "w") as archive:
            archive.writestr(
                "mimetype",
                MIMETYPE,
                compress_type=zipfile.ZIP_STORED,
            )
            archive.writestr(
                "content.xml",
                _build_content_xml(markdown),
                compress_type=zipfile.ZIP_DEFLATED,
            )
            archive.writestr(
                "styles.xml",
                _build_styles_xml(),
                compress_type=zipfile.ZIP_DEFLATED,
            )
            archive.writestr(
                "META-INF/manifest.xml",
                _build_manifest_xml(),
                compress_type=zipfile.ZIP_DEFLATED,
            )
        temporary_path.replace(target)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
    return target


def read_document(path: str | Path) -> str:
    """Read ODT as editable Markdown; retain UTF-8 text compatibility."""
    source = Path(path).expanduser()
    if source.suffix.casefold() == ".odt":
        return read_odt_document(source)
    return source.read_text(encoding="utf-8")


def save_document(path: str | Path, markdown: str) -> Path:
    """Save ODT with real formatting or preserve a UTF-8 text document."""
    target = Path(path).expanduser().resolve()
    if target.suffix.casefold() == ".odt":
        return save_odt_document(target, markdown)
    target.write_text(str(markdown), encoding="utf-8")
    return target
