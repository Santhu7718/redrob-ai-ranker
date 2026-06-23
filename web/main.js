/* ═══════════════════════════════════════════════════════════════
   REDROB AI RANKER — Main JavaScript
   Navbar scroll, mobile menu, counter animation, copy buttons,
   scroll reveal, intersection observers
   ═══════════════════════════════════════════════════════════════ */

// ─────────────────────────────────────────────────
// UPLOAD & SCORE — Multi-Format Interactive UI
// ─────────────────────────────────────────────────
(function initUploadScore() {
  const API_BASE = 'http://localhost:8765';

  // Supported extensions → human label
  const FORMATS = {
    '.jsonl': 'JSONL',
    '.json':  'JSON',
    '.csv':   'CSV',
    '.tsv':   'TSV',
    '.xlsx':  'Excel',
    '.xls':   'Excel 97',
    '.pdf':   'PDF',
    '.txt':   'Plain Text',
  };

  // Element refs
  const btnDefault      = document.getElementById('btnDefault');
  const btnUpload       = document.getElementById('btnUpload');
  const dropZoneWrapper = document.getElementById('dropZoneWrapper');
  const dropZone        = document.getElementById('dropZone');
  const fileInput       = document.getElementById('fileInput');
  const dropZoneIdle    = document.getElementById('dropZoneIdle');
  const dropZoneFile    = document.getElementById('dropZoneFile');
  const dzFileBadge     = document.getElementById('dzFileBadge');
  const selectedFileName  = document.getElementById('selectedFileName');
  const selectedFileSize  = document.getElementById('selectedFileSize');
  const selectedFileFormat = document.getElementById('selectedFileFormat');
  const clearFileBtn    = document.getElementById('clearFile');
  const startRankBtn    = document.getElementById('startRankBtn');
  const uploadAction    = document.getElementById('uploadAction');
  const progressPanel   = document.getElementById('progressPanel');
  const resultsPanel    = document.getElementById('resultsPanel');
  const errorPanel      = document.getElementById('errorPanel');
  const errorMsg        = document.getElementById('errorMsg');
  const retryBtn        = document.getElementById('retryBtn');

  // Progress
  const progressBarFill  = document.getElementById('progressBarFill');
  const progressBarTrack = document.getElementById('progressBarTrack');
  const progressPct      = document.getElementById('progressPct');
  const progressMessage  = document.getElementById('progressMessage');
  const liveScored       = document.getElementById('liveScored');
  const liveTotal        = document.getElementById('liveTotal');
  const liveElapsed      = document.getElementById('liveElapsed');

  // Results
  const sumTotal        = document.getElementById('sumTotal');
  const sumFreshers     = document.getElementById('sumFreshers');
  const sumAvgScore     = document.getElementById('sumAvgScore');
  const sumRuntime      = document.getElementById('sumRuntime');
  const downloadCsvBtn  = document.getElementById('downloadCsvBtn');
  const newRankBtn      = document.getElementById('newRankBtn');
  const candidateSearch = document.getElementById('candidateSearch');
  const resultsTableBody = document.getElementById('resultsTableBody');

  // State
  let currentSource = 'default';
  let currentFile   = null;
  let currentJobId  = null;
  let pollTimer     = null;
  let startTime     = null;
  let elapsedTimer  = null;
  let allResults    = [];
  let activeFilter  = 'all';

  const SIGNAL_COLORS = {
    skill:      '#f43f5e',
    career:     '#8b5cf6',
    experience: '#10b981',
    education:  '#d97706',
    behavioral: '#0ea5e9',
    location:   '#6b7280',
  };

  // ── Helpers ───────────────────────────────────────
  function getExt(filename) {
    const dot = filename.lastIndexOf('.');
    return dot >= 0 ? filename.slice(dot).toLowerCase() : '';
  }

  function isSupported(filename) {
    return getExt(filename) in FORMATS;
  }

  function formatLabel(filename) {
    return FORMATS[getExt(filename)] || getExt(filename).toUpperCase() || 'FILE';
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function escHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Source Selector ───────────────────────────────
  [btnDefault, btnUpload].forEach(btn => {
    btn?.addEventListener('click', () => {
      currentSource = btn.dataset.source;
      btnDefault.classList.toggle('source-btn--active', currentSource === 'default');
      btnDefault.setAttribute('aria-pressed', (currentSource === 'default').toString());
      btnUpload.classList.toggle('source-btn--active', currentSource === 'upload');
      btnUpload.setAttribute('aria-pressed', (currentSource === 'upload').toString());
      if (dropZoneWrapper) {
        dropZoneWrapper.style.display = currentSource === 'upload' ? 'block' : 'none';
        dropZoneWrapper.setAttribute('aria-hidden', (currentSource !== 'upload').toString());
      }
    });
  });

  // ── File Input ────────────────────────────────────
  fileInput?.addEventListener('change', e => {
    const file = e.target.files[0];
    if (file) {
      if (!isSupported(file.name)) {
        showFormatError(file.name);
        fileInput.value = '';
      } else {
        setFile(file);
      }
    }
  });

  // ── Drag & Drop ───────────────────────────────────
  dropZone?.addEventListener('dragover', e => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
  dropZone?.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone?.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (!file) return;
    if (!isSupported(file.name)) {
      showFormatError(file.name);
    } else {
      setFile(file);
    }
  });

  // Keyboard: activate drop zone with Enter/Space
  dropZone?.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput?.click();
    }
  });

  function showFormatError(filename) {
    const ext = getExt(filename) || '(unknown)';
    const supported = Object.keys(FORMATS).join(', ');
    showError(`Unsupported format: "${ext}"\n\nSupported formats: ${supported}`);
  }

  function setFile(file) {
    currentFile = file;
    const ext   = getExt(file.name);
    const label = formatLabel(file.name);

    dropZoneIdle.style.display = 'none';
    dropZoneFile.style.display = 'flex';

    // Update extension badge
    if (dzFileBadge) {
      dzFileBadge.textContent = ext;
      dzFileBadge.setAttribute('data-fmt', ext);
    }

    selectedFileName.textContent  = file.name;
    selectedFileSize.textContent  = formatBytes(file.size);
    if (selectedFileFormat) {
      selectedFileFormat.textContent = `${label} format · auto-parsed`;
    }
  }

  clearFileBtn?.addEventListener('click', e => {
    e.stopPropagation();
    currentFile = null;
    if (fileInput) fileInput.value = '';
    dropZoneIdle.style.display = 'block';
    dropZoneFile.style.display = 'none';
    if (dzFileBadge) {
      dzFileBadge.textContent = '.FILE';
      dzFileBadge.removeAttribute('data-fmt');
    }
    if (selectedFileFormat) selectedFileFormat.textContent = '';
  });

  // ── Start Ranking ─────────────────────────────────
  startRankBtn?.addEventListener('click', async () => {
    if (currentSource === 'upload' && !currentFile) {
      alert('Please select a candidates file first.');
      return;
    }
    await startRanking();
  });

  retryBtn?.addEventListener('click', () => showPanel('upload'));
  newRankBtn?.addEventListener('click', () => { clearRanking(); showPanel('upload'); });

  async function startRanking() {
    showPanel('progress');
    const fmtLabel = currentFile ? formatLabel(currentFile.name) : 'JSONL';
    updateProgress(0, `Connecting to server…`);
    startTime = Date.now();
    startElapsedTimer();

    const formData = new FormData();
    if (currentSource === 'default') {
      formData.append('use_default', 'true');
    } else {
      formData.append('file', currentFile);
    }

    try {
      const res = await fetch(`${API_BASE}/api/rank`, { method: 'POST', body: formData });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      const data = await res.json();
      currentJobId = data.job_id;
      pollProgress();
    } catch (e) {
      showError(`Could not reach server: ${e.message}\n\nMake sure python app.py is running at localhost:8765`);
    }
  }

  function pollProgress() {
    pollTimer = setInterval(async () => {
      if (!currentJobId) return;
      try {
        const res  = await fetch(`${API_BASE}/api/status/${currentJobId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        updateProgress(data.progress, data.message);
        if (data.total)  liveTotal.textContent  = data.total.toLocaleString();
        if (data.scored) liveScored.textContent = data.scored.toLocaleString();
        updateStageIndicator(data.status);

        if (data.status === 'done') {
          clearInterval(pollTimer);
          clearInterval(elapsedTimer);
          allResults = data.results.top100;
          renderResults(data.results);
          showPanel('results');
        } else if (data.status === 'error') {
          clearInterval(pollTimer);
          clearInterval(elapsedTimer);
          showError(data.error || 'An unknown error occurred.');
        }
      } catch (e) {
        clearInterval(pollTimer);
        clearInterval(elapsedTimer);
        showError(`Connection lost: ${e.message}`);
      }
    }, 1500);
  }

  function updateProgress(pct, msg) {
    const p = Math.min(100, Math.max(0, pct));
    if (progressBarFill)  progressBarFill.style.width = `${p}%`;
    if (progressBarTrack) progressBarTrack.setAttribute('aria-valuenow', p);
    if (progressPct)      progressPct.textContent = `${p}%`;
    if (msg && progressMessage) progressMessage.textContent = msg;
  }

  function updateStageIndicator(status) {
    const order = ['loading', 'parsing', 'scoring', 'ranking', 'done'];
    const idx   = order.indexOf(status);
    order.forEach((stage, i) => {
      const el = document.getElementById(`stage-${stage}`);
      if (!el) return;
      el.classList.remove('active', 'done');
      if (i < idx)     el.classList.add('done');
      else if (i === idx) el.classList.add('active');
    });
  }

  function startElapsedTimer() {
    clearInterval(elapsedTimer);
    elapsedTimer = setInterval(() => {
      const elapsed = Math.round((Date.now() - startTime) / 1000);
      if (liveElapsed) {
        liveElapsed.textContent = elapsed < 60
          ? `${elapsed}s`
          : `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`;
      }
    }, 1000);
  }

  // ── Render Results ────────────────────────────────
  function renderResults(data) {
    const stats = data.stats;
    if (sumTotal)    sumTotal.textContent    = stats.total_candidates.toLocaleString();
    if (sumFreshers) sumFreshers.textContent = `${stats.freshers_in_top100}/30`;
    if (sumAvgScore) sumAvgScore.textContent = stats.avg_score_top100.toFixed(4);
    if (sumRuntime) {
      const rt = stats.runtime_seconds;
      sumRuntime.textContent = rt < 60 ? `${rt}s` : `${Math.floor(rt / 60)}m ${Math.round(rt % 60)}s`;
    }
    renderTable(allResults);
  }

  function renderTable(rows) {
    if (!resultsTableBody) return;
    resultsTableBody.innerHTML = '';

    if (rows.length === 0) {
      resultsTableBody.innerHTML =
        '<tr class="no-results-row"><td colspan="7">No candidates match this filter.</td></tr>';
      return;
    }

    rows.forEach((r, idx) => {
      const tr   = document.createElement('tr');
      tr.dataset.index = idx;

      const rank       = allResults.indexOf(r) + 1;
      const badgeClass = rank <= 3 ? 'top3' : rank <= 10 ? 'top10' : '';
      const score      = r.final_score;
      const scoreColor = score >= 0.6 ? '#4ade80' : score >= 0.4 ? '#fbbf24' : '#f87171';
      const yoe        = typeof r.yoe === 'number' ? r.yoe : 0;

      tr.innerHTML = `
        <td class="col-rank"><div class="rank-badge ${badgeClass}">${rank}</div></td>
        <td class="col-name">
          <span class="cand-name">${escHtml(r.name || 'Unknown')}</span>
          <span class="cand-meta" title="${escHtml(r.title || '')} @ ${escHtml(r.company || '')}">
            ${escHtml(r.title || '—')} @ ${escHtml(r.company || '—')}
          </span>
          <span class="cand-id">${escHtml(r.candidate_id)}</span>
        </td>
        <td class="col-score">
          <div class="score-display">
            <span class="score-val" style="color:${scoreColor}">${score.toFixed(4)}</span>
            <div class="score-bar-mini">
              <div class="score-bar-mini-fill" style="width:${(score * 100).toFixed(1)}%;background:${scoreColor}"></div>
            </div>
          </div>
        </td>
        <td class="col-signals">${renderSignalBars(r)}</td>
        <td class="col-yoe" style="text-align:center;font-weight:600;color:${yoe <= 2 ? '#4ade80' : 'var(--color-neutral-300)'}">
          ${yoe.toFixed(1)}
        </td>
        <td class="col-track">
          <span class="track-badge ${r.track === 'fresher' ? 'track-fresher' : 'track-experienced'}">
            ${r.track === 'fresher' ? '🌱 Fresher' : '💼 Expert'}
          </span>
        </td>
        <td class="col-expand">
          <button class="expand-btn" aria-label="Toggle reasoning for ${escHtml(r.name || 'candidate')}" data-row="${idx}" aria-expanded="false">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
        </td>`;
      resultsTableBody.appendChild(tr);

      // Reasoning expand row
      const rr = document.createElement('tr');
      rr.className = 'reasoning-row';
      rr.dataset.forRow = idx;
      rr.innerHTML = `<td colspan="7"><div class="reasoning-text">${escHtml(r.reasoning || 'No reasoning available.')}</div></td>`;
      resultsTableBody.appendChild(rr);
    });

    // Delegate click for expand buttons (re-attach each render)
    resultsTableBody.onclick = e => {
      const btn = e.target.closest('.expand-btn');
      if (!btn) return;
      const rowIdx   = btn.dataset.row;
      const reasonRow = resultsTableBody.querySelector(`.reasoning-row[data-for-row="${rowIdx}"]`);
      if (reasonRow) {
        const visible = reasonRow.classList.toggle('visible');
        btn.classList.toggle('expanded', visible);
        btn.setAttribute('aria-expanded', visible.toString());
      }
    };
  }

  function renderSignalBars(r) {
    const signals = [
      { key: 'skill',      val: r.skill_score,      label: 'SK', color: SIGNAL_COLORS.skill },
      { key: 'career',     val: r.career_score,     label: 'CA', color: SIGNAL_COLORS.career },
      { key: 'experience', val: r.experience_score, label: 'EX', color: SIGNAL_COLORS.experience },
      { key: 'education',  val: r.education_score,  label: 'ED', color: SIGNAL_COLORS.education },
      { key: 'behavioral', val: r.behavioral_score, label: 'BH', color: SIGNAL_COLORS.behavioral },
      { key: 'location',   val: r.location_score,   label: 'LO', color: SIGNAL_COLORS.location },
    ];
    return `<div class="signal-bars">${signals.map(s => {
      const h = Math.max(2, Math.round((s.val || 0) * 20));
      return `<div class="signal-bar-wrap" title="${s.key}: ${(s.val || 0).toFixed(2)}">
        <div class="signal-bar" style="height:${h}px;background:${s.color};opacity:0.85"></div>
        <span class="signal-bar-label">${s.label}</span>
      </div>`;
    }).join('')}</div>`;
  }

  // ── Filter & Search ───────────────────────────────
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('filter-btn--active'));
      btn.classList.add('filter-btn--active');
      activeFilter = btn.dataset.filter;
      applyFilter();
    });
  });
  candidateSearch?.addEventListener('input', applyFilter);

  function applyFilter() {
    const q = (candidateSearch?.value || '').toLowerCase().trim();
    const filtered = allResults.filter(r => {
      const yoe = r.yoe ?? 99;
      const trackOk = activeFilter === 'all'
        || (activeFilter === 'fresher'     && yoe <= 2)
        || (activeFilter === 'experienced' && yoe > 2);
      if (!trackOk) return false;
      if (!q) return true;
      return [r.name, r.title, r.company, r.candidate_id]
        .some(v => (v || '').toLowerCase().includes(q));
    });
    renderTable(filtered);
  }

  // ── Download ──────────────────────────────────────
  downloadCsvBtn?.addEventListener('click', () => {
    if (!currentJobId) return;
    window.open(`${API_BASE}/api/download/${currentJobId}`, '_blank');
  });

  // ── UI State Machine ──────────────────────────────
  function showPanel(panel) {
    if (uploadAction)  uploadAction.style.display  = panel === 'upload'   ? 'block' : 'none';
    if (progressPanel) progressPanel.style.display = panel === 'progress' ? 'block' : 'none';
    if (resultsPanel)  resultsPanel.style.display  = panel === 'results'  ? 'block' : 'none';
    if (errorPanel)    errorPanel.style.display    = panel === 'error'    ? 'block' : 'none';
  }

  function showError(msg) {
    if (errorMsg) errorMsg.textContent = msg;
    showPanel('error');
  }

  function clearRanking() {
    clearInterval(pollTimer);
    clearInterval(elapsedTimer);
    currentJobId = null;
    allResults   = [];
    updateProgress(0, 'Initializing…');
    if (liveScored)  liveScored.textContent  = '0';
    if (liveTotal)   liveTotal.textContent   = '—';
    if (liveElapsed) liveElapsed.textContent = '0s';
    document.querySelectorAll('.progress-stage').forEach(s => s.classList.remove('active', 'done'));
  }

  showPanel('upload');
})();


(function initNavbar() {
  const navbar   = document.getElementById('navbar');
  const toggle   = document.getElementById('navToggle');
  const mobileMenu = document.getElementById('mobile-menu');
  let lastScroll = 0;

  function onScroll() {
    const currentScroll = window.scrollY;
    if (currentScroll > 40) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
    lastScroll = currentScroll;
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll(); // run once on load

  // Mobile menu toggle
  toggle?.addEventListener('click', () => {
    const isOpen = mobileMenu.classList.toggle('open');
    toggle.classList.toggle('open', isOpen);
    toggle.setAttribute('aria-expanded', isOpen.toString());
    mobileMenu.setAttribute('aria-hidden', (!isOpen).toString());
  });

  // Close mobile menu on link click
  document.querySelectorAll('.mobile-nav-link').forEach(link => {
    link.addEventListener('click', () => {
      mobileMenu.classList.remove('open');
      toggle.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
      mobileMenu.setAttribute('aria-hidden', 'true');
    });
  });

  // Smooth active state on nav links
  const navLinks = document.querySelectorAll('.nav-link:not(.nav-cta)');
  const sections = document.querySelectorAll('section[id]');

  const sectionObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = entry.target.id;
        navLinks.forEach(link => {
          const href = link.getAttribute('href');
          link.classList.toggle('active', href === `#${id}`);
        });
      }
    });
  }, { rootMargin: '-40% 0px -55% 0px', threshold: 0 });

  sections.forEach(s => sectionObserver.observe(s));
})();


// ─────────────────────────────────────────────────
// ANIMATED COUNTER
// ─────────────────────────────────────────────────
(function initCounters() {
  const TARGETS = {
    'counter-candidates': { target: 89788, suffix: 'K', divisor: 1000, decimals: 1 }
  };

  function animateCounter(el, target, suffix, divisor, decimals) {
    const duration = 2000;
    const startTime = performance.now();

    function easeOutExpo(t) {
      return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
    }

    function frame(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = easeOutExpo(progress);
      const currentVal = target * eased;

      if (divisor) {
        el.textContent = (currentVal / divisor).toFixed(decimals) + suffix;
      } else {
        el.textContent = Math.round(currentVal).toLocaleString();
      }

      if (progress < 1) {
        requestAnimationFrame(frame);
      }
    }

    requestAnimationFrame(frame);
  }

  const counterObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = entry.target.id;
        if (TARGETS[id]) {
          const { target, suffix = '', divisor, decimals = 0 } = TARGETS[id];
          animateCounter(entry.target, target, suffix, divisor, decimals);
          counterObserver.unobserve(entry.target);
        }
      }
    });
  }, { threshold: 0.5 });

  Object.keys(TARGETS).forEach(id => {
    const el = document.getElementById(id);
    if (el) counterObserver.observe(el);
  });
})();


// ─────────────────────────────────────────────────
// COPY BUTTON FUNCTIONALITY
// ─────────────────────────────────────────────────
(function initCopyButtons() {
  const toast = document.getElementById('toast');
  let toastTimer = null;

  function showToast() {
    toast.classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('visible'), 2500);
  }

  async function copyToClipboard(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        // Fallback for non-secure contexts
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
      }
      return true;
    } catch {
      return false;
    }
  }

  document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const text = btn.getAttribute('data-clipboard')
        .replace(/&#10;/g, '\n')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>');

      const success = await copyToClipboard(text);

      if (success) {
        const originalHTML = btn.innerHTML;
        btn.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          Copied!
        `;
        btn.classList.add('copied');
        showToast();

        setTimeout(() => {
          btn.innerHTML = originalHTML;
          btn.classList.remove('copied');
        }, 2000);
      }
    });
  });
})();


// ─────────────────────────────────────────────────
// SCROLL REVEAL ANIMATIONS
// ─────────────────────────────────────────────────
(function initScrollReveal() {
  // Automatically mark key elements for reveal
  const revealSelectors = [
    '.section-header',
    '.pipeline-step',
    '.score-card',
    '.run-step',
    '.perf-card',
    '.results-col',
    '.arch-grid',
    '.jd-card',
    '.weight-bar-container',
    '.cli-reference',
  ];

  const elements = document.querySelectorAll(revealSelectors.join(', '));

  elements.forEach((el, i) => {
    el.classList.add('reveal');
    // Stagger children of the same parent
    const siblings = el.parentElement?.querySelectorAll(revealSelectors.join(', '));
    if (siblings) {
      let idx = Array.from(siblings).indexOf(el);
      if (idx > 0 && idx <= 4) {
        el.classList.add(`reveal-delay-${idx}`);
      }
    }
  });

  const revealObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, {
    rootMargin: '0px 0px -60px 0px',
    threshold: 0.08
  });

  document.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));
})();


// ─────────────────────────────────────────────────
// SMOOTH SCROLL FOR ANCHOR LINKS
// ─────────────────────────────────────────────────
(function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const targetId = this.getAttribute('href').slice(1);
      const targetEl = document.getElementById(targetId);
      if (targetEl) {
        e.preventDefault();
        const navbarHeight = 72;
        const targetTop = targetEl.getBoundingClientRect().top + window.scrollY - navbarHeight - 16;
        window.scrollTo({ top: targetTop, behavior: 'smooth' });
      }
    });
  });
})();


// ─────────────────────────────────────────────────
// PIPELINE STEP HOVER INTERACTIONS
// ─────────────────────────────────────────────────
(function initPipelineInteractions() {
  const steps = document.querySelectorAll('.pipeline-step');
  steps.forEach((step, index) => {
    step.addEventListener('mouseenter', () => {
      steps.forEach((s, i) => {
        if (i !== index) s.style.opacity = '0.6';
      });
    });
    step.addEventListener('mouseleave', () => {
      steps.forEach(s => s.style.opacity = '1');
    });
  });
})();


// ─────────────────────────────────────────────────
// WEIGHT BAR ANIMATION
// ─────────────────────────────────────────────────
(function initWeightBar() {
  const bar = document.querySelector('.weight-bar');
  if (!bar) return;

  const originalWidths = [];
  const segments = bar.querySelectorAll('.weight-segment');

  segments.forEach(seg => {
    const w = seg.style.width;
    originalWidths.push(w);
    seg.style.width = '0';
    seg.style.overflow = 'hidden';
    seg.style.transition = 'width 1.2s cubic-bezier(0.4, 0, 0.2, 1)';
  });

  const barObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        segments.forEach((seg, i) => {
          setTimeout(() => {
            seg.style.width = originalWidths[i];
          }, i * 80);
        });
        barObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.3 });

  barObserver.observe(bar);
})();


// ─────────────────────────────────────────────────
// SCORE CARD NUMBER PULSE
// ─────────────────────────────────────────────────
(function initScoreCardPulse() {
  const cards = document.querySelectorAll('.score-card');
  cards.forEach(card => {
    const weightNum = card.querySelector('.weight-num');
    if (!weightNum) return;

    card.addEventListener('mouseenter', () => {
      weightNum.style.transition = 'transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)';
      weightNum.style.transform = 'scale(1.15)';
    });
    card.addEventListener('mouseleave', () => {
      weightNum.style.transform = 'scale(1)';
    });
  });
})();


// ─────────────────────────────────────────────────
// KEYBOARD NAVIGATION ENHANCEMENTS
// ─────────────────────────────────────────────────
(function initKeyboardNav() {
  // Trap focus in mobile menu when open
  const mobileMenu = document.getElementById('mobile-menu');
  const toggle     = document.getElementById('navToggle');

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && mobileMenu?.classList.contains('open')) {
      mobileMenu.classList.remove('open');
      toggle?.classList.remove('open');
      toggle?.setAttribute('aria-expanded', 'false');
      mobileMenu.setAttribute('aria-hidden', 'true');
      toggle?.focus();
    }
  });
})();


// ─────────────────────────────────────────────────
// PAGE LOAD ANIMATION
// ─────────────────────────────────────────────────
(function initPageLoad() {
  document.body.style.opacity = '0';
  window.addEventListener('load', () => {
    document.body.style.transition = 'opacity 0.4s ease';
    document.body.style.opacity = '1';
  });
  // Fallback in case load event already fired
  if (document.readyState === 'complete') {
    document.body.style.opacity = '1';
  }
})();


// ─────────────────────────────────────────────────
// PERFORMANCE HINT: Preload key sections
// ─────────────────────────────────────────────────
if ('requestIdleCallback' in window) {
  requestIdleCallback(() => {
    // Prefetch images or heavy sections when idle
    const images = document.querySelectorAll('img[loading="lazy"]');
    images.forEach(img => {
      const src = img.dataset.src;
      if (src) img.src = src;
    });
  });
}
