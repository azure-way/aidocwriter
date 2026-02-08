from __future__ import annotations

import io

import pytest

Workbook = pytest.importorskip("openpyxl").Workbook

from docwriter.rfp_extract import extract_xlsx_text_and_json


def test_extract_xlsx_text_and_json():
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Sheet1"
    sheet.append(["Header1", "Header2"])
    sheet.append(["Value1", "Value2"])
    buffer = io.BytesIO()
    wb.save(buffer)
    data = buffer.getvalue()

    result = extract_xlsx_text_and_json(data)
    assert "SHEET: Sheet1" in result.text
    assert result.json_payload["Sheet1"][0]["Header1"] == "Value1"
