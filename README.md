# COMSATS Past Papers Vault 

Welcome to the COMSATS Past Papers Vault! This project provides a faster and easier way to access official past examination papers and academic resources across all COMSATS University Islamabad (CUI) campuses.

Instead of navigating slow, cluttered portals or searching through disorganized drives, this application gives students and educators an instant, responsive catalog with clean in-browser document previews and high-speed downloads.

---

## Highlights

- **Faster and Easier Search**: Search by course code (e.g., CSC270, MTH100), course title, instructor, or session batch with instant client-side fuzzy matching.
- **Multi-Campus Support**: Filter papers seamlessly across Lahore, Islamabad, Abbottabad, Wah, Attock, Sahiwal, and Vehari.
- **One-Click Downloads**: Save individual PDF papers directly to your preferred folder with zero delays.
- **Batch ZIP Bundling**: Select multiple papers or an entire course query and package them together into an organized ZIP archive in seconds.

---

## Important Note: Run Locally for Best Performance

> [!TIP]
> **Recommended: Run locally instead of using the online deployment.**
> While the online Vercel link is available for quick catalog browsing, running locally is strongly recommended for actual studying and downloading:
> 
> - **Fast and Unrestricted**: Running on your local machine bypasses Vercel serverless load throttling, cold starts, and the strict 4.5 MB payload limit on batch ZIP archives.
> - **No Server Load Limits**: Vercel serverless functions have short execution timeouts under heavy concurrent student traffic. Local runs give direct, reliable download speeds.
> - **Two Local Interfaces**: Choose between the visual web app (`app.py`) or the interactive terminal CLI tool (`CLI.py`).

---

## Quick Start (Run Locally)

### Prerequisites

- Python 3.9 or higher

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Choose Your Interface

#### Method A: Web Interface (Recommended)

Start the local web server:
```bash
python3 app.py
```
Then open your web browser to `http://localhost:5050`.

#### Method B: Interactive Terminal Downloader (CLI)

Run the rich terminal CLI directly:
```bash
python3 CLI.py
```
Features interactive search menus, multi-campus filtering, progress bars, and direct PDF downloads into `./Past_Papers/`.

---


## Credits & Community

Created and maintained by [0xGhost63](https://github.com/0xGhost63/). Contributions, suggestions, and pull requests are always welcome!
