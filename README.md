# COMSATS Past Papers Vault (ARCHIVIST)

Welcome to the COMSATS Past Papers Vault! This project provides a faster and easier way to access official past examination papers and academic resources across all COMSATS University Islamabad (CUI) campuses.

Instead of navigating slow, cluttered portals or searching through disorganized drives, this application gives students and educators an instant, responsive catalog with clean in-browser document previews and high-speed downloads.

---

## Highlights

- **Faster and Easier Search**: Search by course code (e.g., CSC270, MTH100), course title, instructor, or session batch with instant client-side fuzzy matching.
- **Multi-Campus Support**: Filter papers seamlessly across Lahore, Islamabad, Abbottabad, Wah, Attock, Sahiwal, and Vehari.
- **One-Click Downloads**: Save individual PDF papers directly to your preferred folder with zero delays.
- **Batch ZIP Bundling**: Select multiple papers or an entire course query and package them together into an organized ZIP archive in seconds.

---

## Quick Start (Run Locally)

### Prerequisites

- Python 3.9 or higher

### Steps

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Start the application:
   ```bash
   python3 app.py
   ```

3. Open your browser and navigate to:
   ```
   http://localhost:5050
   ```

---

## Production Deployment

### Option 1: Vercel (Free)

1. Push your code to GitHub.
2. Sign in to [Vercel](https://vercel.com) and click **Add New Project**.
3. Select your GitHub repository.
4. Leave Framework Preset as **Other** (Vercel automatically detects `vercel.json` and `api/index.py`).
5. Click **Deploy**.

Alternatively, deploy using the Vercel CLI:
```bash
npm i -g vercel
vercel
```

### Option 2: Docker Container (Render, Railway, Heroku)

Build and run with Docker:
```bash
docker build -t cui-past-papers .
docker run -d -p 5050:5050 --name cui-vault cui-past-papers
```

For Render, Railway, or Heroku, connect your repository and deploy directly from root using the included `Dockerfile` or `Procfile`.

---

## Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `PORT` | Listening port for the HTTP server | `5050` |
| `HOST` | Network interface binding | `0.0.0.0` |
| `UPSTREAM_PORTAL_URL` | Upstream portal base URL override (optional) | Built-in secure default |

---

## Credits & Community

Created and maintained by [0xGhost63](https://github.com/0xGhost63/). Contributions, suggestions, and pull requests are always welcome!
