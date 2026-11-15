#!/usr/bin/env python3

import base64
import difflib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich import print as rprint

# ── Upstream Portal Configuration ─────────────────────────────────────────────
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
GDRIVE_DL_URL   = "https://docs.google.com/uc?export=download"
OUTPUT_BASE     = Path("./Past_Papers")
CACHE_FILE      = Path(".papers_cache.json")
CACHE_TTL       = 7 * 86400   # 7 days

console = Console()

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{UPSTREAM_BASE}/",
})

ASCII_BANNER = (
    "._____  .___.__  ._______  ._____________._\n"
    ":_ ___\\ :   |  \\ : .___  \\ |    ___/\\__ _:|\n"
    "|   |___|   :   || :   |  ||___    \\  |  :|\n"
    "|   /  ||   .   ||     :  ||       /  |   |\n"
    "|. __  ||___|   | \\. ___/ |__:___/   |   |\n"
    " :/ |. |    |___|   :/        :       |___|\n"
    " :   :/             :                      \n"
    "     :"
)


# ── Utilities ─────────────────────────────────────────────────────────────────

def safe_name(text: str) -> str:
    text = text.strip()
    text = re.sub(r'[<>:"/\\|?*]', "_", text)
    text = re.sub(r"\s+", " ", text)
    return text


def clear():
    os.system("clear" if os.name != "nt" else "cls")


def print_banner():
    clear()
    banner_text = Text(ASCII_BANNER, style="bold cyan")
    subtitle    = Text("CUI Past Papers Downloader", style="bold cyan")
    console.print(Align.center(banner_text))
    console.print(Align.center(subtitle))
    console.print()


def print_menu_panel(title: str, items: list[tuple[str, str]]):
    """Render a numbered menu panel."""
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column("key",  style="bold cyan",  no_wrap=True)
    table.add_column("desc", style="white")
    for key, desc in items:
        # Use Text() so brackets are never parsed as rich markup
        table.add_row(Text(f"[{key}]"), desc)
    console.print(Panel(table, title=f"[bold yellow]  {title}  [/]", border_style="blue", expand=False))


# ── Network ───────────────────────────────────────────────────────────────────

def fetch_with_retry(url: str, max_retries: int = 3, **kwargs) -> requests.Response:
    delay = 3
    for attempt in range(1, max_retries + 1):
        try:
            resp = SESSION.get(url, timeout=20, **kwargs)
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait = int(retry_after) if retry_after and retry_after.isdigit() else delay * attempt
                wait = min(wait, 20)
                console.print(f"  [yellow]Rate-limited - waiting {wait}s (attempt {attempt}/{max_retries}) …[/]")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except requests.HTTPError as exc:
            if exc.response.status_code >= 500 and attempt < max_retries:
                time.sleep(delay * attempt)
                continue
            raise
    raise RuntimeError(f"Server rate limit or timeout after {max_retries} attempts.")


def load_cache(ignore_ttl: bool = False) -> Optional[list[dict]]:
    candidates = [CACHE_FILE]
    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
            papers = None
            ts = 0
            if isinstance(data, dict):
                papers = data.get("papers")
                ts = data.get("ts", 0)
            elif isinstance(data, list):
                papers = data
            if papers:
                if path != CACHE_FILE and not CACHE_FILE.exists():
                    save_cache(papers)
                if ignore_ttl or (ts > 0 and time.time() - ts < CACHE_TTL) or ts == 0:
                    return papers
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return None


def save_cache(papers: list[dict]) -> None:
    try:
        CACHE_FILE.write_text(json.dumps({"ts": time.time(), "papers": papers}))
    except OSError:
        pass


def fetch_all_papers(force: bool = False) -> list[dict]:
    if not force:
        cached = load_cache()
        if cached:
            console.print(f"  [dim]Loaded {len(cached)} papers from cache.[/]")
            return cached

    with console.status("[bold cyan]Fetching catalogue…[/]", spinner="dots"):
        try:
            resp = fetch_with_retry(API_URL)
            data = resp.json()
            papers = data.get("papers", [])
            if papers:
                save_cache(papers)
                console.print(f"  [green]{len(papers)} papers fetched successfully.[/]")
                return papers
        except (requests.RequestException, RuntimeError) as exc:
            stale = load_cache(ignore_ttl=True)
            if stale:
                console.print(f"  [yellow]Notice: Unable to refresh from server ({exc}).[/]")
                console.print(f"  [dim]Loaded {len(stale)} papers from cached catalogue.[/]")
                time.sleep(1.2)
                return stale
            console.print(f"  [red]Failed to fetch catalogue: {exc}[/]")
            sys.exit(1)
        except json.JSONDecodeError:
            stale = load_cache(ignore_ttl=True)
            if stale:
                console.print("  [yellow]Notice: API returned invalid data. Using cached catalogue.[/]")
                time.sleep(1.2)
                return stale
            console.print("  [red]API returned invalid JSON.[/]")
            sys.exit(1)


# ── Teacher Matching & Searching ─────────────────────────────────────────────

TITLES_RE = re.compile(r"^(dr|mr|ms|mrs|prof|engr)\.?\s+", re.IGNORECASE)


def strip_titles(name: str) -> str:
    """Strip honorific prefixes (Dr., Mr., Ms., Prof., etc.) repeatedly."""
    cleaned = TITLES_RE.sub("", name.strip())
    while True:
        next_clean = TITLES_RE.sub("", cleaned.strip())
        if next_clean == cleaned:
            break
        cleaned = next_clean
    return cleaned.strip()


def tokenize_name(s: str) -> list[str]:
    """Tokenize a name into lowercase alphanumeric words, handling hyphens and punctuation."""
    s = s.replace("-", " ")
    s = re.sub(r"[^a-zA-Z0-9\s]", " ", s)
    return [w.lower() for w in s.split() if w]


def phonetic_word(w: str) -> str:
    """Normalize common South Asian spelling & phonetic variants."""
    w = w.lower()
    w = re.sub(r"ee", "i", w)
    w = re.sub(r"oo|ou", "u", w)
    w = re.sub(r"ahmed", "ahmad", w)
    w = re.sub(r"mohammad|mohammed|muhamed", "muhammad", w)
    w = re.sub(r"rehman|rahman", "rehman", w)
    w = re.sub(r"qadeer|qadir", "qadeer", w)
    w = re.sub(r"zeeshan|zeshan", "zeeshan", w)
    w = re.sub(r"waseem|wasim", "waseem", w)
    w = re.sub(r"([a-z])\1+", r"\1", w)
    return w


def score_teacher_match(query: str, teacher: str) -> float:
    """
    Score how closely a teacher name matches a search query (0.0 to 100.0).
    Ranks closest wording matches highest:
    - 100.0: Exact raw string match
    - 98.0:  Exact match ignoring honorific titles
    - 96.0:  Exact tokens match regardless of word ordering
    - 95.0:  Full phonetic phrase match
    - 88-96: Core substring match (scaled by coverage)
    - 80-95: All query tokens match teacher tokens (exact or phonetic)
    - 50-80: High fuzzy / sequence similarity
    """
    q_raw = query.strip()
    t_raw = teacher.strip()
    if not q_raw or not t_raw:
        return 0.0

    q_lower = q_raw.lower()
    t_lower = t_raw.lower()

    if q_lower == t_lower:
        return 100.0

    q_core = strip_titles(q_raw).lower()
    t_core = strip_titles(t_raw).lower()

    if not q_core or not t_core:
        return 0.0

    if q_core == t_core:
        return 98.0

    q_core_tokens = tokenize_name(q_core)
    t_core_tokens = tokenize_name(t_core)

    if not q_core_tokens or not t_core_tokens:
        return 0.0

    # Exact token set match regardless of word ordering (e.g. Qadeer Khaula vs Khaula Qadeer)
    if set(q_core_tokens) == set(t_core_tokens):
        return 96.0

    q_phonetic = [phonetic_word(w) for w in q_core_tokens]
    t_phonetic = [phonetic_word(w) for w in t_core_tokens]

    if " ".join(q_phonetic) == " ".join(t_phonetic):
        return 95.0

    # Substring match of core name
    if q_core in t_core and len(q_core) >= 3:
        coverage = len(q_core) / max(len(t_core), 1)
        return 88.0 + coverage * 8.0

    # Token-level matching
    matched_teacher_indices = set()
    total_token_similarity = 0.0

    for qw, qp in zip(q_core_tokens, q_phonetic):
        best_score = 0.0
        best_idx = -1
        for idx, (tw, tp) in enumerate(zip(t_core_tokens, t_phonetic)):
            if qw == tw:
                s = 1.0
            elif qp == tp:
                s = 0.95
            elif qw in tw or tw in qw:
                s = 0.85 * (min(len(qw), len(tw)) / max(len(qw), len(tw)))
            else:
                sim = difflib.SequenceMatcher(None, qw, tw).ratio()
                sim_p = difflib.SequenceMatcher(None, qp, tp).ratio()
                best_sim = max(sim, sim_p)
                s = best_sim if best_sim >= 0.8 else best_sim * 0.7
            if s > best_score:
                best_score = s
                best_idx = idx
        if best_idx != -1 and best_score >= 0.7:
            matched_teacher_indices.add(best_idx)
        total_token_similarity += best_score

    avg_token_sim = total_token_similarity / len(q_core_tokens) if q_core_tokens else 0.0

    all_matched = (len(matched_teacher_indices) == len(q_core_tokens)) and (avg_token_sim >= 0.75)
    if all_matched:
        ratio = len(q_core_tokens) / len(t_core_tokens)
        return 80.0 + avg_token_sim * 10.0 + ratio * 5.0

    core_seq_sim = difflib.SequenceMatcher(None, q_core, t_core).ratio()
    phonetic_seq_sim = difflib.SequenceMatcher(None, " ".join(q_phonetic), " ".join(t_phonetic)).ratio()
    best_seq = max(core_seq_sim, phonetic_seq_sim)

    if best_seq >= 0.7:
        return best_seq * 80.0

    if avg_token_sim >= 0.75 and len(matched_teacher_indices) > 0:
        return avg_token_sim * 70.0

    return 0.0


def find_matching_teachers(query: str, teachers: list[str]) -> list[tuple[str, float]]:
    """
    Search and enlist all teachers matching the query name.
    Ranked strictly from closest matching in wording to lowest score.
    Filters out noise and irrelevant matches.
    """
    q = query.strip()
    if not q or len(q) < 2:
        return []

    scored = []
    for t in teachers:
        if not t or t.strip().lower() == "unknown":
            continue
        sc = score_teacher_match(q, t)
        if sc >= 50.0:
            scored.append((t, sc))

    if not scored:
        return []

    # Sort primarily by score descending, secondarily by shorter name (closer match)
    scored.sort(key=lambda x: (x[1], -len(x[0])), reverse=True)

    top_score = scored[0][1]
    if top_score >= 85.0:
        cutoff = max(70.0, top_score - 20.0)
    else:
        cutoff = max(55.0, top_score - 15.0)

    return [(t, sc) for t, sc in scored if sc >= cutoff]


def is_teacher_match(target: Optional[str], candidate: Optional[str]) -> bool:
    """Accurately check if a target teacher matches a candidate paper teacher name."""
    if not target or not candidate:
        return False
    t_clean = target.strip().lower()
    c_clean = candidate.strip().lower()
    if not t_clean or not c_clean:
        return False
    if t_clean == c_clean:
        return True
    if strip_titles(target).lower() == strip_titles(candidate).lower():
        return True
    if score_teacher_match(target, candidate) >= 75.0:
        return True
    if t_clean in c_clean or c_clean in t_clean:
        return True
    return False


def format_match_badge(score: float) -> str:
    """Format human-readable match indicator for table display."""
    if score >= 97.0:
        return "[bold green]100% Closest Match[/]"
    elif score >= 90.0:
        return f"[bold green]{score:.0f}% Closest Match[/]"
    elif score >= 80.0:
        return f"[green]{score:.0f}% High Match[/]"
    elif score >= 70.0:
        return f"[yellow]{score:.0f}% Medium Match[/]"
    else:
        return f"[dim]{score:.0f}% Match[/]"


def enlist_matching_teachers_table(
    matches: list[tuple[str, float]],
    papers: list[dict],
    title: str = "Matching Teachers",
) -> None:
    """Enlist all matching teachers in a formatted table with paper counts & subjects."""
    table = Table(box=box.SIMPLE_HEAVY, border_style="blue", show_header=True, header_style="bold cyan")
    table.add_column("#",       style="dim",    width=4, justify="right")
    table.add_column("Teacher", style="white",  min_width=28)
    table.add_column("Wording Match", style="green", min_width=22)
    table.add_column("Papers",  style="yellow", width=8, justify="right")
    table.add_column("Subject(s) Taught", style="cyan", min_width=32)

    for i, (name, score) in enumerate(matches, 1):
        teacher_papers = [p for p in papers if is_teacher_match(name, p.get("teacher_name", ""))]
        subjects = sorted(set(p.get("course_title", "") for p in teacher_papers if p.get("course_title")))
        if subjects:
            subj_str = ", ".join(subjects[:2]) + (f" (+{len(subjects)-2} more)" if len(subjects) > 2 else "")
        else:
            subj_str = "[dim]None in current filter[/]"
        badge = format_match_badge(score)
        table.add_row(str(i), name, badge, str(len(teacher_papers)), subj_str)

    console.print(Align.center(table))


# ── Filtering ─────────────────────────────────────────────────────────────────

def filter_papers(
    papers: list[dict],
    subject: Optional[str] = None,
    teacher: Optional[str] = None,
    campus:  Optional[str] = None,
    exam_type: Optional[str] = None,
    category: Optional[str] = None,
) -> list[dict]:
    result = papers
    if subject:
        kw = subject.strip().lower()
        result = [
            p for p in result
            if kw in p.get("course_title", "").lower()
            or kw in p.get("acronym", "").lower()
            or kw in p.get("course_code", "").lower()
        ]
    if teacher:
        tkw = teacher.strip().lower()
        result = [
            p for p in result
            if is_teacher_match(teacher, p.get("teacher_name", ""))
            or tkw in p.get("teacher_name", "").lower()
        ]
    if campus:
        ckw = campus.strip().lower()
        result = [p for p in result if ckw in p.get("campus", "").lower()]
    if exam_type:
        ekw = exam_type.strip().lower()
        result = [p for p in result if ekw in p.get("exam_type", "").lower()]
    if category:
        catkw = category.strip().lower()
        result = [p for p in result if catkw in p.get("exam_category", "").lower()]
    return result


def build_filename(paper: dict) -> str:
    parts = [
        paper.get("acronym", "UNKNOWN"),
        paper.get("exam_type", "").replace(" ", "_"),
        paper.get("exam_category", ""),
        paper.get("batch", ""),
        paper.get("campus", "").replace(" ", "_"),
        f"V{paper.get('variant', '1')}",
    ]
    return safe_name("_".join(p for p in parts if p)) + ".pdf"


# ── Download ──────────────────────────────────────────────────────────────────

def _create_gdrive_session() -> requests.Session:
    """Create a clean session for Google Drive downloads."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    })
    return s


def is_valid_pdf(path: Path) -> bool:
    """Check if file exists, is at least 1KB, and starts with the PDF magic header."""
    try:
        if not path.is_file() or path.stat().st_size < 1024:
            return False
        with open(path, "rb") as f:
            header = f.read(5)
            return header.startswith(b"%PDF")
    except OSError:
        return False


def gdrive_download(file_id: str, dest_path: Path, progress: Progress, task_id) -> bool:
    session = _create_gdrive_session()

    endpoints = [
        ("https://docs.google.com/uc?export=download", {"id": file_id}),
        ("https://drive.usercontent.google.com/download", {"id": file_id, "export": "download"}),
        ("https://drive.google.com/uc?export=download", {"id": file_id}),
    ]

    resp = None
    for url, params in endpoints:
        try:
            req_params = dict(params)
            r = session.get(url, params=req_params, timeout=30, stream=True)
            if r.status_code != 200:
                continue

            content_type = r.headers.get("Content-Type", "")

            # If HTML is returned, check for virus warning or confirmation token
            if "text/html" in content_type:
                confirm_token = None
                for k, v in session.cookies.items():
                    if k.startswith("download_warning"):
                        confirm_token = v
                        break

                html_snippet = ""
                for chunk in r.iter_content(chunk_size=16384):
                    html_snippet += chunk.decode("utf-8", errors="ignore")
                    if len(html_snippet) > 65536:
                        break

                if not confirm_token:
                    m = re.search(r'confirm=([0-9A-Za-z_\-]+)', html_snippet)
                    if m:
                        confirm_token = m.group(1)

                m_action = re.search(r'action="([^"]+)"', html_snippet)
                m_uuid = re.search(r'name="uuid"\s+value="([^"]+)"', html_snippet) or re.search(r'uuid=([a-f0-9-]{36})', html_snippet)

                if confirm_token:
                    req_params["confirm"] = confirm_token
                elif m_uuid:
                    req_params["confirm"] = "t"
                    req_params["uuid"] = m_uuid.group(1)
                else:
                    req_params["confirm"] = "t"

                target_url = m_action.group(1).replace("&amp;", "&") if m_action and "http" in m_action.group(1) else url
                r = session.get(target_url, params=req_params, timeout=60, stream=True)

            if r.status_code == 200:
                resp = r
                break
        except (requests.RequestException, RuntimeError):
            continue

    if not resp:
        return False

    try:
        total = int(resp.headers.get("Content-Length", 0)) or None
        if total:
            progress.update(task_id, total=total)

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        verified = False
        bytes_written = 0

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                if not verified:
                    # CRITICAL: Verify this is an actual PDF file!
                    # Reject HTML documents or sign-in interstitials
                    if not chunk.startswith(b"%PDF"):
                        dest_path.unlink(missing_ok=True)
                        return False
                    verified = True
                f.write(chunk)
                bytes_written += len(chunk)
                progress.update(task_id, advance=len(chunk))

        if not verified or bytes_written < 1024:
            dest_path.unlink(missing_ok=True)
            return False

        return True

    except (requests.RequestException, OSError):
        dest_path.unlink(missing_ok=True)
        return False


def download_paper_file(paper: dict, dest_path: Path, progress: Progress, task_id) -> bool:
    """Download a past paper PDF via the server's official pipeline with GDrive fallback."""
    paper_id = paper.get("id")
    file_id  = paper.get("link", "").strip()

    # Method 1: Official server proxy pipeline (100% reliable for all catalogue papers)
    if paper_id:
        try:
            r_sess = SESSION.post(SET_SESSION_URL, json={"rowID": str(paper_id)}, timeout=20)
            if r_sess.status_code == 200:
                r_dl = SESSION.get(DOWNLOADER_PAGE, timeout=20)
                if r_dl.status_code == 200:
                    m = re.search(r'const\s+TOKEN\s*=\s*\"([^\"]+)\"', r_dl.text)
                    if m:
                        token = m.group(1)
                        resp = SESSION.get(f"{SERVE_PAPER_URL}?token={token}", stream=True, timeout=60)
                        if resp.status_code == 200:
                            total = int(resp.headers.get("Content-Length", 0)) or None
                            if total:
                                progress.update(task_id, total=total)

                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            verified = False
                            bytes_written = 0
                            with open(dest_path, "wb") as f:
                                for chunk in resp.iter_content(chunk_size=8192):
                                    if not chunk:
                                        continue
                                    if not verified:
                                        if not chunk.startswith(b"%PDF"):
                                            dest_path.unlink(missing_ok=True)
                                            break
                                        verified = True
                                    f.write(chunk)
                                    bytes_written += len(chunk)
                                    progress.update(task_id, advance=len(chunk))

                            if verified and bytes_written >= 1024:
                                return True
                            dest_path.unlink(missing_ok=True)
        except (requests.RequestException, OSError):
            dest_path.unlink(missing_ok=True)

    # Method 2: Google Drive fallback
    if file_id:
        return gdrive_download(file_id, dest_path, progress, task_id)

    return False


def download_papers(
    papers: list[dict],
    output_dir: Path,
    target_teacher: Optional[str] = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    teacher_routed = 0

    success = skipped = failed = 0

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}[/]"),
        BarColumn(bar_width=30),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    )

    console.print()
    console.print(Rule("[bold blue]Downloading Papers[/]"))

    with progress:
        for i, paper in enumerate(papers, 1):
            file_id  = paper.get("link", "").strip()
            filename = build_filename(paper)

            # Route to teacher subfolder if it matches the target teacher, else subject root
            is_target_teacher = False
            if target_teacher and is_teacher_match(target_teacher, paper.get("teacher_name", "")):
                is_target_teacher = True
                paper_dir = output_dir / safe_name(target_teacher)
                teacher_routed += 1
            else:
                paper_dir = output_dir

            paper_dir.mkdir(parents=True, exist_ok=True)
            dest = paper_dir / filename

            folder_badge = f" [green]-> {safe_name(target_teacher)}/[/]" if is_target_teacher else ""

            label = (
                f"[{i}/{len(papers)}] "
                f"[cyan]{paper.get('acronym','?')}[/] "
                f"[dim]|[/] {paper.get('exam_type','?')} "
                f"[dim]|[/] {paper.get('exam_category','?')} "
                f"[dim]|[/] {paper.get('batch','?')}"
                f"{folder_badge}"
            )
            console.print(f"  {label}")

            if not file_id and not paper.get("id"):
                console.print("    [yellow]No Paper ID - skipping.[/]")
                skipped += 1
                continue

            if dest.exists():
                if is_valid_pdf(dest):
                    console.print(f"    [dim]Already exists - skipping.[/]")
                    skipped += 1
                    continue
                else:
                    # Remove corrupt/HTML file from earlier run and re-download
                    dest.unlink(missing_ok=True)

            task_id = progress.add_task(f"↓ {filename[:50]}", total=None)
            ok = download_paper_file(paper, dest, progress, task_id)
            progress.remove_task(task_id)

            if ok:
                size_kb = dest.stat().st_size / 1024
                console.print(f"    [green]{filename}  ({size_kb:.0f} KB)[/]")
                success += 1
            else:
                console.print("    [red]Failed (file restricted or invalid).[/]")
                failed += 1

            time.sleep(0.3)

    console.print()
    summary = Table(box=box.ROUNDED, show_header=False, border_style="blue")
    summary.add_column(style="bold", justify="right")
    summary.add_column()
    summary.add_row("[green]Downloaded[/]", str(success))
    summary.add_row("[dim]Skipped[/]",     str(skipped))
    summary.add_row("[red]Failed[/]",      str(failed))
    summary.add_row("[bold]Saved to[/]",   str(output_dir))
    if target_teacher:
        if teacher_routed > 0:
            summary.add_row("[bold]Subfolder[/]",  str(output_dir / safe_name(target_teacher)))
        else:
            summary.add_row("[dim]Subfolder[/]",  f"[dim](no papers matched '{target_teacher}')[/]")
    console.print(Align.center(summary))
    console.print()


# ── Screens ───────────────────────────────────────────────────────────────────

def screen_browse_subjects(papers: list[dict]) -> Optional[str]:
    """Let user pick a subject from a paginated table. Returns chosen subject query string."""
    subjects: dict[str, dict] = {}
    for p in papers:
        key = p.get("acronym", "")
        if key and key not in subjects:
            subjects[key] = {
                "title": p.get("course_title", "?"),
                "code":  p.get("course_code", "?"),
                "acronym": key,
            }
    sorted_subjects = sorted(subjects.values(), key=lambda x: x["title"])
    PAGE = 20

    page = 0
    total_pages = (len(sorted_subjects) - 1) // PAGE + 1

    while True:
        print_banner()
        console.print(Rule(f"[bold yellow]Browse Subjects  [dim](page {page+1}/{total_pages})[/]"))
        console.print()

        table = Table(box=box.SIMPLE_HEAVY, border_style="blue", show_header=True, header_style="bold cyan")
        table.add_column("#",           style="dim",       width=4,  justify="right")
        table.add_column("Subject",     style="white",     min_width=40)
        table.add_column("Code",        style="cyan",      width=12)
        table.add_column("Acronym",     style="yellow",    width=8)

        start = page * PAGE
        chunk = sorted_subjects[start: start + PAGE]
        for i, s in enumerate(chunk, start + 1):
            table.add_row(str(i), s["title"], s["code"], s["acronym"])

        console.print(Align.center(table))
        console.print()

        nav_items = [("1-{max}", "enter row number to select"), ("n", "next page"), ("p", "prev page"), ("b", "back")]
        nav_items[0] = (f"1-{len(chunk)}", "enter row number to select")
        print_menu_panel("Navigation", nav_items)

        choice = Prompt.ask("\n  [bold cyan]>[/]").strip().lower()

        if choice == "n":
            if page < total_pages - 1:
                page += 1
        elif choice == "p":
            if page > 0:
                page -= 1
        elif choice == "b":
            return None
        elif choice.isdigit():
            idx = int(choice) - 1
            global_idx = page * PAGE + idx
            if 0 <= global_idx < len(sorted_subjects):
                return sorted_subjects[global_idx]["acronym"]
            else:
                console.print("  [red]Invalid selection.[/]")
                time.sleep(1)


def screen_search(papers: list[dict]) -> Optional[str]:
    """Free-text search. Returns a query string or None."""
    print_banner()
    console.print(Rule("[bold yellow]Search Papers[/]"))
    console.print()
    console.print("  Enter a subject name, course code, acronym, or keyword.")
    console.print("  [dim]Press Enter with no input to cancel.[/]\n")
    query = Prompt.ask("  [bold cyan]Search[/]").strip()
    return query if query else None


def screen_select_teacher(papers: list[dict], subject_query: str) -> Optional[str]:
    """Show teachers for a subject and let user pick one, search by name, or choose all."""
    filtered = filter_papers(papers, subject_query)
    teachers = sorted(set(p.get("teacher_name", "") for p in filtered if p.get("teacher_name")))

    if not teachers:
        console.print("  [yellow]No teachers found for this subject.[/]")
        time.sleep(1.5)
        return None

    # Show the resolved subject name
    if filtered:
        titles = [p.get("course_title", subject_query) for p in filtered]
        course_title = max(set(titles), key=titles.count)
    else:
        course_title = subject_query

    while True:
        print_banner()
        console.print(Rule(f"[bold yellow]{course_title}[/]"))
        console.print()

        table = Table(box=box.SIMPLE_HEAVY, border_style="blue", show_header=True, header_style="bold cyan")
        table.add_column("#",       style="dim",    width=4, justify="right")
        table.add_column("Teacher", style="white",  min_width=30)
        table.add_column("Papers",  style="yellow", width=8, justify="right")

        for i, t in enumerate(teachers, 1):
            count = sum(1 for p in filtered if p.get("teacher_name") == t)
            table.add_row(str(i), t, str(count))

        console.print(Align.center(table))
        console.print()

        total_count = len(filtered)
        print_menu_panel("Options", [
            ("0",                 f"Download ALL {total_count} papers for this subject"),
            (f"1-{len(teachers)}", "pick a specific teacher"),
            ("s",                 "search teacher by name / keyword"),
            ("b",                 "back"),
        ])

        choice = Prompt.ask("\n  [bold cyan]>[/]").strip()
        choice_lower = choice.lower()

        if choice_lower == "b":
            return "__back__"
        elif choice == "0":
            return None   # None = all teachers
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(teachers):
                return teachers[idx]
            console.print("  [red]Invalid number.[/]")
            time.sleep(1)
        else:
            # Query either from 's' prompt or entered directly as text
            if choice_lower == "s":
                search_q = Prompt.ask("  [bold cyan]Search teacher name[/]").strip()
            else:
                search_q = choice

            if not search_q:
                continue

            matches = find_matching_teachers(search_q, teachers)
            if not matches:
                console.print(f"  [yellow]No teacher matching '{search_q}' found in this subject.[/]")
                time.sleep(1.5)
                continue

            if len(matches) == 1:
                matched_name, sc = matches[0]
                badge = format_match_badge(sc)
                if Confirm.ask(f"  Select closest matching teacher [bold green]{matched_name}[/] ({badge})?", default=True):
                    return matched_name
            else:
                # Enlist all matching teachers with closest matching wording first!
                print_banner()
                console.print(Rule(f"[bold yellow]Matching Teachers for '{search_q}'[/]"))
                console.print()
                enlist_matching_teachers_table(matches, filtered, title=f"Matching Teachers for '{search_q}'")
                console.print()
                print_menu_panel("Selection", [
                    (f"1-{len(matches)}", "pick matching teacher"),
                    ("c", "cancel (return to subject teachers list)"),
                ])
                while True:
                    sub_c = Prompt.ask("\n  [bold cyan]>[/]").strip().lower()
                    if sub_c == "c":
                        break
                    elif sub_c.isdigit():
                        s_idx = int(sub_c) - 1
                        if 0 <= s_idx < len(matches):
                            return matches[s_idx][0]
                        console.print("  [red]Invalid number.[/]")
                    else:
                        console.print("  [red]Please enter a number or 'c'.[/]")


def screen_select_campus(
    papers: list[dict],
    subject_query: str,
    teacher: Optional[str] = None,
) -> Optional[str]:
    """Show campuses for the filtered set. Returns campus name, None (all), or '__back__'."""
    filtered = filter_papers(papers, subject=subject_query)
    campuses = sorted(set(p.get("campus", "") for p in filtered if p.get("campus")))

    # Only one campus - skip the screen entirely
    if len(campuses) <= 1:
        return None

    print_banner()
    console.print(Rule("[bold yellow]Select Campus[/]"))
    console.print()

    table = Table(box=box.SIMPLE_HEAVY, border_style="blue", show_header=True, header_style="bold cyan")
    table.add_column("#",      style="dim",    width=4, justify="right")
    table.add_column("Campus", style="white",  min_width=30)
    table.add_column("Total Papers", style="yellow", width=14, justify="right")
    if teacher:
        table.add_column(f"{teacher[:18]} Papers", style="green", width=22, justify="right")

    for i, c in enumerate(campuses, 1):
        count = sum(1 for p in filtered if p.get("campus") == c)
        if teacher:
            t_cnt = sum(1 for p in filtered if p.get("campus") == c and is_teacher_match(teacher, p.get("teacher_name", "")))
            table.add_row(str(i), c, str(count), str(t_cnt))
        else:
            table.add_row(str(i), c, str(count))
    console.print(Align.center(table))
    console.print()

    print_menu_panel("Options", [
        ("0",                  f"All campuses ({len(filtered)} papers)"),
        (f"1-{len(campuses)}", "pick a specific campus"),
        ("b",                  "back"),
    ])

    while True:
        choice = Prompt.ask("\n  [bold cyan]>[/]").strip().lower()
        if choice == "b":
            return "__back__"
        elif choice == "0":
            return None
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(campuses):
                return campuses[idx]
            console.print("  [red]Invalid number.[/]")
        else:
            console.print("  [red]Please enter a number or 'b'.[/]")


def screen_select_exam_type(
    papers: list[dict],
    subject_query: str,
    campus: Optional[str] = None,
    teacher: Optional[str] = None,
) -> Optional[str]:
    """Show exam types (Mid Term, Final Term, etc.) for the subject. Returns type name, None (all), or '__back__'."""
    filtered = filter_papers(papers, subject=subject_query, campus=campus)
    types = sorted(set(p.get("exam_type", "") for p in filtered if p.get("exam_type")))

    # If only one type (or none), skip selection
    if len(types) <= 1:
        return None

    print_banner()
    console.print(Rule("[bold yellow]Select Exam Type[/]"))
    console.print()

    table = Table(box=box.SIMPLE_HEAVY, border_style="blue", show_header=True, header_style="bold cyan")
    table.add_column("#",         style="dim",    width=4, justify="right")
    table.add_column("Exam Type", style="white",  min_width=25)
    table.add_column("Total Papers", style="yellow", width=14, justify="right")
    if teacher:
        table.add_column(f"{teacher[:18]} Papers", style="green", width=22, justify="right")

    for i, t in enumerate(types, 1):
        count = sum(1 for p in filtered if p.get("exam_type") == t)
        if teacher:
            t_cnt = sum(1 for p in filtered if p.get("exam_type") == t and is_teacher_match(teacher, p.get("teacher_name", "")))
            table.add_row(str(i), t, str(count), str(t_cnt))
        else:
            table.add_row(str(i), t, str(count))
    console.print(Align.center(table))
    console.print()

    print_menu_panel("Options", [
        ("0",               f"All exam types ({len(filtered)} papers)"),
        (f"1-{len(types)}", "pick a specific exam type"),
        ("b",               "back"),
    ])

    while True:
        choice = Prompt.ask("\n  [bold cyan]>[/]").strip().lower()
        if choice == "b":
            return "__back__"
        elif choice == "0":
            return None
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(types):
                chosen_type = types[idx]
                if teacher:
                    t_cnt = sum(1 for p in filtered if p.get("exam_type") == chosen_type and is_teacher_match(teacher, p.get("teacher_name", "")))
                    if t_cnt == 0:
                        console.print(f"  [yellow]Notice: {teacher} has 0 papers in '{chosen_type}'.[/]")
                        if not Confirm.ask("  Continue anyway?", default=False):
                            continue
                return chosen_type
            console.print("  [red]Invalid number.[/]")
        else:
            console.print("  [red]Please enter a number or 'b'.[/]")


def screen_select_category(
    papers: list[dict],
    subject_query: str,
    campus: Optional[str] = None,
    exam_type: Optional[str] = None,
    teacher: Optional[str] = None,
) -> Optional[str]:
    """Show categories (Theory, Lab) for the subject. Returns category name, None (all), or '__back__'."""
    filtered = filter_papers(papers, subject=subject_query, campus=campus, exam_type=exam_type)
    cats = sorted(set(p.get("exam_category", "") for p in filtered if p.get("exam_category")))

    # If only one category (or none), skip selection
    if len(cats) <= 1:
        return None

    print_banner()
    console.print(Rule("[bold yellow]Select Category[/]"))
    console.print()

    table = Table(box=box.SIMPLE_HEAVY, border_style="blue", show_header=True, header_style="bold cyan")
    table.add_column("#",        style="dim",    width=4, justify="right")
    table.add_column("Category", style="white",  min_width=25)
    table.add_column("Total Papers", style="yellow", width=14, justify="right")
    if teacher:
        table.add_column(f"{teacher[:18]} Papers", style="green", width=22, justify="right")

    for i, c in enumerate(cats, 1):
        count = sum(1 for p in filtered if p.get("exam_category") == c)
        if teacher:
            t_cnt = sum(1 for p in filtered if p.get("exam_category") == c and is_teacher_match(teacher, p.get("teacher_name", "")))
            table.add_row(str(i), c, str(count), str(t_cnt))
        else:
            table.add_row(str(i), c, str(count))
    console.print(Align.center(table))
    console.print()

    print_menu_panel("Options", [
        ("0",              f"Both Theory & Lab ({len(filtered)} papers)"),
        (f"1-{len(cats)}", "pick a specific category"),
        ("b",              "back"),
    ])

    while True:
        choice = Prompt.ask("\n  [bold cyan]>[/]").strip().lower()
        if choice == "b":
            return "__back__"
        elif choice == "0":
            return None
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(cats):
                return cats[idx]
            console.print("  [red]Invalid number.[/]")
        else:
            console.print("  [red]Please enter a number or 'b'.[/]")


def confirm_and_download(
    papers: list[dict],
    subject_query: str,
    teacher: Optional[str] = None,
    campus: Optional[str] = None,
    exam_type: Optional[str] = None,
    category: Optional[str] = None,
    output_base: Path = OUTPUT_BASE,
):
    """Show confirmation screen then start download."""
    # Download papers of this subject matching chosen filters (campus, exam_type, category).
    # If a teacher is specified, their papers go into a subfolder, while the rest go into the subject root.
    subject_papers = filter_papers(
        papers,
        subject=subject_query,
        campus=campus,
        exam_type=exam_type,
        category=category,
    )

    if not subject_papers:
        console.print("\n  [red]No papers matched this selection.[/]")
        time.sleep(2)
        return

    # Resolve display names
    titles       = [p.get("course_title", subject_query) for p in subject_papers]
    course_title = max(set(titles), key=titles.count)

    output_dir = output_base / safe_name(course_title)

    teacher_papers_count = 0
    if teacher:
        teacher_papers = [p for p in subject_papers if is_teacher_match(teacher, p.get("teacher_name", ""))]
        other_papers   = [p for p in subject_papers if not is_teacher_match(teacher, p.get("teacher_name", ""))]
        teacher_papers_count = len(teacher_papers)
        # Put teacher papers first in the list
        ordered_papers = teacher_papers + other_papers
    else:
        ordered_papers = subject_papers

    print_banner()
    console.print(Rule("[bold yellow]Confirm Download[/]"))
    console.print()

    info = Table(box=box.ROUNDED, show_header=False, border_style="cyan")
    info.add_column(style="bold dim", justify="right", width=16)
    info.add_column(style="white")
    info.add_row("Subject",   course_title)
    if campus:
        info.add_row("Campus",    campus)
    if exam_type:
        info.add_row("Exam Type", exam_type)
    if category:
        info.add_row("Category",  category)
    if teacher:
        if teacher_papers_count > 0:
            info.add_row("Teacher", f"{teacher} (saved in subfolder)")
            other_cnt = len(subject_papers) - teacher_papers_count
            info.add_row("Papers", f"{len(subject_papers)} file(s) ({teacher_papers_count} by {teacher}, {other_cnt} other)")
        else:
            info.add_row("Teacher", f"{teacher} (0 matching papers with current filters)")
            info.add_row("Papers", f"{len(subject_papers)} file(s) (all by other instructors)")
    else:
        info.add_row("Papers", f"{len(subject_papers)} file(s)")
    info.add_row("Save to",   str(output_dir))
    if teacher and teacher_papers_count > 0:
        info.add_row("Subfolder", str(output_dir / safe_name(teacher)))
    console.print(Align.center(info))
    console.print()

    # Paper preview table
    preview = Table(box=box.SIMPLE, border_style="dim", show_header=True, header_style="bold cyan")
    preview.add_column("Exam Type",     style="white",  min_width=16)
    preview.add_column("Category",      style="cyan",   width=10)
    preview.add_column("Batch",         style="yellow", width=7)
    preview.add_column("Campus",        style="dim",    min_width=14)
    preview.add_column("Teacher",       style="dim",    min_width=20)
    preview.add_column("Folder",        style="green",  min_width=15)

    for p in ordered_papers[:15]:
        is_t = teacher and is_teacher_match(teacher, p.get("teacher_name", ""))
        folder_col = f"[bold green]{safe_name(teacher)}/[/]" if is_t else "[dim](subject root)[/]"
        preview.add_row(
            p.get("exam_type", "?"),
            p.get("exam_category", "?"),
            p.get("batch", "?"),
            p.get("campus", "?"),
            p.get("teacher_name", "?"),
            folder_col,
        )
    if len(ordered_papers) > 15:
        preview.add_row(f"[dim]… and {len(ordered_papers)-15} more[/]", "", "", "", "", "")
    console.print(Align.center(preview))
    console.print()

    if not Confirm.ask("  [bold cyan]Start download?[/]", default=True):
        console.print("  [yellow]Cancelled.[/]")
        time.sleep(1)
        return

    download_papers(ordered_papers, output_dir, target_teacher=teacher)

    Prompt.ask("\n  [dim]Press Enter to return to menu[/]")


def screen_search_teachers(papers: list[dict], initial_query: Optional[str] = None) -> None:
    """Search for teachers across all papers and enlist all matching teachers (closest matching in wording first)."""
    all_teachers = sorted(list(set(p.get("teacher_name", "").strip() for p in papers if p.get("teacher_name"))))
    query = initial_query

    while True:
        if not query:
            print_banner()
            console.print(Rule("[bold yellow]Search Teachers[/]"))
            console.print()
            console.print("  Enter teacher name or keyword (e.g. Khaula, Zeeshan, Wasim Sajid):")
            console.print("  [dim]Press Enter with no input to return to menu.[/]\n")
            query = Prompt.ask("  [bold cyan]Teacher Name[/]").strip()
            if not query:
                return

        matches = find_matching_teachers(query, all_teachers)

        print_banner()
        console.print(Rule(f"[bold yellow]Teacher Search: '{query}'[/]"))
        console.print()

        if not matches:
            console.print(f"  [yellow]No teachers found matching '{query}'.[/]")
            console.print("  [dim]Tip: Try searching by first name, last name, or without title prefixes.[/]\n")
            print_menu_panel("Options", [
                ("s", "search another teacher name"),
                ("a", "browse all teachers"),
                ("b", "back to menu"),
            ])
            choice = Prompt.ask("\n  [bold cyan]>[/]").strip().lower()
            if choice == "s":
                query = None
                continue
            elif choice == "a":
                screen_list_all_teachers(papers)
                return
            else:
                return

        # Enlist all matching teachers with closest matching in wording first!
        enlist_matching_teachers_table(matches, papers, title=f"Matching Teachers for '{query}' ({len(matches)} found)")
        console.print()

        print_menu_panel("Options", [
            (f"1-{len(matches)}", "select teacher to view & download papers"),
            ("s", "search another teacher name"),
            ("a", "browse all teachers"),
            ("b", "back to menu"),
        ])

        while True:
            choice = Prompt.ask("\n  [bold cyan]>[/]").strip().lower()
            if choice == "b":
                return
            elif choice == "s":
                query = None
                break
            elif choice == "a":
                screen_list_all_teachers(papers)
                return
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(matches):
                    selected_teacher = matches[idx][0]
                    teacher_papers = [p for p in papers if is_teacher_match(selected_teacher, p.get("teacher_name", ""))]
                    _download_by_teacher(teacher_papers, selected_teacher)
                    return
                console.print("  [red]Invalid number.[/]")
            else:
                query = choice
                break


def screen_list_all_teachers(papers: list[dict]):
    """Browse all teachers across all subjects."""
    teachers: dict[str, int] = {}
    for p in papers:
        t = p.get("teacher_name", "")
        if t and t.strip().lower() != "unknown":
            teachers[t] = teachers.get(t, 0) + 1

    sorted_teachers = sorted(teachers.items(), key=lambda x: x[0])
    PAGE = 25
    page = 0
    total_pages = (len(sorted_teachers) - 1) // PAGE + 1

    while True:
        print_banner()
        console.print(Rule(f"[bold yellow]All Teachers  [dim](page {page+1}/{total_pages})[/]"))
        console.print()

        table = Table(box=box.SIMPLE_HEAVY, border_style="blue", show_header=True, header_style="bold cyan")
        table.add_column("#",       style="dim",    width=5,  justify="right")
        table.add_column("Teacher", style="white",  min_width=35)
        table.add_column("Papers",  style="yellow", width=8,  justify="right")

        start  = page * PAGE
        chunk  = sorted_teachers[start: start + PAGE]
        for i, (name, count) in enumerate(chunk, start + 1):
            table.add_row(str(i), name, str(count))

        console.print(Align.center(table))
        console.print()

        print_menu_panel("Navigation", [
            (f"1-{len(chunk)}", "select teacher to browse their papers"),
            ("s", "search teacher by name (closest wording match)"),
            ("n", "next page"),
            ("p", "prev page"),
            ("b", "back to menu"),
        ])

        choice = Prompt.ask("\n  [bold cyan]>[/]").strip()
        choice_lower = choice.lower()
        if choice_lower == "n":
            if page < total_pages - 1:
                page += 1
        elif choice_lower == "p":
            if page > 0:
                page -= 1
        elif choice_lower == "b":
            return
        elif choice_lower == "s":
            screen_search_teachers(papers)
            return
        elif choice.isdigit():
            idx = int(choice) - 1
            global_idx = page * PAGE + idx
            if 0 <= global_idx < len(sorted_teachers):
                teacher_name  = sorted_teachers[global_idx][0]
                teacher_papers = [p for p in papers if is_teacher_match(teacher_name, p.get("teacher_name", ""))]
                _download_by_teacher(teacher_papers, teacher_name)
                return
            console.print("  [red]Invalid selection.[/]")
            time.sleep(1)
        else:
            # Treat direct string entry as a search query
            screen_search_teachers(papers, initial_query=choice)
            return


def screen_teacher_hub(papers: list[dict]) -> None:
    """Hub screen for searching and browsing teachers."""
    while True:
        print_banner()
        console.print(Rule("[bold yellow]Search & Browse Teachers[/]"))
        console.print()
        console.print("  Type a teacher's name (e.g. Khaula, Zeeshan, Wasim) to search,")
        console.print("  or choose an option below:\n")

        print_menu_panel("Teacher Directory", [
            ("1", "Search Teacher by Name (enlists closest wording matches)"),
            ("2", "Browse All Teachers Alphabetically (page by page)"),
            ("b", "Back to Main Menu"),
        ])

        choice = Prompt.ask("\n  [bold cyan]>[/]").strip()
        choice_lower = choice.lower()
        if choice_lower in ("b", "q"):
            return
        elif choice == "1":
            screen_search_teachers(papers)
            return
        elif choice == "2":
            screen_list_all_teachers(papers)
            return
        elif choice:
            # If user directly typed a teacher name, search it immediately!
            screen_search_teachers(papers, initial_query=choice)
            return


def screen_direct_download(papers: list[dict]) -> None:
    """Prompt for subject, optional teacher, optional campus, exam type & category, then download."""
    print_banner()
    console.print(Rule("[bold yellow]Direct Download[/]"))
    console.print()
    console.print("  Enter a subject name, acronym, or course code.")
    console.print("  [dim]Leave teacher / filters blank to include all.[/]\n")

    subject = Prompt.ask("  [bold cyan]Subject[/]").strip()
    if not subject:
        console.print("  [yellow]No subject entered. Returning to menu.[/]")
        time.sleep(1)
        return

    subject_papers_all = filter_papers(papers, subject=subject)
    if not subject_papers_all:
        print_banner()
        console.print(f"\n  [red]No papers found for subject:[/] [bold]{subject}[/]")
        console.print("  [dim]Try a different subject name, acronym, or course code.[/]\n")
        Prompt.ask("  [dim]Press Enter to continue[/]")
        return

    titles = [p.get("course_title", subject) for p in subject_papers_all]
    course_title = max(set(titles), key=titles.count)

    teacher_input = Prompt.ask(
        "\n  [bold cyan]Teacher [dim](optional - press Enter to skip)[/][bold cyan][/]"
    ).strip()

    teacher = None
    if teacher_input:
        subject_teachers = sorted(list(set(p.get("teacher_name", "").strip() for p in subject_papers_all if p.get("teacher_name"))))
        matches = find_matching_teachers(teacher_input, subject_teachers)

        if matches:
            if len(matches) == 1:
                closest_name, score = matches[0]
                badge = format_match_badge(score)
                cnt = sum(1 for p in subject_papers_all if is_teacher_match(closest_name, p.get("teacher_name", "")))
                console.print(f"\n  Found matching teacher: [bold green]{closest_name}[/] ({badge}, {cnt} paper(s))")
                if Confirm.ask("  Use this teacher?", default=True):
                    teacher = closest_name
                else:
                    teacher = teacher_input
            else:
                print_banner()
                console.print(Rule(f"[bold yellow]Matching Teachers for '{teacher_input}' in {course_title}[/]"))
                console.print()
                enlist_matching_teachers_table(matches, subject_papers_all, title="Matching Teachers in Subject")
                console.print()
                print_menu_panel("Selection", [
                    (f"1-{len(matches)}", "pick matching teacher"),
                    ("0", f"keep raw term '{teacher_input}'"),
                    ("s", "skip teacher filter"),
                ])
                while True:
                    t_choice = Prompt.ask("\n  [bold cyan]>[/]").strip().lower()
                    if t_choice == "s":
                        teacher = None
                        break
                    elif t_choice == "0":
                        teacher = teacher_input
                        break
                    elif t_choice.isdigit():
                        t_idx = int(t_choice) - 1
                        if 0 <= t_idx < len(matches):
                            teacher = matches[t_idx][0]
                            break
                        console.print("  [red]Invalid number.[/]")
                    else:
                        console.print("  [red]Please enter a valid option.[/]")
        else:
            # Check across entire catalogue
            all_teachers = sorted(list(set(p.get("teacher_name", "").strip() for p in papers if p.get("teacher_name"))))
            cat_matches = find_matching_teachers(teacher_input, all_teachers)
            if cat_matches:
                print_banner()
                console.print(f"\n  [yellow]Notice: '{teacher_input}' does not have papers in '{course_title}'.[/]")
                console.print("  However, matching teachers were found in other subjects:\n")
                enlist_matching_teachers_table(cat_matches[:5], papers, title="Matching Teachers in Other Subjects")
                console.print()
                print_menu_panel("Options", [
                    ("1", f"keep '{teacher_input}' anyway (will download 0 teacher papers)"),
                    ("2", "skip teacher filter"),
                ])
                opt = Prompt.ask("\n  [bold cyan]>[/]").strip().lower()
                if opt == "1":
                    teacher = teacher_input
                else:
                    teacher = None
            else:
                console.print(f"\n  [yellow]No teacher matching '{teacher_input}' found in catalogue.[/]")
                if Confirm.ask(f"  Keep '{teacher_input}' as raw filter anyway?", default=False):
                    teacher = teacher_input
                else:
                    teacher = None

        if teacher:
            t_papers = [p for p in subject_papers_all if is_teacher_match(teacher, p.get("teacher_name", ""))]
            if t_papers:
                print_banner()
                console.print(Rule(f"[bold yellow]{teacher} in {course_title}[/]"))
                console.print()
                console.print(f"  Found [bold green]{len(t_papers)} paper(s)[/] by [white]{teacher}[/] for [cyan]{course_title}[/]:\n")
                for p in t_papers:
                    console.print(f"   • [yellow]{p.get('exam_type','?')}[/] [cyan]{p.get('exam_category','?')}[/] ({p.get('batch','?')}) - [dim]{p.get('campus','?')}[/]")
                console.print()
                print_menu_panel("Download Scope", [
                    ("1", f"Download ONLY {teacher}'s paper(s) ({len(t_papers)} file(s)) [Default]"),
                    ("2", f"Download {teacher}'s paper(s) + other instructors' papers for {course_title}"),
                ])
                scope = Prompt.ask("  [bold cyan]Choose scope[/]", default="1").strip()
                if scope == "1":
                    confirm_and_download(
                        papers,
                        subject,
                        teacher=teacher,
                        only_teacher=True,
                        output_base=OUTPUT_BASE,
                    )
                    return

    # Campus selection
    campus = screen_select_campus(papers, subject, teacher=teacher)
    if campus == "__back__":
        return

    # Exam type selection (Mid Term / Final Term / etc.)
    exam_type = screen_select_exam_type(papers, subject, campus=campus, teacher=teacher)
    if exam_type == "__back__":
        return

    # Category selection (Theory / Lab)
    category = screen_select_category(papers, subject, campus=campus, exam_type=exam_type, teacher=teacher)
    if category == "__back__":
        return

    confirm_and_download(
        papers,
        subject,
        teacher=teacher,
        campus=campus,
        exam_type=exam_type,
        category=category,
        output_base=OUTPUT_BASE,
    )


def _download_by_teacher(teacher_papers: list[dict], teacher_name: str):
    """Download all papers by a specific teacher across any subject."""
    if not teacher_papers:
        console.print("  [yellow]No papers found.[/]")
        time.sleep(1.5)
        return

    print_banner()
    console.print(Rule(f"[bold yellow]{teacher_name}[/]"))
    console.print()

    subjects = sorted(set(p.get("course_title", "?") for p in teacher_papers))

    info = Table(box=box.ROUNDED, show_header=False, border_style="cyan")
    info.add_column(style="bold dim", justify="right", width=14)
    info.add_column(style="white")
    info.add_row("Teacher", teacher_name)
    info.add_row("Total Papers", str(len(teacher_papers)))
    info.add_row("Subjects", ", ".join(subjects))
    info.add_row("Save to", str(OUTPUT_BASE / safe_name(teacher_name)))
    console.print(Align.center(info))
    console.print()

    # Preview table
    preview = Table(box=box.SIMPLE, border_style="dim", show_header=True, header_style="bold cyan")
    preview.add_column("Subject",       style="white",  min_width=24)
    preview.add_column("Exam Type",     style="cyan",   min_width=12)
    preview.add_column("Category",      style="yellow", width=10)
    preview.add_column("Batch",         style="dim",    width=8)
    preview.add_column("Campus",        style="dim",    min_width=14)

    for p in teacher_papers[:15]:
        preview.add_row(
            p.get("course_title", "?"),
            p.get("exam_type", "?"),
            p.get("exam_category", "?"),
            p.get("batch", "?"),
            p.get("campus", "?"),
        )
    if len(teacher_papers) > 15:
        preview.add_row(f"[dim]… and {len(teacher_papers)-15} more[/]", "", "", "", "")
    console.print(Align.center(preview))
    console.print()

    if not Confirm.ask("  [bold cyan]Start download?[/]", default=True):
        console.print("  [yellow]Cancelled.[/]")
        time.sleep(1)
        return

    output_dir = OUTPUT_BASE / safe_name(teacher_name)
    download_papers(teacher_papers, output_dir)
    Prompt.ask("\n  [dim]Press Enter to return to menu[/]")


# ── Main Menu ─────────────────────────────────────────────────────────────────

def main():
    papers = None  # lazy load

    while True:
        print_banner()

        # Show cache status
        cached = load_cache()
        cache_status = (
            "[green]●  Catalogue cached[/]" if cached
            else "[yellow]○  No cache - will fetch on first use[/]"
        )
        console.print(Align.center(Text.from_markup(cache_status)))
        console.print()

        print_menu_panel("Main Menu", [
            ("1", "Browse & Download by Subject"),
            ("2", "Search by Keyword (Subject or Teacher)"),
            ("3", "Search & Browse Teachers"),
            ("4", "Refresh Catalogue"),
            ("5", "Direct Download - type subject, optional teacher & filters"),
            ("q", "Quit"),
        ])

        choice = Prompt.ask("\n  [bold cyan]>[/]").strip().lower()

        # Lazy load papers on first actual use
        if choice in ("1", "2", "3", "5") and papers is None:
            papers = fetch_all_papers()

        if choice == "1":
            while True:
                subject_query = screen_browse_subjects(papers)
                if subject_query is None:
                    break
                teacher_result = screen_select_teacher(papers, subject_query)
                if teacher_result == "__back__":
                    continue
                campus_result = screen_select_campus(papers, subject_query, teacher=teacher_result)
                if campus_result == "__back__":
                    continue
                exam_type_result = screen_select_exam_type(papers, subject_query, campus=campus_result, teacher=teacher_result)
                if exam_type_result == "__back__":
                    continue
                category_result = screen_select_category(
                    papers, subject_query, campus=campus_result, exam_type=exam_type_result, teacher=teacher_result
                )
                if category_result == "__back__":
                    continue
                confirm_and_download(
                    papers,
                    subject_query,
                    teacher=teacher_result,     # None = all teachers
                    campus=campus_result,       # None = all campuses
                    exam_type=exam_type_result, # None = all types
                    category=category_result,   # None = both Theory & Lab
                    output_base=OUTPUT_BASE,
                )
                break

        elif choice == "2":
            query = screen_search(papers)
            if query:
                subject_results = filter_papers(papers, subject=query)
                all_teachers = sorted(list(set(p.get("teacher_name", "").strip() for p in papers if p.get("teacher_name"))))
                teacher_matches = find_matching_teachers(query, all_teachers)

                if not subject_results and not teacher_matches:
                    print_banner()
                    console.print(f"\n  [red]No papers or teachers found for:[/] [bold]{query}[/]")
                    console.print("  [dim]Try a different keyword, course code, acronym, or teacher name.[/]\n")
                    Prompt.ask("  [dim]Press Enter to continue[/]")
                elif not subject_results and teacher_matches:
                    # User searched for a teacher! Enlist matching teachers directly
                    print_banner()
                    console.print(Rule(f"[bold yellow]Teachers Matching '{query}'[/]"))
                    console.print()
                    enlist_matching_teachers_table(teacher_matches, papers, title=f"Matching Teachers for '{query}'")
                    console.print()
                    print_menu_panel("Options", [
                        (f"1-{len(teacher_matches)}", "select teacher to view & download papers"),
                        ("b", "back to main menu"),
                    ])
                    t_choice = Prompt.ask("\n  [bold cyan]>[/]").strip().lower()
                    if t_choice.isdigit():
                        t_idx = int(t_choice) - 1
                        if 0 <= t_idx < len(teacher_matches):
                            sel_teacher = teacher_matches[t_idx][0]
                            t_papers = [p for p in papers if is_teacher_match(sel_teacher, p.get("teacher_name", ""))]
                            _download_by_teacher(t_papers, sel_teacher)
                elif subject_results and teacher_matches:
                    # Matched both subjects and teachers
                    print_banner()
                    console.print(Rule(f"[bold yellow]Results for '{query}'[/]"))
                    console.print()
                    console.print(f"  Found [cyan]{len(subject_results)} subject paper(s)[/] AND [green]{len(teacher_matches)} matching teacher(s)[/].\n")
                    print_menu_panel("Choose View", [
                        ("1", f"Browse Subject Papers ({len(subject_results)} papers)"),
                        ("2", f"Enlist Matching Teachers ({len(teacher_matches)} teachers)"),
                        ("b", "Back to Main Menu"),
                    ])
                    v_choice = Prompt.ask("\n  [bold cyan]>[/]").strip().lower()
                    if v_choice == "2":
                        print_banner()
                        enlist_matching_teachers_table(teacher_matches, papers, title=f"Matching Teachers for '{query}'")
                        console.print()
                        print_menu_panel("Options", [
                            (f"1-{len(teacher_matches)}", "select teacher to view & download papers"),
                            ("b", "back to main menu"),
                        ])
                        t_choice = Prompt.ask("\n  [bold cyan]>[/]").strip().lower()
                        if t_choice.isdigit():
                            t_idx = int(t_choice) - 1
                            if 0 <= t_idx < len(teacher_matches):
                                sel_teacher = teacher_matches[t_idx][0]
                                t_papers = [p for p in papers if is_teacher_match(sel_teacher, p.get("teacher_name", ""))]
                                _download_by_teacher(t_papers, sel_teacher)
                    elif v_choice == "1":
                        teacher_result = screen_select_teacher(papers, query)
                        if teacher_result != "__back__":
                            campus_result = screen_select_campus(papers, query, teacher=teacher_result)
                            if campus_result != "__back__":
                                exam_type_result = screen_select_exam_type(papers, query, campus=campus_result, teacher=teacher_result)
                                if exam_type_result != "__back__":
                                    category_result = screen_select_category(
                                        papers, query, campus=campus_result, exam_type=exam_type_result, teacher=teacher_result
                                    )
                                    if category_result != "__back__":
                                        confirm_and_download(
                                            papers,
                                            query,
                                            teacher=teacher_result,
                                            campus=campus_result,
                                            exam_type=exam_type_result,
                                            category=category_result,
                                            output_base=OUTPUT_BASE,
                                        )
                else:
                    teacher_result = screen_select_teacher(papers, query)
                    if teacher_result != "__back__":
                        campus_result = screen_select_campus(papers, query, teacher=teacher_result)
                        if campus_result != "__back__":
                            exam_type_result = screen_select_exam_type(papers, query, campus=campus_result, teacher=teacher_result)
                            if exam_type_result != "__back__":
                                category_result = screen_select_category(
                                    papers, query, campus=campus_result, exam_type=exam_type_result, teacher=teacher_result
                                )
                                if category_result != "__back__":
                                    confirm_and_download(
                                        papers,
                                        query,
                                        teacher=teacher_result,
                                        campus=campus_result,
                                        exam_type=exam_type_result,
                                        category=category_result,
                                        output_base=OUTPUT_BASE,
                                    )

        elif choice == "3":
            screen_teacher_hub(papers)

        elif choice == "4":
            papers = fetch_all_papers(force=True)
            console.print("  [green]Catalogue refreshed.[/]")
            time.sleep(1.5)

        elif choice == "5":
            if papers is None:
                papers = fetch_all_papers()
            screen_direct_download(papers)

        elif choice == "q":
            print_banner()
            console.print(Align.center(Text("Goodbye!", style="bold cyan")))
            console.print()
            sys.exit(0)

        else:
            console.print("  [red]Invalid option. Choose 1–5 or q.[/]")
            time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n  [dim]Interrupted. Goodbye![/]\n")
        sys.exit(0)
