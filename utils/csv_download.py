"""UTF-8 CSV download helpers (Excel-compatible BOM)."""

from __future__ import annotations

import csv
from io import StringIO

from flask import Response

CSV_BOM = "\ufeff"


def build_csv_download_response(
    *,
    filename: str,
    headers: list[str],
    rows: list[list],
) -> Response:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    payload = (CSV_BOM + buffer.getvalue()).encode("utf-8")
    return Response(
        payload,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
