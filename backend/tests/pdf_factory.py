from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)


def create_test_pdf(
    *page_texts: str,
    password: str | None = None,
) -> bytes:
    writer = PdfWriter()

    for text in page_texts:
        page = writer.add_blank_page(
            width=612,
            height=792,
        )
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            },
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): font,
                    },
                ),
            },
        )

        escaped_text = (
            text.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        content_stream = DecodedStreamObject()
        content_stream.set_data(
            (
                "BT /F1 12 Tf 72 720 Td "
                f"({escaped_text}) Tj ET"
            ).encode("latin-1"),
        )
        page[NameObject("/Contents")] = writer._add_object(
            content_stream,
        )

    if password is not None:
        writer.encrypt(password)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()
