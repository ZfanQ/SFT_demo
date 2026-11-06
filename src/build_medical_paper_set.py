#!/usr/bin/env python3
"""Build a PubMed-indexed medical/biomedical original-research full-paper corpus."""
import argparse
import csv
import difflib
import fcntl
import hashlib
import io
import json
import os
import random
import re
import shutil
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

S3 = "https://pmc-oa-opendata.s3.amazonaws.com/"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
IDCONV = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
FEED = "https://feed.scicommons.org/api/articles/items"
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
TOPICS = [
    ("neurology", '"Nervous System Diseases"[MeSH Terms]', r"nervous|neurolog|brain|stroke|dementia|alzheimer|parkinson|epilep|multiple sclerosis"),
    ("psychiatry", '"Mental Disorders"[MeSH Terms]', r"mental disorders|depress|anxiety|schizophren|bipolar|psychiatr|autism"),
    ("oncology", '"Neoplasms"[MeSH Terms]', r"neoplasm|cancer|carcinoma|tumor|tumour|leukemia|lymphoma|oncolog"),
    ("cardiovascular", '"Cardiovascular Diseases"[MeSH Terms]', r"cardiovascular|coronary|heart failure|myocardial|hypertension|atrial fibrillation"),
    ("endocrine_metabolic", '("Diabetes Mellitus"[MeSH Terms] OR "Metabolic Diseases"[MeSH Terms])', r"diabet|metabolic diseases|obesity|endocrin|thyroid"),
    ("infectious_disease", '("Communicable Diseases"[MeSH Terms] OR "Infections"[MeSH Terms])', r"infectious|infections|covid|tuberculosis|hiv|sepsis|hepatitis|pneumonia|viral|bacterial"),
    ("respiratory", '"Respiratory Tract Diseases"[MeSH Terms]', r"respiratory|pulmonary|asthma|lung diseases|copd"),
    ("gastroenterology", '"Digestive System Diseases"[MeSH Terms]', r"digestive|gastro|liver diseases|crohn|colitis|pancreat|cirrhosis"),
    ("renal_urology", '"Urologic Diseases"[MeSH Terms]', r"urologic|kidney|renal|dialysis|urinary|prostatic"),
    ("surgery_anesthesia", '("Surgical Procedures, Operative"[MeSH Terms] OR "Anesthesia"[MeSH Terms])', r"surgical|surgery|anesthe|anaesthe|perioperative|postoperative"),
]
EXCLUDED_PT = {"Review", "Systematic Review", "Meta-Analysis", "Case Reports", "Editorial", "Letter",
    "Comment", "Clinical Trial Protocol", "Published Erratum", "Retracted Publication", "Retraction of Publication", "Preprint"}
BAD_TITLE = re.compile(r"\b(protocol|systematic review|meta-analysis|meta analysis|scoping review|case report|case series|bibliometric|narrative review|consensus|guideline|editorial|perspective)\b", re.I)
API_LOCK = threading.Lock()
LAST_API = 0.0
TOKENIZER = None
MAX_ARTICLE_TOKENS = 39424


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_bytes(body)
    temporary.chmod(0o664)
    temporary.replace(path)


def savejson(path, value):
    write(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def checked_url(url):
    if url.startswith("s3://pmc-oa-opendata/"):
        url = url.replace("s3://pmc-oa-opendata/", S3, 1)
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or p.hostname not in {"pmc-oa-opendata.s3.amazonaws.com", "pmc.ncbi.nlm.nih.gov", "eutils.ncbi.nlm.nih.gov", "feed.scicommons.org"}:
        raise ValueError("Unexpected source URL: " + url)
    return url


def get(url):
    global LAST_API
    url = checked_url(url)
    if not url.startswith(S3):
        with API_LOCK:
            time.sleep(max(0, 0.45 - (time.monotonic() - LAST_API)))
            LAST_API = time.monotonic()
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SFT-biomedical-benchmark/0.1"})
            with urllib.request.urlopen(req, timeout=40) as response:
                checked_url(response.geturl())
                body = response.read(50 * 1024 * 1024 + 1)
            if len(body) > 50 * 1024 * 1024:
                raise ValueError("Source exceeds 50 MiB")
            expected = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("md5", [None])[0]
            if expected and hashlib.md5(body).hexdigest() != expected.lower():
                raise ValueError("PMC object MD5 mismatch")
            return body
        except urllib.error.HTTPError as error:
            if error.code not in (408, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))


def cached(path, url):
    if path.exists():
        body = path.read_bytes()
        expected = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("md5", [None])[0]
        if expected and hashlib.md5(body).hexdigest() != expected.lower():
            raise ValueError("Cached PMC object MD5 mismatch")
        return body
    body = get(url)
    write(path, body)
    return body


def plain(node):
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def truth(value):
    return str(value).lower() in ("true", "yes", "1")


def norm_words(text):
    text = unicodedata.normalize("NFKC", text).lower()
    words = re.findall(r"\w+", text)
    labels = {"background", "objective", "objectives", "purpose", "aim", "aims", "methods", "method", "results", "conclusion", "conclusions"}
    return [w for w in words if w not in labels]


def abstract_text(node):
    """Preserve author wording while separating XML section boundaries."""
    if node is None:
        return ""
    blocks = []
    for child in node:
        if child.tag == "title":
            continue
        if child.tag == "sec":
            heading = plain(child.find("title"))
            # Read each outer paragraph once; list-item paragraphs can be nested
            # inside it and must not be appended a second time.
            value = abstract_text(child)
            if heading and value:
                value = heading.rstrip(":") + ": " + value
            blocks.append(value)
        elif child.tag == "p":
            blocks.append(plain(child))
        else:
            value = plain(child)
            if value:
                blocks.append(value)
    if not blocks:
        return plain(node)
    return "\n\n".join(blocks)


def parse_pubmed(body):
    result = {}
    for node in ET.fromstring(body).findall("PubmedArticle"):
        pmid = node.findtext("MedlineCitation/PMID")
        art = node.find("MedlineCitation/Article")
        ids = {x.attrib.get("IdType"): x.text for x in node.findall("PubmedData/ArticleIdList/ArticleId")}
        abstract = "\n".join(plain(x) for x in art.findall("Abstract/AbstractText"))
        mesh = [plain(x) for x in node.findall("MedlineCitation/MeshHeadingList/MeshHeading/DescriptorName")]
        types = [plain(x) for x in art.findall("PublicationTypeList/PublicationType")]
        year = art.findtext("Journal/JournalIssue/PubDate/Year")
        if not year:
            year = (re.search(r"\b(20\d\d)\b", art.findtext("Journal/JournalIssue/PubDate/MedlineDate", "")) or [None, ""])[1]
        linked_retraction = [x.attrib.get("RefType") for x in node.findall("MedlineCitation/CommentsCorrectionsList/CommentsCorrections")
                             if x.attrib.get("RefType") in ("RetractionIn", "RetractionOf", "ExpressionOfConcernIn")]
        result[pmid] = {"pmid": pmid, "title": plain(art.find("ArticleTitle")), "pubmed_abstract": abstract,
            "journal": plain(art.find("Journal/Title")), "year": year, "doi": (ids.get("doi") or "").lower(),
            "mesh": mesh, "publication_types": types, "language": art.findtext("Language"),
            "pmcid": ids.get("pmc"), "retraction_flags": linked_retraction,
            "url": "https://pubmed.ncbi.nlm.nih.gov/" + pmid + "/"}
    return result


def eligibility(record):
    if "Humans" not in record["mesh"]:
        return "no_humans_mesh"
    if record["language"] != "eng":
        return "not_english"
    if not record["year"] or not 2022 <= int(record["year"]) <= 2026:
        return "outside_2022_2026"
    if set(record["publication_types"]) & EXCLUDED_PT or record["retraction_flags"]:
        return "excluded_publication_type_or_retraction"
    if BAD_TITLE.search(record["title"]):
        return "protocol_review_case_or_nonresearch_title"
    if len(record["pubmed_abstract"].split()) < 50:
        return "missing_or_short_author_abstract"
    return None


def xml_text(article):
    # Every textual section is retained, including original abstract and references.
    parts = [plain(article.find("front/article-meta/title-group/article-title"))]
    for abstract in article.findall("front/article-meta/abstract"):
        if abstract.attrib.get("abstract-type", "") not in ("graphical", "toc", "teaser"):
            parts.append(abstract_text(abstract))
    def append_blocks(node):
        if node.tag in ("article-title", "title", "p", "ref", "table", "disp-formula"):
            value = plain(node)
            if value:
                parts.append(value)
            # Nested list paragraphs, formulas and reference titles are already
            # included in their outer block; do not duplicate that text.
            return
        for child in node:
            append_blocks(child)
    for section in (article.find("body"), article.find("back"), article.find("floats-group")):
        if section is None:
            continue
        append_blocks(section)
    return "\n\n".join(parts) + "\n"


def inspect_candidate(root, record, mapping):
    pmid = record["pmid"]
    destination = root / "staging" / ("PMID" + pmid)
    destination.mkdir(parents=True, exist_ok=True)
    error = None
    try:
        pmcid = mapping.get("pmcid")
        if not pmcid:
            raise ValueError("no_pmc_mapping")
        if str(mapping.get("live", "")).lower() in ("false", "0"):
            raise ValueError("pmc_embargoed")
        query = urllib.parse.urlencode({"list-type": 2, "prefix": pmcid + ".", "delimiter": "/"})
        listing = ET.fromstring(cached(destination / "versions.xml", S3 + "?" + query))
        if listing.findtext("s:IsTruncated", namespaces=NS) == "true":
            raise ValueError("version_listing_truncated")
        prefixes = sorted(x.text for x in listing.findall("s:CommonPrefixes/s:Prefix", NS) if x.text)
        if not prefixes:
            raise ValueError("no_cloud_version")
        version_errors = []
        for prefix in prefixes:
            if not re.fullmatch(r"PMC\d+\.\d+/", prefix):
                continue
            name = prefix.rstrip("/")
            try:
                metadata = json.loads(cached(destination / (name + ".json"), S3 + prefix + name + ".json"))
                if str(metadata.get("pmid")) != pmid:
                    raise ValueError("version_pmid_mismatch")
                if truth(metadata.get("is_manuscript")) or truth(metadata.get("is_retracted")):
                    raise ValueError("manuscript_or_retracted_version")
                if not truth(metadata.get("is_pmc_openaccess")) or not metadata.get("pdf_url") or not metadata.get("xml_url"):
                    raise ValueError("not_open_access_with_pdf_and_xml")
                xml_body = cached(destination / (name + ".xml"), metadata["xml_url"])
                article = ET.fromstring(xml_body)
                if article.tag != "article" or article.attrib.get("article-type") not in ("research-article", "original-article", "clinical-trial"):
                    raise ValueError("not_original_research_article")
                ids = {x.attrib.get("pub-id-type"): plain(x) for x in article.findall("front/article-meta/article-id")}
                if ids.get("pmid") != pmid:
                    raise ValueError("fulltext_pmid_mismatch")
                if record["doi"] and ids.get("doi", "").lower() != record["doi"]:
                    raise ValueError("fulltext_doi_mismatch")
                author_abstracts = [x for x in article.findall("front/article-meta/abstract")
                    if x.attrib.get("abstract-type", "") not in ("graphical", "toc", "teaser")]
                abstract = abstract_text(author_abstracts[0]) if author_abstracts else ""
                if len(abstract.split()) < 50:
                    raise ValueError("missing_fulltext_author_abstract")
                score = difflib.SequenceMatcher(None, norm_words(abstract), norm_words(record["pubmed_abstract"]), autojunk=False).ratio()
                if score < 0.95:
                    raise ValueError(f"abstract_version_discrepancy:{score:.3f}")
                body = article.find("body")
                if body is None or len(plain(body).split()) < 800:
                    raise ValueError("missing_or_short_article_body")
                headings = " ".join(plain(x) for x in body.findall(".//sec/title"))
                if not re.search(r"method|material|patient|participant|study design|procedure", headings, re.I):
                    raise ValueError("no_methods_section")
                if not re.search(r"result|finding", headings, re.I):
                    raise ValueError("no_results_section")
                pdf_body = cached(destination / (name + ".pdf"), metadata["pdf_url"])
                if not pdf_body.startswith(b"%PDF-"):
                    raise ValueError("not_a_pdf")
                import pymupdf
                page_stats = []
                with pymupdf.open(stream=pdf_body, filetype="pdf") as doc:
                    if doc.page_count < 3 or doc.needs_pass:
                        raise ValueError("short_or_encrypted_pdf")
                    for page in doc:
                        raw = page.get_text()
                        pix = page.get_pixmap(matrix=pymupdf.Matrix(0.12, 0.12), alpha=False)
                        if not pix.width or not pix.height:
                            raise ValueError("unrenderable_pdf_page")
                        page_stats.append({"page": page.number + 1, "words": len(raw.split()), "characters": len(raw)})
                    if sum(p["words"] for p in page_stats) < 800:
                        raise ValueError("pdf_has_insufficient_digital_text")
                text = xml_text(article)
                tokens = len(TOKENIZER.encode(text, add_special_tokens=False)) if TOKENIZER else None
                if tokens is not None and tokens > MAX_ARTICLE_TOKENS:
                    raise ValueError(f"full_article_exceeds_context_budget:{tokens}>{MAX_ARTICLE_TOKENS}")
                write(destination / "author_abstract.txt", (abstract + "\n").encode())
                write(destination / "pubmed_abstract.txt", (record["pubmed_abstract"] + "\n").encode())
                write(destination / "fulltext.txt", text.encode())
                result = dict(record, pmcid=pmcid, version=name, abstract=abstract, abstract_source="same-version PMC JATS",
                    abstract_pubmed_similarity=score, abstract_verified_against_fulltext=True,
                    pdf_all_pages_rendered=True, pdf_page_stats=page_stats, pdf_pages=len(page_stats),
                    fulltext_words=len(text.split()), body_words=len(plain(body).split()), section_headings=headings,
                    qwen3_8b_full_article_tokens=tokens,
                    license_code=metadata.get("license_code"), is_manuscript=False, is_retracted=False,
                    pmc_metadata=metadata, checked_at=now(), split="unassigned", staging_path=str(destination),
                    stage_files={"paper.pdf": name + ".pdf", "fulltext.xml": name + ".xml",
                        "author_abstract.txt": "author_abstract.txt", "pubmed_abstract.txt": "pubmed_abstract.txt", "fulltext.txt": "fulltext.txt"})
                savejson(destination / "validation.json", result)
                return result, None
            except Exception as issue:
                version_errors.append(name + ":" + str(issue))
        raise ValueError("; ".join(version_errors) or "no_eligible_version")
    except Exception as issue:
        error = str(issue)
        savejson(destination / "rejection.json", {"pmid": pmid, "reason": error, "checked_at": now()})
        return None, error


def main():
    global TOKENIZER
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "papers_200_20261011")
    parser.add_argument("--per-topic", type=int, default=20)
    parser.add_argument("--search-candidates", type=int, default=150)
    parser.add_argument("--feed-pages", type=int, default=10)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    os.umask(0o002)
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    # A completed flat collection is frozen; verify without recreating old folders.
    flat_summary = root / "Metadata/summary.json"
    if flat_summary.exists():
        metadata = json.loads(flat_summary.read_text())
        if metadata.get("status") != "complete":
            raise ValueError("Existing flat collection is incomplete; inspect it before rebuilding")
        frozen = [json.loads(line) for line in (root/"Metadata/manifest.jsonl").read_text().splitlines() if line.strip()]
        if len(frozen) != metadata["target"] or len(frozen) != len(TOPICS)*args.per_topic:
            raise ValueError("Frozen collection size differs from requested target")
        for row in frozen:
            for asset in row["files"].values():
                if sha((root/asset["path"]).read_bytes()) != asset["sha256"]:
                    raise ValueError("Frozen asset failed hash validation: " + asset["path"])
        print("Completed flat collection verified: 200 papers; no downloads or layout changes", flush=True)
        return 0
    for folder in ("raw", "metadata", "staging", "papers", "logs"):
        (root / folder).mkdir(exist_ok=True)
    lock = (root / ".build.lock").open("a+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    summary_path = root / "summary.json"
    if summary_path.exists():
        previous = json.loads(summary_path.read_text())
        if previous.get("status") == "complete":
            if previous.get("target") != len(TOPICS)*args.per_topic:
                raise ValueError("Completed collection has a different target size")
            manifest = [json.loads(x) for x in (root/"manifest.jsonl").read_text().splitlines() if x.strip()]
            for row in manifest:
                for asset in row["files"].values():
                    assert sha((root/asset["path"]).read_bytes()) == asset["sha256"]
            print("Completed frozen collection verified; no new downloads", flush=True)
            return 0
    policy = {"target": len(TOPICS)*args.per_topic, "topics": [x[0] for x in TOPICS], "per_topic": args.per_topic,
        "source_priority": "SciCommons PubMed records, supplemented with PubMed/PMC", "seed": 20261011,
        "language": "English", "years": [2022, 2026], "humans_mesh_required": True,
        "original_research_only": True, "published_open_access_version_with_pdf_xml_abstract": True,
        "excluded_publication_types": sorted(EXCLUDED_PT), "journal_cap": 25,
        "abstract_pubmed_match_min": .95, "minimum_body_words": 800,
        "input": "Whole article, including abstract, tables/captions, references and appendices present in JATS; no truncation",
        "limitations": "Automatic structural/topic/version checks, not a manual scientific-quality audit. PDF images/equation appearance are preserved in PDF; text representation is approximate.",
        "meeting_alignment": "Full-paper summarization, separate author abstract reference, identical inputs across models, first ~10 for debugging, scale based on speed/quality; no teacher summaries or model inference generated here."}
    savejson(root / "metadata/selection_policy.json", policy)
    from transformers import AutoTokenizer
    TOKENIZER = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B", cache_dir="/data/SFT_demo/.cache/huggingface/hub", local_files_only=True)
    policy["full_article_token_budget"] = {"tokenizer":"Qwen/Qwen3-8B", "article_text_max":MAX_ARTICLE_TOKENS,
        "context_cap":40960, "reserved_for_chat_and_output":1536, "no_truncation":True}
    savejson(root / "metadata/selection_policy.json", policy)
    feed, feed_error, cursor, snapshot = {}, None, "", None
    for page in range(1, args.feed_pages+1):
        query = {"source":"pubmed", "limit":100, "sort":"recent", "time_window":"all"}
        if cursor: query["cursor"] = cursor
        url = FEED + "?" + urllib.parse.urlencode(query)
        try:
            raw = cached(root / "raw" / f"scicommons_pubmed_{page}.json", url)
            value = json.loads(raw)
            if snapshot is None: snapshot = value["artifact_version"]
            if snapshot != value["artifact_version"]: raise ValueError("Feed snapshot changed during pagination")
            for item in value["items"]:
                pmid = str(item.get("external_id") or "")
                if pmid.isdigit():feed[pmid] = item
            next_cursor = value.get("next_cursor")
            if not value.get("has_more") or not next_cursor:break
            if next_cursor == cursor:raise ValueError("Repeated feed cursor")
            cursor = next_cursor
            print(f"FEED page {page}: {len(feed)} unique PubMed records", flush=True)
        except Exception as issue:
            feed_error = str(issue);break
    savejson(root / "metadata/feed_snapshot.json", {"artifact_version": snapshot, "records": len(feed), "error": feed_error, "url": FEED})
    print(f"FEED ready: {len(feed)} records; error={feed_error}", flush=True)
    queries, query_sets, all_ids = {}, {}, set(feed)
    base = '(humans[MeSH Terms]) AND "pubmed pmc"[sb] AND english[lang] AND 2022/01/01:2026/10/11[PDAT] NOT (review[pt] OR systematic review[pt] OR meta-analysis[pt] OR case reports[pt] OR editorial[pt] OR letter[pt] OR clinical trial protocol[pt] OR retracted publication[pt] OR published erratum[pt] OR preprint[pt])'
    for topic, medical_query, _ in TOPICS:
        term = "(" + medical_query + ") AND " + base
        url = EUTILS + "esearch.fcgi?" + urllib.parse.urlencode({"db":"pubmed", "retmode":"json", "retmax":args.search_candidates, "sort":"pub_date", "term":term, "tool":"SFT-biomedical-benchmark"})
        value = json.loads(cached(root / "raw" / ("pubmed_search_" + topic + "_" + sha(term.encode())[:10] + ".json"), url))["esearchresult"]
        if value.get("errorlist") or value.get("warninglist", {}).get("phrasesignored"):
            raise ValueError("Invalid search query: " + topic + " " + str(value))
        query_sets[topic] = set(value["idlist"]);all_ids.update(value["idlist"])
        queries[topic] = {"url":url,"term":term,"total_matches":int(value["count"]),"candidate_pmids":value["idlist"]}
        print(f"SEARCH {topic}: {len(value['idlist'])} candidates / {value['count']} matches", flush=True)
    savejson(root / "metadata/search_queries.json", queries)
    ids = sorted(all_ids, key=int, reverse=True)
    records = {}
    for start in range(0, len(ids), 200):
        url = EUTILS + "efetch.fcgi?" + urllib.parse.urlencode({"db":"pubmed", "id":",".join(ids[start:start+200]), "retmode":"xml", "tool":"SFT-biomedical-benchmark"})
        raw = cached(root / "raw" / ("pubmed_records_" + sha(",".join(ids[start:start+200]).encode())[:12] + ".xml"), url)
        records.update(parse_pubmed(raw))
        print(f"METADATA {len(records)}/{len(ids)}", flush=True)
    queues, rejected_metadata = {x[0]:[] for x in TOPICS}, []
    for pmid in ids:
        r = records.get(pmid)
        if not r:
            rejected_metadata.append({"pmid":pmid,"reason":"pubmed_record_missing"});continue
        issue = eligibility(r)
        if issue:
            rejected_metadata.append({"pmid":pmid,"reason":issue});continue
        assigned = [topic for topic,_,_ in TOPICS if pmid in query_sets[topic]]
        if not assigned and pmid in feed:
            medical_text = " ".join(r["mesh"] + [r["title"]])
            assigned = [topic for topic,_,pattern in TOPICS if re.search(pattern, medical_text, re.I)]
        if not assigned:
            rejected_metadata.append({"pmid":pmid,"reason":"outside_medical_topic_strata"});continue
        r["source"] = "scicommons_pubmed" if pmid in feed else "pubmed_pmc_supplement"
        if pmid in feed:r["scicommons_record"] = feed[pmid]
        r["eligible_topics"] = assigned
        for topic in assigned:queues[topic].append(r)
    savejson(root / "metadata/metadata_exclusions.json", rejected_metadata)
    eligible_ids = sorted({r["pmid"] for q in queues.values() for r in q},key=int,reverse=True)
    mappings = {}
    for start in range(0, len(eligible_ids), 200):
        url = IDCONV + "?" + urllib.parse.urlencode({"ids":",".join(eligible_ids[start:start+200]), "idtype":"pmid", "format":"json", "tool":"SFT-biomedical-benchmark"})
        value = json.loads(cached(root / "raw" / ("pmc_mapping_" + sha(",".join(eligible_ids[start:start+200]).encode())[:12] + ".json"), url))
        if value.get("status") != "ok":raise ValueError("ID mapping failed")
        for entry in value["records"]:mappings[str(entry.get("requested-id") or entry.get("pmid"))] = entry
    selected, outcomes, used_pmids, used_dois, journal_counts = [], {}, set(), set(), Counter()
    rejection_log = root / "logs/selection_rejections.jsonl"
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for topic,_,_ in TOPICS:
            q = queues[topic]
            rng = random.Random(20261011 + [x[0] for x in TOPICS].index(topic))
            supplement = [r for r in q if r["source"] != "scicommons_pubmed"]
            rng.shuffle(supplement)
            q = [r for r in q if r["source"] == "scicommons_pubmed"] + supplement
            count = 0
            remaining = [r for r in q if r["pmid"] not in used_pmids and (not r["doi"] or r["doi"] not in used_dois)]
            for start in range(0, len(remaining), args.workers):
                batch = remaining[start:start+args.workers]
                jobs = {}
                for r in batch:
                    if r["pmid"] not in outcomes and journal_counts[r["journal"]] < policy["journal_cap"]:
                        if not mappings.get(r["pmid"], {}).get("pmcid"):
                            outcomes[r["pmid"]] = (None, "no_pmc_mapping")
                        else:jobs[r["pmid"]] = pool.submit(inspect_candidate, root, r, mappings[r["pmid"]])
                for r in batch:
                    if count >= args.per_topic:break
                    if journal_counts[r["journal"]] >= policy["journal_cap"]:continue
                    if r["pmid"] in jobs:outcomes[r["pmid"]] = jobs[r["pmid"]].result()
                    good, issue = outcomes.get(r["pmid"], (None,"journal_cap"))
                    if not good:
                        with rejection_log.open("a") as log:log.write(json.dumps({"pmid":r["pmid"],"topic":topic,"reason":issue},ensure_ascii=False)+"\n")
                        print(f"REJECT {topic} PMID{r['pmid']}: {issue}",flush=True);continue
                    if good["pmid"] in used_pmids or (good["doi"] and good["doi"] in used_dois):continue
                    paper_id = f"med_{len(selected)+1:04d}"
                    final = root / "papers" / paper_id
                    final.mkdir(exist_ok=True)
                    good = dict(good, paper_id=paper_id, topic=topic, files={})
                    for newname,oldname in good["stage_files"].items():
                        body = (Path(good["staging_path"])/oldname).read_bytes()
                        write(final/newname,body)
                        good["files"][newname] = {"path":str((final/newname).relative_to(root)),"bytes":len(body),"sha256":sha(body)}
                    savejson(final/"metadata.json",good)
                    selected.append(good);used_pmids.add(good["pmid"])
                    if good["doi"]:used_dois.add(good["doi"])
                    journal_counts[good["journal"]] += 1;count += 1
                    write(root/"manifest.jsonl",("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in selected)).encode())
                    savejson(root/"progress.json",{"selected":len(selected),"target":policy["target"],"topics":dict(Counter(x["topic"] for x in selected)),"updated_at":now()})
                    print(f"ACCEPT {len(selected)}/{policy['target']} {paper_id} {topic} PMID{good['pmid']} {good['pdf_pages']} pages: {good['title']}",flush=True)
                # Await extra speculative validations and retain for later topic reuse.
                for pmid,job in jobs.items():
                    if pmid not in outcomes:outcomes[pmid]=job.result()
                if count >= args.per_topic:break
            print(f"TOPIC {topic}: {count}/{args.per_topic}",flush=True)
    expected = policy["target"]
    complete = len(selected) == expected and all(sum(x["topic"]==t for x in selected)==args.per_topic for t,_,_ in TOPICS)
    verified = 0
    for r in selected:
        for asset in r["files"].values():
            assert sha((root/asset["path"]).read_bytes()) == asset["sha256"]
            verified += 1
    csvbuf = io.StringIO()
    fields = ["paper_id","topic","pmid","pmcid","doi","year","journal","title","source","pdf_pages","fulltext_words","abstract_pubmed_similarity","license_code"]
    writer = csv.DictWriter(csvbuf,fieldnames=fields,extrasaction="ignore");writer.writeheader();writer.writerows(selected)
    write(root/"papers.csv",csvbuf.getvalue().encode())
    suggestions=[]
    for topic,_,_ in TOPICS:
        values=sorted([r for r in selected if r["topic"]==topic],key=lambda r:r["fulltext_words"])
        if values:suggestions.append(values[len(values)//2]["paper_id"])
    savejson(root/"suggested_dev_10.json",{"paper_ids":suggestions,"purpose":"One medium-length article per topic for initial debugging; not a frozen train/test split. Replace with familiar articles after team review."})
    summary={"status":"complete" if complete else "incomplete","target":expected,"selected":len(selected),
        "topics":dict(Counter(x["topic"] for x in selected)),"sources":dict(Counter(x["source"] for x in selected)),
        "journals":dict(journal_counts),"all_have_pdf_xml_abstract":all(x["pdf_all_pages_rendered"] and x["abstract_verified_against_fulltext"] for x in selected),
        "unique_pmids":len(used_pmids),"verified_asset_files":verified,"finished_at":now(),"output":str(root),
        "raw_source_responses":"raw/","manual_scientific_review":"not_performed"}
    savejson(root/"summary.json",summary)
    readme=f'''Medical full-paper corpus — 2026-10-11\n\nStatus: {summary['status']}; selected {len(selected)}/{expected}.\nScope: English medical and disease-related biomedical original research, PubMed indexed, 2022–2026; Humans MeSH is an indexing criterion, not a guarantee of a human clinical trial.\nTen medical topic strata; {args.per_topic} papers each. Website PubMed candidates prioritized; PubMed/PMC supplementation authorized.\nEvery selected paper has published open-access PDF (every page parsed and rendered), same-version full JATS XML, independent author abstract and full article text. Abstract matched with PubMed (>=95% token-sequence similarity). Unique PMID and DOI.\nRead summary.json, papers.csv and manifest.jsonl. Per-paper files are under papers/med_XXXX/.\nRaw API responses and frozen query/selection policy are in raw/ and metadata/.\nRejected and unused download candidates are under staging/; they are NOT members of the 200-paper corpus.\nMethods/results/body structure checked. Scientific quality, table/equation interpretation and factual adequacy have NOT been manually certified.\nNo truncation or model inference. Whole-paper TXT includes original abstract, references and extractable JATS captions/tables. PDF preserves visual information.\nAuthor abstracts are references; they are not replacements for full-paper model input or absolute gold summaries.\nSuggested first 10 are in suggested_dev_10.json; all papers remain unassigned to train/dev/test. Teacher references and four-model outputs still need generation.\n200 papers, years, Humans MeSH filter and topic quotas are implementation choices, not frozen professor requirements.\nBias: accessible English PubMed-indexed original research with Humans MeSH; recent records without Humans MeSH, closed-access papers and reviews are excluded. This is not the entire SciCommons feed.\nSources: SciCommons API; NCBI PubMed eSearch/eFetch; PMC ID Converter; PMC official Cloud Service (https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/).\n'''
    write(root/"README.txt",readme.encode())
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
