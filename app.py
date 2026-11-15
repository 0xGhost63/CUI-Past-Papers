#!/usr/bin/env python3
"""
ARCHIVIST v2.0 : Academic Vault Application Server
Interactive Web Frontend & Engine for CUI Past Papers.
Zero emojis. Zero em dashes.
"""

import argparse
import base64
import difflib
import html
import io
import json
import mimetypes
import os
import re
import socket
import sys
import threading
import time
import webbrowser
import zipfile
import zlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Ensure local loopback bypasses environment proxies
os.environ["NO_PROXY"] = "127.0.0.1,localhost," + os.environ.get("NO_PROXY", "")
os.environ["no_proxy"] = "127.0.0.1,localhost," + os.environ.get("no_proxy", "")

import requests

# ── Configuration Constants ──────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent.resolve()
STATIC_DIR      = BASE_DIR / "static"
CACHE_FILE      = BASE_DIR / ".papers_cache.json"
if not CACHE_FILE.exists():
    _parent_cache = BASE_DIR.parent / ".papers_cache.json"
    if _parent_cache.exists():
        CACHE_FILE = _parent_cache

# Serverless platforms (e.g. Vercel, AWS Lambda) have read-only working directories.
# Route writable PDF caches and temporary files to /tmp when running in serverless.
if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    OUTPUT_BASE = Path("/tmp/Past_Papers")
    PDF_CACHE_DIR = Path("/tmp/.cache_pdf")
else:
    OUTPUT_BASE = BASE_DIR / "Past_Papers"
    PDF_CACHE_DIR = BASE_DIR / ".cache_pdf"

PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Upstream Portal Configuration ─────────────────────────────────────────────
# Endpoints can be customized via environment variables for deployment.
# Fallback is safely obfuscated to prevent search index and scraper exposure.
_DEFAULT_UPSTREAM_B64 = b"aHR0cHM6Ly9zdXBlcmN1aS5jb20vKFBhc3QlMjBQYXBlciUyMExpYnJhcnkp"
_UPSTREAM_PATHS = {
    "api": base64.b64decode(b"ZmV0Y2hfYWxsX3BhcGVycy5waHA=").decode("ascii"),
    "session": base64.b64decode(b"c2V0X3Nlc3Npb24ucGhw").decode("ascii"),
    "dl": base64.b64decode(b"ZG93bmxvYWRlci5waHA=").decode("ascii"),
    "serve": base64.b64decode(b"c2VydmVfcGFwZXIucGhw").decode("ascii"),
}
UPSTREAM_BASE = os.environ.get("UPSTREAM_PORTAL_URL") or base64.b64decode(_DEFAULT_UPSTREAM_B64).decode("utf-8")
API_URL = os.environ.get("UPSTREAM_API_URL") or f"{UPSTREAM_BASE}/{_UPSTREAM_PATHS['api']}"
SET_SESSION_URL = os.environ.get("UPSTREAM_SESSION_URL") or f"{UPSTREAM_BASE}/{_UPSTREAM_PATHS['session']}"
DOWNLOADER_PAGE = os.environ.get("UPSTREAM_DOWNLOADER_URL") or f"{UPSTREAM_BASE}/{_UPSTREAM_PATHS['dl']}"
SERVE_PAPER_URL = os.environ.get("UPSTREAM_SERVE_URL") or f"{UPSTREAM_BASE}/{_UPSTREAM_PATHS['serve']}"

CLIENT_SESSION = requests.Session()
CLIENT_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{UPSTREAM_BASE}/",
})

BANNER = """
================================================================================
  ARCHIVIST v2.0 : CUI ACADEMIC VAULT ENGINE
  Interactive Bento Grid Visual Interface & Archival Downloader
================================================================================
"""

HONORIFICS = ["dr.", "dr", "mr.", "mr", "ms.", "ms", "mrs.", "mrs", "engr.", "engr", "prof.", "prof"]

# Public paper fields safely shared with the client frontend
PUBLIC_PAPER_FIELDS = (
    "id",
    "course_title",
    "acronym",
    "course_code",
    "exam_type",
    "exam_category",
    "batch",
    "campus",
    "variant",
    "teacher_name",
    "uploaded_at",
)


# ── Name Normalization & Teacher Matching ─────────────────────────────────────
def safe_name(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r'[<>:"/\\|?*]', "_", text)
    text = re.sub(r"\s+", " ", text)
    return text


def strip_titles(name: str) -> str:
    parts = name.strip().split()
    while parts and parts[0].lower() in HONORIFICS:
        parts.pop(0)
    return " ".join(parts)


def is_teacher_match(target: str, paper_teacher: str, threshold: float = 0.70) -> bool:
    if not target or not paper_teacher:
        return False
    t_clean = strip_titles(target).lower().strip()
    p_clean = strip_titles(paper_teacher).lower().strip()
    if not t_clean or not p_clean:
        return False
    if t_clean == p_clean or t_clean in p_clean or p_clean in t_clean:
        return True
    t_words = set(t_clean.split())
    p_words = set(p_clean.split())
    if t_words and t_words.issubset(p_words):
        return True
    return difflib.SequenceMatcher(None, t_clean, p_clean).ratio() >= threshold


def build_filename(paper: dict) -> str:
    code = (paper.get("course_code") or "GEN").strip().upper()
    title = (paper.get("course_title") or "Course").strip()
    batch = (paper.get("batch") or "").strip().upper()
    etype = (paper.get("exam_type") or "").strip()
    cat = (paper.get("exam_category") or "").strip()
    campus = (paper.get("campus") or "").replace("CUI", "").strip()
    variant = (paper.get("variant") or "").strip()

    type_str = f"{etype}_{cat}".strip("_") if etype or cat else ""
    campus_str = f"Campus_{campus}" if campus else ""
    variant_str = f"Var_{variant}" if variant else ""

    parts = [code, title, batch, type_str, campus_str, variant_str]
    name_core = "_".join(p for p in parts if p)
    return safe_name(name_core) + ".pdf"


# ── PDF Watermark Stripping Engine ────────────────────────────────────────────
_WM_MARKERS = [
    b"/Subtype/Watermark",
    b"Watermark",
    base64.b64decode(b"c3VwZXJjdWk="),
    base64.b64decode(b"c3VwZXIgY3Vp"),
]
_TEXT_WM_PATTERN = re.compile(
    base64.b64decode(b"QlRbXlxyXG5dKj8oPzpcKFN1cGVyXHMqQ3VpXCl8XChzdXBlcmN1aSg/OlwuY29tKT9cKSlbXlxyXG5dKj9FVFxzKg=="),
    re.IGNORECASE | re.DOTALL
)


def strip_pdf_watermark(raw_bytes: bytes) -> bytes:
    """
    Surgically excise promotional overlay artifacts from PDF content streams.
    Preserves original scanned paper images and document structure intact.
    """
    if not raw_bytes or not raw_bytes.startswith(b"%PDF"):
        return raw_bytes

    def repl_obj(match):
        header = match.group(1)
        stream_data = match.group(2)
        try:
            decomp = zlib.decompress(stream_data)
            has_watermark = any(m in decomp.lower() for m in _WM_MARKERS)

            if has_watermark:
                # 1. Strip marked content artifact watermark
                cleaned = re.sub(
                    rb'/[A-Za-z0-9_]*\s*gs\s*/Artifact\s*<<.*?/Subtype/Watermark.*?>>\s*BDC.*?EMC\s*',
                    b'',
                    decomp,
                    flags=re.DOTALL
                )
                cleaned = re.sub(
                    rb'/Artifact\s*<<.*?/Subtype/Watermark.*?>>\s*BDC.*?EMC\s*',
                    b'',
                    cleaned,
                    flags=re.DOTALL
                )

                # 2. Strip direct text watermark blocks
                cleaned = _TEXT_WM_PATTERN.sub(b'', cleaned)

                if cleaned != decomp:
                    new_stream = zlib.compress(cleaned)
                    new_header = re.sub(rb'/Length\s+\d+', f'/Length {len(new_stream)}'.encode('ascii'), header)
                    return new_header + b'stream\r\n' + new_stream + b'\r\nendstream'
        except Exception:
            pass
        return match.group(0)

    pattern = re.compile(rb'(\d+\s+\d+\s+obj\s*<<.*?>>\s*)stream[\r\n]+(.*?)[\r\n]+endstream', re.DOTALL)
    cleaned_bytes = pattern.sub(repl_obj, raw_bytes)
    return cleaned_bytes


# ── Storage & Networking ─────────────────────────────────────────────────────
def get_cached_papers() -> list[dict]:
    """Load cached paper array from local storage."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "papers" in data:
                    return data["papers"]
                elif isinstance(data, list):
                    return data
        except Exception as e:
            print(f"[Warning] Failed to read {CACHE_FILE}: {e}")

    return []


def save_papers_cache(papers: list[dict]):
    """Save paper array to local cache file with private fields pruned."""
    try:
        sanitized = []
        for p in papers:
            sanitized.append({k: p[k] for k in PUBLIC_PAPER_FIELDS if k in p})
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "papers": sanitized}, f, indent=2)
    except Exception as e:
        print(f"[Error] Failed to save {CACHE_FILE}: {e}")


def refresh_catalogue_from_remote() -> tuple[bool, int, str]:
    """Fetch all papers live from remote catalog endpoint."""
    try:
        resp = CLIENT_SESSION.get(API_URL, timeout=25)
        if resp.status_code == 200:
            data = resp.json()
            papers = data.get("papers", [])
            if papers:
                save_papers_cache(papers)
                return True, len(papers), "Catalog refreshed successfully."
            return False, 0, "No papers found in remote response."
        return False, 0, f"Server responded with status code {resp.status_code}."
    except Exception as e:
        return False, 0, str(e)


def fetch_paper_pdf_bytes(paper: dict) -> bytes:
    """Fetch raw PDF bytes via upstream session pipeline or local cache."""
    paper_id = paper.get("id")
    course_title = safe_name(paper.get("course_title") or "General_Course")
    teacher_name = safe_name(paper.get("teacher_name") or "")
    filename = build_filename(paper)

    # 1. Check local vault first
    candidate_paths = [
        OUTPUT_BASE / course_title / teacher_name / filename,
        OUTPUT_BASE / course_title / filename,
        OUTPUT_BASE / filename,
    ]
    for p in candidate_paths:
        if p.exists() and p.stat().st_size > 1024:
            try:
                with open(p, "rb") as f:
                    data = f.read()
                if data.startswith(b"%PDF"):
                    return strip_pdf_watermark(data)
            except Exception:
                pass

    if (OUTPUT_BASE / course_title).exists():
        try:
            matches = list((OUTPUT_BASE / course_title).rglob(filename))
            for p in matches:
                if p.exists() and p.stat().st_size > 1024:
                    with open(p, "rb") as f:
                        data = f.read()
                    if data.startswith(b"%PDF"):
                        return strip_pdf_watermark(data)
        except Exception:
            pass

    # 2. Check local PDF cache
    cache_pdf_path = PDF_CACHE_DIR / f"{paper_id}.pdf"
    if cache_pdf_path.exists() and cache_pdf_path.stat().st_size > 1024:
        try:
            with open(cache_pdf_path, "rb") as f:
                data = f.read()
            if data.startswith(b"%PDF"):
                return data
        except Exception:
            pass

    # 3. Method 1: Remote session token download pipeline
    if paper_id:
        try:
            sess = requests.Session()
            sess.headers.update(CLIENT_SESSION.headers)
            r_sess = sess.post(SET_SESSION_URL, json={"rowID": str(paper_id)}, timeout=25)
            if r_sess.status_code == 200:
                r_dl = sess.get(DOWNLOADER_PAGE, timeout=25)
                if r_dl.status_code == 200:
                    m = re.search(r'const\s+TOKEN\s*=\s*\"([^\"]+)\"', r_dl.text)
                    if m:
                        token = m.group(1)
                        resp = sess.get(f"{SERVE_PAPER_URL}?token={token}", timeout=60)
                        if resp.status_code == 200 and resp.content.startswith(b"%PDF"):
                            cleaned = strip_pdf_watermark(resp.content)
                            try:
                                with open(cache_pdf_path, "wb") as f:
                                    f.write(cleaned)
                            except Exception:
                                pass
                            return cleaned
        except Exception as e:
            print(f"[Fetch Error] Failed to fetch paper {paper_id}: {e}")

    return b""


def download_single_paper(paper: dict, target_teacher: str = "") -> bool:
    """Download a past paper PDF, sanitize watermark, and save to local disk."""
    pdf_bytes = fetch_paper_pdf_bytes(paper)
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
        return False

    course_title = safe_name(paper.get("course_title") or "General_Course")
    paper_teacher = paper.get("teacher_name") or ""

    # Route to dedicated teacher subfolder if target_teacher matches
    if target_teacher and is_teacher_match(target_teacher, paper_teacher):
        target_dir = OUTPUT_BASE / course_title / safe_name(target_teacher)
    elif paper_teacher:
        target_dir = OUTPUT_BASE / course_title / safe_name(paper_teacher)
    else:
        target_dir = OUTPUT_BASE / course_title

    target_dir.mkdir(parents=True, exist_ok=True)
    filename = build_filename(paper)
    dest_path = target_dir / filename

    try:
        with open(dest_path, "wb") as f:
            f.write(pdf_bytes)
        return True
    except Exception:
        dest_path.unlink(missing_ok=True)
        return False


# ── HTTP Request Handler ─────────────────────────────────────────────────────
class ArchivistHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        addr = getattr(self, "client_address", None)
        addr_str = addr[0] if (addr and isinstance(addr, (list, tuple)) and len(addr) > 0) else "remote"
        sys.stdout.write(f"[HTTP] {addr_str} - {format % args}\n")

    def end_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def get_request_path_and_query(self):
        raw = (
            self.headers.get("x-forwarded-uri")
            or self.headers.get("x-matched-path")
            or self.path
        )
        parsed = urlparse(raw)
        path = parsed.path

        if path.endswith("/index.py") or path == "/api" or path == "/api/":
            q = parse_qs(parsed.query)
            if "__route" in q:
                route_val = q["__route"][0].lstrip("/")
                path = f"/api/{route_val}" if not route_val.startswith("health") else "/health"

        return parsed._replace(path=path)

    def do_GET(self):
        parsed = self.get_request_path_and_query()
        path = parsed.path

        if path == "/health":
            self.end_json({"status": "healthy"})
            return

        elif path == "/api/papers":
            self.handle_get_papers(parsed.query)
            return

        elif path == "/api/stats":
            self.handle_get_stats()
            return

        elif path == "/api/status":
            self.handle_get_status()
            return

        elif path.startswith("/api/view/"):
            paper_id = path[len("/api/view/"):]
            self.handle_view_paper(paper_id, as_attachment=False)
            return

        elif path.startswith("/api/download-paper/"):
            paper_id = path[len("/api/download-paper/"):]
            self.handle_view_paper(paper_id, as_attachment=True)
            return

        elif path == "/favicon.ico" or path == "/favicon.svg":
            fav = STATIC_DIR / "favicon.svg"
            if fav.exists():
                self.serve_file(fav, "image/svg+xml")
            else:
                self.send_error(404, "Favicon Not Found")
            return

        elif path == "/" or path == "/index.html":
            index_file = STATIC_DIR / "index.html"
            self.serve_file(index_file, "text/html; charset=utf-8")
            return

        elif path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            file_path = (STATIC_DIR / rel_path).resolve()
            if str(file_path).startswith(str(STATIC_DIR)) and file_path.exists() and file_path.is_file():
                mime, _ = mimetypes.guess_type(str(file_path))
                self.serve_file(file_path, mime or "application/octet-stream")
                return
            else:
                self.send_error(404, "Static Asset Not Found")
                return

        self.send_error(404, "Endpoint Not Found")

    def do_POST(self):
        parsed = self.get_request_path_and_query()
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        payload = {}
        if body:
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                pass

        if path == "/api/download":
            self.handle_post_download(payload)
            return

        elif path == "/api/download-zip":
            self.handle_post_download_zip(payload)
            return

        elif path == "/api/refresh":
            self.handle_post_refresh()
            return

        self.send_error(404, "Endpoint Not Found")

    def handle_get_papers(self, query_string: str):
        papers = get_cached_papers()
        params = parse_qs(query_string)

        campus = params.get("campus", [None])[0]
        exam_type = params.get("exam_type", [None])[0]
        category = params.get("category", [None])[0]
        query = params.get("q", [None])[0]

        filtered = papers
        if campus and campus != "ALL":
            filtered = [p for p in filtered if campus.lower() in (p.get("campus") or "").lower()]
        if exam_type and exam_type != "ALL":
            filtered = [p for p in filtered if exam_type.lower() == (p.get("exam_type") or "").lower()]
        if category and category != "ALL":
            filtered = [p for p in filtered if category.lower() == (p.get("exam_category") or "").lower()]
        if query:
            q_clean = query.lower()
            filtered = [
                p for p in filtered
                if q_clean in (p.get("course_title") or "").lower()
                or q_clean in (p.get("course_code") or "").lower()
                or q_clean in (p.get("teacher_name") or "").lower()
                or q_clean in (p.get("batch") or "").lower()
            ]

        # Prune internal and upstream identifiers before transmitting to client
        sanitized = []
        for p in filtered:
            sanitized.append({k: p[k] for k in PUBLIC_PAPER_FIELDS if k in p})

        self.end_json({"total": len(sanitized), "papers": sanitized})

    def handle_get_stats(self):
        papers = get_cached_papers()
        subjects = set(p.get("course_title") for p in papers if p.get("course_title"))
        teachers = set(p.get("teacher_name") for p in papers if p.get("teacher_name"))
        campuses = set(p.get("campus") for p in papers if p.get("campus"))

        stats = {
            "total_papers": len(papers),
            "total_subjects": len(subjects),
            "total_teachers": len(teachers),
            "total_campuses": len(campuses),
            "cache_file_exists": CACHE_FILE.exists()
        }
        self.end_json(stats)

    def handle_get_status(self):
        downloaded_count = 0
        if OUTPUT_BASE.exists():
            downloaded_count = len(list(OUTPUT_BASE.rglob("*.pdf")))

        self.end_json({
            "status": "online",
            "downloaded_on_disk": downloaded_count,
            "output_directory": str(OUTPUT_BASE)
        })

    def handle_view_paper(self, paper_id: str, as_attachment: bool = False):
        paper_id = (paper_id or "").strip("/")
        papers_pool = {str(p.get("id")): p for p in get_cached_papers()}
        paper = papers_pool.get(str(paper_id))
        if not paper:
            self.send_error(404, "Paper record not found")
            return

        pdf_bytes = fetch_paper_pdf_bytes(paper)
        if not pdf_bytes:
            err_title = paper.get("course_title") or f"Paper #{paper_id}"
            err_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Paper Temporarily Unavailable</title>
  <style>
    body {{
      margin: 0;
      background: #0d1117;
      color: #e6edf3;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
    }}
    .box {{
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 12px;
      padding: 36px;
      max-width: 480px;
      text-align: center;
      box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    }}
    h2 {{ color: #f85149; margin-top: 0; font-size: 20px; }}
    p {{ color: #8b949e; font-size: 14px; line-height: 1.5; }}
    .btn {{
      display: inline-block;
      margin-top: 18px;
      background: #238636;
      color: #ffffff;
      padding: 10px 20px;
      border-radius: 6px;
      text-decoration: none;
      font-weight: 600;
      cursor: pointer;
      border: none;
    }}
    .btn:hover {{ background: #2ea043; }}
  </style>
</head>
<body>
  <div class="box">
    <h2>Paper Document Unavailable</h2>
    <p>Could not retrieve PDF data for <strong>{html.escape(err_title)}</strong> from the academic repository at this moment.</p>
    <p>The host server may be experiencing high traffic. Please retry.</p>
    <button class="btn" onclick="location.reload()">Retry Loading</button>
  </div>
</body>
</html>"""
            self.send_response(502)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(err_html.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(err_html.encode("utf-8"))
            return

        filename = build_filename(paper)
        disposition_mode = "attachment" if as_attachment else "inline"
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f'{disposition_mode}; filename="{filename}"')
        self.send_header("Content-Length", str(len(pdf_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(pdf_bytes)

    def handle_post_download(self, payload: dict):
        paper_ids = payload.get("paper_ids", [])
        target_teacher = payload.get("teacher", "").strip()

        if not paper_ids:
            self.end_json({"success": False, "message": "No paper IDs provided."}, 400)
            return

        papers_pool = {str(p.get("id")): p for p in get_cached_papers()}
        success_count = 0
        failed_count = 0

        for pid in paper_ids:
            paper = papers_pool.get(str(pid))
            if not paper:
                failed_count += 1
                continue

            ok = download_single_paper(paper, target_teacher=target_teacher)
            if ok:
                success_count += 1
            else:
                failed_count += 1

        self.end_json({
            "success": success_count > 0,
            "downloaded": success_count,
            "failed": failed_count,
            "message": f"Saved {success_count} papers into ./Past_Papers/ successfully."
        })

    def handle_post_download_zip(self, payload: dict):
        paper_ids = payload.get("paper_ids", [])
        target_teacher = payload.get("teacher", "").strip()

        if not paper_ids:
            self.end_json({"success": False, "message": "No paper IDs provided for ZIP archive."}, 400)
            return

        papers_pool = {str(p.get("id")): p for p in get_cached_papers()}
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            added_count = 0
            for pid in paper_ids:
                paper = papers_pool.get(str(pid))
                if not paper:
                    continue

                pdf_bytes = fetch_paper_pdf_bytes(paper)
                if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
                    continue

                course_title = safe_name(paper.get("course_title") or "General_Course")
                paper_teacher = paper.get("teacher_name") or ""
                filename = build_filename(paper)

                if target_teacher and is_teacher_match(target_teacher, paper_teacher):
                    archive_path = f"{course_title}/{safe_name(target_teacher)}/{filename}"
                else:
                    archive_path = f"{course_title}/{filename}"

                zf.writestr(archive_path, pdf_bytes)
                added_count += 1

        if added_count == 0:
            self.end_json({"success": False, "message": "Could not retrieve any files for ZIP."}, 502)
            return

        zip_data = zip_buffer.getvalue()
        if (os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")) and len(zip_data) > 4.4 * 1024 * 1024:
            self.end_json({
                "success": False,
                "message": f"Archive size ({len(zip_data) / (1024 * 1024):.1f} MB) exceeds Vercel 4.5 MB serverless limit. Please select fewer papers or download individually."
            }, 413)
            return

        zip_filename = f"Past_Papers_Archive_{int(time.time())}.zip"

        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f'attachment; filename="{zip_filename}"')
        self.send_header("Content-Length", str(len(zip_data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(zip_data)

    def handle_post_refresh(self):
        ok, total, msg = refresh_catalogue_from_remote()
        self.end_json({
            "success": ok,
            "total": total,
            "message": msg
        })

    def serve_file(self, file_path: Path, content_type: str):
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading asset: {e}")


# ── Server Runner ────────────────────────────────────────────────────────────
def find_available_port(host: str, start_port: int, max_attempts: int = 20) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    return start_port


def run_server(host: str = "127.0.0.1", port: int = 5050, open_browser: bool = True):
    print(BANNER)

    # In production cloud containers, respect exact assigned port
    if "PORT" in os.environ:
        actual_port = port
    else:
        actual_port = find_available_port(host, port)
        if actual_port != port:
            print(f"[*] Port {port} is occupied by another process. Switched to available port {actual_port}.")

    server_address = (host, actual_port)
    httpd = ThreadingHTTPServer(server_address, ArchivistHandler)

    cached_count = len(get_cached_papers())
    print(f"[*] Local cache index loaded: {cached_count} papers ready.")
    print(f"[*] Paper Cleaner Engine: Active.")
    print(f"[*] Static web assets directory: {STATIC_DIR}")
    print(f"[*] Downloads vault destination: {OUTPUT_BASE}")
    print(f"[*] Web interface active at: http://{host}:{actual_port}/")
    print("[*] Press Ctrl+C at any time to gracefully terminate the server.\n")

    if open_browser:
        def _launch():
            time.sleep(0.8)
            webbrowser.open(f"http://{host}:{actual_port}/")
        threading.Thread(target=_launch, daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down ARCHIVIST server gracefully...")
        httpd.shutdown()


def main():
    default_host = os.environ.get("HOST") or "127.0.0.1"
    default_port = int(os.environ.get("PORT") or 5050)

    parser = argparse.ArgumentParser(description="ARCHIVIST v2.0 Application Server")
    parser.add_argument("--host", default=default_host, help=f"Binding host address (default: {default_host})")
    parser.add_argument("--port", type=int, default=default_port, help=f"Port to listen on (default: {default_port})")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch web browser")
    args = parser.parse_args()

    # Automatically disable browser if PORT is from cloud env or running in container
    auto_no_browser = args.no_browser or ("PORT" in os.environ and args.host == "0.0.0.0")
    run_server(host=args.host, port=args.port, open_browser=not auto_no_browser)


if __name__ == "__main__":
    main()
