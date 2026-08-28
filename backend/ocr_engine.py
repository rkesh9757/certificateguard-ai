"""
ocr_engine.py

Runs OCR on an uploaded certificate image and pulls out the same fields
the frontend's client-side Tesseract.js pass looks for: candidate name,
institution, certificate ID, issue date, and course.

Requires the Tesseract OCR binary to be installed on the host machine
(this is separate from the pytesseract Python package):
  - Ubuntu/Debian: sudo apt-get install tesseract-ocr
  - macOS:         brew install tesseract
  - Windows:        https://github.com/UB-Mannheim/tesseract/wiki
"""

import re
import io
import pytesseract
from PIL import Image

from database import get_institution_names

# --- Windows only ---
# The Tesseract OCR program (not the pytesseract Python package) doesn't
# always get added to your PATH by its installer. If run_ocr() below
# raises "tesseract is not installed or it's not in your PATH", uncomment
# the next line and point it at wherever you installed Tesseract-OCR:
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

CERT_ID_RE = re.compile(r"\b[A-Z0-9][A-Z0-9-]{5,}\b")
DATE_RE = re.compile(
    r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
    r"|\d{4}-\d{2}-\d{2}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)
NAME_RE = re.compile(
    r"(?:certify that|awarded to|presented to|this is to certify that)\s+"
    r"([A-Z][A-Za-z.\s]{2,40})",
    re.IGNORECASE,
)
TITLE_LINE_RE = re.compile(r"^[A-Z][a-zA-Z]+(\s[A-Z][a-zA-Z]+){1,3}$")
INSTITUTION_LINE_RE = re.compile(r"university|institute|college|academy|board", re.IGNORECASE)
COURSE_RE = re.compile(
    r"(?:course on|course in|program(?:me)? in|for (?:successfully )?completing)\s+"
    r"([A-Za-z0-9 ,&-]{4,60})",
    re.IGNORECASE,
)


def run_ocr(image_bytes: bytes):
    """
    Returns (text, confidence) where confidence is a 0-100 average of
    per-word confidences reported by Tesseract (mirrors the .confidence
    value Tesseract.js returns on the frontend).
    """
    image = Image.open(io.BytesIO(image_bytes))

    text = pytesseract.image_to_string(image)

    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    confidences = [int(c) for c in data.get("conf", []) if c not in ("-1", -1)]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return text, avg_confidence, image.size  # size = (width, height)


def extract_fields(text: str) -> dict:
    clean = text.replace("\r", "")
    fields = {
        "candidateName": "",
        "institution": "",
        "certId": "",
        "issueDate": "",
        "course": "",
    }

    # Certificate ID: uppercase alphanumeric token containing at least one digit
    id_matches = CERT_ID_RE.findall(clean.upper())
    id_candidate = next((m for m in id_matches if any(ch.isdigit() for ch in m)), None)
    if not id_candidate and id_matches:
        id_candidate = id_matches[0]
    if id_candidate:
        fields["certId"] = id_candidate.strip()

    # Institution: match against the known dataset first
    lower_clean = clean.lower()
    known = get_institution_names()
    matched_institution = next((name for name in known if name.lower() in lower_clean), None)
    if matched_institution:
        fields["institution"] = matched_institution
    else:
        for line in clean.split("\n"):
            if INSTITUTION_LINE_RE.search(line):
                fields["institution"] = line.strip()[:80]
                break

    # Date
    date_match = DATE_RE.search(clean)
    if date_match:
        fields["issueDate"] = date_match.group(0)

    # Candidate name
    name_match = NAME_RE.search(clean)
    if name_match:
        fields["candidateName"] = name_match.group(1).strip().split("\n")[0]
    else:
        for line in clean.split("\n"):
            line = line.strip()
            if TITLE_LINE_RE.match(line):
                fields["candidateName"] = line
                break

    # Course
    course_match = COURSE_RE.search(clean)
    if course_match:
        fields["course"] = course_match.group(1).strip().split("\n")[0]

    return fields