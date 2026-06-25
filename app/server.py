import csv
import io
import json
import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.docx_engine import extract_fields, generate_batch_zip, generate_document

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _file_response(
    handler: BaseHTTPRequestHandler,
    status: int,
    content: bytes,
    content_type: str,
    filename: str,
) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(content)))
    handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler.end_headers()
    handler.wfile.write(content)


def _parse_multipart(body: bytes, content_type: str) -> dict[str, Any]:
    match = re.search(r"boundary=(.+)", content_type)
    if not match:
        raise ValueError("Missing multipart boundary")

    boundary = match.group(1).strip().strip('"').encode("utf-8")
    delimiter = b"--" + boundary
    parts = body.split(delimiter)
    result: dict[str, Any] = {"files": {}, "fields": {}}

    for part in parts:
        if not part or part in (b"--", b"--\r\n"):
            continue
        chunk = part
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]
        if chunk.endswith(b"\r\n"):
            chunk = chunk[:-2]

        header_bytes, _, data = chunk.partition(b"\r\n\r\n")
        if not header_bytes:
            continue

        headers = header_bytes.decode("utf-8", errors="replace")
        name_match = re.search(r'name="([^"]+)"', headers)
        if not name_match:
            continue
        name = name_match.group(1)

        filename_match = re.search(r'filename="([^"]*)"', headers)
        if filename_match is not None:
            filename = filename_match.group(1)
            if data.endswith(b"\r\n"):
                data = data[:-2]
            result["files"][name] = {"filename": filename, "content": data}
        else:
            text = data.decode("utf-8").strip()
            if text.endswith("\r\n"):
                text = text[:-2]
            result["fields"][name] = text

    return result


class AppHandler(BaseHTTPRequestHandler):
    server_version = "WordTemplateGenerator/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            _json_response(self, HTTPStatus.OK, {"status": "ok"})
            return

        if path == "/":
            path = "/index.html"

        file_path = (STATIC_DIR / path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(STATIC_DIR.resolve())):
            self.send_error(HTTPStatus.FORBIDDEN)
            return

        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content = file_path.read_bytes()
        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = content_type or "application/octet-stream"

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")

        try:
            if parsed.path == "/api/templates/scan":
                self._handle_scan(body, content_type)
            elif parsed.path == "/api/generate":
                self._handle_generate(body, content_type)
            elif parsed.path == "/api/generate/batch":
                self._handle_batch(body, content_type)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"detail": str(exc)})
        except Exception as exc:
            _json_response(
                self,
                HTTPStatus.BAD_REQUEST,
                {"detail": f"Request failed: {exc}"},
            )

    def _handle_scan(self, body: bytes, content_type: str) -> None:
        payload = _parse_multipart(body, content_type)
        template = payload["files"].get("template")
        if not template or not template["content"]:
            raise ValueError("Please upload a .docx template file")

        filename = template["filename"] or "template.docx"
        if not filename.lower().endswith(".docx"):
            raise ValueError("Please upload a .docx template file")

        fields = extract_fields(template["content"])
        _json_response(
            self,
            HTTPStatus.OK,
            {
                "filename": filename,
                "fields": fields,
                "placeholder_syntax": "{{ field_name }}",
            },
        )

    def _handle_generate(self, body: bytes, content_type: str) -> None:
        payload = _parse_multipart(body, content_type)
        template = payload["files"].get("template")
        if not template:
            raise ValueError("Template file is required")

        raw_data = payload["fields"].get("data", "{}")
        data = json.loads(raw_data)
        if not isinstance(data, dict):
            raise ValueError("Data must be a JSON object")

        doc_bytes, filename = generate_document(template["content"], data)
        _file_response(
            self,
            HTTPStatus.OK,
            doc_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename,
        )

    def _handle_batch(self, body: bytes, content_type: str) -> None:
        payload = _parse_multipart(body, content_type)
        template = payload["files"].get("template")
        csv_file = payload["files"].get("csv_file")

        if not template:
            raise ValueError("Template file is required")
        if not csv_file or not csv_file["content"]:
            raise ValueError("CSV file is required")

        mapping = json.loads(payload["fields"].get("field_mapping", "{}"))
        if not isinstance(mapping, dict):
            raise ValueError("Field mapping must be a JSON object")

        filename_field = payload["fields"].get("filename_field", "").strip() or None
        headers, raw_records = _parse_csv_records(csv_file["content"])
        if not raw_records:
            raise ValueError("CSV contains no data rows")

        mapped_records: list[dict[str, Any]] = []
        for row in raw_records:
            record: dict[str, Any] = {}
            for template_field, csv_column in mapping.items():
                if csv_column and csv_column in row:
                    record[template_field] = row[csv_column]
            mapped_records.append(record)

        zip_bytes = generate_batch_zip(
            template["content"],
            mapped_records,
            filename_field=filename_field,
        )
        _file_response(
            self,
            HTTPStatus.OK,
            zip_bytes,
            "application/zip",
            "documents.zip",
        )


def _parse_csv_records(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV file has no header row")

    headers = [header.strip() for header in reader.fieldnames if header and header.strip()]
    records: list[dict[str, str]] = []
    for row in reader:
        record = {
            key.strip(): (value or "").strip()
            for key, value in row.items()
            if key
        }
        if any(record.values()):
            records.append(record)

    return headers, records


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Word Template Generator running at http://{host}:{port}", flush=True)
    server.serve_forever()
