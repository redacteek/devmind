#!/usr/bin/env python3
"""
GitHub Repository Explainer — Web panel with Flask + Claude API
"""

import os
import re
import base64
import threading
import webbrowser
from urllib.parse import urlparse

import anthropic
import requests
from flask import Flask, render_template_string, request, Response, stream_with_context

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GitHub Repo Explainer</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', sans-serif; background: #0d1117; color: #e6edf3; min-height: 100vh; }
    .container { max-width: 900px; margin: 0 auto; padding: 40px 20px; }
    h1 { text-align: center; font-size: 2rem; margin-bottom: 8px; color: #58a6ff; }
    .subtitle { text-align: center; color: #8b949e; margin-bottom: 40px; font-size: 0.95rem; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 28px; margin-bottom: 24px; }
    label { display: block; font-size: 0.85rem; color: #8b949e; margin-bottom: 6px; font-weight: 500; }
    input[type="text"], input[type="password"] {
      width: 100%; padding: 10px 14px; background: #0d1117; border: 1px solid #30363d;
      border-radius: 8px; color: #e6edf3; font-size: 0.95rem; transition: border-color .2s;
    }
    input:focus { outline: none; border-color: #58a6ff; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
    .full { margin-bottom: 16px; }
    button {
      width: 100%; padding: 12px; background: #238636; border: none; border-radius: 8px;
      color: #fff; font-size: 1rem; font-weight: 600; cursor: pointer; transition: background .2s;
    }
    button:hover { background: #2ea043; }
    button:disabled { background: #3d4450; cursor: not-allowed; }
    #output-card { display: none; }
    #output {
      background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
      padding: 20px; min-height: 200px; white-space: pre-wrap; line-height: 1.7;
      font-size: 0.92rem; color: #e6edf3; max-height: 600px; overflow-y: auto;
    }
    .status { font-size: 0.82rem; color: #8b949e; margin-bottom: 10px; }
    .error { color: #f85149; }
    .spinner {
      display: inline-block; width: 14px; height: 14px; border: 2px solid #30363d;
      border-top-color: #58a6ff; border-radius: 50%; animation: spin .7s linear infinite;
      vertical-align: middle; margin-right: 6px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>
<div class="container">
  <h1>🔍 GitHub Repo Explainer</h1>
  <p class="subtitle">Enter a repository link and Claude will explain what it does</p>

  <div class="card">
    <div class="row">
      <div>
        <label>🔗 GitHub Repository URL</label>
        <input id="repo" type="text" placeholder="https://github.com/owner/repo" />
      </div>
      <div>
        <label>🔑 Anthropic API Key</label>
        <input id="apikey" type="password" placeholder="sk-ant-..." />
      </div>
    </div>
    <div class="full">
      <label>📁 Max files to analyze (1–30)</label>
      <input id="maxfiles" type="text" value="15" style="max-width:120px" />
    </div>
    <button id="btn" onclick="explain()">✨ Explain Repository</button>
  </div>

  <div class="card" id="output-card">
    <div class="status" id="status"></div>
    <div id="output"></div>
  </div>
</div>

<script>
async function explain() {
  const repo = document.getElementById('repo').value.trim();
  const apikey = document.getElementById('apikey').value.trim();
  const maxfiles = parseInt(document.getElementById('maxfiles').value) || 15;

  if (!repo || !apikey) { alert('Please fill in the repository URL and API key'); return; }

  const btn = document.getElementById('btn');
  const card = document.getElementById('output-card');
  const output = document.getElementById('output');
  const status = document.getElementById('status');

  btn.disabled = true;
  btn.textContent = 'Analyzing...';
  card.style.display = 'block';
  output.textContent = '';
  status.innerHTML = '<span class="spinner"></span>Fetching repository structure...';

  try {
    const response = await fetch('/explain', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo, apikey, maxfiles })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6);
        if (data === '[DONE]') continue;
        try {
          const msg = JSON.parse(data);
          if (msg.type === 'status') {
            status.innerHTML = '<span class="spinner"></span>' + msg.text;
          } else if (msg.type === 'text') {
            output.textContent += msg.text;
            output.scrollTop = output.scrollHeight;
            status.innerHTML = '✅ Generating explanation...';
          } else if (msg.type === 'error') {
            output.innerHTML = '<span class="error">Error: ' + msg.text + '</span>';
            status.textContent = '';
          } else if (msg.type === 'done') {
            status.textContent = '✅ Done!';
          }
        } catch(e) {}
      }
    }
  } catch(e) {
    output.innerHTML = '<span class="error">Connection error: ' + e.message + '</span>';
  }

  btn.disabled = false;
  btn.textContent = '✨ Explain Repository';
}

document.addEventListener('keydown', e => {
  if (e.key === 'Enter') explain();
});
</script>
</body>
</html>
"""

def parse_github_url(url: str) -> tuple[str, str]:
    """Extract owner and repo from a GitHub URL."""
    url = url.strip().rstrip('/')
    match = re.search(r'github\.com/([^/]+)/([^/\s]+)', url)
    if not match:
        raise ValueError(f"Could not parse GitHub URL: {url}")
    owner, repo = match.group(1), match.group(2)
    repo = re.sub(r'\.git$', '', repo)
    return owner, repo


def fetch_repo_tree(owner: str, repo: str) -> list[dict]:
    """Fetch the file tree of a repository via GitHub API."""
    api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    resp = requests.get(api_url, timeout=15, headers={"Accept": "application/vnd.github+json"})
    if resp.status_code == 404:
        raise ValueError(f"Repository {owner}/{repo} not found or is private")
    resp.raise_for_status()
    data = resp.json()
    return [item for item in data.get("tree", []) if item["type"] == "blob"]


# File extensions worth reading
READABLE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.java', '.kt', '.rb',
    '.cpp', '.c', '.h', '.cs', '.php', '.swift', '.scala', '.r', '.sh', '.bash',
    '.md', '.txt', '.rst', '.yaml', '.yml', '.json', '.toml', '.ini', '.cfg',
    '.html', '.css', '.sql', '.dockerfile', 'dockerfile', '.env.example',
    '.gitignore', 'makefile', 'requirements.txt', 'package.json', 'cargo.toml',
    'go.mod', 'pyproject.toml', 'setup.py', 'readme',
}

SKIP_DIRS = {'node_modules', '.git', 'vendor', '__pycache__', '.venv', 'dist', 'build', '.next'}


def should_read(path: str) -> bool:
    parts = path.lower().split('/')
    # Skip service directories
    for part in parts[:-1]:
        if part in SKIP_DIRS:
            return False
    filename = parts[-1]
    ext = os.path.splitext(filename)[1].lower()
    return ext in READABLE_EXTENSIONS or filename in READABLE_EXTENSIONS


def fetch_file_content(owner: str, repo: str, path: str) -> str | None:
    """Read file content via GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    try:
        resp = requests.get(url, timeout=10, headers={"Accept": "application/vnd.github+json"})
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("encoding") == "base64":
            content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            # Truncate very large files
            if len(content) > 8000:
                content = content[:8000] + "\n... [file truncated]"
            return content
    except Exception:
        return None
    return None


def build_context(owner: str, repo: str, max_files: int) -> tuple[str, list[str]]:
    """Build repository context for Claude."""
    tree = fetch_repo_tree(owner, repo)

    # Prioritize important files
    priority_files = []
    other_files = []
    priority_names = {'readme.md', 'readme.txt', 'readme.rst', 'readme',
                      'package.json', 'requirements.txt', 'pyproject.toml',
                      'cargo.toml', 'go.mod', 'setup.py', 'dockerfile',
                      'docker-compose.yml', 'makefile', '.github'}

    for item in tree:
        path = item['path']
        if not should_read(path):
            continue
        if os.path.basename(path).lower() in priority_names:
            priority_files.append(path)
        else:
            other_files.append(path)

    selected = priority_files + other_files
    selected = selected[:max_files]

    parts = [f"# Repository: {owner}/{repo}\n\n## File structure:\n"]
    for item in tree[:80]:
        parts.append(f"  {item['path']}")
    parts.append("\n\n## Key file contents:\n")

    fetched = []
    for path in selected:
        content = fetch_file_content(owner, repo, path)
        if content:
            parts.append(f"\n### {path}\n```\n{content}\n```")
            fetched.append(path)

    return "\n".join(parts), fetched


@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/explain', methods=['POST'])
def explain():
    data = request.get_json()
    repo_url = data.get('repo', '').strip()
    api_key = data.get('apikey', '').strip()
    max_files = min(max(int(data.get('maxfiles', 15)), 1), 30)

    def generate():
        try:
            import json

            yield f"data: {json.dumps({'type':'status','text':'Parsing URL...'})}\n\n"
            owner, repo = parse_github_url(repo_url)

            yield f"data: {json.dumps({'type':'status','text':f'Fetching structure of {owner}/{repo}...'})}\n\n"
            context, fetched_files = build_context(owner, repo, max_files)

            yield f"data: {json.dumps({'type':'status','text':f'Loaded {len(fetched_files)} files — sending to Claude...'})}\n\n"

            client = anthropic.Anthropic(api_key=api_key)

            prompt = f"""You are an experienced software engineer. Analyze the repository below and provide a thorough explanation.

{context}

Please explain:
1. **Purpose** — what does this project do?
2. **Tech stack** — languages, frameworks, libraries
3. **Architecture** — how the code is organized, key components
4. **Entry points** — where execution starts, main files
5. **Key functionality** — core features and capabilities
6. **How to run** — if inferable from files (Dockerfile, requirements, etc.)
7. **Notable details** — anything worth highlighting

Be structured, clear, and concise."""

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
            import json
            yield f"data: {json.dumps({'type':'error','text':str(e)})}\n\n"
        except anthropic.AuthenticationError:
            import json
            yield f"data: {json.dumps({'type':'error','text':'Invalid Anthropic API key'})}\n\n"
        except Exception as e:
            import json
            yield f"data: {json.dumps({'type':'error','text':str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


if __name__ == '__main__':
    port = 5000
    url = f"http://localhost:{port}"
    print(f"\n🚀 GitHub Repo Explainer is running!")
    print(f"   Open in browser: {url}\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
