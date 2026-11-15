// CUI Past Papers Vault : Core Application Logic
// Bento Grid Architecture with Client-Side Fuzzy Search, Theme Switching, and Batch Downloader
// Zero emojis. Zero em dashes.

const AppState = {
  papers: [],
  filtered: [],
  teachers: [],
  selectedIds: new Set(),
  currentView: "papers", // 'papers' or 'teachers'
  viewMode: "table",     // Tabular matrix
  activeCampus: "Lahore", // Default to Lahore
  activeExamType: "ALL",
  activeCategory: "ALL",
  searchQuery: "",
  sortBy: "default",
  inspectingPaper: null,
  renderLimit: 40
};

// Procedural Audio Engine
var AudioSys = window.AudioSys = window.AudioSys || (typeof AudioEngine !== "undefined" ? new AudioEngine() : null);

// Teacher Fuzzy Scoring (aligned with downloader.py)
const HONORIFICS = ["dr.", "dr", "mr.", "mr", "ms.", "ms", "mrs.", "mrs", "engr.", "engr", "prof.", "prof"];

function stripTitles(name) {
  let parts = name.trim().split(/\s+/);
  while (parts.length > 0 && HONORIFICS.includes(parts[0].toLowerCase())) {
    parts.shift();
  }
  return parts.join(" ");
}

function normalizePhonetic(word) {
  let w = word.toLowerCase().trim();
  w = w.replace(/ee/g, "i").replace(/ea/g, "i");
  w = w.replace(/oo/g, "u");
  w = w.replace(/kh/g, "k").replace(/gh/g, "g").replace(/ph/g, "f");
  w = w.replace(/sh/g, "s").replace(/zh/g, "z");
  w = w.replace(/w/g, "v");
  w = w.replace(/(.)\1+/g, "$1");
  return w;
}

function calculateTeacherMatch(query, teacherName) {
  if (!query || !teacherName) return 0;
  const qClean = query.toLowerCase().trim();
  const tClean = teacherName.toLowerCase().trim();
  if (qClean === tClean) return 100;

  const qCore = stripTitles(query).toLowerCase();
  const tCore = stripTitles(teacherName).toLowerCase();
  if (!qCore || !tCore) return 0;
  if (qCore === tCore) return 98;

  const qTokens = qCore.split(/\s+/).filter(Boolean);
  const tTokens = tCore.split(/\s+/).filter(Boolean);

  const qSet = new Set(qTokens);
  const tSet = new Set(tTokens);
  if (qTokens.length === tTokens.length && [...qSet].every(x => tSet.has(x))) {
    return 96;
  }

  const qPhon = qTokens.map(normalizePhonetic).join(" ");
  const tPhon = tTokens.map(normalizePhonetic).join(" ");
  if (qPhon === tPhon) return 94;

  if (tCore.includes(qCore) && qCore.length >= 3) {
    const coverage = qCore.length / Math.max(tCore.length, 1);
    return 88 + coverage * 8;
  }

  let matchedTokens = 0;
  for (const qt of qTokens) {
    if (tTokens.some(tt => tt.includes(qt) || qt.includes(tt))) {
      matchedTokens++;
    }
  }

  if (matchedTokens === qTokens.length) {
    return 82;
  } else if (matchedTokens > 0) {
    return (matchedTokens / qTokens.length) * 65;
  }

  return 0;
}

// DOM References
const DOM = {
  themeToggleBtn: document.getElementById("theme-toggle-btn"),
  themeStatusText: document.getElementById("theme-status-text"),
  themeSunIcon: document.getElementById("theme-sun-icon"),
  themeMoonIcon: document.getElementById("theme-moon-icon"),
  searchInput: document.getElementById("search-input"),
  searchClearBtn: document.getElementById("search-clear-btn"),
  searchBox: document.getElementById("search-box"),
  papersContainer: document.getElementById("papers-container"),
  teachersContainer: document.getElementById("teachers-container"),
  resultsCount: document.getElementById("results-count"),
  selectAllBtn: document.getElementById("select-all-btn"),
  selectAllLabel: document.getElementById("select-all-label"),
  metricTotalPapers: document.getElementById("metric-total-papers"),
  metricTotalSubjects: document.getElementById("metric-total-subjects"),
  metricTotalTeachers: document.getElementById("metric-total-teachers"),
  metricCampuses: document.getElementById("metric-campuses"),
  metricPapersFoot: document.getElementById("metric-papers-foot"),
  metricSubjectsFoot: document.getElementById("metric-subjects-foot"),
  metricTeachersFoot: document.getElementById("metric-teachers-foot"),
  metricCampusesFoot: document.getElementById("metric-campuses-foot"),
  campusPills: document.getElementById("campus-pills"),
  examTypePills: document.getElementById("exam-type-pills"),
  categoryPills: document.getElementById("category-pills"),
  sortSelect: document.getElementById("sort-select"),
  tabPapersBtn: document.getElementById("tab-papers-btn"),
  tabTeachersBtn: document.getElementById("tab-teachers-btn"),
  refreshBtn: document.getElementById("refresh-btn"),
  soundToggleBtn: document.getElementById("sound-toggle-btn"),
  batchDock: document.getElementById("batch-dock"),
  batchCount: document.getElementById("batch-count"),
  batchTeacherInput: document.getElementById("batch-teacher-input"),
  teachersDatalist: document.getElementById("teachers-datalist"),
  batchZipBtn: document.getElementById("batch-zip-btn"),
  batchDownloadBtn: document.getElementById("batch-download-btn"),
  batchClearBtn: document.getElementById("batch-clear-btn"),
  drawerOverlay: document.getElementById("drawer-overlay"),
  inspectionDrawer: document.getElementById("inspection-drawer"),
  drawerCloseBtn: document.getElementById("drawer-close-btn"),
  drawerContent: document.getElementById("drawer-content"),
  toastContainer: document.getElementById("toast-container")
};

// Application Initialization
async function initApp() {
  try {
    setupTheme();
    bindEvents();
    setupKeyboardShortcuts();
    updateSoundVisualizer();
    await loadCatalogue();
  } catch (err) {
    console.error("[Archivist] initApp ERROR:", err);
  }

  // Trigger entrance animations on top bento tiles
  requestAnimationFrame(() => {
    animateEntrance(".bento-tile", 50);
  });
}

// Staggered Entrance Animation for Bento Grid Tiles
function animateEntrance(selector, baseDelay = 0) {
  const items = document.querySelectorAll(selector);
  items.forEach((el, index) => {
    const delay = baseDelay + index * 40;
    el.style.animationDelay = `${delay}ms`;
    el.classList.add("animate-entrance");
  });
}

// Show skeleton loading state
function showSkeletonLoading(container, count = 6) {
  const skeletons = Array.from({ length: count }, () => `
    <div class="skeleton-card">
      <div class="skeleton skeleton-text short" style="margin-bottom: 8px;"></div>
      <div class="skeleton skeleton-text long" style="margin-bottom: 12px;"></div>
      <div class="skeleton skeleton-block" style="margin-bottom: 8px;"></div>
      <div class="skeleton skeleton-block" style="margin-bottom: 8px;"></div>
      <div class="skeleton skeleton-block" style="margin-bottom: 16px;"></div>
      <div style="display: flex; justify-content: space-between;">
        <div class="skeleton skeleton-block" style="width: 80px;"></div>
        <div style="display: flex; gap: 6px;">
          <div class="skeleton skeleton-block" style="width: 30px; height: 30px; border-radius: 6px;"></div>
          <div class="skeleton skeleton-block" style="width: 30px; height: 30px; border-radius: 6px;"></div>
        </div>
      </div>
    </div>
  `).join("");

  container.className = "papers-grid skeleton-grid";
  container.innerHTML = skeletons;
}

// Dark / Light Mode System
function setupTheme() {
  const savedTheme = localStorage.getItem("archivist_theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const initialTheme = savedTheme || (prefersDark ? "dark" : "light");

  applyTheme(initialTheme);

  if (DOM.themeToggleBtn) {
    DOM.themeToggleBtn.addEventListener("click", () => {
      AudioSys.playSwitch();
      const current = document.documentElement.getAttribute("data-theme") || "light";
      const next = current === "dark" ? "light" : "dark";
      applyTheme(next);
      localStorage.setItem("archivist_theme", next);
    });
  }
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const isDark = theme === "dark";

  if (DOM.themeStatusText) {
    DOM.themeStatusText.textContent = isDark ? "Dark Mode" : "Light Mode";
  }

  if (DOM.themeSunIcon && DOM.themeMoonIcon) {
    if (isDark) {
      DOM.themeSunIcon.classList.remove("active");
      DOM.themeMoonIcon.classList.add("active");
    } else {
      DOM.themeSunIcon.classList.add("active");
      DOM.themeMoonIcon.classList.remove("active");
    }
  }

  updateFavicon(isDark);
}

function updateFavicon(isDark) {
  const favicon = document.querySelector('link[rel="icon"]');
  if (favicon) {
    const svg = isDark
      ? `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="6" fill="#1B1B1F"/><text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle" font-family="monospace" font-weight="bold" font-size="18" fill="#F6EEDC">CUI</text></svg>`
      : `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="6" fill="#FFF6E9"/><text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle" font-family="monospace" font-weight="bold" font-size="18" fill="#1B1B1F">CUI</text></svg>`;
    favicon.href = `data:image/svg+xml,${encodeURIComponent(svg)}`;
  }
}

// Data Fetching & Indexing
async function loadCatalogue() {
  try {
    DOM.resultsCount.innerHTML = "<span>Loading archive index...</span>";
    showSkeletonLoading(DOM.papersContainer, 8);

    const res = await fetch("/api/papers");
    if (!res.ok) {
      throw new Error(`Server status ${res.status}`);
    }
    const data = await res.json();
    AppState.papers = data.papers || [];

    buildTeacherDirectory();
    populateTeacherDatalist();
    applyFilters();
  } catch (err) {
    DOM.resultsCount.innerHTML = `<span style='color:var(--color-tomato)'>Failed to load catalog index (${escapeHtml(err.message)})</span>`;
    DOM.papersContainer.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 48px; text-align: center; background: var(--color-surface); border: 2px dashed var(--border-subtle); border-radius: var(--radius-md);">
        <p style="font-family: var(--font-mono); color: var(--color-tomato); font-size: 14px; font-weight: 700; margin-bottom: 8px;">
          Catalogue Connection Notice
        </p>
        <p style="color: var(--text-secondary); font-size: 13px; max-width: 520px; margin: 0 auto 16px auto;">
          The local server index could not be reached. Ensure app_v2.py is running and refresh this page.
        </p>
        <button class="pill-btn active" onclick="loadCatalogue()">Retry Connection</button>
      </div>
    `;
    showToast("Catalogue loading error: " + err.message, "error");
  }
}

function buildPaperFilename(paper) {
  if (!paper) return "past_paper.pdf";
  const code = (paper.course_code || "").trim().replace(/[^a-zA-Z0-9_-]/g, "_");
  const title = (paper.course_title || "Paper").trim().replace(/[^a-zA-Z0-9_-]/g, "_");
  const type = (paper.exam_type || "").trim().replace(/[^a-zA-Z0-9_-]/g, "_");
  const batch = (paper.batch || "").trim().replace(/[^a-zA-Z0-9_-]/g, "_");
  const campus = (paper.campus || "").trim().replace(/[^a-zA-Z0-9_-]/g, "_");
  const parts = [code, title, type, batch, campus].filter(Boolean);
  return `${parts.join("_") || "exam_paper"}.pdf`;
}

function buildTeacherDirectory(sourcePapers) {
  const papers = sourcePapers || (AppState.filtered && AppState.filtered.length > 0 ? AppState.filtered : AppState.papers);
  const map = new Map();
  papers.forEach(p => {
    const raw = (p.teacher_name || "").trim();
    if (!raw) return;
    if (!map.has(raw)) {
      map.set(raw, { name: raw, count: 0, subjects: new Set(), campuses: new Set() });
    }
    const rec = map.get(raw);
    rec.count++;
    if (p.course_title) rec.subjects.add(p.course_title);
    if (p.campus) rec.campuses.add(p.campus);
  });

  AppState.teachers = Array.from(map.values())
    .map(t => ({
      name: t.name,
      count: t.count,
      subjects: Array.from(t.subjects),
      campuses: Array.from(t.campuses)
    }))
    .sort((a, b) => b.count - a.count);

  populateTeacherDatalist();
}

function populateTeacherDatalist() {
  if (!DOM.teachersDatalist) return;
  DOM.teachersDatalist.innerHTML = AppState.teachers.slice(0, 80)
    .map(t => `<option value="${escapeHtml(t.name)}">${escapeHtml(t.name)} (${t.count} papers)</option>`)
    .join("");
}

// Dynamic Stats calculation based on current active filtered subset
function calculateStats() {
  const currentSet = AppState.filtered;
  const total = currentSet.length;
  const subjects = new Set(currentSet.map(p => p.course_title).filter(Boolean)).size;
  const teachers = new Set(currentSet.map(p => p.teacher_name).filter(Boolean)).size;
  const campuses = new Set(currentSet.map(p => p.campus).filter(Boolean)).size;

  animateCounter(DOM.metricTotalPapers, total);
  animateCounter(DOM.metricTotalSubjects, subjects);
  animateCounter(DOM.metricTotalTeachers, teachers);
  animateCounter(DOM.metricCampuses, campuses);

  // Update footer labels on metric tiles
  const campusesFoot = DOM.metricCampusesFoot || document.getElementById("metric-campuses-foot");
  if (campusesFoot) {
    if (AppState.activeCampus === "ALL") {
      campusesFoot.textContent = "All campuses active";
    } else {
      campusesFoot.textContent = `Active default: ${AppState.activeCampus}`;
    }
  }

  const papersFoot = DOM.metricPapersFoot || document.getElementById("metric-papers-foot");
  if (papersFoot) {
    if (AppState.activeExamType !== "ALL") {
      papersFoot.textContent = `${AppState.activeExamType} exams`;
    } else if (AppState.activeCategory !== "ALL") {
      papersFoot.textContent = `${AppState.activeCategory} papers`;
    } else {
      papersFoot.textContent = "Cataloged exam papers";
    }
  }
}

// Smooth animated counter that never clobbers or resets prematurely
function animateCounter(el, target) {
  if (!el) return;
  const startVal = parseInt((el.textContent || "0").replace(/,/g, "")) || 0;
  if (startVal === target) {
    el.textContent = target.toLocaleString();
    return;
  }

  if (el._animFrameId) {
    cancelAnimationFrame(el._animFrameId);
  }

  let startTime = null;
  const duration = 400; // snappy 400ms transition

  function step(now) {
    if (!startTime) startTime = now;
    const progress = Math.min((now - startTime) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3); // cubic ease-out
    const current = Math.round(startVal + (target - startVal) * ease);
    el.textContent = current.toLocaleString();

    if (progress < 1) {
      el._animFrameId = requestAnimationFrame(step);
    } else {
      el.textContent = target.toLocaleString();
      el._animFrameId = null;
    }
  }

  el._animFrameId = requestAnimationFrame(step);
}

// Filtering & Search
function applyFilters(resetLimit = true) {
  if (resetLimit) {
    AppState.renderLimit = 40;
  }
  const q = AppState.searchQuery.toLowerCase().trim();
  const campus = AppState.activeCampus;
  const exam = AppState.activeExamType;
  const cat = AppState.activeCategory;

  const qTokens = q ? q.split(/\s+/).filter(Boolean) : [];
  const qClean = q.replace(/[^a-z0-9]/g, "");

  AppState.filtered = AppState.papers.filter(p => {
    // Campus filter
    if (campus !== "ALL") {
      const pCampus = (p.campus || "").toLowerCase();
      if (!pCampus.includes(campus.toLowerCase())) return false;
    }

    // Exam Type filter
    if (exam !== "ALL") {
      if ((p.exam_type || "").toLowerCase() !== exam.toLowerCase()) return false;
    }

    // Category filter
    if (cat !== "ALL") {
      if ((p.exam_category || "").toLowerCase() !== cat.toLowerCase()) return false;
    }

    // Text query search
    if (q) {
      const title = (p.course_title || "").toLowerCase();
      const code = (p.course_code || "").toLowerCase();
      const codeClean = code.replace(/[^a-z0-9]/g, "");
      const acr = (p.acronym || "").toLowerCase();
      const teacher = (p.teacher_name || "").toLowerCase();
      const batch = (p.batch || "").toLowerCase();
      const examType = (p.exam_type || "").toLowerCase();
      const examCat = (p.exam_category || "").toLowerCase();
      const campusName = (p.campus || "").toLowerCase();

      // Combined searchable haystack
      const haystack = `${title} ${code} ${codeClean} ${acr} ${teacher} ${batch} ${examType} ${examCat} ${campusName}`;

      // 1. Normalized course code match (e.g. "mth 100" -> "mth100")
      if (qClean && codeClean.includes(qClean)) return true;

      // 2. Direct full-query substring match
      if (haystack.includes(q)) return true;

      // 3. Multi-token match: every word in query must match somewhere in haystack
      if (qTokens.length > 1) {
        const allMatch = qTokens.every(tok => {
          const cleanTok = tok.replace(/[^a-z0-9]/g, "");
          return haystack.includes(tok) || (cleanTok && haystack.includes(cleanTok));
        });
        if (allMatch) return true;
      }

      // 4. Fuzzy instructor name match
      if (q.length >= 3 && p.teacher_name) {
        const teacherScore = calculateTeacherMatch(q, p.teacher_name);
        if (teacherScore >= 60) return true;
      }

      return false;
    }

    return true;
  });

  sortFiltered();

  // Dynamic teachers index scoped strictly to active filtered set
  buildTeacherDirectory(AppState.filtered);

  const campusLabel = campus === "ALL" ? "All Campuses" : `${campus} Campus`;
  DOM.resultsCount.innerHTML = `Showing <strong>${AppState.filtered.length}</strong> of ${AppState.papers.length} catalogued papers (${campusLabel})`;

  // Keep stats widgets synchronized with filtered set
  calculateStats();

  renderPapers();

  updateSelectionUI();
}

function sortFiltered() {
  if (AppState.sortBy === "title") {
    AppState.filtered.sort((a, b) => (a.course_title || "").localeCompare(b.course_title || ""));
  } else if (AppState.sortBy === "teacher") {
    AppState.filtered.sort((a, b) => (a.teacher_name || "").localeCompare(b.teacher_name || ""));
  } else if (AppState.sortBy === "recent") {
    AppState.filtered.sort((a, b) => (b.uploaded_at || "").localeCompare(a.uploaded_at || ""));
  } else {
    // Default catalog: sort by id numerically descending
    AppState.filtered.sort((a, b) => (parseInt(b.id) || 0) - (parseInt(a.id) || 0));
  }
}

// Rendering Papers
function renderPapers() {
  DOM.papersContainer.style.display = "block";
  if (DOM.teachersContainer) DOM.teachersContainer.style.display = "none";

  if (AppState.filtered.length === 0) {
    DOM.papersContainer.innerHTML = `
      <div style="padding: 48px 24px; text-align: center; background: var(--color-surface); border: 2px dashed var(--border-subtle); border-radius: var(--radius-md);">
        <p style="font-family: var(--font-mono); color: var(--text-muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">
          No papers match the specified query filters
        </p>
        <p style="color: var(--text-secondary); font-size: 13px; max-width: 480px; margin: 0 auto 16px auto;">
          Try selecting "All Campuses" or "All Exams", or clearing your search term.
        </p>
        <button class="pill-btn active" onclick="resetFilters()">Reset All Filters</button>
      </div>
    `;
    return;
  }

  renderTableView();
  updateSelectionUI();
}

function getExamPillClass(examType) {
  const t = (examType || "").toLowerCase();
  if (t.includes("mid")) return "mid";
  if (t.includes("final")) return "final";
  if (t.includes("sessional")) return "sessional";
  return "general";
}

// Progressive Batch Rendering: Sentinel & Observer
let sentinelObserver = null;

function setupScrollSentinel() {
  if (sentinelObserver) {
    sentinelObserver.disconnect();
    sentinelObserver = null;
  }
  const sentinel = document.getElementById("grid-load-more-sentinel");
  if (!sentinel) return;

  if (typeof IntersectionObserver !== "undefined") {
    sentinelObserver = new IntersectionObserver((entries) => {
      if (entries[0] && entries[0].isIntersecting) {
        sentinelObserver.disconnect();
        sentinelObserver = null;
        loadMorePapers();
      }
    }, { rootMargin: "350px" });
    sentinelObserver.observe(sentinel);
  }
}

function loadMorePapers() {
  AppState.renderLimit = (AppState.renderLimit || 40) + 40;
  renderTableView();
  updateSelectionUI();
}

// Render Tabular Matrix View
function renderTableView() {
  const total = AppState.filtered.length;
  const limit = AppState.renderLimit || 40;
  const visible = AppState.filtered.slice(0, limit);

  const rowsHtml = visible.map(p => {
    const isSelected = AppState.selectedIds.has(p.id);
    const examClass = getExamPillClass(p.exam_type);
    return `
      <tr class="${isSelected ? 'selected' : ''}" data-id="${p.id}">
        <td style="width: 36px;">
          <input type="checkbox" class="card-checkbox" data-id="${p.id}" ${isSelected ? 'checked' : ''}>
        </td>
        <td><span class="course-code-tag">${escapeHtml(p.course_code || 'GEN')}</span></td>
        <td style="font-weight: 700; color: var(--text-main); font-family: var(--font-display);">${escapeHtml(p.course_title || 'Untitled')}</td>
        <td style="font-family: var(--font-mono);">${escapeHtml(p.teacher_name || 'Unassigned')}</td>
        <td><span class="exam-pill ${examClass}">${escapeHtml(p.exam_type || 'Exam')}</span></td>
        <td style="font-family: var(--font-mono);">${escapeHtml(p.campus || 'CUI')}</td>
        <td style="font-family: var(--font-mono);">${escapeHtml(p.batch || '')}</td>
        <td style="text-align: right; white-space: nowrap;">
          <button class="pill-btn card-action-inspect" data-id="${p.id}" style="padding: 3px 8px;" title="Preview Paper" type="button">
            Preview
          </button>
          <button class="pill-btn active card-action-download" data-id="${p.id}" style="padding: 3px 8px; margin-left: 6px;" title="Download PDF" type="button">
            Save
          </button>
        </td>
      </tr>
    `;
  }).join("");

  let loadMoreRow = "";
  if (total > limit) {
    const remaining = total - limit;
    loadMoreRow = `
      <tr>
        <td colspan="8" style="text-align: center; padding: 18px;">
          <div id="grid-load-more-sentinel">
            <button id="load-more-btn" class="pill-btn active" type="button" onclick="loadMorePapers()">
              Load More Papers (${remaining} remaining)
            </button>
          </div>
        </td>
      </tr>
    `;
  }

  DOM.papersContainer.className = "papers-table-wrapper";
  DOM.papersContainer.innerHTML = `
    <table class="papers-table">
      <thead>
        <tr>
          <th style="width: 36px;">
            <input type="checkbox" id="table-select-all" class="card-checkbox" title="Select all filtered papers" onchange="toggleSelectAllFiltered()">
          </th>
          <th>Code</th>
          <th>Course Title</th>
          <th>Instructor</th>
          <th>Exam</th>
          <th>Campus</th>
          <th>Batch</th>
          <th style="text-align: right;">Action</th>
        </tr>
      </thead>
      <tbody>
        ${rowsHtml}
        ${loadMoreRow}
      </tbody>
    </table>
  `;

  setupScrollSentinel();
}

// Rendering Teachers Directory (Internal helper if container exists)
function renderTeachers() {
  if (!DOM.teachersContainer) return;
  DOM.papersContainer.style.display = "none";
  DOM.teachersContainer.style.display = "grid";

  const q = AppState.searchQuery.toLowerCase().trim();
  let list = AppState.teachers;

  if (q) {
    list = list
      .map(t => ({ ...t, score: calculateTeacherMatch(q, t.name) }))
      .filter(t => t.score > 0 || t.name.toLowerCase().includes(q))
      .sort((a, b) => (b.score || 0) - (a.score || 0));
  }

  if (list.length === 0) {
    DOM.teachersContainer.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 48px; text-align: center; background: var(--color-surface); border: 2px dashed var(--border-subtle); border-radius: var(--radius-md);">
        <p style="font-family: var(--font-mono); color: var(--text-muted); font-size: 13px;">No instructors match your search criteria</p>
      </div>
    `;
    return;
  }

  const html = list.map(t => {
    const subjectsCount = t.subjects.length;
    const campusesStr = t.campuses.join(", ") || "General";
    return `
      <article class="teacher-card" data-id="${escapeHtml(t.name)}" onclick="filterByTeacher('${escapeHtml(t.name)}')">
        <div class="teacher-card-head">
          <h4 class="teacher-name-title">${escapeHtml(t.name)}</h4>
          <span class="teacher-papers-count">${t.count} Papers</span>
        </div>
        <div style="font-size: 11px; font-family: var(--font-mono); color: var(--text-muted); margin-bottom: 8px;">
          ${escapeHtml(campusesStr)}
        </div>
        <div class="teacher-tags-wrap">
          ${t.subjects.slice(0, 3).map(s => `<span class="subject-chip">${escapeHtml(s)}</span>`).join("")}
          ${subjectsCount > 3 ? `<span class="subject-chip">+${subjectsCount - 3} more</span>` : ""}
        </div>
        <button class="teacher-filter-btn btn-press" type="button" onclick="event.stopPropagation(); filterByTeacher('${escapeHtml(t.name)}')">
          Filter Papers by Instructor
        </button>
      </article>
    `;
  }).join("");

  DOM.teachersContainer.className = "teachers-grid";
  DOM.teachersContainer.innerHTML = html;

  DOM.teachersContainer.querySelectorAll(".teacher-card").forEach(card => {
    card.addEventListener("mouseenter", () => {
      if (AudioSys && !AudioSys.isMuted()) {
        AudioSys.playTick(1200);
      }
    });
  });
}

// Filter Papers by Selected Instructor (clears campus constraint so all papers are shown)
function filterByTeacher(name) {
  AudioSys.playSwitch();
  AppState.currentView = "papers";
  if (DOM.tabPapersBtn) DOM.tabPapersBtn.classList.add("active");
  if (DOM.tabTeachersBtn) DOM.tabTeachersBtn.classList.remove("active");

  // Reset filters to show all papers by this teacher across campuses
  AppState.activeCampus = "ALL";
  AppState.activeExamType = "ALL";
  AppState.activeCategory = "ALL";

  // Update pill indicators in UI
  DOM.campusPills.querySelectorAll(".pill-btn").forEach(b => {
    b.classList.toggle("active", b.getAttribute("data-val") === "ALL");
  });
  DOM.examTypePills.querySelectorAll(".pill-btn").forEach(b => {
    b.classList.toggle("active", b.getAttribute("data-val") === "ALL");
  });
  DOM.categoryPills.querySelectorAll(".pill-btn").forEach(b => {
    b.classList.toggle("active", b.getAttribute("data-val") === "ALL");
  });

  AppState.searchQuery = name;
  DOM.searchInput.value = name;
  if (DOM.searchClearBtn) {
    DOM.searchClearBtn.style.display = "flex";
  }
  if (DOM.batchTeacherInput) {
    DOM.batchTeacherInput.value = name;
  }
  applyFilters();
}

// Reset All Filters to default state
function resetFilters() {
  AudioSys.playTick();
  AppState.searchQuery = "";
  DOM.searchInput.value = "";
  if (DOM.searchClearBtn) {
    DOM.searchClearBtn.style.display = "none";
  }
  AppState.activeCampus = "Lahore";
  AppState.activeExamType = "ALL";
  AppState.activeCategory = "ALL";
  AppState.currentView = "papers";

  if (DOM.tabPapersBtn) DOM.tabPapersBtn.classList.add("active");
  if (DOM.tabTeachersBtn) DOM.tabTeachersBtn.classList.remove("active");

  DOM.campusPills.querySelectorAll(".pill-btn").forEach(p => {
    p.classList.toggle("active", p.getAttribute("data-val") === "Lahore");
  });

  DOM.examTypePills.querySelectorAll(".pill-btn").forEach(p => {
    p.classList.toggle("active", p.getAttribute("data-val") === "ALL");
  });

  DOM.categoryPills.querySelectorAll(".pill-btn").forEach(p => {
    p.classList.toggle("active", p.getAttribute("data-val") === "ALL");
  });

  applyFilters();
}

// Paper Inspection Drawer with In-Browser PDF Preview
function inspectPaper(id) {
  const paper = AppState.papers.find(p => p.id === id);
  if (!paper) return;

  AudioSys.playTick();
  AppState.inspectingPaper = paper;

  const viewUrl = `/api/view/${paper.id}`;

  DOM.drawerContent.innerHTML = `
    <div class="drawer-field">
      <span class="drawer-field-label">Course Title</span>
      <span class="drawer-field-val" style="font-size: 1.25rem; font-family: var(--font-display);">${escapeHtml(paper.course_title || 'Untitled')}</span>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
      <div class="drawer-field">
        <span class="drawer-field-label">Course Code</span>
        <span class="drawer-field-val" style="font-family: var(--font-mono);">${escapeHtml(paper.course_code || 'GEN')}</span>
      </div>
      <div class="drawer-field">
        <span class="drawer-field-label">Acronym</span>
        <span class="drawer-field-val" style="font-family: var(--font-mono);">${escapeHtml(paper.acronym || 'N/A')}</span>
      </div>
    </div>

    <div class="drawer-field">
      <span class="drawer-field-label">Instructor</span>
      <span class="drawer-field-val">${escapeHtml(paper.teacher_name || 'Unassigned / Multiple')}</span>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
      <div class="drawer-field">
        <span class="drawer-field-label">Exam Type</span>
        <span class="drawer-field-val">${escapeHtml(paper.exam_type || 'Exam')}</span>
      </div>
      <div class="drawer-field">
        <span class="drawer-field-label">Category</span>
        <span class="drawer-field-val">${escapeHtml(paper.exam_category || 'Theory')}</span>
      </div>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
      <div class="drawer-field">
        <span class="drawer-field-label">Campus</span>
        <span class="drawer-field-val">${escapeHtml(paper.campus || 'CUI')}</span>
      </div>
      <div class="drawer-field">
        <span class="drawer-field-label">Session Batch</span>
        <span class="drawer-field-val" style="font-family: var(--font-mono);">${escapeHtml(paper.batch || 'Archived')}</span>
      </div>
    </div>

    <div class="drawer-field" style="margin-top: 10px;">
      <span class="drawer-field-label">Document Viewer</span>
      <div class="preview-embed-box">
        <object data="${viewUrl}" type="application/pdf">
          <iframe src="${viewUrl}" title="Paper Viewer">
            <p>PDF preview unavailable. Use the buttons below to open or download.</p>
          </iframe>
        </object>
      </div>
    </div>

    <div style="margin-top: 10px; display: flex; flex-direction: column; gap: 10px;">
      <a href="${viewUrl}" target="_blank" rel="noopener noreferrer" class="dock-btn dock-btn-sky" style="justify-content: center; text-decoration: none;">
        ${Icons.externalLink}
        <span>Open PDF in Dedicated Browser Tab</span>
      </a>

      <button class="dock-btn dock-btn-tomato" style="justify-content: center;" onclick="downloadSinglePaper('${paper.id}')">
        ${Icons.download}
        <span>Download PDF</span>
      </button>
    </div>
  `;

  DOM.drawerOverlay.classList.add("open");
  DOM.inspectionDrawer.classList.add("open");

  setTimeout(() => {
    DOM.drawerCloseBtn.focus();
  }, 100);
}

function closeDrawer() {
  AudioSys.playTick();
  DOM.drawerOverlay.classList.remove("open");
  DOM.inspectionDrawer.classList.remove("open");
  AppState.inspectingPaper = null;
}

// Batch Selection & Operations
function toggleSelect(id) {
  AudioSys.playTick();
  if (AppState.selectedIds.has(id)) {
    AppState.selectedIds.delete(id);
  } else {
    AppState.selectedIds.add(id);
  }
  updateSelectionUI();
}

function toggleSelectAllFiltered() {
  AudioSys.playTick();
  if (AppState.filtered.length === 0) return;

  const allSelected = AppState.filtered.every(p => AppState.selectedIds.has(p.id));
  if (allSelected) {
    AppState.filtered.forEach(p => AppState.selectedIds.delete(p.id));
  } else {
    AppState.filtered.forEach(p => AppState.selectedIds.add(p.id));
  }
  updateSelectionUI();
}

function updateSelectionUI() {
  const filteredTotal = AppState.filtered.length;
  const selectedFilteredCount = AppState.filtered.filter(p => AppState.selectedIds.has(p.id)).length;
  const allFilteredSelected = filteredTotal > 0 && selectedFilteredCount === filteredTotal;
  const someFilteredSelected = selectedFilteredCount > 0 && selectedFilteredCount < filteredTotal;

  if (DOM.selectAllBtn && DOM.selectAllLabel) {
    if (filteredTotal > 0 && AppState.currentView === "papers") {
      DOM.selectAllBtn.style.display = "inline-flex";
      if (allFilteredSelected) {
        DOM.selectAllBtn.classList.add("active");
        DOM.selectAllLabel.textContent = `Deselect All (${filteredTotal})`;
      } else {
        DOM.selectAllBtn.classList.remove("active");
        DOM.selectAllLabel.textContent = `Select All (${filteredTotal})`;
      }
    } else {
      DOM.selectAllBtn.style.display = "none";
    }
  }

  const tableSelectAll = document.getElementById("table-select-all");
  if (tableSelectAll) {
    tableSelectAll.checked = allFilteredSelected;
    tableSelectAll.indeterminate = someFilteredSelected;
  }

  DOM.papersContainer.querySelectorAll(".card-checkbox").forEach(cb => {
    if (cb.id === "table-select-all") return;
    const id = cb.getAttribute("data-id");
    cb.checked = AppState.selectedIds.has(id);
  });

  DOM.papersContainer.querySelectorAll(".paper-card, tbody tr").forEach(el => {
    const id = el.getAttribute("data-id");
    if (AppState.selectedIds.has(id)) {
      el.classList.add("selected");
    } else {
      el.classList.remove("selected");
    }
  });

  updateBatchDock();
}

function getEffectiveSelectedIds() {
  const filteredIdSet = new Set(AppState.filtered.map(p => String(p.id)));
  return Array.from(AppState.selectedIds).filter(id => filteredIdSet.has(String(id)));
}

function updateBatchDock() {
  const effectiveIds = getEffectiveSelectedIds();
  const count = effectiveIds.length;
  if (count > 0) {
    DOM.batchDock.classList.add("visible");
    DOM.batchCount.textContent = count;
  } else {
    DOM.batchDock.classList.remove("visible");
  }
}

function clearBatch() {
  AudioSys.playTick();
  AppState.filtered.forEach(p => AppState.selectedIds.delete(p.id));
  updateSelectionUI();
}

// Download Handlers
async function downloadBatchZip() {
  let ids = getEffectiveSelectedIds();
  if (ids.length === 0) {
    if (AppState.filtered.length > 0 && AppState.filtered.length <= 50) {
      ids = AppState.filtered.map(p => p.id);
    } else {
      AudioSys.playAlert();
      showToast("Select papers using checkboxes to build a ZIP archive", "info");
      return;
    }
  }

  const targetTeacher = DOM.batchTeacherInput ? DOM.batchTeacherInput.value.trim() : "";
  const campusTag = AppState.activeCampus !== "ALL" ? `${AppState.activeCampus}_` : "";
  const now = new Date();
  const dateStr = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}`;
  const suggestedZipName = `Past_Papers_${campusTag}${dateStr}.zip`;

  // Step 1: Prompt the user for save location FIRST via native file explorer
  let fileHandle = null;
  if (typeof window.showSaveFilePicker === "function") {
    try {
      fileHandle = await window.showSaveFilePicker({
        suggestedName: suggestedZipName,
        types: [{
          description: "ZIP Archive (*.zip)",
          accept: { "application/zip": [".zip"] }
        }]
      });
    } catch (pickerErr) {
      if (pickerErr.name === "AbortError") {
        return; // User cancelled file explorer dialog
      }
      console.warn("showSaveFilePicker unsupported or blocked, fallback to browser download:", pickerErr);
    }
  }

  // Step 2: Fetch and package the archive with button spinner
  AudioSys.playSwitch();
  showToast(`Preparing ZIP archive (${ids.length} papers)...`, "loading");

  const startTime = Date.now();
  try {
    DOM.batchZipBtn.disabled = true;
    DOM.batchZipBtn.innerHTML = `
      <span class="container uib-jelly-loader" style="--uib-size: 20px; --uib-color: #FFFFFF; display: inline-block; margin-right: 8px;"></span>
      <span>Packaging ${ids.length} files...</span>
    `;

    const res = await fetch("/api/download-zip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paper_ids: ids, teacher: targetTeacher })
    });

    if (!res.ok) {
      throw new Error(`Server returned HTTP ${res.status}`);
    }

    if (fileHandle) {
      const writable = await fileHandle.createWritable();
      if (res.body && typeof res.body.pipeTo === "function") {
        await res.body.pipeTo(writable);
      } else {
        const blob = await res.blob();
        await writable.write(blob);
        await writable.close();
      }
    } else {
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = suggestedZipName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    }

    AudioSys.playSuccess();
    showToast(`ZIP Archive (${ids.length} papers) downloaded successfully`, "success");
    clearBatch();
  } catch (err) {
    AudioSys.playAlert();
    showToast("ZIP export failed: " + err.message, "error");
  } finally {
    const elapsed = Date.now() - startTime;
    if (elapsed < 350) {
      await new Promise(r => setTimeout(r, 350 - elapsed));
    }
    DOM.batchZipBtn.disabled = false;
    DOM.batchZipBtn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
      <span>Download ZIP</span>
    `;
  }
}

async function downloadSinglePaper(id) {
  const paper = AppState.papers.find(p => p.id === id);
  const title = paper ? (paper.course_title || `Paper #${id}`) : `Paper #${id}`;
  const filename = buildPaperFilename(paper);

  // Step 1: Prompt the user for save location FIRST via native file explorer
  let fileHandle = null;
  if (typeof window.showSaveFilePicker === "function") {
    try {
      fileHandle = await window.showSaveFilePicker({
        suggestedName: filename,
        types: [{
          description: "PDF Document (*.pdf)",
          accept: { "application/pdf": [".pdf"] }
        }]
      });
    } catch (pickerErr) {
      if (pickerErr.name === "AbortError") {
        return; // User clicked Cancel in file explorer
      }
      console.warn("showSaveFilePicker unsupported or blocked, fallback to browser download:", pickerErr);
    }
  }

  // Step 2: Fetch and stream the PDF with inline spinner
  AudioSys.playSwitch();
  showToast(`Downloading: ${title}...`, "loading");

  const actionBtns = document.querySelectorAll(`.card-action-download[data-id="${id}"]`);
  actionBtns.forEach(btn => {
    btn.disabled = true;
    btn.dataset.prevHtml = btn.innerHTML;
    btn.innerHTML = `<span class="container uib-jelly-loader" style="--uib-size: 20px; --uib-color: #FFFFFF; display: inline-block;"></span>`;
  });

  const drawerBtn = DOM.inspectionDrawer ? DOM.inspectionDrawer.querySelector(".dock-btn-tomato") : null;
  if (drawerBtn) {
    drawerBtn.disabled = true;
    drawerBtn.dataset.prevHtml = drawerBtn.innerHTML;
    drawerBtn.innerHTML = `<span class="container uib-jelly-loader" style="--uib-size: 20px; --uib-color: #FFFFFF; display: inline-block; margin-right: 8px;"></span><span>Downloading...</span>`;
  }

  const startTime = Date.now();
  try {
    const res = await fetch(`/api/download-paper/${id}`);
    if (!res.ok) {
      throw new Error(`Server returned HTTP ${res.status}`);
    }

    if (fileHandle) {
      const writable = await fileHandle.createWritable();
      if (res.body && typeof res.body.pipeTo === "function") {
        await res.body.pipeTo(writable);
      } else {
        const blob = await res.blob();
        await writable.write(blob);
        await writable.close();
      }
    } else {
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    }

    AudioSys.playSuccess();
    showToast(`Downloaded: ${filename}`, "success");
  } catch (err) {
    AudioSys.playAlert();
    showToast("Download error: " + err.message, "error");
  } finally {
    const elapsed = Date.now() - startTime;
    if (elapsed < 350) {
      await new Promise(r => setTimeout(r, 350 - elapsed));
    }
    actionBtns.forEach(btn => {
      btn.disabled = false;
      btn.innerHTML = btn.dataset.prevHtml || "Save";
    });
    if (drawerBtn) {
      drawerBtn.disabled = false;
      drawerBtn.innerHTML = drawerBtn.dataset.prevHtml || `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
        <span>Download PDF</span>
      `;
    }
  }
}

// Live Catalogue Sync
async function refreshCatalogue() {
  AudioSys.playSwitch();
  DOM.refreshBtn.classList.add("spinning");
  showToast("Re-indexing latest catalog from academic vault...", "info");

  try {
    const res = await fetch("/api/refresh", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      AudioSys.playSuccess();
      showToast(`Updated archive index: ${data.total} papers ready`, "success");
      await loadCatalogue();
    } else {
      AudioSys.playAlert();
      showToast(data.message || "Failed to update catalog", "error");
    }
  } catch (err) {
    AudioSys.playAlert();
    showToast("Network error updating catalog", "error");
  } finally {
    DOM.refreshBtn.classList.remove("spinning");
  }
}

// Audio Controls
function toggleSound() {
  const isMuted = AudioSys.toggleMute();
  updateSoundVisualizer();
  showToast(isMuted ? "Audio feedback muted" : "Audio feedback active", "info");
}

function updateSoundVisualizer() {
  const isMuted = AudioSys.isMuted();
  if (isMuted) {
    DOM.soundToggleBtn.classList.remove("sound-active");
    DOM.soundToggleBtn.title = "Audio Muted (Click to Enable)";
  } else {
    DOM.soundToggleBtn.classList.add("sound-active");
    DOM.soundToggleBtn.title = "Audio Active (Click to Mute)";
  }
}

// Toast System
function showToast(message, type = "info", duration = 4000) {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;

  const iconSvg = type === "loading"
    ? `<span class="container uib-jelly-loader" style="--uib-size: 20px; --uib-color: var(--color-tomato); margin-right: 6px;"></span>`
    : (type === "success" ? Icons.check : (type === "error" ? Icons.close : Icons.activity));
  toast.innerHTML = `
    <span>${iconSvg}</span>
    <span>${escapeHtml(message)}</span>
    <div class="toast-progress" style="animation-duration: ${duration}ms;"></div>
  `;

  DOM.toastContainer.appendChild(toast);

  requestAnimationFrame(() => {
    toast.style.animationPlayState = "running";
  });

  setTimeout(() => {
    toast.classList.add("exiting");
    setTimeout(() => toast.remove(), 220);
  }, duration);

  if (type === "success" || type === "error") {
    notifyPageTitle(message, type);
  }
}

let originalTitle = document.title;
let titleNotifyTimeout = null;

function notifyPageTitle(message, type) {
  const prefix = type === "success" ? "[OK] " : (type === "error" ? "[ERR] " : "[INFO] ");
  document.title = `${prefix}${message}`;

  clearTimeout(titleNotifyTimeout);
  titleNotifyTimeout = setTimeout(() => {
    document.title = originalTitle;
  }, 3000);
}

function showToastWithAction(message, type, actionLabel, actionFn, duration = 6000) {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;

  const iconSvg = type === "success" ? Icons.check : (type === "error" ? Icons.close : Icons.activity);
  toast.innerHTML = `
    <span>${iconSvg}</span>
    <span style="flex: 1;">${escapeHtml(message)}</span>
    <button class="toast-action-btn" style="
      background: transparent;
      border: 1.5px solid currentColor;
      color: inherit;
      padding: 4px 10px;
      border-radius: var(--radius-xs);
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      cursor: pointer;
      margin-left: 8px;
    ">${actionLabel}</button>
    <div class="toast-progress" style="animation-duration: ${duration}ms;"></div>
  `;

  const actionBtn = toast.querySelector(".toast-action-btn");
  actionBtn.addEventListener("click", () => {
    toast.classList.add("exiting");
    setTimeout(() => toast.remove(), 220);
    actionFn();
  });

  DOM.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("exiting");
    setTimeout(() => toast.remove(), 220);
  }, duration);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function setCampus(campusName) {
  AudioSys.playSwitch();
  AppState.activeCampus = campusName;
  AppState.selectedIds.clear();
  DOM.campusPills.querySelectorAll(".pill-btn").forEach(b => {
    b.classList.toggle("active", b.getAttribute("data-val") === campusName);
  });
  applyFilters();
}

function setView(view) {
  AudioSys.playSwitch();
  AppState.currentView = "papers";
  applyFilters();
}

function setViewMode(mode) {
  AppState.viewMode = "table";
  renderPapers();
}

function animatePillSelection(container, selectedBtn) {
  container.querySelectorAll(".pill-btn").forEach(b => {
    b.classList.remove("active");
  });
  selectedBtn.classList.add("active");
}

// Event Bindings
function bindEvents() {
  // Search Input with Debounce (Fluid, responsive keystrokes)
  let searchTimer = null;
  DOM.searchInput.addEventListener("input", (e) => {
    const val = e.target.value;
    AppState.searchQuery = val;
    if (DOM.searchClearBtn) {
      DOM.searchClearBtn.style.display = val ? "flex" : "none";
    }
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      applyFilters();
    }, 120);
  });

  if (DOM.searchClearBtn) {
    DOM.searchClearBtn.addEventListener("click", () => {
      AudioSys.playTick();
      DOM.searchInput.value = "";
      AppState.searchQuery = "";
      DOM.searchClearBtn.style.display = "none";
      applyFilters();
      DOM.searchInput.focus();
    });
  }

  // Campus Filter Pills
  DOM.campusPills.querySelectorAll(".pill-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      AudioSys.playSwitch();
      animatePillSelection(DOM.campusPills, btn);
      AppState.activeCampus = btn.getAttribute("data-val");
      AppState.selectedIds.clear();
      applyFilters();
    });
  });

  // Exam Type Filter Pills
  DOM.examTypePills.querySelectorAll(".pill-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      AudioSys.playSwitch();
      animatePillSelection(DOM.examTypePills, btn);
      AppState.activeExamType = btn.getAttribute("data-val");
      applyFilters();
    });
  });

  // Category Filter Pills
  DOM.categoryPills.querySelectorAll(".pill-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      AudioSys.playSwitch();
      animatePillSelection(DOM.categoryPills, btn);
      AppState.activeCategory = btn.getAttribute("data-val");
      applyFilters();
    });
  });

  // Papers Container Event Delegation (High performance, zero memory leaks)
  DOM.papersContainer.addEventListener("click", (e) => {
    if (e.target.id === "table-select-all") {
      return;
    }

    const checkbox = e.target.closest(".card-checkbox");
    if (checkbox) {
      e.stopPropagation();
      const id = checkbox.getAttribute("data-id");
      if (id) toggleSelect(id);
      return;
    }

    const inspectBtn = e.target.closest(".card-action-inspect");
    if (inspectBtn) {
      e.stopPropagation();
      const id = inspectBtn.getAttribute("data-id");
      if (id) inspectPaper(id);
      return;
    }

    const downloadBtn = e.target.closest(".card-action-download");
    if (downloadBtn) {
      e.stopPropagation();
      const id = downloadBtn.getAttribute("data-id");
      if (id) downloadSinglePaper(id);
      return;
    }

    if (e.target.closest("#load-more-btn")) {
      return;
    }

    const card = e.target.closest(".paper-card, tbody tr");
    if (card) {
      const id = card.getAttribute("data-id");
      if (id) inspectPaper(id);
    }
  });

  // Sort Dropdown
  DOM.sortSelect.addEventListener("change", (e) => {
    AudioSys.playTick();
    AppState.sortBy = e.target.value;
    sortFiltered();
    renderPapers();
  });

  // Segmented Tabs (if present)
  if (DOM.tabPapersBtn) {
    DOM.tabPapersBtn.addEventListener("click", () => setView("papers"));
  }
  if (DOM.tabTeachersBtn) {
    DOM.tabTeachersBtn.addEventListener("click", () => setView("teachers"));
  }

  // Utility Actions
  DOM.refreshBtn.addEventListener("click", refreshCatalogue);
  DOM.soundToggleBtn.addEventListener("click", toggleSound);

  if (DOM.selectAllBtn) {
    DOM.selectAllBtn.addEventListener("click", toggleSelectAllFiltered);
  }

  // Batch Operations
  if (DOM.batchZipBtn) {
    DOM.batchZipBtn.addEventListener("click", downloadBatchZip);
  }
  if (DOM.batchDownloadBtn) {
    DOM.batchDownloadBtn.addEventListener("click", downloadBatchZip);
  }
  if (DOM.batchClearBtn) {
    DOM.batchClearBtn.addEventListener("click", clearBatch);
  }

  // Inspection Drawer Close
  DOM.drawerCloseBtn.addEventListener("click", closeDrawer);
  DOM.drawerOverlay.addEventListener("click", closeDrawer);

  // Touch Support
  document.addEventListener("touchstart", (e) => {
    const card = e.target.closest(".paper-card, .teacher-card, .bento-tile, .metric-tile");
    if (card) {
      card.classList.add("touch-active");
    }
  }, { passive: true });

  document.addEventListener("touchend", (e) => {
    const card = e.target.closest(".paper-card, .teacher-card, .bento-tile, .metric-tile");
    if (card) {
      card.classList.remove("touch-active");
    }
  }, { passive: true });
}

// Global Keyboard Shortcuts
function setupKeyboardShortcuts() {
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (DOM.inspectionDrawer.classList.contains("open")) {
        closeDrawer();
        return;
      }
    }

    if (e.key === "/" && document.activeElement !== DOM.searchInput) {
      e.preventDefault();
      DOM.searchInput.focus();
      return;
    }

    if (e.key.toLowerCase() === "m" && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
      e.preventDefault();
      toggleSound();
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

// Window Exports for HTML inline onclick handlers
window.loadCatalogue = loadCatalogue;
window.resetFilters = resetFilters;
window.toggleSelect = toggleSelect;
window.toggleSelectAllFiltered = toggleSelectAllFiltered;
window.inspectPaper = inspectPaper;
window.downloadSinglePaper = downloadSinglePaper;
window.downloadBatch = downloadBatchZip;
window.downloadBatchZip = downloadBatchZip;
window.clearBatch = clearBatch;
window.filterByTeacher = filterByTeacher;
window.closeDrawer = closeDrawer;
window.refreshCatalogue = refreshCatalogue;
window.toggleSound = toggleSound;
window.setView = setView;
window.setViewMode = setViewMode;
window.setCampus = setCampus;
window.loadMorePapers = loadMorePapers;
