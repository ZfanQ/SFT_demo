#!/usr/bin/env python3
"""Generate separate development-only long/short summaries; preserve originals."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time

TASK = ("Write one self-contained English paragraph of 180-220 words, strictly at most 250 words, "
        "summarizing this complete article. Cover objective, actual design and population, methods, "
        "principal results, conclusion and material limitations supported by this article. Preserve "
        "outcome definitions, direction, numerical denominators and qualifiers such as vaccine-related, "
        "adjusted and per-protocol. Keep molecular modification, recognition, binding and stabilization "
        "roles distinct. Distinguish experimentally manipulated cells/animals from patient observational "
        "data: do not append a blanket statement that experimental work is observational or establishes "
        "no causality. Separate demonstrated in-model intervention effects from unvalidated pathway "
        "mediation and unproven clinical efficacy. Do not invent generic limitations. No headings, "
        "lists, citations or commentary.\n\nCOMPLETE ARTICLE:\n")
SHORT = ("Using only the following source-grounded longer summary, write a shorter preview in exactly "
         "two or three English sentences, about 50-80 words and at most 90 words. State what was studied, "
         "the main result and the most important evidence limitation. Preserve safety qualifiers, "
         "experimental setting, direction and uncertainty. Do not invent details or expand clinical "
         "claims. One paragraph, no headings, bullets, abbreviations with periods or commentary.\n\n")


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")
    path.chmod(0o664)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    out = args.output.resolve(); out.mkdir(exist_ok=False); out.chmod(0o2775); os.umask(0o002)
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", 11435)) == 0:
            raise RuntimeError("Private server is still active; refusing interference")
    import pymupdf
    from tokenizers import Tokenizer
    root = Path("/data/SFT_demo/Oct")
    spec = importlib.util.spec_from_file_location("qwen_original", root / "Qwen8b_run/run.py")
    q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
    q.URL = "http://127.0.0.1:11435"; q.TASK = TASK
    original_api = q.api
    calls = []
    def tracked(route, body=None):
        result = original_api(route, body)
        calls.append({"route": route, "request": body, "response": result})
        save(out / "raw_calls.json", calls)
        return result
    q.api = tracked
    tokenizer = Tokenizer.from_file(str(next(Path("/data/SFT_demo/.cache/huggingface/hub/models--Qwen--Qwen3-8B").glob("snapshots/*/tokenizer.json"))))
    ids = [5, 12, 49, 100, 128]
    save(out / "protocol.json", {"model": "qwen3:8b", "long_task": TASK, "short_task": SHORT,
         "source_ids": ids, "context": q.CTX, "chunk_tokens": q.CHUNK, "temperature": 0, "seed": 42,
         "short_source": "revised longer summary", "scope": "Error-enriched development cases; not a held-out test or a 200-paper rollout."})
    env = os.environ.copy(); env.update(OLLAMA_HOST="127.0.0.1:11435", OLLAMA_MODELS="/data/SFT_demo/.models/ollama", OLLAMA_NUM_PARALLEL="1", OLLAMA_MAX_LOADED_MODELS="1")
    log = (out / "server.log").open("w")
    proc = subprocess.Popen(["/data/SFT_demo/.tools/ollama/bin/ollama", "serve"], env=env,
                            stdout=log, stderr=log, start_new_session=True)
    outputs = []
    try:
        for _ in range(60):
            if proc.poll() is not None:
                raise RuntimeError("Private server exited")
            try:
                original_api("/api/version"); break
            except Exception:
                time.sleep(.5)
        else:
            raise RuntimeError("Server startup timed out")
        if not any(x["name"] == "qwen3:8b" for x in original_api("/api/tags")["models"]):
            raise ValueError("Qwen must already be installed")
        for n in ids:
            path = root / "All_papers/paper" / f"paper{n:03d}.pdf"
            with pymupdf.open(path) as doc:
                text = "\n\n".join(page.get_text(sort=True) for page in doc).strip()
            start = time.perf_counter()
            long, chunks = q.summarize(text, tokenizer, {"stage": "development"})
            for _ in range(3):
                short = q.generate(SHORT + long, tokenizer, 350)
                count = len(re.split(r"(?<=[.!?])\s+(?=[A-Z])", short))
                if q.valid(short) and len(short.split()) <= 90 and count in (2, 3):
                    break
            else:
                raise ValueError("Short preview failed length/sentence validation")
            item = {"paper_id": f"paper{n:03d}", "long": long, "short": short,
                    "long_words": len(long.split()), "short_words": len(short.split()),
                    "short_sentences": count, "chunks": chunks, "elapsed_s": time.perf_counter() - start,
                    "pdf_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "extracted_text_sha256": hashlib.sha256(text.encode()).hexdigest()}
            outputs.append(item); save(out / "outputs.json", outputs)
            (out / f"long_paper{n:03d}.txt").write_text(long + "\n")
            (out / f"short_paper{n:03d}.txt").write_text(short + "\n")
            print("Saved development long/short", item["paper_id"], item["long_words"], item["short_words"], flush=True)
        save(out / "status.json", {"state": "generated_pending_independent_review", "papers": len(outputs)})
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL); proc.wait()
        log.close()


if __name__ == "__main__":
    main()
