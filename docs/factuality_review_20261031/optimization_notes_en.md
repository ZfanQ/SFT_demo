# Calibration Changes and Evidence Integrity

## Preserved versions

The original 200-paper snapshot preserves the historical same-version PDF extraction and current summary bytes. All 200 PDF hashes matched the scored versions; all 800 source-text hashes can be rechecked locally. Current Qwen/GPT/author-abstract hashes matched the earlier evidence-review manifest. The ten selected original PDFs were separately downloaded and hash-verified.

The first bounded trial (`calibration_v1`) accepted one review and rejected an evidence quotation in the second. Version 2 introduced up to two mechanical-validation retries, with independent sessions and all failed raw responses retained. It eventually accepted both cases, but one candidate needed three attempts. These diagnostic results are excluded from the final calibration counts.

Inspection of paper019 showed that the historical PyMuPDF `get_text(sort=True)` extraction interleaved left/right column lines. A sentence about all DM1 patients being detected was interrupted by unrelated text from the adjacent column. Reading the same PDF with `sort=False`, and independently with Poppler default reading order, recovered the contiguous passage. Consequently, the failure cannot simply be described as fabrication of scientific evidence: extraction order was a demonstrated contributor.

For version 3, all ten selected PDFs were re-extracted with Poppler default reading order, preserving PDF page breaks. The original PDFs, summaries and old text snapshots remain unchanged. Page counts, text lengths, PDF hashes and a concrete regression passage are checked in `inputs/reading_order_checks.json`. Version 3 uses `inputs/calibration_requests_reading_order_v3.json`; its extraction/protocol hashes are separate. Cross-version output counts must not be combined.

Count/length checks are only safeguards. They do not certify every table, figure, equation, supplementary file or page reading order. The human reader should open the original PDF for any doubtful evidence. Expansion to 200 Gemma summaries must first apply and audit the corrected extraction method to all eligible PDFs.

## Human review boundary

Exact quotation/page matching establishes that evidence exists in the supplied text; it cannot determine whether the interpretation is correct, whether a statistical nuance is material, or whether a reasonable summary is being judged too harshly. All new findings remain automated suspicions pending independent human calibration. Numerical flags are queue entries, not additional confirmed errors.

Review the blinded packet and PDFs before GPT conclusions. Save separate reviewer files and record any prior exposure. The packet contains 10 papers and 20 candidates; five papers were previously Gemma-flagged and five were unflagged. A separate 20-paper unflagged control set was reserved before the new reviews. Neither this enriched pilot nor the historical targeted review estimates a population error rate.
