import io
import re
import zipfile
from typing import Any
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_TAG_T = f"{{{W_NS}}}t"

ET.register_namespace("w", W_NS)

PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
XML_PARTS = (
    "word/document.xml",
    "word/footnotes.xml",
    "word/endnotes.xml",
)
XML_PREFIXES = ("word/header", "word/footer")


def _is_docx(content: bytes) -> bool:
    return len(content) >= 2 and content[:2] == b"PK"


def _should_process_xml(name: str) -> bool:
    if name in XML_PARTS:
        return True
    return any(name.startswith(prefix) for prefix in XML_PREFIXES)


def _collect_text_nodes(root: ET.Element) -> list[ET.Element]:
    return [node for node in root.iter(W_TAG_T)]


def _paragraph_text(nodes: list[ET.Element]) -> str:
    return "".join(node.text or "" for node in nodes)


def _replace_in_nodes(nodes: list[ET.Element], new_text: str) -> None:
    if not nodes:
        return
    nodes[0].text = new_text
    for node in nodes[1:]:
        node.text = ""


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _replace_placeholders(text: str, data: dict[str, Any]) -> str:
    def replacer(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in data:
            return match.group(0)
        return _xml_escape(str(data[key]))

    return PLACEHOLDER_RE.sub(replacer, text)


def _process_xml(xml_bytes: bytes, data: dict[str, Any]) -> bytes:
    root = ET.fromstring(xml_bytes)
    paragraph_tag = f"{{{W_NS}}}p"

    for paragraph in root.iter(paragraph_tag):
        text_nodes = _collect_text_nodes(paragraph)
        if not text_nodes:
            continue
        original = _paragraph_text(text_nodes)
        updated = _replace_placeholders(original, data)
        if updated != original:
            _replace_in_nodes(text_nodes, updated)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True, short_empty_elements=False)


def extract_fields(template_bytes: bytes) -> list[str]:
    if not _is_docx(template_bytes):
        raise ValueError("Invalid file: expected a .docx document")

    fields: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(template_bytes)) as archive:
        for name in archive.namelist():
            if not _should_process_xml(name):
                continue
            xml_text = archive.read(name).decode("utf-8")
            fields.update(PLACEHOLDER_RE.findall(xml_text))

    return sorted(fields)


def generate_document(
    template_bytes: bytes,
    data: dict[str, Any],
    filename: str | None = None,
) -> tuple[bytes, str]:
    if not _is_docx(template_bytes):
        raise ValueError("Invalid template file")

    input_zip = zipfile.ZipFile(io.BytesIO(template_bytes))
    output = io.BytesIO()

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as out_zip:
        for item in input_zip.infolist():
            content = input_zip.read(item.filename)
            if _should_process_xml(item.filename):
                content = _process_xml(content, data)
            out_zip.writestr(item, content)

    input_zip.close()
    output.seek(0)

    base = filename or _pick_filename(data) or "document"
    if not base.lower().endswith(".docx"):
        base = f"{base}.docx"

    return output.read(), _sanitize_filename(base)


def _sanitize_filename(name: str, fallback: str = "document") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name.strip())
    cleaned = cleaned.rstrip(". ")
    return cleaned or fallback


def _pick_filename(data: dict[str, Any]) -> str | None:
    for key in ("filename", "file_name", "name", "customer_name", "title"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def generate_batch_zip(
    template_bytes: bytes,
    records: list[dict[str, Any]],
    filename_field: str | None = None,
) -> bytes:
    if not records:
        raise ValueError("No records provided for batch generation")

    zip_buffer = io.BytesIO()
    used_names: dict[str, int] = {}

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, record in enumerate(records, start=1):
            custom_name = None
            if filename_field and filename_field in record:
                custom_name = str(record[filename_field])
            elif "filename" in record:
                custom_name = str(record["filename"])

            doc_bytes, doc_name = generate_document(
                template_bytes,
                record,
                filename=custom_name or f"document_{index}",
            )

            if doc_name in used_names:
                used_names[doc_name] += 1
                stem = doc_name.rsplit(".", 1)[0]
                doc_name = f"{stem}_{used_names[doc_name]}.docx"
            else:
                used_names[doc_name] = 1

            archive.writestr(doc_name, doc_bytes)

    zip_buffer.seek(0)
    return zip_buffer.read()
