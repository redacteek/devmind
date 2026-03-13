#!/usr/bin/env python3
"""
DevMind v2 — GitHub Repository Explainer
Configure your API key below, then run: python github_explainer_v2.py
"""

# ─────────────────────────────────────────
#   CONFIGURATION — edit this section
# ─────────────────────────────────────────
ANTHROPIC_API_KEY = "sk-ant-YOUR-KEY-HERE"
PORT = 5000
MAX_FILES_DEFAULT = 15
# ─────────────────────────────────────────

import os
import re
import base64
import json
import threading
import webbrowser

import anthropic
import requests
from flask import Flask, render_template_string, request, Response, stream_with_context

app = Flask(__name__)

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DevMind — Repo Explainer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg:        #080b10;
      --surface:   #0d1117;
      --panel:     #111620;
      --border:    #1e2733;
      --border2:   #263040;
      --accent:    #3b82f6;
      --accent2:   #6366f1;
      --green:     #22c55e;
      --red:       #ef4444;
      --yellow:    #f59e0b;
      --text:      #e2e8f0;
      --muted:     #64748b;
      --muted2:    #94a3b8;
      --mono:      'JetBrains Mono', monospace;
      --sans:      'Inter', sans-serif;
    }

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: var(--sans);
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      overflow-x: hidden;
    }

    /* ── Grid noise overlay ── */
    body::before {
      content: '';
      position: fixed; inset: 0;
      background-image:
        linear-gradient(rgba(59,130,246,.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(59,130,246,.03) 1px, transparent 1px);
      background-size: 40px 40px;
      pointer-events: none;
      z-index: 0;
    }

    /* ── Top bar ── */
    .topbar {
      position: sticky; top: 0; z-index: 100;
      display: flex; align-items: center; justify-content: space-between;
      padding: 0 28px;
      height: 56px;
      background: rgba(8,11,16,.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
    }
    .logo {
      display: flex; align-items: center; gap: 10px;
      font-weight: 700; font-size: 1rem; letter-spacing: -.3px;
    }
    .logo-icon {
      width: 28px; height: 28px; border-radius: 7px;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      display: flex; align-items: center; justify-content: center;
      font-size: 14px;
    }
    .logo-version {
      font-family: var(--mono); font-size: .65rem; color: var(--accent);
      background: rgba(59,130,246,.1); border: 1px solid rgba(59,130,246,.2);
      padding: 2px 7px; border-radius: 4px;
    }
    .topbar-right { display: flex; align-items: center; gap: 12px; }
    .status-dot {
      width: 7px; height: 7px; border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 6px var(--green);
      animation: pulse-dot 2s ease-in-out infinite;
    }
    @keyframes pulse-dot {
      0%,100% { opacity: 1; } 50% { opacity: .4; }
    }
    .topbar-label { font-size: .75rem; color: var(--muted); }

    /* ── Main layout: two columns ── */
    .layout {
      position: relative; z-index: 1;
      display: grid;
      grid-template-columns: 380px 1fr;
      gap: 0;
      min-height: calc(100vh - 56px);
    }

    /* ── Left panel ── */
    .left-panel {
      background: var(--panel);
      border-right: 1px solid var(--border);
      padding: 28px 24px;
      display: flex; flex-direction: column; gap: 20px;
    }

    .section-label {
      font-size: .68rem; font-weight: 600; letter-spacing: .1em;
      text-transform: uppercase; color: var(--muted);
      margin-bottom: 10px;
    }

    .input-group { display: flex; flex-direction: column; gap: 6px; }
    .input-label {
      font-size: .78rem; color: var(--muted2); font-weight: 500;
      display: flex; align-items: center; gap: 6px;
    }
    .input-label .icon { font-size: .9rem; }

    input[type="text"], input[type="number"] {
      width: 100%;
      padding: 10px 14px;
      background: var(--surface);
      border: 1px solid var(--border2);
      border-radius: 8px;
      color: var(--text);
      font-family: var(--mono); font-size: .82rem;
      transition: border-color .15s, box-shadow .15s;
      outline: none;
    }
    input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(59,130,246,.12);
    }
    input::placeholder { color: var(--muted); }

    /* Number input width */
    input[type="number"] { max-width: 100px; }

    .divider {
      height: 1px; background: var(--border); margin: 4px 0;
    }

    /* ── Analyze button ── */
    .btn-analyze {
      display: flex; align-items: center; justify-content: center; gap: 8px;
      width: 100%; padding: 12px 20px;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      border: none; border-radius: 10px;
      color: #fff; font-family: var(--sans); font-size: .9rem; font-weight: 600;
      cursor: pointer;
      transition: opacity .15s, transform .1s, box-shadow .15s;
      box-shadow: 0 4px 20px rgba(59,130,246,.25);
    }
    .btn-analyze:hover:not(:disabled) {
      opacity: .9;
      box-shadow: 0 6px 28px rgba(59,130,246,.4);
    }
    .btn-analyze:active:not(:disabled) { transform: scale(.98); }
    .btn-analyze:disabled {
      background: var(--border2); box-shadow: none; cursor: not-allowed; color: var(--muted);
    }

    /* ── File stats ── */
    .stats-row {
      display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
    }
    .stat-card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 8px; padding: 12px 14px;
    }
    .stat-value {
      font-family: var(--mono); font-size: 1.3rem; font-weight: 600;
      color: var(--accent);
    }
    .stat-label { font-size: .72rem; color: var(--muted); margin-top: 2px; }

    /* ── File list ── */
    .file-list {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 8px; overflow: hidden; flex: 1;
    }
    .file-list-header {
      padding: 10px 14px;
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      font-size: .72rem; color: var(--muted); font-weight: 500;
      display: flex; align-items: center; gap: 6px;
    }
    .file-items {
      max-height: 260px; overflow-y: auto;
      padding: 6px;
    }
    .file-items::-webkit-scrollbar { width: 4px; }
    .file-items::-webkit-scrollbar-track { background: transparent; }
    .file-items::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }
    .file-item {
      display: flex; align-items: center; gap: 8px;
      padding: 5px 8px; border-radius: 5px;
      font-family: var(--mono); font-size: .72rem; color: var(--muted2);
      transition: background .1s;
    }
    .file-item:hover { background: var(--panel); }
    .file-item .dot {
      width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0;
      background: var(--accent);
    }

    /* ── Right panel ── */
    .right-panel {
      display: flex; flex-direction: column;
      background: var(--surface);
    }

    /* Terminal header */
    .terminal-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 0 20px;
      height: 44px;
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    .terminal-dots { display: flex; gap: 6px; }
    .terminal-dots span {
      width: 11px; height: 11px; border-radius: 50%;
    }
    .dot-red   { background: #ff5f57; }
    .dot-yellow{ background: #febc2e; }
    .dot-green { background: #28c840; }
    .terminal-title {
      font-family: var(--mono); font-size: .75rem; color: var(--muted);
    }
    .terminal-actions { display: flex; gap: 6px; }
    .tag {
      font-family: var(--mono); font-size: .65rem;
      padding: 2px 8px; border-radius: 4px;
      border: 1px solid var(--border2); color: var(--muted);
    }

    /* Status bar */
    .status-bar {
      display: flex; align-items: center; gap: 10px;
      padding: 8px 20px;
      border-bottom: 1px solid var(--border);
      background: var(--panel);
      min-height: 36px;
      flex-shrink: 0;
    }
    .spinner {
      width: 13px; height: 13px; border-radius: 50%;
      border: 2px solid var(--border2); border-top-color: var(--accent);
      animation: spin .6s linear infinite; flex-shrink: 0;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .status-text { font-size: .78rem; color: var(--muted2); font-family: var(--mono); }

    /* Output area */
    .output-wrap {
      flex: 1; overflow-y: auto; padding: 24px 28px;
    }
    .output-wrap::-webkit-scrollbar { width: 5px; }
    .output-wrap::-webkit-scrollbar-track { background: transparent; }
    .output-wrap::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 3px; }

    .output-empty {
      height: 100%; display: flex; flex-direction: column;
      align-items: center; justify-content: center; gap: 14px;
      color: var(--muted);
    }
    .output-empty-icon { font-size: 2.5rem; opacity: .3; }
    .output-empty-text { font-size: .85rem; }

    #output {
      font-family: var(--sans); font-size: .9rem; line-height: 1.8;
      color: var(--text); white-space: pre-wrap;
    }
    #output strong, #output b { color: var(--accent); font-weight: 600; }
    .error-msg { color: var(--red); font-family: var(--mono); font-size: .85rem; }

    /* Markdown-style bold via regex replacement */
    .md-bold { color: var(--accent2); font-weight: 600; }

    /* ── Bottom status bar ── */
    .bottom-bar {
      display: flex; align-items: center; justify-content: space-between;
      padding: 0 20px; height: 28px;
      background: var(--accent);
      flex-shrink: 0;
    }
    .bottom-bar-text {
      font-size: .68rem; font-weight: 500; color: rgba(255,255,255,.85);
      font-family: var(--mono);
    }

    /* ── Responsive ── */
    @media (max-width: 800px) {
      .layout { grid-template-columns: 1fr; }
      .left-panel { border-right: none; border-bottom: 1px solid var(--border); }
    }
  </style>
</head>
<body>

<!-- Top bar -->
<header class="topbar">
  <div class="logo">
    <div class="logo-icon">🧠</div>
    DevMind
    <span class="logo-version">v2.0</span>
  </div>
  <div class="topbar-right">
    <div class="status-dot"></div>
    <span class="topbar-label">Claude Opus 4.6 · Ready</span>
  </div>
</header>

<div class="layout">

  <!-- ── Left panel ── -->
  <aside class="left-panel">

    <div>
      <div class="section-label">Repository</div>
      <div class="input-group">
        <label class="input-label"><span class="icon">🔗</span> GitHub URL</label>
        <input id="repo" type="text" placeholder="https://github.com/owner/repo"
               onkeydown="if(event.key==='Enter') analyze()" />
      </div>
    </div>

    <div class="divider"></div>

    <div>
      <div class="section-label">Options</div>
      <div class="input-group">
        <label class="input-label"><span class="icon">📁</span> Max files (1–30)</label>
        <input id="maxfiles" type="number" value="{{ max_files }}" min="1" max="30" />
      </div>
    </div>

    <button class="btn-analyze" id="btn" onclick="analyze()">
      <span id="btn-icon">⚡</span>
      <span id="btn-text">Analyze Repository</span>
    </button>

    <div class="divider"></div>

    <!-- Stats -->
    <div>
      <div class="section-label">Session stats</div>
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-value" id="stat-files">—</div>
          <div class="stat-label">Files loaded</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" id="stat-tokens">—</div>
          <div class="stat-label">Est. tokens</div>
        </div>
      </div>
    </div>

    <!-- File list -->
    <div>
      <div class="section-label">Analyzed files</div>
      <div class="file-list">
        <div class="file-list-header">
          📄 &nbsp;Files sent to Claude
        </div>
        <div class="file-items" id="file-list-items">
          <div class="file-item" style="color:var(--muted)">
            <span style="font-size:.78rem">No files yet</span>
          </div>
        </div>
      </div>
    </div>

  </aside>

  <!-- ── Right panel ── -->
  <main class="right-panel">

    <div class="terminal-header">
      <div class="terminal-dots">
        <span class="dot-red"></span>
        <span class="dot-yellow"></span>
        <span class="dot-green"></span>
      </div>
      <span class="terminal-title">devmind — output</span>
      <div class="terminal-actions">
        <span class="tag" id="model-tag">claude-opus-4-6</span>
        <span class="tag" id="repo-tag">no repo</span>
      </div>
    </div>

    <div class="status-bar" id="status-bar">
      <span class="status-text" id="status-text" style="color:var(--muted)">
        Waiting for input...
      </span>
    </div>

    <div class="output-wrap" id="output-wrap">
      <div class="output-empty" id="output-empty">
        <div class="output-empty-icon">🔭</div>
        <div class="output-empty-text">Paste a GitHub URL and click Analyze</div>
      </div>
      <div id="output" style="display:none"></div>
    </div>

    <div class="bottom-bar">
      <span class="bottom-bar-text">DevMind v2 · Powered by Claude Opus 4.6</span>
      <span class="bottom-bar-text" id="bottom-time"></span>
    </div>

  </main>
</div>

<script>
let startTime = null;
let timerInterval = null;

function setStatus(text, spinning = false) {
  const bar = document.getElementById('status-bar');
  const el  = document.getElementById('status-text');
  bar.innerHTML = '';
  if (spinning) {
    const s = document.createElement('div');
    s.className = 'spinner';
    bar.appendChild(s);
  }
  const t = document.createElement('span');
  t.className = 'status-text';
  t.textContent = text;
  bar.appendChild(t);
}

function startTimer() {
  startTime = Date.now();
  timerInterval = setInterval(() => {
    const s = ((Date.now() - startTime) / 1000).toFixed(1);
    document.getElementById('bottom-time').textContent = `${s}s elapsed`;
  }, 100);
}

function stopTimer() {
  clearInterval(timerInterval);
}

// Minimal markdown: **bold** → <span class=md-bold>
function renderMd(text) {
  return text.replace(/\*\*(.*?)\*\*/g, '<span class="md-bold">$1</span>');
}

async function analyze() {
  const repo = document.getElementById('repo').value.trim();
  const maxfiles = parseInt(document.getElementById('maxfiles').value) || 15;

  if (!repo) { alert('Please enter a GitHub repository URL'); return; }

  const btn     = document.getElementById('btn');
  const btnText = document.getElementById('btn-text');
  const btnIcon = document.getElementById('btn-icon');
  const output  = document.getElementById('output');
  const empty   = document.getElementById('output-empty');

  btn.disabled = true;
  btnIcon.textContent = '⏳';
  btnText.textContent = 'Analyzing...';

  empty.style.display = 'none';
  output.style.display = 'block';
  output.innerHTML = '';

  document.getElementById('stat-files').textContent = '—';
  document.getElementById('stat-tokens').textContent = '—';
  document.getElementById('file-list-items').innerHTML =
    '<div class="file-item"><span style="font-size:.78rem;color:var(--muted)">Loading...</span></div>';

  // Update header tag
  const repoName = repo.replace('https://github.com/', '').split('/').slice(0,2).join('/');
  document.getElementById('repo-tag').textContent = repoName || 'repo';

  setStatus('Fetching repository structure...', true);
  startTimer();

  try {
    const resp = await fetch('/explain', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo, maxfiles })
    });

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let rawText = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6);
        if (data === '[DONE]') continue;
        try {
          const msg = JSON.parse(data);

          if (msg.type === 'status') {
            setStatus(msg.text, true);

          } else if (msg.type === 'files') {
            document.getElementById('stat-files').textContent = msg.count;
            document.getElementById('stat-tokens').textContent =
              (msg.chars / 4).toFixed(0);
            const ul = document.getElementById('file-list-items');
            ul.innerHTML = '';
            msg.files.forEach(f => {
              const d = document.createElement('div');
              d.className = 'file-item';
              d.innerHTML = `<span class="dot"></span>${f}`;
              ul.appendChild(d);
            });

          } else if (msg.type === 'text') {
            rawText += msg.text;
            output.innerHTML = renderMd(rawText);
            document.getElementById('output-wrap').scrollTop =
              document.getElementById('output-wrap').scrollHeight;
            setStatus('Generating explanation...', true);

          } else if (msg.type === 'error') {
            output.innerHTML = `<span class="error-msg">⚠ Error: ${msg.text}</span>`;
            setStatus('Error occurred', false);

          } else if (msg.type === 'done') {
            setStatus('✓ Analysis complete', false);
            stopTimer();
          }
        } catch(e) {}
      }
    }
  } catch(e) {
    output.innerHTML = `<span class="error-msg">⚠ Connection error: ${e.message}</span>`;
    setStatus('Connection failed', false);
    stopTimer();
  }

  btn.disabled = false;
  btnIcon.textContent = '⚡';
  btnText.textContent = 'Analyze Repository';
}
</script>
</body>
</html>
"""


# ── GitHub helpers ──────────────────────────────────────────

def parse_github_url(url: str) -> tuple[str, str]:
    url = url.strip().rstrip('/')
    match = re.search(r'github\.com/([^/]+)/([^/\s]+)', url)
    if not match:
        raise ValueError(f"Could not parse GitHub URL: {url}")
    owner, repo = match.group(1), match.group(2)
    repo = re.sub(r'\.git$', '', repo)
    return owner, repo


def fetch_repo_tree(owner: str, repo: str) -> list[dict]:
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    resp = requests.get(url, timeout=15, headers={"Accept": "application/vnd.github+json"})
    if resp.status_code == 404:
        raise ValueError(f"Repository {owner}/{repo} not found or is private")
    resp.raise_for_status()
    return [i for i in resp.json().get("tree", []) if i["type"] == "blob"]


READABLE_EXT = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.java', '.kt', '.rb',
    '.cpp', '.c', '.h', '.cs', '.php', '.swift', '.scala', '.sh', '.bash',
    '.md', '.txt', '.rst', '.yaml', '.yml', '.json', '.toml', '.ini', '.cfg',
    '.html', '.css', '.sql', '.env.example',
}
READABLE_NAMES = {
    'readme', 'readme.md', 'readme.txt', 'readme.rst',
    'dockerfile', 'makefile', 'docker-compose.yml',
    'requirements.txt', 'package.json', 'cargo.toml',
    'go.mod', 'pyproject.toml', 'setup.py',
}
SKIP_DIRS = {'node_modules', '.git', 'vendor', '__pycache__', '.venv', 'dist', 'build', '.next'}
PRIORITY_NAMES = {
    'readme.md', 'readme.txt', 'readme.rst', 'readme',
    'package.json', 'requirements.txt', 'pyproject.toml',
    'cargo.toml', 'go.mod', 'setup.py', 'dockerfile',
    'docker-compose.yml', 'makefile',
}


def should_read(path: str) -> bool:
    parts = path.lower().split('/')
    for part in parts[:-1]:
        if part in SKIP_DIRS:
            return False
    filename = parts[-1]
    ext = os.path.splitext(filename)[1].lower()
    return ext in READABLE_EXT or filename in READABLE_NAMES


def fetch_file(owner: str, repo: str, path: str) -> str | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    try:
        resp = requests.get(url, timeout=10, headers={"Accept": "application/vnd.github+json"})
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("encoding") == "base64":
            content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            if len(content) > 8000:
                content = content[:8000] + "\n... [file truncated]"
            return content
    except Exception:
        return None


def build_context(owner: str, repo: str, max_files: int):
    tree = fetch_repo_tree(owner, repo)
    priority, other = [], []
    for item in tree:
        p = item['path']
        if not should_read(p):
            continue
        (priority if os.path.basename(p).lower() in PRIORITY_NAMES else other).append(p)

    selected = (priority + other)[:max_files]
    parts = [f"# Repository: {owner}/{repo}\n\n## File structure:\n"]
    for item in tree[:100]:
        parts.append(f"  {item['path']}")
    parts.append("\n\n## Key file contents:\n")

    fetched, total_chars = [], 0
    for path in selected:
        content = fetch_file(owner, repo, path)
        if content:
            parts.append(f"\n### {path}\n```\n{content}\n```")
            fetched.append(path)
            total_chars += len(content)

    return "\n".join(parts), fetched, total_chars


# ── Flask routes ────────────────────────────────────────────

@app.route('/')
def index():
    return render_template_string(HTML, max_files=MAX_FILES_DEFAULT)


@app.route('/explain', methods=['POST'])
def explain():
    data = request.get_json()
    repo_url  = data.get('repo', '').strip()
    max_files = min(max(int(data.get('maxfiles', MAX_FILES_DEFAULT)), 1), 30)

    def generate():
        try:
            yield f"data: {json.dumps({'type':'status','text':'Parsing URL...'})}\n\n"
            owner, repo = parse_github_url(repo_url)

            yield f"data: {json.dumps({'type':'status','text':f'Fetching {owner}/{repo} file tree...'})}\n\n"
            context, fetched_files, total_chars = build_context(owner, repo, max_files)

            yield f"data: {json.dumps({'type':'files','count':len(fetched_files),'chars':total_chars,'files':fetched_files})}\n\n"
            yield f"data: {json.dumps({'type':'status','text':f'Loaded {len(fetched_files)} files — asking Claude...'})}\n\n"

            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

            prompt = f"""You are an expert software engineer and technical writer.
Analyze the repository below and provide a clear, well-structured explanation.

{context}

Please cover:
1. **Purpose** — what problem does this project solve?
2. **Tech stack** — languages, frameworks, key libraries
3. **Architecture** — how the codebase is organized, key modules/components
4. **Entry points** — how the program starts, main files to read first
5. **Key functionality** — core features and how they work
6. **How to run** — setup and run instructions based on config files
7. **Notable patterns** — design decisions, interesting implementation details

Be thorough but concise. Use **bold** for important terms."""

            with client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=4096,
                thinking={"type": "adaptive"},
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                for event in stream:
                    if event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            yield f"data: {json.dumps({'type':'text','text':event.delta.text})}\n\n"

            yield f"data: {json.dumps({'type':'done'})}\n\n"
            yield "data: [DONE]\n\n"

        except ValueError as e:
            yield f"data: {json.dumps({'type':'error','text':str(e)})}\n\n"
        except anthropic.AuthenticationError:
            yield f"data: {json.dumps({'type':'error','text':'Invalid Anthropic API key — edit ANTHROPIC_API_KEY in the script'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','text':str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


if __name__ == '__main__':
    if ANTHROPIC_API_KEY.startswith("sk-ant-YOUR"):
        print("\n⚠  Set your ANTHROPIC_API_KEY at the top of this file!\n")

    url = f"http://localhost:{PORT}"
    print(f"\n🧠 DevMind v2 is running → {url}\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
