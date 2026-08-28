"""
verification_engine.py

Same seven-check heuristic engine as the frontend's runVerification():
required fields, ID format, institution recognition, date plausibility,
a database cross-check, plus image resolution and OCR confidence for
uploads. Produces the same shape of result (checks, score, verdict) so
it's a drop-in replacement for the client-side version.
"""

import re
from datetime import datetime

from database import get_institution_names, find_certificate_by_id

CERT_ID_FORMAT_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{5,}$", re.IGNORECASE)


def _try_parse_date(value: str):
    if not value:
        return None
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"]
    for fmt in formats:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def run_verification(fields: dict, mode: str, ocr_confidence: float = None, image_dims=None) -> dict:
    checks = []
    forced_fake = False

    candidate_name = fields.get("candidateName", "").strip()
    institution = fields.get("institution", "").strip()
    cert_id = fields.get("certId", "").strip()
    issue_date = fields.get("issueDate", "").strip()

    # 1. Required fields present
    required_ok = bool(candidate_name and institution and cert_id and issue_date)
    checks.append({
        "id": "fields", "weight": 15, "pass": required_ok,
        "label": "All core fields present" if required_ok else "One or more core fields missing",
        "detail": (
            "Candidate name, institution, certificate ID and date were all located."
            if required_ok else
            "A genuine certificate should clearly state the candidate name, issuer, ID and date "
            "— one or more could not be found."
        ),
        "tone": "ok" if required_ok else "bad",
    })

    # 2. Certificate ID format
    id_ok = bool(cert_id and CERT_ID_FORMAT_RE.match(cert_id))
    checks.append({
        "id": "idFormat", "weight": 15, "pass": id_ok,
        "label": "Certificate ID format is plausible" if id_ok else "Certificate ID format looks unusual",
        "detail": (
            f'"{cert_id}" follows a typical alphanumeric ID pattern.' if id_ok else
            "The ID is missing, too short, or doesn't follow a typical certificate ID pattern."
        ),
        "tone": "ok" if id_ok else "warn",
    })

    # 3. Institution recognized
    known_institutions = get_institution_names()
    inst_ok = bool(institution) and any(
        institution.lower() in name.lower() or name.lower() in institution.lower()
        for name in known_institutions
    )
    checks.append({
        "id": "institution", "weight": 15, "pass": inst_ok,
        "label": "Institution recognized" if inst_ok else "Institution not in demo records",
        "detail": (
            f'"{institution}" matches a known issuer in the verification dataset.' if inst_ok else
            "This issuer isn't in the small demo dataset used here — not necessarily a red flag, "
            "but it can't be independently confirmed."
        ),
        "tone": "ok" if inst_ok else "warn",
    })

    # 4. Date validity
    parsed_date = _try_parse_date(issue_date)
    date_ok = bool(parsed_date and 1950 <= parsed_date.year <= datetime.now().year and parsed_date <= datetime.now())
    checks.append({
        "id": "date", "weight": 15, "pass": date_ok,
        "label": "Issue date is plausible" if date_ok else "Issue date could not be validated",
        "detail": (
            "The date parses correctly and falls within a plausible range." if date_ok else
            "The date is missing, unparsable, or falls outside a plausible range (e.g. in the future)."
        ),
        "tone": "ok" if date_ok else "bad",
    })

    # 5. Database cross-check
    if cert_id:
        record = find_certificate_by_id(cert_id)
        if record:
            first_name_token = candidate_name.lower().split(" ")[0] if candidate_name else ""
            name_ok = bool(first_name_token) and first_name_token in record["candidate_name"].lower()
            if name_ok:
                checks.append({
                    "id": "dbcheck", "weight": 25, "pass": True,
                    "label": "Certificate ID matched in verification records",
                    "detail": (
                        f'Record on file: {record["candidate_name"]} — {record["institution"]} — '
                        f'{record["course"]} ({record["issue_date"]}).'
                    ),
                    "tone": "ok",
                })
            else:
                forced_fake = True
                checks.append({
                    "id": "dbcheck", "weight": 25, "pass": False,
                    "label": "Certificate ID registered to a different candidate",
                    "detail": (
                        f'ID "{cert_id}" is on file for a different name in verification records. '
                        "This is a strong inconsistency."
                    ),
                    "tone": "bad",
                })
        else:
            checks.append({
                "id": "dbcheck", "weight": 25, "pass": False, "partial": 0.4,
                "label": "Certificate ID not found in demo records",
                "detail": (
                    "No matching entry in this demo's small verification dataset — expected for "
                    "most real certificates here, so treated as inconclusive rather than negative."
                ),
                "tone": "warn",
            })

    # 6. Image quality (upload mode only)
    if mode == "upload" and image_dims:
        width, height = image_dims
        good_res = width >= 500 and height >= 500
        checks.append({
            "id": "imgQuality", "weight": 10, "pass": good_res,
            "label": "Scan resolution is adequate" if good_res else "Low resolution scan",
            "detail": (
                f"Image is {width}×{height}px — enough detail for reliable reading." if good_res else
                f"Image is only {width}×{height}px — fine print and seals may not be reliably readable."
            ),
            "tone": "ok" if good_res else "warn",
        })

    # 7. OCR confidence (upload mode only)
    if mode == "upload" and ocr_confidence is not None:
        conf_ok = ocr_confidence >= 65
        checks.append({
            "id": "ocrConf", "weight": 10, "pass": conf_ok,
            "label": "Text extraction was clear" if conf_ok else "Text extraction was unclear",
            "detail": (
                f"OCR reported {round(ocr_confidence)}% confidence reading this image." if conf_ok else
                f"OCR reported only {round(ocr_confidence)}% confidence — could be a poor scan, "
                "an unusual font, or signs of tampering."
            ),
            "tone": "ok" if conf_ok else "warn",
        })

    # ---- scoring ----
    total_weight = sum(c["weight"] for c in checks)
    earned = sum(
        c["weight"] if c["pass"] else (c["weight"] * c.get("partial", 0))
        for c in checks
    )
    score = round((earned / total_weight) * 100) if total_weight else 0
    if forced_fake:
        score = min(score, 20)

    if score < 40:
        verdict = "fake"
    elif score < 75:
        verdict = "suspicious"
    else:
        verdict = "genuine"

    return {"checks": checks, "score": score, "verdict": verdict}