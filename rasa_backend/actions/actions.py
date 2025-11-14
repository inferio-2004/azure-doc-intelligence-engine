# actions.py
import os
import re
import difflib
import tempfile
from typing import List, Tuple

import pymongo
import gridfs
import fitz  # PyMuPDF
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.types import DomainDict

# --- CONFIG must match your Flask server ---
MONGO_URI    = "mongodb://localhost:27017/"
DB_NAME      = "pdf_bot"
PDF_BUCKET   = "pdfs"
INDEX_COLL   = "index"
MAPPING_COLL = "mappings"
# ----------------


def parse_page_query(page_query: str) -> List[Tuple[int, int]]:
    """
    "5"            -> [(5,5)]
    "5-7"          -> [(5,7)]
    "2,4,6-8"      -> [(2,2),(4,4),(6,8)]
    """
    segments = []
    for part in page_query.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            segments.append((int(start), int(end)))
        else:
            p = int(part)
            segments.append((p, p))
    return segments


class ActionSearchByTopicOrPage(Action):
    def name(self) -> str:
        return "action_search_by_topic_or_page"

    def __init__(self):
        client      = pymongo.MongoClient(MONGO_URI)
        self.db     = client[DB_NAME]
        self.fs     = gridfs.GridFS(self.db, collection=PDF_BUCKET)
        self.idx    = self.db[INDEX_COLL]
        self.maps   = self.db[MAPPING_COLL]

    def clean_topic_key(self, key: str) -> str:
        return re.sub(r"^\d+(\.\d+)*\s*", "", key).strip().lower()

    def extract_pdf_text(self, path: str, start: int, end: int) -> str:
        doc = fitz.open(path)
        pages = []
        for p in range(start - 1, end):
            pages.append(doc.load_page(p).get_text())
        doc.close()
        return "\n".join(pages).strip()

    def get_by_pages(self, start: int, end: int, pdf_path: str) -> str:
        try:
            text = self.extract_pdf_text(pdf_path, start, end)
            return text or "— no text on those pages —"
        except Exception as ex:
            return f"Error reading PDF: {ex}"

    def by_page_ranges(self, page_ranges: List[Tuple[int, int]], pdf_path: str) -> str:
        parts = []
        for s, e in page_ranges:
            header = f"📄 Page {s}" + (f"–{e}" if e != s else "")
            body   = self.get_by_pages(s, e, pdf_path)
            parts.append(f"{header}:\n\n{body}")
        return "\n\n".join(parts)

    def by_topic(self, topic: str, topic_map: dict, pdf_path: str) -> str:
        cleaned = {self.clean_topic_key(k): k for k in topic_map}
        tl      = topic.lower().strip()

        if tl in cleaned:
            real = cleaned[tl]
        else:
            matches = difflib.get_close_matches(tl, cleaned.keys(), n=1, cutoff=0.6)
            if not matches:
                return f"❌ Topic '{topic}' not found."
            real = cleaned[matches[0]]

        s, e = topic_map[real]
        header = (f"📘 '{real}' on page {s}" if s == e
                  else f"📘 '{real}' pages {s}–{e}")
        body = self.get_by_pages(s, e, pdf_path)
        return f"{header}:\n\n{body}"

    def run(self, dispatcher: CollectingDispatcher,
        tracker: Tracker, domain: DomainDict):

        pdf_name   = tracker.get_slot("pdf_name")
        topic      = tracker.get_slot("topic")
        page_query = tracker.get_slot("page_query")

        if not pdf_name:
            dispatcher.utter_message("❌ Please first tell me which PDF to load.")
            return []

        idx_doc = self.idx.find_one({"filename": pdf_name})
        if not idx_doc:
            # If the user asked for a topic, this is a problem.
            if topic:
                dispatcher.utter_message(f"❌ No index entry for '{pdf_name}'.")
                return []
            else:
                # If it's a page-based query, we can still try to load the PDF from GridFS
                idx_doc = {}  # create dummy
                topic_map = {}
        else:
            # 2) Fetch topic_map document
            map_doc = self.maps.find_one({"_id": idx_doc.get("mapping_id")})
            topic_map = map_doc.get("topic_map", {}) if map_doc else {}

        # 3) Load PDF into temp file
        try:
            gf       = self.fs.find_one({"filename": pdf_name})
            pdf_data = gf.read()
            tmp      = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            tmp.write(pdf_data)
            tmp.flush()
            pdf_path = tmp.name
        except Exception as ex:
            dispatcher.utter_message(f"❌ Error loading PDF: {ex}")
            return []

        # 4) Handle empty topic_map
        if not topic_map:
            if topic:
                dispatcher.utter_message(
                    "ℹ️ No Table of Contents was found for this PDF. Please use **page numbers** to extract content.\n"
                    "Example: 'Show me page 5' or 'Show me pages 2-4'"
                )
                return [SlotSet("topic", None)]

            if page_query:
                try:
                    ranges = parse_page_query(page_query)
                    output = self.by_page_ranges(ranges, pdf_path)
                except Exception:
                    output = "❌ Invalid page query. Use e.g. `5`, `5-7`, or `2,4,6-8`."
                dispatcher.utter_message(output)
                return [SlotSet("page_query", None)]
            else:
                dispatcher.utter_message(
                    "❗ I couldn't find any Table of Contents for this PDF. Please ask for **page numbers** to extract content."
                )
                return []

        # 5) If topic_map exists → handle topic or page query
        if page_query:
            try:
                ranges = parse_page_query(page_query)
                output = self.by_page_ranges(ranges, pdf_path)
            except Exception:
                output = "❌ Invalid page query. Use e.g. `5`, `5-7`, or `2,4,6-8`."
        elif topic:
            output = self.by_topic(topic, topic_map, pdf_path)
        else:
            output = "❌ Please ask me for a topic or a page number/range."

        dispatcher.utter_message(output)
        return [SlotSet("topic", None), SlotSet("page_query", None)]

