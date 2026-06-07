#!/usr/bin/env python3
"""Local web demo for the no-defense handbook RAG baseline."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from baseline_rag import (
    build_context,
    build_vectorizer,
    generate_extractive_answer,
    load_chunks,
    make_prompt,
    retrieve,
)


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Baseline RAG Demo</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #20242a;
      --muted: #626b78;
      --line: #d9dee7;
      --accent: #176f6b;
      --accent-2: #c4572c;
      --soft: #edf7f5;
      --warn: #fff4e8;
      --shadow: 0 14px 38px rgba(29, 35, 44, 0.08);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      min-height: 100vh;
    }
    header {
      background: #ffffff;
      border-bottom: 1px solid var(--line);
      padding: 20px 28px 18px;
    }
    .header-inner {
      max-width: 1280px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
    }
    h1 {
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
      letter-spacing: 0;
    }
    .subtitle {
      margin-top: 6px;
      color: var(--muted);
      font-size: 14px;
    }
    .badge-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .badge {
      border: 1px solid var(--line);
      background: var(--soft);
      color: #175a56;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 650;
      white-space: nowrap;
    }
    main {
      max-width: 1280px;
      margin: 0 auto;
      padding: 24px 28px 32px;
      display: grid;
      grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
      gap: 18px;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    .controls {
      padding: 18px;
      align-self: start;
      position: sticky;
      top: 16px;
    }
    label {
      display: block;
      font-size: 13px;
      color: var(--muted);
      font-weight: 700;
      margin-bottom: 8px;
    }
    textarea, input {
      width: 100%;
      border: 1px solid #c8d0dc;
      border-radius: 6px;
      font: inherit;
      color: var(--ink);
      background: #ffffff;
      outline: none;
    }
    textarea {
      min-height: 132px;
      resize: vertical;
      padding: 12px;
      line-height: 1.45;
    }
    input {
      padding: 9px 10px;
    }
    textarea:focus, input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(23, 111, 107, 0.15);
    }
    .field {
      margin-bottom: 16px;
    }
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .button-row {
      display: flex;
      gap: 10px;
      align-items: center;
    }
    button {
      border: 0;
      border-radius: 6px;
      padding: 10px 14px;
      font: inherit;
      font-weight: 750;
      cursor: pointer;
      min-height: 42px;
    }
    #run {
      background: var(--accent);
      color: white;
      flex: 1;
    }
    #sample {
      background: #eef1f5;
      color: #25303b;
    }
    button:disabled {
      opacity: 0.65;
      cursor: wait;
    }
    .note {
      margin-top: 14px;
      padding: 12px;
      background: var(--warn);
      border: 1px solid #f1d7b8;
      border-radius: 6px;
      color: #75512c;
      font-size: 13px;
      line-height: 1.45;
    }
    .results {
      min-height: 620px;
      overflow: hidden;
    }
    .tabs {
      display: flex;
      border-bottom: 1px solid var(--line);
      background: #fbfcfd;
    }
    .tab {
      border-radius: 0;
      background: transparent;
      color: var(--muted);
      border-right: 1px solid var(--line);
      min-height: 48px;
      padding: 12px 16px;
    }
    .tab.active {
      color: var(--accent);
      background: #ffffff;
      box-shadow: inset 0 -3px 0 var(--accent);
    }
    .panel {
      display: none;
      padding: 18px;
    }
    .panel.active { display: block; }
    .answer {
      font-size: 16px;
      line-height: 1.65;
      margin: 0;
      white-space: pre-wrap;
    }
    .meta {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fbfcfd;
    }
    .metric strong {
      display: block;
      font-size: 18px;
      margin-bottom: 2px;
    }
    .metric span {
      color: var(--muted);
      font-size: 12px;
    }
    .chunk {
      border: 1px solid var(--line);
      border-radius: 8px;
      margin-bottom: 12px;
      overflow: hidden;
      background: #ffffff;
    }
    .chunk-head {
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 10px;
      align-items: center;
      padding: 10px 12px;
      background: #f8fafb;
      border-bottom: 1px solid var(--line);
    }
    .rank {
      width: 28px;
      height: 28px;
      display: inline-grid;
      place-items: center;
      background: #e9f3f2;
      color: var(--accent);
      border-radius: 999px;
      font-weight: 800;
      font-size: 13px;
    }
    .source {
      min-width: 0;
      font-size: 13px;
      color: var(--muted);
      overflow-wrap: anywhere;
    }
    .score {
      color: var(--accent-2);
      font-weight: 800;
      font-size: 13px;
      white-space: nowrap;
    }
    .chunk-body {
      padding: 12px;
      line-height: 1.55;
      font-size: 14px;
      white-space: pre-wrap;
    }
    pre {
      margin: 0;
      padding: 14px;
      background: #111827;
      color: #e5e7eb;
      border-radius: 8px;
      overflow: auto;
      line-height: 1.5;
      font-size: 13px;
      max-height: 560px;
      white-space: pre-wrap;
    }
    .empty {
      padding: 42px 24px;
      color: var(--muted);
      text-align: center;
      line-height: 1.5;
    }
    .error {
      color: #9b1c1c;
      background: #fff0f0;
      border: 1px solid #f0baba;
      border-radius: 6px;
      padding: 12px;
      margin-top: 14px;
      display: none;
    }
    @media (max-width: 900px) {
      .header-inner { display: block; }
      .badge-row { justify-content: flex-start; margin-top: 12px; }
      main { grid-template-columns: 1fr; padding: 16px; }
      .controls { position: static; }
      .meta { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .tabs { overflow-x: auto; }
      .tab { white-space: nowrap; }
    }
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <div>
        <h1>Baseline RAG Demo</h1>
        <div class="subtitle">No-defense retrieval and answer generation over the handbook chunks.</div>
      </div>
      <div class="badge-row">
        <span class="badge" id="chunk-count">chunks: loading</span>
        <span class="badge">retrieval: TF-IDF</span>
        <span class="badge">defense: none</span>
      </div>
    </div>
  </header>
  <main>
    <section class="controls">
      <div class="field">
        <label for="question">Question</label>
        <textarea id="question">What is the Cycle to Work scheme and what is the spending limit?</textarea>
      </div>
      <div class="grid-2">
        <div class="field">
          <label for="top-k">Top K</label>
          <input id="top-k" type="number" min="1" max="20" value="8" />
        </div>
        <div class="field">
          <label for="max-context">Max Context Chars</label>
          <input id="max-context" type="number" min="1000" max="20000" step="500" value="6000" />
        </div>
      </div>
      <div class="button-row">
        <button id="run">Run Baseline RAG</button>
        <button id="sample">Sample</button>
      </div>
      <div class="note">
        This demo intentionally has no prompt-injection defenses. It shows the raw baseline behavior for later comparison.
      </div>
      <div class="error" id="error"></div>
    </section>
    <section class="results">
      <div class="tabs">
        <button class="tab active" data-tab="answer">Answer</button>
        <button class="tab" data-tab="chunks">Retrieved Chunks</button>
        <button class="tab" data-tab="context">Context</button>
        <button class="tab" data-tab="prompt">Prompt</button>
      </div>
      <div class="panel active" id="answer-panel">
        <div id="answer-empty" class="empty">Run a question to inspect the baseline answer and its citations.</div>
        <div id="answer-content" style="display:none">
          <div class="meta">
            <div class="metric"><strong id="metric-top-k">-</strong><span>retrieved chunks</span></div>
            <div class="metric"><strong id="metric-context">-</strong><span>context chars</span></div>
            <div class="metric"><strong id="metric-best">-</strong><span>best score</span></div>
            <div class="metric"><strong id="metric-source">-</strong><span>top source</span></div>
          </div>
          <p class="answer" id="answer-text"></p>
        </div>
      </div>
      <div class="panel" id="chunks-panel">
        <div id="chunks-list" class="empty">Retrieved chunks will appear here.</div>
      </div>
      <div class="panel" id="context-panel">
        <pre id="context-text">Retrieved context will appear here.</pre>
      </div>
      <div class="panel" id="prompt-panel">
        <pre id="prompt-text">Full prompt will appear here.</pre>
      </div>
    </section>
  </main>
  <script>
    const samples = [
      "What is the Cycle to Work scheme and what is the spending limit?",
      "How can employees request flexible working?",
      "What private medical insurance does the company provide?",
      "What does an Associate Software Engineer do?",
      "What are the responsibilities of a Lead Data Engineer?",
      "What benefits are available to support hybrid working?"
    ];
    let sampleIndex = 0;

    const $ = (id) => document.getElementById(id);

    document.querySelectorAll(".tab").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
        document.querySelectorAll(".panel").forEach((panel) => panel.classList.remove("active"));
        button.classList.add("active");
        $(button.dataset.tab + "-panel").classList.add("active");
      });
    });

    $("sample").addEventListener("click", () => {
      sampleIndex = (sampleIndex + 1) % samples.length;
      $("question").value = samples[sampleIndex];
    });

    $("run").addEventListener("click", runQuery);
    $("question").addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        runQuery();
      }
    });

    async function loadHealth() {
      const response = await fetch("/api/health");
      const data = await response.json();
      $("chunk-count").textContent = "chunks: " + data.chunk_count;
    }

    async function runQuery() {
      const question = $("question").value.trim();
      const error = $("error");
      if (!question) {
        error.textContent = "Please enter a question.";
        error.style.display = "block";
        return;
      }
      error.style.display = "none";
      $("run").disabled = true;
      $("run").textContent = "Running...";

      try {
        const response = await fetch("/api/query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question,
            top_k: Number($("top-k").value),
            max_context_chars: Number($("max-context").value)
          })
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "Request failed.");
        }
        renderResult(data);
      } catch (err) {
        error.textContent = err.message;
        error.style.display = "block";
      } finally {
        $("run").disabled = false;
        $("run").textContent = "Run Baseline RAG";
      }
    }

    function renderResult(data) {
      $("answer-empty").style.display = "none";
      $("answer-content").style.display = "block";
      $("answer-text").textContent = data.answer;
      $("metric-top-k").textContent = data.retrieved.length;
      $("metric-context").textContent = data.context.length;
      $("metric-best").textContent = data.retrieved.length ? data.retrieved[0].score.toFixed(3) : "-";
      $("metric-source").textContent = data.retrieved.length ? data.retrieved[0].source_type : "-";
      $("context-text").textContent = data.context;
      $("prompt-text").textContent = data.prompt;

      const chunks = data.retrieved.map((chunk) => `
        <article class="chunk">
          <div class="chunk-head">
            <span class="rank">${chunk.rank}</span>
            <div class="source">
              <strong>${escapeHtml(chunk.chunk_id)}</strong>
              &nbsp; ${escapeHtml(chunk.file_name)}
              <br />${escapeHtml(chunk.section_path)}
            </div>
            <div class="score">score ${Number(chunk.score).toFixed(3)}</div>
          </div>
          <div class="chunk-body">${escapeHtml(chunk.text)}</div>
        </article>
      `).join("");
      $("chunks-list").className = "";
      $("chunks-list").innerHTML = chunks || '<div class="empty">No chunks retrieved.</div>';
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    loadHealth().catch(() => {
      $("chunk-count").textContent = "chunks: unavailable";
    });
  </script>
</body>
</html>
"""


class RagDemoHandler(BaseHTTPRequestHandler):
    server_version = "RagDemo/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_text(HTML, content_type="text/html; charset=utf-8")
            return
        if parsed.path == "/api/health":
            self.send_json(
                {
                    "status": "ok",
                    "chunk_count": int(len(self.server.chunks)),  # type: ignore[attr-defined]
                    "default_top_k": self.server.default_top_k,  # type: ignore[attr-defined]
                }
            )
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/query":
            self.send_error(404, "Not found")
            return

        try:
            payload = self.read_json()
            question = str(payload.get("question", "")).strip()
            if not question:
                raise ValueError("Question is required.")
            top_k = int(payload.get("top_k", self.server.default_top_k))  # type: ignore[attr-defined]
            max_context_chars = int(payload.get("max_context_chars", 6000))
            top_k = max(1, min(top_k, 20))
            max_context_chars = max(1000, min(max_context_chars, 20000))

            retrieved = retrieve(
                question,
                self.server.chunks,  # type: ignore[attr-defined]
                self.server.vectorizer,  # type: ignore[attr-defined]
                self.server.chunk_matrix,  # type: ignore[attr-defined]
                top_k,
            )
            context = build_context(retrieved, max_context_chars)
            answer = generate_extractive_answer(question, retrieved)
            prompt = make_prompt(question, context)

            self.send_json(
                {
                    "question": question,
                    "answer": answer,
                    "context": context,
                    "prompt": prompt,
                    "retrieved": [chunk.__dict__ for chunk in retrieved],
                }
            )
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=400)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw)

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, body: str, content_type: str, status: int = 200) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        print("%s - %s" % (self.address_string(), format % args))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the local baseline RAG demo.")
    parser.add_argument("--chunks", default="handbook-main/chunks.csv", help="Path to chunks.csv.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind.")
    parser.add_argument("--top-k", type=int, default=8, help="Default number of retrieved chunks.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = load_chunks(Path(args.chunks))
    vectorizer, chunk_matrix = build_vectorizer(chunks["retrieval_text"])

    server = ThreadingHTTPServer((args.host, args.port), RagDemoHandler)
    server.chunks = chunks  # type: ignore[attr-defined]
    server.vectorizer = vectorizer  # type: ignore[attr-defined]
    server.chunk_matrix = chunk_matrix  # type: ignore[attr-defined]
    server.default_top_k = args.top_k  # type: ignore[attr-defined]

    url = f"http://{args.host}:{args.port}"
    print(f"Serving baseline RAG demo at {url}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
