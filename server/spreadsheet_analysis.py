import io
import os
import json
import pymongo
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from shapely.geometry import Polygon, Point

# Azure AI Document Intelligence credentials
DOC_INTEL_ENDPOINT = os.getenv("DOC_INTEL_ENDPOINT")
DOC_INTEL_KEY = os.getenv("DOC_INTEL_KEY")

# MongoDB connection (falls back to localhost)
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "pdf_bot")

# Initialize clients
doc_client = DocumentAnalysisClient(
    endpoint=DOC_INTEL_ENDPOINT,
    credential=AzureKeyCredential(DOC_INTEL_KEY)
)
mongo = pymongo.MongoClient(MONGO_URI)
db = mongo[DB_NAME]
coll = db["spreadsheet_analysis"]


def analyze_spreadsheet_auto_merge(pdf_bytes: bytes, file_name: str) -> dict:
    """
    Analyze a PDF via Azure prebuilt-layout, automatically merging tables
    horizontally or vertically based on layout, interleaving non-table text,
    stores { filename, merged: True, data } in MongoDB, and returns the JSON.
    """
    # Run Form Recognizer
    stream = io.BytesIO(pdf_bytes)
    poller = doc_client.begin_analyze_document("prebuilt-layout", document=stream)
    result = poller.result()

    # Prepare JSON structure
    data = {"activeSheet": "Sheet1", "sheets": [{"name": "Sheet1", "rows": []}]}
    sheet_rows = []
    current_row = 1

    # Process each page
    for page in result.pages:
        # Collect tables with geometry
        tables = []
        for tbl in result.tables:
            region = tbl.bounding_regions[0]
            if region.page_number != page.page_number:
                continue
            coords = [(p.x, p.y) for p in region.polygon]
            ys = [y for _, y in coords]
            xs = [x for x, _ in coords]
            poly = Polygon(coords)
            tables.append({
                "table": tbl,
                "poly": poly,
                "ymin": min(ys),
                "ymax": max(ys),
                "xmin": min(xs)
            })
        # Cluster into bands
        bands = []
        for tbl in tables:
            placed = False
            for band in bands:
                if not (tbl["ymax"] < band["ymin"] or tbl["ymin"] > band["ymax"]):
                    band["tables"].append(tbl)
                    band["ymin"] = min(band["ymin"], tbl["ymin"])
                    band["ymax"] = max(band["ymax"], tbl["ymax"])
                    placed = True
                    break
            if not placed:
                bands.append({"tables": [tbl], "ymin": tbl["ymin"], "ymax": tbl["ymax"]})

        # Build layout elements
        elements = []
        for band in bands:
            # sort left-to-right
            band["tables"].sort(key=lambda t: t["xmin"])
            # compute col offsets
            offsets, cum = [], 0
            for t in band["tables"]:
                ncols = max(c.column_index for c in t["table"].cells) + 1
                offsets.append(cum)
                cum += ncols
                        # collect band rows (handle colspan)
            band_rows = {}
            for idx, t in enumerate(band["tables"]):
                off = offsets[idx]
                for cell in t["table"].cells:
                    r, c = cell.row_index, cell.column_index
                    # detect colspan (default 1)
                    span = getattr(cell, 'column_span', 1)
                    for span_idx in range(span):
                        col_key = off + c + span_idx
                        band_rows.setdefault(r, []).append({
                            "col": col_key,
                            "text": cell.content.strip()
                        })
            elements.append({"type": "band", "y": band["ymin"], "rows": band_rows})

        # Add non-table text
        table_polys = [b["poly"] for b in tables]
        for line in page.lines:
            coords = [(p.x, p.y) for p in line.polygon]
            ys = [y for _, y in coords]
            cy = sum(ys) / len(ys)
            pt = Point(sum(x for x, _ in coords) / len(coords), cy)
            if not any(poly.contains(pt) for poly in table_polys):
                elements.append({"type": "line", "y": cy, "text": line.content.strip()})

        # Sort and emit
        elements.sort(key=lambda e: e["y"])
        for el in elements:
            if el["type"] == "band":
                for r in sorted(el["rows"]):
                    cells = el["rows"][r]
                    cells.sort(key=lambda x: x["col"])
                    row_cells = [{"value": c["text"], "enable": True, "index": i + 1}
                                 for i, c in enumerate(cells)]
                    sheet_rows.append({"cells": row_cells, "index": current_row})
                    current_row += 1
                current_row += 1
            else:
                sheet_rows.append({
                    "cells": [{"value": el["text"], "enable": True, "index": 1}],
                    "index": current_row
                })
                current_row += 1

    data["sheets"][0]["rows"] = sheet_rows

    # Store into MongoDB
    coll.insert_one({"filename": file_name, "merged": True, "data": data})

    return data