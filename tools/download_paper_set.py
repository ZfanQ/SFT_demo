#!/usr/bin/env python3
"""Download a frozen SciCommons candidate set without running any language model."""
import argparse
import fcntl
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

S3 = "https://pmc-oa-opendata.s3.amazonaws.com/"
ID_API = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
HOSTS = {"arxiv.org", "export.arxiv.org", "pmc.ncbi.nlm.nih.gov",
         "pmc-oa-opendata.s3.amazonaws.com"}
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def atomic(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".part")
    temp.write_bytes(body)
    temp.chmod(0o664)
    temp.replace(path)


def json_save(path, obj):
    atomic(path, (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode())


def https_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme == "s3" and parsed.netloc == "pmc-oa-opendata":
        url = S3 + parsed.path.lstrip("/")
        if parsed.query:
            url += "?" + parsed.query
        parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS:
        raise ValueError("Unexpected download URL: " + url)
    return url


def fetch(url):
    url = https_url(url)
    for attempt in range(3):
        try:
            time.sleep(1 if "arxiv.org" not in url else 3)
            req = urllib.request.Request(url, headers={
                "User-Agent": "SFT-study-paper-download/0.1"})
            with urllib.request.urlopen(req, timeout=45) as response:
                https_url(response.geturl())
                body = response.read(50 * 1024 * 1024 + 1)
            if len(body) > 50 * 1024 * 1024:
                raise ValueError("Response exceeds 50 MiB")
            return body
        except urllib.error.HTTPError as error:
            if error.code not in (408, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            time.sleep(min(60, max(5 * (attempt + 1),
                int(error.headers.get("Retry-After", "0"))
                if error.headers.get("Retry-After", "0").isdigit() else 0)))
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def validate(body, kind):
    if kind == "pdf":
        if not body.startswith(b"%PDF-"):
            raise ValueError("Response is not a PDF")
        import pymupdf
        with pymupdf.open(stream=body, filetype="pdf") as doc:
            if doc.page_count == 0 or doc.needs_pass:
                raise ValueError("PDF is empty or encrypted")
            # Opening every page catches malformed page objects; not an extraction audit.
            for page in doc:
                _ = page.rect
    elif kind == "xml":
        article = ET.fromstring(body)
        tags = {node.tag.split("}")[-1] for node in article.iter()}
        if "article" not in tags or "body" not in tags:
            raise ValueError("XML has no article body")
    elif kind == "txt":
        text = body.decode("utf-8").strip()
        if not text or text.lower().startswith(("<!doctype html", "<html")):
            raise ValueError("Response is empty or HTML")


def save_file(root, relative, kind, url=None, reuse=None, expected_sha=None):
    path = root / relative
    if path.exists():
        body = path.read_bytes()
        validate(body, kind)
        if expected_sha and digest(body) != expected_sha:
            raise ValueError("Existing file checksum mismatch: " + relative)
    else:
        body = reuse.read_bytes() if reuse and reuse.exists() else fetch(url)
        validate(body, kind)
        if expected_sha and digest(body) != expected_sha:
            raise ValueError("Source file checksum mismatch: " + relative)
        atomic(path, body)
    if url:
        md5 = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("md5", [None])[0]
        if md5 and hashlib.md5(body).hexdigest() != md5.lower():
            raise ValueError("PMC source checksum mismatch: " + relative)
    return {"path": relative, "format": kind, "sha256": digest(body),
            "bytes": len(body), "url": url}


def pmid_for(row):
    pmid = str(row.get("external_id") or "").strip()
    if pmid.isdigit():
        return pmid
    match = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", row.get("url", ""))
    if not match:
        raise ValueError("No PMID for " + row["paper_id"])
    return match.group(1)


def pmc_versions(pmcid):
    query = urllib.parse.urlencode({"list-type": 2, "prefix": pmcid + ".",
                                  "delimiter": "/"})
    listing = ET.fromstring(fetch(S3 + "?" + query))
    if listing.findtext("s:IsTruncated", namespaces=NS) == "true":
        raise ValueError("Version listing truncated; needs pagination")
    prefixes = [node.text for node in listing.findall("s:CommonPrefixes/s:Prefix", NS)]
    return sorted(p for p in prefixes if p and re.fullmatch(r"PMC\d+\.\d+/", p))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(
        "/data/SFT_demo/.cache/datasets/scicommons-20261008-pbb6slrn"))
    parser.add_argument("--output", type=Path, default=Path(
        "/data/SFT_demo/tools_codex/papers_200_20261011"))
    args = parser.parse_args()
    os.umask(0o002)
    source, root = args.source.resolve(), args.output.resolve()
    if source == root or source in root.parents:
        raise ValueError("Output must be outside the original candidate directory")
    original = (source / "candidates.jsonl").read_bytes()
    rows = [json.loads(line) for line in original.decode().splitlines() if line.strip()]
    ids = [row["paper_id"] for row in rows]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r"candidate_\d+", x) for x in ids):
        raise ValueError("Duplicate or invalid candidate IDs")
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".download.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("A downloader is already running in this directory")
        for folder in ("pdfs", "abstracts", "fulltext", "metadata", "logs"):
            (root / folder).mkdir(exist_ok=True)
        frozen = root / "metadata/candidates.jsonl"
        if frozen.exists() and frozen.read_bytes() != original:
            raise ValueError("Output directory belongs to a different candidate set")
        atomic(frozen, original)
        for row in rows:
            atomic(root / "abstracts" / (row["paper_id"] + ".txt"),
                   (str(row.get("abstract") or "").strip() + "\n").encode())
        prior_path = root / "download_manifest.jsonl"
        prior = {r["paper_id"]: r for r in (
            [json.loads(x) for x in prior_path.read_text().splitlines() if x.strip()]
            if prior_path.exists() else [])}
        results = []
        for row in rows:
            result = {"paper_id": row["paper_id"], "source": row["source"],
                      "title": row["title"], "files": [], "errors": [],
                      "abstract_verified_against_fulltext": False,
                      "fulltext_extraction_verified": False, "checked_at": stamp()}
            # Reuse completed files only after hash and format checks.
            old = prior.get(row["paper_id"], {})
            if old.get("status") == "downloaded_unchecked" and old.get("files") and not old.get("errors"):
                try:
                    for item in old["files"]:
                        save_file(root, item["path"], item["format"],
                                  expected_sha=item["sha256"])
                    result = old
                except Exception as error:
                    result["errors"].append("Resume validation: " + str(error))
            if result is not old:
                try:
                    if row["source"] == "arxiv":
                        if not row.get("pdf_url"):
                            raise ValueError("Candidate has no PDF URL")
                        reuse = source / str(row.get("fulltext_path") or "__missing__")
                        if source not in reuse.resolve().parents:
                            reuse = None
                        result["files"].append(save_file(root,
                            "pdfs/" + row["paper_id"] + ".pdf", "pdf", row["pdf_url"],
                            reuse=reuse, expected_sha=row.get("pdf_sha256")))
                    elif row["source"] == "pubmed":
                        pmid = pmid_for(row)
                        query = urllib.parse.urlencode({"ids": pmid, "idtype": "pmid",
                            "format": "json", "tool": "SFT-study-paper-download"})
                        mapping_body = fetch(ID_API + "?" + query)
                        atomic(root / "metadata" / (row["paper_id"] + "-mapping.json"), mapping_body)
                        mapping = json.loads(mapping_body)
                        if mapping.get("status") != "ok":
                            raise ValueError("PMC identifier lookup failed")
                        matches = [r for r in mapping.get("records", [])
                            if str(r.get("requested-id") or r.get("pmid")) == pmid]
                        entry = matches[0] if matches else {}
                        result["pmid"] = pmid
                        pmcid = entry.get("pmcid")
                        if not pmcid:
                            result["status"] = "no_pmc_mapping"
                        elif str(entry.get("live", "")).lower() in ("false", "0"):
                            result["status"] = "embargoed"
                        else:
                            result["pmcid"] = pmcid
                            prefixes = pmc_versions(pmcid)
                            result["status"] = "no_cloud_fulltext" if not prefixes else "pending"
                            result["versions"] = []
                            for prefix in prefixes:
                                name = prefix.rstrip("/")
                                try:
                                    metadata_body = fetch(S3 + prefix + name + ".json")
                                    atomic(root / "metadata" / (row["paper_id"] + "-" + name + ".json"), metadata_body)
                                    metadata = json.loads(metadata_body)
                                    if str(metadata.get("pmid")) != pmid:
                                        raise ValueError("PMC metadata PMID mismatch")
                                    version = {"prefix": prefix, "is_manuscript": metadata.get("is_manuscript"),
                                        "license_code": metadata.get("license_code"),
                                        "is_retracted": metadata.get("is_retracted"),
                                        "files": []}
                                    result["versions"].append(version)
                                    for key, kind, folder in (("pdf_url", "pdf", "pdfs"),
                                        ("xml_url", "xml", "fulltext"), ("text_url", "txt", "fulltext")):
                                        if not metadata.get(key):
                                            continue
                                        try:
                                            saved = save_file(root, folder + "/" + row["paper_id"]
                                                + "-" + name + "." + kind, kind, metadata[key])
                                            version["files"].append(saved)
                                            result["files"].append(saved)
                                        except Exception as error:
                                            result["errors"].append(name + " " + kind + ": " + str(error))
                                except Exception as error:
                                    result["errors"].append(prefix + ": " + str(error))
                    else:
                        raise ValueError("Unsupported paper source")
                except Exception as error:
                    result["errors"].append(str(error))
                if result["files"]:
                    result["status"] = "downloaded_unchecked"
                elif result["errors"]:
                    result["status"] = "failed"
                else:
                    result.setdefault("status", "no_fulltext")
            results.append(result)
            # Include untouched records on interruption; rewrite atomically after each paper.
            unfinished = [{"paper_id": r["paper_id"], "source": r["source"], "status": "pending"}
                          for r in rows[len(results):]]
            atomic(prior_path, ("".join(json.dumps(r, ensure_ascii=False) + "\n"
                   for r in results + unfinished)).encode())
            print(f"{len(results)}/{len(rows)} {row['paper_id']}: {result['status']} "
                  f"({len(result['files'])} files)", flush=True)
            for error in result["errors"]:
                print("  " + error, flush=True)
        summary = {"candidates": len(rows), "status": dict(Counter(r["status"] for r in results)),
            "papers_with_pdf": sum(any(f["format"] == "pdf" for f in r["files"]) for r in results),
            "papers_with_fulltext_file": sum(bool(r["files"]) for r in results),
            "papers_with_download_errors": sum(bool(r["errors"]) for r in results),
            "output": str(root), "finished_at": stamp()}
        json_save(root / "download_summary.json", summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
        return 1 if summary["papers_with_download_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
