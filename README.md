# DevMind — GitHub Repo Explainer

A web panel powered by **Claude AI** that explains any public GitHub repository.

## Features

- Paste a GitHub repo URL and get a full breakdown in seconds
- Streams the AI response in real time
- Analyzes up to 30 key files (README, source code, configs, etc.)
- Powered by Claude Opus 4.6 with adaptive thinking

## Installation

```bash
pip install anthropic flask requests
```

## Usage

```bash
python github_explainer.py
```

Then open [http://localhost:5000](http://localhost:5000) in your browser.

## Requirements

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)
