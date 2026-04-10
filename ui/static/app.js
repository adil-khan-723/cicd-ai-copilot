// ── Setup wizard ───────────────────────────────────────────────────────────

const overlay     = document.getElementById('setupOverlay');
const saveBtn     = document.getElementById('setupSaveBtn');
const skipBtn     = document.getElementById('setupSkipBtn');
const newProjBtn  = document.getElementById('newProjectBtn');
const repoChip    = document.getElementById('repoChip');
const setupError  = document.getElementById('setupError');

function showSetup() { overlay.classList.add('visible'); }
function hideSetup() { overlay.classList.remove('visible'); }

// Show on first visit if not configured
if (!localStorage.getItem('devops_ai_configured')) showSetup();

newProjBtn.addEventListener('click', showSetup);
repoChip.addEventListener('click', showSetup);
skipBtn.addEventListener('click', hideSetup);

saveBtn.addEventListener('click', async () => {
  const payload = {
    github_repo:   document.getElementById('in-repo').value.trim(),
    github_token:  document.getElementById('in-token').value.trim(),
    jenkins_url:   document.getElementById('in-jenkins-url').value.trim(),
    jenkins_user:  document.getElementById('in-jenkins-user').value.trim(),
    jenkins_token: document.getElementById('in-jenkins-token').value.trim(),
  };

  setupError.style.display = 'none';
  saveBtn.textContent = 'Saving…';
  saveBtn.disabled = true;

  try {
    const res  = await fetch('/api/setup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (res.ok && data.ok) {
      localStorage.setItem('devops_ai_configured', '1');
      document.getElementById('repoName').textContent =
        payload.github_repo.replace('/', ' / ');
      hideSetup();
      loadJobs();
    } else {
      setupError.textContent = data.detail || JSON.stringify(data);
      setupError.style.display = 'block';
    }
  } catch (e) {
    setupError.textContent = 'Network error: ' + e.message;
    setupError.style.display = 'block';
  } finally {
    saveBtn.textContent = 'Save & Launch Dashboard →';
    saveBtn.disabled = false;
  }
});

// ── Sidebar navigation ─────────────────────────────────────────────────────

const pipelinePanel = document.getElementById('pipelinePanel');
const chatPanel     = document.getElementById('chatPanel');
const jobsPanel     = document.getElementById('jobsPanel');

const navMap = {
  'nav-pipelines': () => { show(pipelinePanel); show(chatPanel); hide(jobsPanel); },
  'nav-chat':      () => { hide(pipelinePanel); show(chatPanel); hide(jobsPanel); },
  'nav-jobs':      () => { hide(pipelinePanel); hide(chatPanel); show(jobsPanel); loadJobs(); },
  'nav-audit':     () => { /* placeholder */ },
  'nav-settings':  () => showSetup(),
};

function show(el) { if (el) { el.style.display = 'flex'; } }
function hide(el) { if (el) { el.style.display = 'none'; } }

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const fn = navMap[btn.id];
    if (fn) fn();
  });
});

// ── Active failures counter ────────────────────────────────────────────────

let activeFailureCount = 0;

function incrementFailures() {
  activeFailureCount++;
  const badge = document.getElementById('failureBadge');
  const chip  = document.getElementById('attentionChip');
  const dot   = document.getElementById('failureDot');
  badge.textContent = activeFailureCount;
  badge.style.display = 'flex';
  chip.textContent = `${activeFailureCount} need attention`;
  chip.style.display = 'block';
  dot.style.display = 'block';
  document.getElementById('activeFailures').textContent = activeFailureCount;
}

function decrementFailures() {
  if (activeFailureCount > 0) activeFailureCount--;
  const badge = document.getElementById('failureBadge');
  const chip  = document.getElementById('attentionChip');
  const dot   = document.getElementById('failureDot');
  badge.textContent = activeFailureCount;
  if (activeFailureCount === 0) {
    badge.style.display = 'none';
    chip.style.display  = 'none';
    dot.style.display   = 'none';
  }
  document.getElementById('activeFailures').textContent = activeFailureCount;
}

// ── SSE — pipeline event feed ──────────────────────────────────────────────

const feedList  = document.getElementById('feedList');
const buildCards = {};   // "job#build" → { card, flow, lines, logSection, actionsEl }

const evtSource = new EventSource('/events');
evtSource.onmessage = e => handleEvent(JSON.parse(e.data));
evtSource.onerror   = () => console.warn('SSE disconnected — browser will auto-reconnect');

function handleEvent(ev) {
  const key = `${ev.job}#${ev.build}`;
  if (ev.type === 'step')             { ensureCard(key, ev.job, ev.build); appendStep(key, ev); }
  if (ev.type === 'analysis_complete'){ ensureCard(key, ev.job, ev.build); renderFixActions(key, ev); }
  if (ev.type === 'fix_result')       { updateAfterFix(key, ev); }
}

function ensureCard(key, job, build) {
  if (buildCards[key]) return;

  // Remove placeholder if present
  const placeholder = feedList.querySelector('[data-placeholder]');
  if (placeholder) placeholder.remove();

  const card = document.createElement('div');
  card.className = 'build-card active';
  card.dataset.key = key;
  card.innerHTML = `
    <div class="build-header">
      <div class="bh-dot run"></div>
      <div class="bh-job">${escHtml(job)}</div>
      <div class="bh-build">#${escHtml(String(build))} · RUNNING</div>
      <div class="bh-time">${timestamp()}</div>
    </div>
    <div class="stage-graph">
      <div class="stage-graph-label">Stage progression</div>
      <div class="stage-flow" id="flow-${key}"></div>
    </div>
    <div class="incr-log" id="log-${key}" style="display:none">
      <div class="incr-log-label">Live log</div>
      <div class="log-lines" id="lines-${key}"></div>
    </div>
    <div class="fix-actions" id="actions-${key}" style="display:none"></div>
  `;

  feedList.insertBefore(card, feedList.firstChild);
  buildCards[key] = {
    card,
    flow:       card.querySelector(`#flow-${key}`),
    logSection: card.querySelector(`#log-${key}`),
    lines:      card.querySelector(`#lines-${key}`),
    actionsEl:  card.querySelector(`#actions-${key}`),
  };

  incrementFailures();
}

function appendStep(key, ev) {
  const c = buildCards[key];
  if (!c) return;

  // Stage node
  const statusClass = ev.status === 'done' ? 'passed' : ev.status === 'fail' ? 'failed' : 'running';
  const icon        = ev.status === 'done' ? '✓'      : ev.status === 'fail' ? '✗'      : '…';
  const node = document.createElement('div');
  node.className = `stage-node ${statusClass}`;
  node.innerHTML = `
    <div class="stage-circle ${statusClass}">${icon}</div>
    <div class="stage-label ${statusClass}">${escHtml(ev.stage.replace(/_/g, ' '))}</div>
  `;
  c.flow.appendChild(node);

  // Log line
  if (ev.detail) {
    c.logSection.style.display = 'block';
    const line = document.createElement('div');
    line.className = ev.status === 'fail' ? 'll-fail' : ev.status === 'running' ? 'll-highlight' : 'll-pass';
    line.textContent = `+ [${ev.stage}] ${ev.detail}`;
    c.lines.appendChild(line);
    c.lines.scrollTop = c.lines.scrollHeight;
  }
}

function renderFixActions(key, ev) {
  const c = buildCards[key];
  if (!c) return;

  // Update header
  c.card.querySelector('.bh-dot').className   = 'bh-dot fail';
  c.card.querySelector('.bh-build').textContent = `#${ev.build} · FAILURE`;

  // Log the LLM result
  if (c.lines) {
    c.logSection.style.display = 'block';
    const line = document.createElement('div');
    line.className   = 'll-highlight';
    line.textContent = `→ LLM: ${ev.fix_type} · ${Math.round((ev.confidence || 0) * 100)}% confidence`;
    c.lines.appendChild(line);
    c.lines.scrollTop = c.lines.scrollHeight;
  }

  // Render buttons
  c.actionsEl.style.display = 'flex';
  const isDiagnostic = ev.fix_type === 'diagnostic_only' || (ev.confidence || 0) < 0.75;

  if (isDiagnostic) {
    c.actionsEl.innerHTML = `
      <button class="btn btn-diag" style="flex:2">Manual review required · ${escHtml(ev.fix_type || '')}</button>
    `;
  } else {
    c.actionsEl.innerHTML = `
      <button class="btn btn-apply" id="apply-${key}">Apply Fix · ${escHtml(ev.fix_type)}</button>
      <button class="btn btn-dismiss" id="dismiss-${key}">Dismiss</button>
    `;
    document.getElementById(`apply-${key}`).addEventListener('click', () =>
      applyFix(ev.job, String(ev.build), ev.fix_type, key));
    document.getElementById(`dismiss-${key}`).addEventListener('click', () =>
      dismissCard(key));
  }
}

async function applyFix(job, build, fixType, key) {
  const c = buildCards[key];
  if (!c) return;
  c.actionsEl.innerHTML = `<span style="font-family:var(--mono);font-size:10px;color:var(--text3)">Applying fix…</span>`;

  try {
    const res  = await fetch('/api/fix', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fix_type: fixType, job_name: job, build_number: build }),
    });
    const data = await res.json();

    c.actionsEl.innerHTML = data.success
      ? `<span style="font-family:var(--mono);font-size:10px;color:var(--green)">✓ Fix applied · ${escHtml(data.detail)}</span>`
      : `<span style="font-family:var(--mono);font-size:10px;color:var(--red)">✗ Failed · ${escHtml(data.detail)}</span>`;

    if (data.success) {
      decrementFailures();
      c.card.querySelector('.bh-dot').className = 'bh-dot ok';
      c.card.style.opacity = '0.6';
    }
  } catch (e) {
    c.actionsEl.innerHTML = `<span style="font-family:var(--mono);font-size:10px;color:var(--red)">✗ Network error: ${escHtml(e.message)}</span>`;
  }
}

function dismissCard(key) {
  const c = buildCards[key];
  if (!c) return;
  c.actionsEl.style.display = 'none';
  c.card.style.opacity = '0.35';
  decrementFailures();
}

function updateAfterFix(key, ev) {
  const c = buildCards[key];
  if (!c) return;
  c.card.querySelector('.bh-dot').className = ev.success ? 'bh-dot ok' : 'bh-dot fail';
}

// ── Agent chat ─────────────────────────────────────────────────────────────

const chatInput    = document.getElementById('chatInput');
const sendBtnEl    = document.getElementById('sendBtn');
const chatMessages = document.getElementById('chatMessages');

let pendingContent  = null;
let pendingPlatform = null;
let pendingDesc     = null;

sendBtnEl.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = '';

  appendUserBubble(text);
  const bubble = appendAgentBubble('');
  bubble.style.cssText = 'font-family:var(--mono);font-size:10px;color:var(--text3);display:flex;align-items:center;gap:6px';
  bubble.innerHTML = `<span>thinking</span><div class="tdot"></div><div class="tdot"></div><div class="tdot"></div>`;

  fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: text }),
  })
  .then(res => res.text())
  .then(responseText => {
    bubble.style.cssText = '';

    const isJenkins = responseText.includes('pipeline {') && responseText.includes('stages');
    const isGithub  = responseText.includes('on:') && responseText.includes('jobs:');
    const isCode    = isJenkins || isGithub;

    if (isCode) {
      pendingContent  = responseText;
      pendingPlatform = isJenkins ? 'jenkins' : 'github';
      pendingDesc     = text;
      const label     = isJenkins ? 'Jenkinsfile' : 'GitHub Actions workflow';
      bubble.innerHTML = `
        Here's your ${escHtml(label)}. Review it and approve to commit to your repo and apply to Jenkins.
        <div class="code-block"><pre style="margin:0;white-space:pre-wrap;overflow-x:auto">${escHtml(responseText)}</pre></div>
        <div class="msg-actions">
          <button class="msg-btn primary" id="approveBtn">Approve &amp; Commit + Apply to Jenkins</button>
          <button class="msg-btn secondary" id="cancelBtn">Cancel</button>
        </div>
      `;
      document.getElementById('approveBtn').addEventListener('click', approveAndCommit);
      document.getElementById('cancelBtn').addEventListener('click', () => {
        document.getElementById('approveBtn').closest('.msg-actions').remove();
        pendingContent = null;
      });
    } else {
      bubble.textContent = responseText;
    }
    chatMessages.scrollTop = chatMessages.scrollHeight;
  })
  .catch(err => { bubble.textContent = `Error: ${err.message}`; });
}

async function approveAndCommit() {
  if (!pendingContent) return;
  const sysMsg = appendSysEvent('committing to GitHub + applying to Jenkins…');

  try {
    const res  = await fetch('/api/commit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform:         pendingPlatform,
        content:          pendingContent,
        description:      pendingDesc,
        apply_to_jenkins: pendingPlatform === 'jenkins',
      }),
    });
    const data = await res.json();

    if (data.ok) {
      const jenkins = data.jenkins
        ? (data.jenkins.ok ? `Jenkins job updated (${data.jenkins.job})` : `Jenkins: ${data.jenkins.error}`)
        : 'Jenkins: skipped';
      sysMsg.innerHTML = `<span class="se-lbl">✓</span>Committed to <span style="color:var(--cyan)">${escHtml(data.file_path)}</span> · ${escHtml(jenkins)}`;
    } else {
      sysMsg.innerHTML = `<span class="se-lbl" style="color:var(--red)">✗</span>${escHtml(data.detail || 'Commit failed')}`;
    }
  } catch (e) {
    sysMsg.innerHTML = `<span class="se-lbl" style="color:var(--red)">✗</span>Network error: ${escHtml(e.message)}`;
  }

  pendingContent = null;
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendUserBubble(text) {
  const el = document.createElement('div');
  el.className = 'msg user';
  el.innerHTML = `
    <div class="msg-avatar user">A</div>
    <div class="msg-content">
      <div class="msg-label">YOU</div>
      <div class="msg-bubble">${escHtml(text)}</div>
    </div>
  `;
  chatMessages.appendChild(el);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendAgentBubble(text) {
  const el = document.createElement('div');
  el.className = 'msg';
  el.innerHTML = `
    <div class="msg-avatar agent">AI</div>
    <div class="msg-content">
      <div class="msg-label">AGENT</div>
      <div class="msg-bubble"></div>
    </div>
  `;
  chatMessages.appendChild(el);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  const bubble = el.querySelector('.msg-bubble');
  if (text) bubble.textContent = text;
  return bubble;
}

function appendSysEvent(text) {
  const el = document.createElement('div');
  el.className = 'sys-event';
  el.innerHTML = `<span class="se-lbl">→</span>${escHtml(text)}`;
  chatMessages.appendChild(el);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return el;
}

// ── Jenkins jobs tab ───────────────────────────────────────────────────────

let jobsLoaded = false;

async function loadJobs() {
  if (jobsLoaded) return;
  const list  = document.getElementById('jobsList');
  const count = document.getElementById('jobsCount');

  try {
    const res  = await fetch('/api/jobs');
    const jobs = await res.json();

    count.textContent = `${jobs.length} jobs`;

    if (jobs.length === 0) {
      list.innerHTML = `<div style="font-family:var(--mono);font-size:10px;color:var(--text3);padding:20px;text-align:center">No jobs found · check Jenkins connection</div>`;
      return;
    }

    const statusColor = { success: 'var(--green)', failure: 'var(--red)', running: 'var(--yellow)', unknown: 'var(--text3)' };

    list.innerHTML = jobs.map(job => `
      <div class="job-row">
        <div style="width:8px;height:8px;border-radius:50%;background:${statusColor[job.status] || 'var(--text3)'};flex-shrink:0"></div>
        <div class="job-name">${escHtml(job.name)}</div>
        <button class="job-run-btn" onclick="triggerJob('${escHtml(job.name)}')">▶ run</button>
      </div>
    `).join('');

    // Update Jenkins status in topbar
    document.getElementById('jenkinsStatus').textContent = 'online';
    document.getElementById('jenkinsDot').classList.remove('err');

    jobsLoaded = true;
  } catch (e) {
    count.textContent = 'error';
    list.innerHTML = `<div style="font-family:var(--mono);font-size:10px;color:var(--red);padding:20px;text-align:center">Failed to load jobs: ${escHtml(e.message)}</div>`;
    document.getElementById('jenkinsStatus').textContent = 'offline';
    document.getElementById('jenkinsDot').classList.add('err');
  }
}

async function triggerJob(jobName) {
  try {
    const res  = await fetch('/api/trigger', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_name: jobName }),
    });
    const data = await res.json();
    alert(data.ok ? `✓ Triggered ${jobName}` : `✗ Failed: ${data.error}`);
    jobsLoaded = false; // refresh on next open
  } catch (e) {
    alert(`Network error: ${e.message}`);
  }
}

// ── Utilities ──────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function timestamp() {
  return new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

// ── Init ───────────────────────────────────────────────────────────────────

// Load jobs silently on startup so topbar Jenkins status updates
if (localStorage.getItem('devops_ai_configured')) {
  loadJobs().catch(() => {});
}
