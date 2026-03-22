/* Sport-Suite Sentinel — Tabbed dashboard with visual elements */

const API_BASE = '';
const REFRESH_INTERVAL = 5000;

// --- Utility ---

function esc(str) {
    if (str == null) return '';
    const d = document.createElement('div');
    d.textContent = String(str);
    return d.innerHTML;
}

async function fetchJSON(url, options = {}) {
    try {
        const resp = await fetch(API_BASE + url, options);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.error(`Fetch error: ${url}`, err);
        return null;
    }
}

function badge(text, type) {
    return `<span class="badge badge-${type}">${text}</span>`;
}

function timeAgo(dateStr) {
    if (!dateStr) return '--';
    const raw = dateStr.endsWith('Z') ? dateStr : dateStr + 'Z';
    const d = new Date(raw);
    const now = new Date();
    const diffS = Math.floor((now - d) / 1000);
    if (diffS < 0) return 'just now';
    if (diffS < 60) return `${diffS}s ago`;
    if (diffS < 3600) return `${Math.floor(diffS / 60)}m ago`;
    if (diffS < 86400) return `${Math.floor(diffS / 3600)}h ago`;
    return `${Math.floor(diffS / 86400)}d ago`;
}

function severityBadge(severity) {
    const map = { critical: 'critical', high: 'critical', warning: 'warning', medium: 'warning', low: 'info', info: 'info' };
    return badge(severity, map[severity] || 'unknown');
}

function statusBadge(status) {
    const map = {
        healthy: 'healthy', running: 'running', success: 'success',
        warning: 'warning', detected: 'warning', investigating: 'warning',
        remediating: 'warning', critical: 'critical', failed: 'failed',
        error: 'critical', escalated: 'escalated',
        triggered: 'warning', down: 'critical', degraded: 'warning',
    };
    return badge(status, map[status] || 'unknown');
}

function fmtNum(v) {
    if (v == null) return '--';
    const n = parseFloat(v);
    if (isNaN(n)) return '--';
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return n % 1 === 0 ? n.toLocaleString() : n.toFixed(1);
}

// --- Tabs ---

let activeTab = localStorage.getItem('sentinel-tab') || 'overview';

function initTabs() {
    const bar = document.getElementById('tab-bar');
    const btns = bar.querySelectorAll('.tab-btn');
    const indicator = document.getElementById('tab-indicator');

    function activateTab(name) {
        activeTab = name;
        localStorage.setItem('sentinel-tab', name);

        btns.forEach(b => b.classList.toggle('active', b.dataset.tab === name));
        document.querySelectorAll('.tab-panel').forEach(p => {
            p.classList.toggle('active', p.id === `panel-${name}`);
        });

        const activeBtn = bar.querySelector(`.tab-btn[data-tab="${name}"]`);
        if (activeBtn && indicator) {
            indicator.style.left = activeBtn.offsetLeft + 'px';
            indicator.style.width = activeBtn.offsetWidth + 'px';
        }
    }

    btns.forEach(btn => {
        btn.addEventListener('click', () => activateTab(btn.dataset.tab));
    });

    activateTab(activeTab);

    window.addEventListener('resize', () => {
        const activeBtn = bar.querySelector(`.tab-btn[data-tab="${activeTab}"]`);
        if (activeBtn && indicator) {
            indicator.style.left = activeBtn.offsetLeft + 'px';
            indicator.style.width = activeBtn.offsetWidth + 'px';
        }
    });
}

// --- SVG Ring Gauges ---

function updateRing(containerId, percent, color) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const fill = container.querySelector('.ring-fill');
    if (!fill) return;

    const r = parseFloat(fill.getAttribute('r'));
    const circumference = 2 * Math.PI * r;
    const clamped = Math.max(0, Math.min(100, percent || 0));
    const offset = circumference - (clamped / 100) * circumference;

    fill.style.strokeDasharray = circumference;
    fill.style.strokeDashoffset = offset;
    fill.style.stroke = color || 'var(--green)';
}

function ringColor(percent, thresholds) {
    if (percent >= (thresholds?.critical || 90)) return 'var(--red)';
    if (percent >= (thresholds?.warning || 70)) return 'var(--yellow)';
    return 'var(--green)';
}

// --- Animated Value Count-up ---

const animatedValues = {};

function animateValue(el, to, duration) {
    if (!el) return;
    const display = el.textContent;
    const from = parseFloat(display) || 0;
    if (isNaN(to) || from === to) {
        el.textContent = isNaN(to) ? '--' : to;
        return;
    }

    const key = el.id || el.textContent;
    if (animatedValues[key]) cancelAnimationFrame(animatedValues[key]);

    const start = performance.now();
    const isInt = Number.isInteger(to);

    function step(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / (duration || 400), 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = from + (to - from) * eased;
        el.textContent = isInt ? Math.round(current) : current.toFixed(1);
        if (progress < 1) {
            animatedValues[key] = requestAnimationFrame(step);
        }
    }

    animatedValues[key] = requestAnimationFrame(step);
}

// --- Sparklines ---

const sparklineHistory = {
    cpu: [],
    memory: [],
    connections: [],
    locks: [],
    cache: [],
};

const SPARKLINE_MAX = 10;

function pushSparkline(key, value) {
    if (!sparklineHistory[key]) sparklineHistory[key] = [];
    sparklineHistory[key].push(value ?? 0);
    if (sparklineHistory[key].length > SPARKLINE_MAX) {
        sparklineHistory[key].shift();
    }
}

function renderSparkline(elementId, key, maxVal) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const data = sparklineHistory[key] || [];
    if (data.length === 0) { el.innerHTML = ''; return; }

    const peak = maxVal || Math.max(...data, 1);
    el.innerHTML = data.map((v, i) => {
        const h = Math.max(2, (v / peak) * 24);
        const opacity = i === data.length - 1 ? '1' : '0.4';
        return `<div class="sparkline-bar" style="height:${h}px;opacity:${opacity}"></div>`;
    }).join('');
}

// --- Validation Filter ---

let validationFilter = 'all';
let validationRulesData = [];

function initValidationFilters() {
    const container = document.getElementById('validation-filters');
    if (!container) return;

    container.addEventListener('click', (e) => {
        const pill = e.target.closest('.pill');
        if (!pill) return;

        container.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        validationFilter = pill.dataset.filter;
        renderValidationTable();
    });
}

function renderValidationTable() {
    const tbody = document.getElementById('validation-rules');
    if (!tbody) return;

    let filtered = validationRulesData;
    if (validationFilter === 'passed') filtered = filtered.filter(r => r.passed);
    if (validationFilter === 'failed') filtered = filtered.filter(r => !r.passed);

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No rules match filter</td></tr>`;
        return;
    }

    tbody.innerHTML = filtered.map((r, idx) => {
        const origIdx = validationRulesData.indexOf(r);
        return `
        <tr class="clickable" onclick="showRule(${origIdx})">
            <td>${esc(r.rule_name)}</td>
            <td>${esc(r.rule_type || '--')}</td>
            <td>${esc(r.table_name || '--')}</td>
            <td><span class="severity-dot ${r.severity || 'info'}"></span> ${esc(r.severity || '--')}</td>
            <td>${r.passed ? badge('PASS', 'success') : badge('FAIL', r.severity === 'critical' ? 'critical' : 'warning')}</td>
            <td style="font-family:var(--font-mono)">${r.violation_count ?? 0}</td>
        </tr>`;
    }).join('');
}

// --- Infrastructure vs Sport-Suite chaos split ---

const INFRA_SCENARIOS = new Set([
    'long_running_query', 'deadlock', 'data_corruption',
    'orphaned_records', 'job_failure', 'connection_flood',
]);

function isInfraScenario(name) {
    const key = (name || '').toLowerCase().replace(/[\s-]+/g, '_');
    for (const s of INFRA_SCENARIOS) {
        if (key.includes(s)) return true;
    }
    return !/(api_blackout|dag_overlap|feature_drift|conviction|line_ingestion|win_rate|prediction_stale)/i.test(name);
}

// --- Update Functions ---

function updateHealth(health) {
    const el = (id, val) => {
        const e = document.getElementById(id);
        if (e) e.textContent = val ?? '--';
    };

    const cpu = health.cpu_percent != null ? Math.round(health.cpu_percent) : null;
    const mem = health.memory_used_mb != null ? Math.round(health.memory_used_mb) : null;
    const memPct = (health.memory_total_mb > 0 && health.memory_used_mb != null)
        ? (health.memory_used_mb / health.memory_total_mb) * 100 : 0;
    const cacheHit = health.cache_hit_ratio != null ? Math.round(health.cache_hit_ratio) : null;

    // Animate values
    animateValue(document.getElementById('metric-cpu'), cpu, 400);
    animateValue(document.getElementById('metric-memory'), mem, 400);
    animateValue(document.getElementById('metric-cache'), cacheHit, 400);
    el('metric-connections', health.connection_count ?? '--');
    el('metric-locks', health.lock_wait_count ?? '--');

    // Update ring gauges
    updateRing('ring-cpu', cpu, ringColor(cpu || 0, { warning: 70, critical: 90 }));
    updateRing('ring-memory', memPct, ringColor(memPct, { warning: 75, critical: 90 }));
    // Cache hit: higher is better — green > 95, yellow > 80, red below
    const cacheColor = (cacheHit || 0) >= 95 ? 'var(--green)' : (cacheHit || 0) >= 80 ? 'var(--yellow)' : 'var(--red)';
    updateRing('ring-cache', cacheHit, cacheColor);

    // Status dot + text
    const dotEl = document.getElementById('status-dot');
    const textEl = document.getElementById('status-text');
    const st = health.status || 'unknown';
    if (dotEl) {
        dotEl.className = 'status-dot';
        if (['healthy', 'warning', 'critical'].includes(st)) dotEl.classList.add(st);
    }
    if (textEl) textEl.textContent = st.toUpperCase();

    // Card threshold coloring
    const applyThreshold = (cardId, val, warn, crit) => {
        const card = document.getElementById(cardId);
        if (!card) return;
        card.classList.remove('status-warning', 'status-critical');
        if (val >= crit) card.classList.add('status-critical');
        else if (val >= warn) card.classList.add('status-warning');
    };

    applyThreshold('card-cpu', cpu || 0, 70, 90);
    applyThreshold('card-memory', memPct, 75, 90);
    applyThreshold('card-locks', health.lock_wait_count || 0, 5, 15);

    // Sparklines
    pushSparkline('cpu', cpu);
    pushSparkline('memory', mem);
    pushSparkline('connections', health.connection_count);
    pushSparkline('locks', health.lock_wait_count);
    pushSparkline('cache', cacheHit);

    renderSparkline('sparkline-cpu', 'cpu', 100);
    renderSparkline('sparkline-memory', 'memory');
    renderSparkline('sparkline-connections', 'connections');
    renderSparkline('sparkline-locks', 'locks');
    renderSparkline('sparkline-cache', 'cache', 100);
}

function updateIncidents(open, recent) {
    const container = document.getElementById('incidents-list');
    const countEl = document.getElementById('incident-count');
    const headerCountEl = document.getElementById('header-incidents');
    if (!container) return;

    const trulyOpen = open.filter(i => !['resolved', 'escalated'].includes(i.status));

    if (countEl) {
        countEl.textContent = trulyOpen.length;
        countEl.className = trulyOpen.length === 0 ? 'count-badge zero' : 'count-badge';
    }
    if (headerCountEl) headerCountEl.textContent = trulyOpen.length;

    if (trulyOpen.length === 0 && recent.length === 0) {
        container.innerHTML = '<p class="empty-state">All clear — no open incidents</p>';
        return;
    }

    let items, heading = '';
    if (trulyOpen.length > 0) {
        items = trulyOpen;
    } else {
        items = recent.slice(0, 5);
        heading = '<p class="list-subheader">Recent (all resolved)</p>';
    }

    container.innerHTML = heading + items.map(i => `
        <div class="list-item clickable" onclick="showIncident(${i.id})">
            <span class="severity-dot ${i.severity || 'info'}"></span>
            <span class="item-title">${esc(i.title)}</span>
            ${severityBadge(i.severity)}
            ${statusBadge(i.status)}
            <span class="item-meta">${timeAgo(i.detected_at)}</span>
        </div>
    `).join('');
}

let jobsData = [];
let jobRunsData = [];

function updateJobs(jobs, runs) {
    jobsData = jobs;
    jobRunsData = runs;
    const jobsEl = document.getElementById('jobs-list');
    const runsEl = document.getElementById('job-runs-list');

    if (jobsEl) {
        if (jobs.length === 0) {
            jobsEl.innerHTML = '<p class="empty-state">No jobs configured</p>';
        } else {
            jobsEl.innerHTML = jobs.map((j, idx) => `
                <div class="list-item clickable" onclick="showJob(${idx})">
                    <span class="item-title">${esc(j.name)}</span>
                    <span class="item-meta">${esc(j.schedule)}</span>
                    ${j.enabled ? badge('ON', 'success') : badge('OFF', 'unknown')}
                </div>
            `).join('');
        }
    }

    if (runsEl) {
        if (runs.length === 0) {
            runsEl.innerHTML = '<p class="empty-state">No recent runs</p>';
        } else {
            runsEl.innerHTML = runs.map((r, idx) => `
                <div class="list-item clickable" onclick="showJobRun(${idx})">
                    <span class="item-title">${esc(r.job_name)}</span>
                    ${statusBadge(r.status)}
                    <span class="item-meta">${r.duration_ms != null ? r.duration_ms + 'ms' : '--'}</span>
                    <span class="item-meta">${timeAgo(r.started_at)}</span>
                </div>
            `).join('');
        }
    }
}

function updateValidation(scorecard) {
    const pctEl = document.getElementById('score-percent');
    const passedEl = document.getElementById('score-passed');
    const failedEl = document.getElementById('score-failed');
    const criticalEl = document.getElementById('score-critical');

    const scorePct = scorecard.score_percent ?? 0;
    animateValue(pctEl, scorePct, 600);
    if (passedEl) passedEl.textContent = scorecard.passed ?? 0;
    if (failedEl) failedEl.textContent = scorecard.failed ?? 0;
    if (criticalEl) criticalEl.textContent = scorecard.critical_failures ?? 0;

    const color = scorePct < 50 ? 'var(--red)' : scorePct < 80 ? 'var(--yellow)' : 'var(--green)';
    updateRing('ring-validation', scorePct, color);

    if (scorecard.rules) {
        validationRulesData = scorecard.rules;
        renderValidationTable();
    }
}

function updateChaos(scenarios) {
    const infraEl = document.getElementById('chaos-infra');
    const suiteEl = document.getElementById('chaos-sportsuite');
    if (!infraEl || !suiteEl) return;

    const infra = [];
    const suite = [];

    scenarios.forEach(s => {
        if (isInfraScenario(s.name)) infra.push(s);
        else suite.push(s);
    });

    const renderScenarios = (list) => {
        if (list.length === 0) return '<p class="empty-state">No scenarios</p>';
        return list.map(s => `
            <div class="scenario-item">
                <span class="severity-dot ${s.severity || 'info'}"></span>
                <span class="item-title">${esc(s.name)}</span>
                ${s.on_cooldown ? badge(`${s.cooldown_remaining_s}s`, 'cooldown') : ''}
                <button class="btn-trigger" ${s.on_cooldown ? 'disabled' : ''}
                        onclick="triggerChaos('${esc(s.name)}')">
                    Trigger
                </button>
            </div>
        `).join('');
    };

    infraEl.innerHTML = renderScenarios(infra);
    suiteEl.innerHTML = renderScenarios(suite);
}

function updatePostmortems(postmortems) {
    const containers = [
        document.getElementById('postmortems-list'),
        document.getElementById('chaos-postmortems'),
    ];

    const cleanSummary = (s) => (s || '').replace(/\*\*/g, '');

    const unique = [];
    const seen = new Set();
    for (const p of postmortems) {
        const key = p.incident_title || '';
        if (!seen.has(key)) {
            seen.add(key);
            unique.push({
                ...p,
                repeat_count: postmortems.filter(x => (x.incident_title || '') === key).length,
            });
        }
    }

    const html = unique.length === 0
        ? '<p class="empty-state">No postmortems yet</p>'
        : unique.map(p => `
            <div class="postmortem-item clickable" onclick="showIncident(${p.incident_id})">
                <div class="postmortem-stripe ${p.severity || 'info'}"></div>
                <div class="postmortem-content">
                    <div class="postmortem-header">
                        <strong>${esc(p.incident_title || 'Incident #' + p.incident_id)}</strong>
                        <span>
                            ${severityBadge(p.severity || 'info')}
                            ${p.repeat_count > 1 ? badge('x' + p.repeat_count, 'unknown') : ''}
                            <span class="item-meta">${timeAgo(p.generated_at)}</span>
                        </span>
                    </div>
                    <div class="postmortem-summary">${esc(cleanSummary(p.summary))}</div>
                </div>
            </div>
        `).join('');

    containers.forEach(c => { if (c) c.innerHTML = html; });
}

function updatePipeline(metrics) {
    const el = (id, val) => {
        const e = document.getElementById(id);
        if (e) e.textContent = val ?? '--';
    };

    const setBar = (id, pctVal, max) => {
        const bar = document.getElementById(id);
        if (bar) bar.style.width = Math.min(100, ((parseFloat(pctVal) || 0) / max) * 100) + '%';
    };

    // Data Quality tab metrics
    const winRate = parseFloat(metrics.win_rate_7d) || 0;
    el('metric-winrate', winRate ? winRate.toFixed(1) : '--');
    el('metric-predictions', fmtNum(metrics.predictions_today));
    el('metric-snapshots', fmtNum(metrics.line_snapshots_today));
    el('metric-drift', metrics.drift_alerts ?? 0);

    // Header win rate
    const headerWR = document.getElementById('header-winrate');
    if (headerWR) headerWR.textContent = winRate ? winRate.toFixed(1) + '%' : '--';

    // Progress bars in Data Quality tab
    setBar('bar-winrate', winRate, 100);
    setBar('bar-predictions', metrics.predictions_today, 100);
    setBar('bar-snapshots', metrics.line_snapshots_today, 15000);
    setBar('bar-drift', metrics.drift_alerts, 10);

    // Win rate color coding
    const wrCard = document.getElementById('card-winrate');
    if (wrCard) {
        wrCard.classList.remove('status-warning', 'status-critical');
        if (winRate > 0 && winRate <= 50) wrCard.classList.add('status-critical');
        else if (winRate > 0 && winRate <= 55) wrCard.classList.add('status-warning');
    }

    // Pipeline tab: stat cards
    el('metric-pl-winrate', winRate ? winRate.toFixed(1) : '--');
    el('metric-pl-predictions', fmtNum(metrics.predictions_today));
    el('metric-pl-snapshots', fmtNum(metrics.line_snapshots_today));
    setBar('bar-pl-winrate', winRate, 100);
    setBar('bar-pl-volume', metrics.line_snapshots_today, 15000);

    // Model versions
    const models = metrics.model_versions || [];
    el('metric-pl-models', models.length > 0 ? models.join(', ') : '--');
    setBar('bar-pl-models', models.length, 4);

    // API health
    const apiStatus = metrics.api_status || [];
    const healthyAPIs = apiStatus.filter(a => a.status === 'healthy').length;
    const totalAPIs = apiStatus.length || 0;
    el('metric-pl-api-status', totalAPIs > 0 ? `${healthyAPIs}/${totalAPIs}` : '--');
    const avgLatency = metrics.avg_api_response_ms;
    el('metric-pl-latency', avgLatency != null ? Math.round(avgLatency) : '--');
    setBar('bar-pl-latency', avgLatency, 10000);

    // Win rate card color
    const plWrCard = document.getElementById('card-pl-winrate');
    if (plWrCard) {
        plWrCard.classList.remove('card--accent-green', 'card--accent-yellow', 'card--accent-red');
        if (winRate > 55) plWrCard.classList.add('card--accent-green');
        else if (winRate > 50) plWrCard.classList.add('card--accent-yellow');
        else if (winRate > 0) plWrCard.classList.add('card--accent-red');
        else plWrCard.classList.add('card--accent-green');
    }

    setBar('bar-pl-winrate', winRate, 100);

    // Conviction distribution
    const conv = metrics.conviction_distribution || {};
    const convTotal = (conv.LOCKED || 0) + (conv.STRONG || 0) + (conv.WATCH || 0) + (conv.SKIP || 0);

    const setConv = (key, id) => {
        const val = conv[key] || 0;
        el(`${id}-val`, val);
        const bar = document.getElementById(id);
        if (bar) bar.style.width = (convTotal > 0 ? (val / convTotal) * 100 : 0) + '%';
    };

    setConv('LOCKED', 'conv-locked');
    setConv('STRONG', 'conv-strong');
    setConv('WATCH', 'conv-watch');
    setConv('SKIP', 'conv-skip');

    // Pipeline runs list
    const runsEl = document.getElementById('pipeline-runs-list');
    const runs = metrics.latest_pipeline_runs || [];
    if (runsEl) {
        if (runs.length === 0) {
            runsEl.innerHTML = '<p class="empty-state">No pipeline runs</p>';
        } else {
            runsEl.innerHTML = runs.map(r => `
                <div class="list-item">
                    <span class="item-title">${esc(r.dag_name)}</span>
                    ${statusBadge(r.status)}
                    <span class="item-meta">${r.predictions_generated != null ? r.predictions_generated + ' preds' : ''}</span>
                    <span class="item-meta">${timeAgo(r.started_at)}</span>
                </div>
            `).join('');
        }
    }
}

// --- SLA ---

async function refreshSLA() {
    const data = await fetchJSON('/api/incidents/metrics/sla');
    if (!data) return;

    const el = (id, val) => {
        const e = document.getElementById(id);
        if (e) e.textContent = val ?? '--';
    };

    el('sla-total', data.total_incidents);
    el('sla-resolved', data.resolved_count);
    el('sla-escalated', data.escalated_count);
    el('sla-mttr', data.avg_resolution_minutes != null
        ? data.avg_resolution_minutes.toFixed(1) + 'm' : '--');
    el('sla-compliance', data.sla_compliance_rate != null
        ? data.sla_compliance_rate.toFixed(0) + '%' : '--');
    el('sla-auto-rate', data.auto_remediation_rate != null
        ? data.auto_remediation_rate.toFixed(0) + '%' : '--');

    const complianceBar = document.getElementById('sla-compliance-bar');
    if (complianceBar && data.sla_compliance_rate != null) {
        complianceBar.style.width = Math.min(100, data.sla_compliance_rate) + '%';
    }

    const headerSla = document.getElementById('header-sla');
    if (headerSla) {
        headerSla.textContent = data.sla_compliance_rate != null
            ? data.sla_compliance_rate.toFixed(0) + '%' : '--';
    }
}

// --- Detail Modals ---

function showRule(index) {
    const r = validationRulesData[index];
    if (!r) return;

    const modal = document.getElementById('incident-modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    const actions = document.getElementById('modal-actions');

    let samples = '';
    if (r.sample_values) {
        try {
            const parsed = JSON.parse(r.sample_values);
            if (Array.isArray(parsed) && parsed.length > 0) {
                samples = `<div class="detail-row full">
                    <span class="detail-label">Sample Violations</span>
                    <span class="detail-value mono">${parsed.map(v => esc(String(v))).join(', ')}</span>
                </div>`;
            }
        } catch (_) {}
    }

    title.textContent = `Rule: ${r.rule_name}`;
    body.innerHTML = `
        <div class="detail-grid">
            <div class="detail-row">
                <span class="detail-label">Status</span>
                <span class="detail-value">${r.passed ? badge('PASS', 'success') : badge('FAIL', r.severity === 'critical' ? 'critical' : 'warning')}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Rule Type</span>
                <span class="detail-value">${esc(r.rule_type || '--')}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Table</span>
                <span class="detail-value mono">${esc(r.table_name || '--')}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Column</span>
                <span class="detail-value mono">${esc(r.column_name || '--')}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Severity</span>
                <span class="detail-value">${severityBadge(r.severity || 'info')}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Violations</span>
                <span class="detail-value mono">${r.violation_count ?? 0}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Last Run</span>
                <span class="detail-value">${timeAgo(r.executed_at)}</span>
            </div>
            ${r.description ? `<div class="detail-row full">
                <span class="detail-label">Description</span>
                <span class="detail-value">${esc(r.description)}</span>
            </div>` : ''}
            ${samples}
        </div>
    `;
    actions.innerHTML = '<button class="btn" onclick="document.getElementById(\'incident-modal\').classList.remove(\'active\')">Close</button>';
    modal.classList.add('active');
}

function showJob(index) {
    const j = jobsData[index];
    if (!j) return;

    const modal = document.getElementById('incident-modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    const actions = document.getElementById('modal-actions');

    const runs = jobRunsData.filter(r => r.job_name === j.name);
    const runRows = runs.length === 0
        ? '<p class="empty-state">No recent runs</p>'
        : runs.map(r => `
            <div class="list-item" style="padding:6px 0">
                ${statusBadge(r.status)}
                <span class="item-meta">${r.duration_ms != null ? r.duration_ms + 'ms' : '--'}</span>
                <span class="item-meta">${timeAgo(r.started_at)}</span>
                ${r.error_message ? `<span style="color:var(--red);font-size:var(--font-size-sm)">${esc(r.error_message).substring(0, 60)}</span>` : ''}
            </div>
        `).join('');

    title.textContent = `Job: ${j.name}`;
    body.innerHTML = `
        <div class="detail-grid">
            <div class="detail-row">
                <span class="detail-label">Status</span>
                <span class="detail-value">${j.enabled ? badge('ENABLED', 'success') : badge('DISABLED', 'unknown')}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Schedule</span>
                <span class="detail-value mono">${esc(j.schedule)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Last Run</span>
                <span class="detail-value">${j.last_run ? timeAgo(j.last_run) : 'Never'}</span>
            </div>
            ${j.description ? `<div class="detail-row full">
                <span class="detail-label">Description</span>
                <span class="detail-value">${esc(j.description)}</span>
            </div>` : ''}
            <div class="detail-row full" style="margin-top:8px">
                <span class="detail-label">Recent Runs</span>
                <div style="width:100%">${runRows}</div>
            </div>
        </div>
    `;
    actions.innerHTML = `
        <button class="btn" onclick="triggerJob('${esc(j.name)}')">Trigger Now</button>
        <button class="btn" onclick="document.getElementById('incident-modal').classList.remove('active')">Close</button>
    `;
    modal.classList.add('active');
}

function showJobRun(index) {
    const r = jobRunsData[index];
    if (!r) return;

    const modal = document.getElementById('incident-modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    const actions = document.getElementById('modal-actions');

    title.textContent = `Job Run: ${r.job_name}`;
    body.innerHTML = `
        <div class="detail-grid">
            <div class="detail-row">
                <span class="detail-label">Status</span>
                <span class="detail-value">${statusBadge(r.status)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Duration</span>
                <span class="detail-value mono">${r.duration_ms != null ? r.duration_ms + 'ms' : '--'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Started</span>
                <span class="detail-value">${timeAgo(r.started_at)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Completed</span>
                <span class="detail-value">${r.completed_at ? timeAgo(r.completed_at) : 'Running...'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Rows Affected</span>
                <span class="detail-value mono">${r.rows_affected ?? '--'}</span>
            </div>
            ${r.error_message ? `<div class="detail-row full">
                <span class="detail-label">Error</span>
                <span class="detail-value" style="color:var(--red);font-family:var(--font-mono);font-size:var(--font-size-sm);white-space:pre-wrap">${esc(r.error_message)}</span>
            </div>` : ''}
        </div>
    `;
    actions.innerHTML = '<button class="btn" onclick="document.getElementById(\'incident-modal\').classList.remove(\'active\')">Close</button>';
    modal.classList.add('active');
}

async function triggerJob(name) {
    const btn = event.target;
    btn.textContent = 'Running...';
    btn.disabled = true;
    await fetchJSON('/api/jobs/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_name: name }),
    });
    document.getElementById('incident-modal').classList.remove('active');
    refreshDashboard();
}

// --- Actions ---

async function triggerChaos(name) {
    const result = await fetchJSON('/api/chaos/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: name }),
    });
    if (result) refreshDashboard();
}

async function triggerRandomChaos() {
    const result = await fetchJSON('/api/chaos/random', { method: 'POST' });
    if (result) refreshDashboard();
}

async function runValidation() {
    const btn = document.querySelector('[onclick="runValidation()"]');
    if (btn) { btn.textContent = 'Running...'; btn.disabled = true; }
    await fetchJSON('/api/validation/run', { method: 'POST' });
    if (btn) { btn.textContent = 'Run Now'; btn.disabled = false; }
    refreshDashboard();
}

async function showIncident(id) {
    const data = await fetchJSON(`/api/incidents/${id}`);
    if (!data) return;

    const modal = document.getElementById('incident-modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    const actions = document.getElementById('modal-actions');

    title.textContent = `Incident #${data.id}`;
    body.innerHTML = `
        <div class="detail-grid">
            <div class="detail-row">
                <span class="detail-label">Title</span>
                <span class="detail-value">${esc(data.title)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Type</span>
                <span class="detail-value">${esc(data.incident_type)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Severity</span>
                <span class="detail-value">${severityBadge(data.severity)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Status</span>
                <span class="detail-value">${statusBadge(data.status)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Detected</span>
                <span class="detail-value">${timeAgo(data.detected_at)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Resolved</span>
                <span class="detail-value">${data.resolved_at ? timeAgo(data.resolved_at) + ' by ' + esc(data.resolved_by || 'unknown') : 'Not yet'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Dedup Key</span>
                <span class="detail-value mono">${esc(data.dedup_key || '--')}</span>
            </div>
            ${data.description ? `<div class="detail-row full">
                <span class="detail-label">Description</span>
                <span class="detail-value">${esc(data.description)}</span>
            </div>` : ''}
        </div>
    `;

    const canRemediate = ['detected', 'investigating', 'escalated'].includes(data.status);
    const canAck = data.status === 'detected';
    actions.innerHTML = `
        ${canAck ? `<button class="btn" onclick="ackIncident(${data.id})">Acknowledge</button>` : ''}
        ${canRemediate ? `<button class="btn btn-danger" onclick="remediateIncident(${data.id})">Remediate</button>` : ''}
        <button class="btn" onclick="viewPostmortem(${data.id})">Postmortem</button>
    `;

    modal.classList.add('active');
}

function closeModal(event) {
    if (event.target.classList.contains('modal-overlay')) {
        event.target.classList.remove('active');
    }
}

async function ackIncident(id) {
    await fetchJSON(`/api/incidents/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'investigating' }),
    });
    document.getElementById('incident-modal').classList.remove('active');
    refreshDashboard();
}

async function remediateIncident(id) {
    await fetchJSON(`/api/incidents/${id}/remediate`, { method: 'POST' });
    document.getElementById('incident-modal').classList.remove('active');
    refreshDashboard();
}

async function viewPostmortem(id) {
    const data = await fetchJSON(`/api/incidents/${id}/postmortem`);
    const body = document.getElementById('modal-body');
    const title = document.getElementById('modal-title');
    const actions = document.getElementById('modal-actions');

    if (!data || data.detail) {
        body.innerHTML = '<p class="empty-state">No postmortem available for this incident.</p>';
        title.textContent = `Postmortem — Incident #${id}`;
        actions.innerHTML = `<button class="btn" onclick="showIncident(${id})">Back</button>`;
        return;
    }

    title.textContent = `Postmortem — Incident #${id}`;
    body.innerHTML = `
        <div class="detail-grid">
            <div class="detail-row full">
                <span class="detail-label">Summary</span>
                <span class="detail-value">${esc(data.summary || '--')}</span>
            </div>
            <div class="detail-row full">
                <span class="detail-label">Root Cause</span>
                <span class="detail-value">${esc(data.root_cause || '--')}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Impact Duration</span>
                <span class="detail-value">${data.impact_duration_minutes ? data.impact_duration_minutes + ' min' : '--'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Generated</span>
                <span class="detail-value">${timeAgo(data.generated_at)}</span>
            </div>
        </div>
    `;
    actions.innerHTML = `<button class="btn" onclick="showIncident(${id})">Back</button>`;
}

// --- Refresh Liveness Indicator ---

function signalRefresh() {
    const ts = document.getElementById('last-updated');
    const panel = document.getElementById(`panel-${activeTab}`);

    const cards = panel
        ? panel.querySelectorAll('.card, .healthcare-metric-card')
        : [];
    const vals = panel
        ? panel.querySelectorAll('.metric-value, .hm-value, .sla-value, .bar-value, .ring-value')
        : [];

    if (ts) ts.classList.remove('ts-flash');
    cards.forEach(el => el.classList.remove('refresh-pulse'));
    vals.forEach(el => el.classList.remove('val-blink'));

    void document.body.offsetWidth;

    if (ts) ts.classList.add('ts-flash');
    cards.forEach(el => el.classList.add('refresh-pulse'));
    vals.forEach(el => el.classList.add('val-blink'));
}

// --- Main Refresh Loop ---

async function refreshDashboard() {
    const spinner = document.getElementById('refresh-spinner');
    if (spinner) spinner.classList.add('active');

    const data = await fetchJSON('/api/dashboard');

    if (spinner) spinner.classList.remove('active');
    if (!data) return;

    updateHealth(data.health || {});
    updateIncidents(data.open_incidents || [], data.recent_incidents || []);
    updateJobs(data.jobs || [], data.recent_job_runs || []);
    updateValidation(data.validation || {});
    updateChaos(data.chaos_scenarios || []);
    updatePipeline(data.pipeline || {});
    updatePostmortems(data.postmortems || []);

    document.getElementById('last-updated').textContent =
        new Date().toLocaleTimeString();

    signalRefresh();
}

// --- Init ---

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initValidationFilters();
    refreshDashboard();
    refreshSLA();
    setInterval(refreshDashboard, REFRESH_INTERVAL);
    setInterval(refreshSLA, 30000);
});
