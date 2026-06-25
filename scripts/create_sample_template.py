"""Create a sample .docx template using only the Python standard library."""

import io
import zipfile
from pathlib import Path

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

DOCUMENT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Customer Letter</w:t></w:r></w:p>
    <w:p><w:r><w:t>Dear {{ customer_name }},</w:t></w:r></w:p>
    <w:p><w:r><w:t>Your order #{{ order_id }} on {{ order_date }} totals ${{ amount }}.</w:t></w:r></w:p>
    <w:p><w:r><w:t>Thank you for your business.</w:t></w:r></w:p>
  </w:body>
</w:document>
"""


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "samples" / "letter_template.docx"
    output.parent.mkdir(parents=True, exist_ok=True)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", RELS)
        archive.writestr("word/document.xml", DOCUMENT)

    output.write_bytes(buffer.getvalue())
    print(f"Created {output}")


if __name__ == "__main__":
    main()
