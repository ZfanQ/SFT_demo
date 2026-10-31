#!/usr/bin/env python3
"""Small ABBA throughput pilot on a private Ollama server; originals untouched."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import statistics
import subprocess
import threading
import time
from urllib.request import Request, urlopen


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")
    path.chmod(0o664)


def api(route, payload=None):
    req = Request("http://127.0.0.1:11435" + route,
                  data=json.dumps(payload).encode() if payload is not None else None,
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=600) as response:
        return json.load(response)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--parallel-sequence", default="1,2,2,1")
    args = p.parse_args()
    sequence = [int(x) for x in args.parallel_sequence.split(",")]
    if not sequence or any(x not in (1, 2, 3) for x in sequence):
        raise ValueError("This bounded pilot supports only one to three parallel slots")
    root = Path("/data/SFT_demo/Oct")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    out.chmod(0o2775)
    os.umask(0o002)
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 11435)) == 0:
            raise RuntimeError("Private port is already in use; refusing to interfere")
    import pymupdf
    from tokenizers import Tokenizer
    spec = importlib.util.spec_from_file_location("original_qwen", root / "Qwen8b_run/run.py")
    original = importlib.util.module_from_spec(spec); spec.loader.exec_module(original)
    tokenizer_path = next(Path("/data/SFT_demo/.cache/huggingface/hub/models--Qwen--Qwen3-8B").glob("snapshots/*/tokenizer.json"))
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    inputs = []
    for number in [1, 2, 3, 4, 7, 8]:
        path = root / "All_papers/paper" / f"paper{number:03d}.pdf"
        with pymupdf.open(path) as doc:
            text = "\n\n".join(page.get_text(sort=True) for page in doc).strip()
        prompt = original.TASK + text
        estimate = len(tokenizer.encode(original.SYSTEM + prompt).ids)
        if estimate > 27000:
            raise ValueError("Pilot includes an overlong paper; do not silently truncate")
        inputs.append({"paper_id": f"paper{number:03d}", "prompt": prompt,
                       "pdf_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                       "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                       "token_estimate": estimate})
    save(out / "inputs.json", inputs)
    # Read the installed inventory through the existing service; never pull a model.
    with urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as response:
        installed = json.load(response)["models"]
    tag = next(x for x in installed if x["name"] == "qwen3:8b")
    save(out / "protocol.json", {"model": tag, "sequence": sequence,
         "papers": [x["paper_id"] for x in inputs], "context": 32768,
         "temperature": 0, "seed": 42, "num_predict": 850,
         "private_port": 11435, "existing_service_modified": False,
         "note": "Single-chunk full-paper pilot; warm-start timings, validity not factual certification.",
         "tokenizer_sha256": hashlib.sha256(tokenizer_path.read_bytes()).hexdigest(),
         "source_runner_sha256": hashlib.sha256((root / "Qwen8b_run/run.py").read_bytes()).hexdigest()})
    rounds = []
    for index, parallel in enumerate(sequence, 1):
        # Abort if another user loads a model in the shared service.
        with urlopen("http://127.0.0.1:11434/api/ps", timeout=5) as response:
            if json.load(response).get("models"):
                raise RuntimeError("Shared Ollama became active; pilot stops before next round")
        env = os.environ.copy()
        env.update(OLLAMA_HOST="127.0.0.1:11435", OLLAMA_MODELS="/data/SFT_demo/.models/ollama",
                   OLLAMA_NUM_PARALLEL=str(parallel), OLLAMA_MAX_LOADED_MODELS="1")
        log = (out / f"server_round{index}.log").open("w")
        proc = subprocess.Popen(["/data/SFT_demo/.tools/ollama/bin/ollama", "serve"],
                                env=env, stdout=log, stderr=log, start_new_session=True)
        stop = threading.Event()
        samples = []
        def monitor():
            while not stop.wait(1):
                result = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
                    "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=8)
                samples.append({"time": time.time(), "raw": result.stdout.strip()})
        worker = None
        try:
            for _ in range(60):
                if proc.poll() is not None:
                    raise RuntimeError("Private server exited during startup")
                try:
                    api("/api/version"); break
                except Exception:
                    time.sleep(0.5)
            else:
                raise RuntimeError("Private server failed to start")
            api("/api/chat", {"model": "qwen3:8b", "stream": False, "think": False,
                "messages": [{"role": "user", "content": "Reply with ready."}],
                "options": {"num_ctx": 32768, "num_predict": 8, "temperature": 0}, "keep_alive": "10m"})
            loaded = api("/api/ps")
            save(out / f"loaded_round{index}.json", loaded)
            if any(x.get("size_vram", 0) < x.get("size", 0) * .95 for x in loaded.get("models", [])):
                raise RuntimeError("Model offloaded to CPU; refuse unequal benchmark")
            worker = threading.Thread(target=monitor, daemon=True); worker.start()
            def infer(item):
                started = time.perf_counter()
                response = api("/api/chat", {"model": "qwen3:8b", "stream": False, "think": False,
                    "messages": [{"role": "system", "content": original.SYSTEM},
                                 {"role": "user", "content": item["prompt"]}],
                    "options": {"num_ctx": 32768, "num_predict": 850, "temperature": 0, "seed": 42},
                    "keep_alive": "10m"})
                latency = time.perf_counter() - started
                save(out / f"round{index}_{item['paper_id']}.json", response)
                text = response.get("message", {}).get("content", "").strip()
                valid = bool(response.get("done") and response.get("done_reason") != "length" and original.valid(text))
                return {"paper_id": item["paper_id"], "latency_s": latency, "valid": valid,
                        "words": len(text.split()), "output_sha256": hashlib.sha256(text.encode()).hexdigest(),
                        **{k: response.get(k) for k in ("load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration")}}
            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=parallel) as pool:
                rows = list(pool.map(infer, inputs))
            elapsed = time.perf_counter() - start
            result = {"round": index, "parallel": parallel, "elapsed_s": elapsed,
                      "papers_per_minute": len(rows) * 60 / elapsed,
                      "valid_papers_per_minute": sum(x["valid"] for x in rows) * 60 / elapsed,
                      "median_latency_s": statistics.median(x["latency_s"] for x in rows), "results": rows}
            rounds.append(result); save(out / "rounds.json", rounds)
            print(json.dumps({k: v for k, v in result.items() if k != "results"}), flush=True)
        finally:
            stop.set()
            if worker is not None:
                worker.join(timeout=10)
            save(out / f"gpu_round{index}.json", samples)
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL); proc.wait()
            log.close()
    save(out / "status.json", {"state": "completed", "rounds": len(rounds), "inferences": len(rounds) * len(inputs)})


if __name__ == "__main__":
    main()
