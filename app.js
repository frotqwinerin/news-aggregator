/**
 * MY News Digest — Dashboard (app.js)
 *
 * Pure vanilla JS. Reads from /data/index.json and /data/YYYY-MM-DD.json.
 * Compatible with GitHub Pages (no server required).
 */

'use strict';

// ── Configuration ─────────────────────────────────────────────────────────────

/** Category order for the sidebar. Must match scraper.py CATEGORIES keys. */
const CATEGORY_ORDER = ['tech', 'society', 'security'];

/**
 * Set this to your GitHub Actions URL so the "Trigger scrape" button works.
 * Example: 'https://github.com/your-username/news-aggregator/actions'
 * Leave as '' to hide the button.
 */
const GITHUB_ACTIONS_URL = '';

// ── State ─────────────────────────────────────────────────────────────────────

let state = {
  index: null,        // data/index.json content
  data: null,         // data/YYYY-MM-DD.json content
  currentDate: '',    // selected date string YYYY-MM-DD
  currentCat: '',     // active category id
  searchQuery: '',    // live search string
};

// ── DOM refs (populated in init) ──────────────────────────────────────────────

const $ = id => document.getElementById(id);
let dom = {};

// ── Utility ───────────────────────────────────────────────────────────────────

/**
 * Format an ISO date string as a relative or absolute label.
 * e.g. "2 hours ago", "yesterday", "3 days ago"
 */
function timeAgo(isoStr) {
  if (!isoStr) return 'Unknown time';
  const then = new Date(isoStr);
  const nowMs = Date.now();
  const diffMs = nowMs - then.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 2) return 'Just now';
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  // Fall back to locale date
  return then.toLocaleDateString('en-MY', { day: 'numeric', month: 'short', year: 'numeric' });
}

/**
 * Format a date string YYYY-MM-DD for display in the dropdown.
 */
function formatDateLabel(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  const isSameDay = (a, b) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();

  if (isSameDay(d, today)) return `Today — ${dateStr}`;
  if (isSameDay(d, yesterday)) return `Yesterday — ${dateStr}`;
  return d.toLocaleDateString('en-MY', {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
  });
}

/**
 * Escape text for safe HTML insertion.
 */
function esc(str) {
  return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/**
 * Highlight search terms in text (returns HTML string).
 */
function highlight(text, query) {
  if (!query || !text) return esc(text);
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const rx = new RegExp(`(${escaped})`, 'gi');
  return esc(text).replace(rx, '<mark class="highlight">$1</mark>');
}

/**
 * Set a CSS custom property on :root.
 */
function setCSSVar(name, value) {
  document.documentElement.style.setProperty(name, value);
}

// ── Data fetching ─────────────────────────────────────────────────────────────

async function fetchJSON(url) {
  const resp = await fetch(url, { cache: 'no-cache' });
  if (!resp.ok) throw new Error(`HTTP ${resp.status} for ${url}`);
  return resp.json();
}

// ── UI state helpers ──────────────────────────────────────────────────────────

function showLoading() {
  dom.loadingState.style.display = '';
  dom.emptyState.style.display = 'none';
  dom.errorState.style.display = 'none';
  dom.contentArea.style.display = 'none';
}

function showEmpty() {
  dom.loadingState.style.display = 'none';
  dom.emptyState.style.display = '';
  dom.errorState.style.display = 'none';
  dom.contentArea.style.display = 'none';
}

function showError(title, msg) {
  dom.loadingState.style.display = 'none';
  dom.emptyState.style.display = 'none';
  dom.errorState.style.display = '';
  dom.contentArea.style.display = 'none';
  $('errorTitle').textContent = title;
  $('errorMsg').textContent = msg;
}

function showContent() {
  dom.loadingState.style.display = 'none';
  dom.emptyState.style.display = 'none';
  dom.errorState.style.display = 'none';
  dom.contentArea.style.display = '';
}

// ── Sidebar rendering ─────────────────────────────────────────────────────────

function renderSidebar() {
  if (!state.data) return;
  const cats = state.data.categories || {};

  // Build category nav buttons
  const nav = dom.catNav;
  nav.innerHTML = '';

  const orderedKeys = CATEGORY_ORDER.filter(k => cats[k]);
  // Include any extra categories the scraper might have added
  Object.keys(cats).forEach(k => { if (!orderedKeys.includes(k)) orderedKeys.push(k); });

  orderedKeys.forEach(catId => {
    const cat = cats[catId];
    const btn = document.createElement('button');
    btn.className = 'cat-btn' + (catId === state.currentCat ? ' active' : '');
    btn.dataset.cat = catId;
    btn.style.setProperty('--cat-color', cat.color);
    btn.setAttribute('role', 'tab');
    btn.setAttribute('aria-selected', catId === state.currentCat ? 'true' : 'false');
    btn.innerHTML = `
      <span class="cat-icon">${cat.icon}</span>
      <span class="cat-label">${esc(cat.label)}</span>
      <span class="cat-count">${cat.article_count}</span>
    `;
    btn.addEventListener('click', () => switchCategory(catId));
    nav.appendChild(btn);
  });

  // Stats panel
  const totalArticles = Object.values(cats).reduce((s, c) => s + (c.article_count || 0), 0);
  dom.sidebarStats.innerHTML = `
    <div class="stat-row"><span>Date</span><span class="stat-value">${state.currentDate}</span></div>
    <div class="stat-row"><span>Total articles</span><span class="stat-value">${totalArticles}</span></div>
    <div class="stat-row"><span>Categories</span><span class="stat-value">${Object.keys(cats).length}</span></div>
  `;

  // Last updated
  const genAt = state.data.generated_at;
  if (genAt) {
    dom.lastUpdated.textContent = `Updated: ${timeAgo(genAt)}`;
  }
}

// ── Category switching ────────────────────────────────────────────────────────

function switchCategory(catId) {
  if (!state.data) return;
  const cats = state.data.categories || {};
  if (!cats[catId]) return;

  state.currentCat = catId;
  state.searchQuery = '';
  dom.searchInput.value = '';

  // Update active state in sidebar
  document.querySelectorAll('.cat-btn').forEach(btn => {
    const isActive = btn.dataset.cat === catId;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
    if (isActive) btn.style.setProperty('--cat-color', cats[catId].color);
  });

  // Update accent color globally
  setCSSVar('--cat-color', cats[catId].color);

  renderContent();
}

// ── Content rendering ─────────────────────────────────────────────────────────

function renderContent() {
  if (!state.data || !state.currentCat) return;
  const cat = (state.data.categories || {})[state.currentCat];
  if (!cat) return;

  showContent();

  // Briefing
  const briefingCard = dom.briefingCard;
  if (cat.briefing) {
    briefingCard.style.display = '';
    $('briefingLabel').textContent = cat.label;
    $('briefingText').textContent = cat.briefing;
  } else {
    briefingCard.style.display = 'none';
  }

  // Articles header
  $('articlesTitle').textContent = cat.label;

  // Apply search filter
  const q = state.searchQuery.trim().toLowerCase();
  const articles = (cat.articles || []).filter(a => {
    if (!q) return true;
    return (
      (a.title || '').toLowerCase().includes(q) ||
      (a.summary || '').toLowerCase().includes(q) ||
      (a.source || '').toLowerCase().includes(q)
    );
  });

  $('searchCount').textContent = q ? `${articles.length} results` : '';
  $('articlesCount').textContent = `${cat.article_count} articles`;

  const grid = dom.articleGrid;
  grid.innerHTML = '';

  if (articles.length === 0) {
    dom.noResults.style.display = '';
  } else {
    dom.noResults.style.display = 'none';
    articles.forEach(article => {
      grid.appendChild(buildArticleCard(article, q, cat.color));
    });
  }
}

// ── Article card builder ──────────────────────────────────────────────────────

function buildArticleCard(article, query, catColor) {
  const card = document.createElement('article');
  card.className = 'article-card';
  card.setAttribute('role', 'listitem');
  card.setAttribute('tabindex', '0');
  card.style.setProperty('--cat-color', catColor);

  const titleHtml = highlight(article.title, query);
  const summaryHtml = highlight(article.summary, query);
  const timeLabel = timeAgo(article.published);

  // Image section
  let imageHtml = '';
  if (article.image) {
    imageHtml = `
      <div class="card-image-wrap">
        <img class="card-image" src="${esc(article.image)}" alt="" loading="lazy"
             onerror="this.parentElement.innerHTML='<div class=\\'card-image-placeholder\\'>📄</div>'" />
        <span class="card-source-badge">${esc(article.source)}</span>
      </div>`;
  } else {
    imageHtml = `
      <div class="card-image-wrap">
        <div class="card-image-placeholder">📄</div>
        <span class="card-source-badge">${esc(article.source)}</span>
      </div>`;
  }

  card.innerHTML = `
    ${imageHtml}
    <div class="card-body">
      <div class="card-title">${titleHtml}</div>
      <div class="card-time">${esc(timeLabel)}</div>
      <div class="card-summary">${summaryHtml}</div>
      <div class="card-footer">
        <span class="card-read-more">Read more →</span>
      </div>
    </div>
  `;

  // Open modal on click / Enter key
  const openModal = () => showModal(article, catColor);
  card.addEventListener('click', openModal);
  card.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') openModal(); });

  return card;
}

// ── Modal ─────────────────────────────────────────────────────────────────────

function showModal(article, catColor) {
  setCSSVar('--cat-color', catColor);
  $('modalSource').textContent = article.source;
  $('modalTitle').textContent = article.title;
  $('modalMeta').textContent = article.published
    ? `Published: ${new Date(article.published).toLocaleString('en-MY', {
        dateStyle: 'medium', timeStyle: 'short',
      })}`
    : 'Date unknown';
  $('modalSummary').textContent = article.summary || 'No summary available.';
  $('modalLink').href = article.url;

  dom.modalBackdrop.style.display = '';
  dom.modal.querySelector('.modal-close').focus();
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  dom.modalBackdrop.style.display = 'none';
  document.body.style.overflow = '';
}

// ── Date picker ───────────────────────────────────────────────────────────────

function populateDatePicker(dates) {
  const sel = dom.datePicker;
  sel.innerHTML = '';
  if (!dates || dates.length === 0) {
    const opt = document.createElement('option');
    opt.textContent = 'No data available';
    sel.appendChild(opt);
    return;
  }
  dates.forEach(d => {
    const opt = document.createElement('option');
    opt.value = d;
    opt.textContent = formatDateLabel(d);
    sel.appendChild(opt);
  });
}

function updateNavButtons() {
  const dates = (state.index && state.index.dates) || [];
  const idx = dates.indexOf(state.currentDate);
  dom.btnPrevDay.disabled = idx >= dates.length - 1;
  dom.btnNextDay.disabled = idx <= 0;
}

// ── Load data ─────────────────────────────────────────────────────────────────

async function loadIndex() {
  try {
    state.index = await fetchJSON('data/index.json');
  } catch (e) {
    state.index = { dates: [], latest: null };
  }
}

async function loadData(dateStr) {
  state.currentDate = dateStr;
  dom.datePicker.value = dateStr;
  updateNavButtons();
  showLoading();

  try {
    state.data = await fetchJSON(`data/${dateStr}.json`);
  } catch (e) {
    showError(
      `No data for ${dateStr}`,
      'Either the scraper hasn\'t run yet for this date, or the file is missing. ' +
      'Run the scraper or check GitHub Actions.'
    );
    state.data = null;
    return;
  }

  // Choose first available category if not yet set
  const cats = Object.keys(state.data.categories || {});
  if (!state.currentCat || !cats.includes(state.currentCat)) {
    state.currentCat = cats[0] || '';
  }

  if (!state.currentCat) {
    showEmpty();
    return;
  }

  renderSidebar();
  setCSSVar('--cat-color', (state.data.categories[state.currentCat] || {}).color || '#4f46e5');
  renderContent();
}

// ── Search ────────────────────────────────────────────────────────────────────

function handleSearch(query) {
  state.searchQuery = query;
  renderContent();
}

// ── Initialisation ────────────────────────────────────────────────────────────

async function init() {
  // Cache DOM references
  dom = {
    loadingState: $('loadingState'),
    emptyState:   $('emptyState'),
    errorState:   $('errorState'),
    contentArea:  $('contentArea'),
    catNav:       $('catNav'),
    sidebarStats: $('sidebarStats'),
    lastUpdated:  $('lastUpdated'),
    datePicker:   $('datePicker'),
    btnPrevDay:   $('btnPrevDay'),
    btnNextDay:   $('btnNextDay'),
    btnToday:     $('btnToday'),
    btnRefresh:   $('btnRefresh'),
    searchInput:  $('searchInput'),
    briefingCard: $('briefingCard'),
    articleGrid:  $('articleGrid'),
    noResults:    $('noResults'),
    modalBackdrop:$('modalBackdrop'),
    modal:        document.querySelector('.modal'),
  };

  showLoading();

  // ── GitHub Actions link ────────────────────────────────────────────────────
  if (GITHUB_ACTIONS_URL) {
    const link = $('ghActionsLink');
    link.href = GITHUB_ACTIONS_URL;
    link.style.display = '';
  }

  // ── Load index ─────────────────────────────────────────────────────────────
  await loadIndex();
  const dates = (state.index && state.index.dates) || [];

  if (dates.length === 0) {
    showEmpty();
    return;
  }

  populateDatePicker(dates);

  // Load latest by default
  const defaultDate = state.index.latest || dates[0];
  await loadData(defaultDate);

  // ── Event listeners ────────────────────────────────────────────────────────

  // Date picker change
  dom.datePicker.addEventListener('change', e => {
    if (e.target.value) loadData(e.target.value);
  });

  // Prev / Next day navigation
  dom.btnPrevDay.addEventListener('click', () => {
    const dates = (state.index && state.index.dates) || [];
    const idx = dates.indexOf(state.currentDate);
    if (idx < dates.length - 1) loadData(dates[idx + 1]);
  });

  dom.btnNextDay.addEventListener('click', () => {
    const dates = (state.index && state.index.dates) || [];
    const idx = dates.indexOf(state.currentDate);
    if (idx > 0) loadData(dates[idx - 1]);
  });

  // Latest button
  dom.btnToday.addEventListener('click', () => {
    const dates = (state.index && state.index.dates) || [];
    if (dates.length) loadData(dates[0]);
  });

  // Refresh button (re-fetch current date)
  dom.btnRefresh.addEventListener('click', async () => {
    await loadIndex();
    const dates = (state.index && state.index.dates) || [];
    populateDatePicker(dates);
    if (state.currentDate) await loadData(state.currentDate);
  });

  // Search — debounced
  let searchTimeout;
  dom.searchInput.addEventListener('input', e => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => handleSearch(e.target.value), 250);
  });

  // Keyboard shortcut: / to focus search
  document.addEventListener('keydown', e => {
    if (e.key === '/' && document.activeElement !== dom.searchInput) {
      e.preventDefault();
      dom.searchInput.focus();
    }
    if (e.key === 'Escape') closeModal();
  });

  // Modal close
  $('modalClose').addEventListener('click', closeModal);
  dom.modalBackdrop.addEventListener('click', e => {
    if (e.target === dom.modalBackdrop) closeModal();
  });
}

// ── Boot ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
