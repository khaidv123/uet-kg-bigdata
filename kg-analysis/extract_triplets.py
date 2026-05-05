"""
Streaming extract: chỉ lấy head/relation/tail/stage/source từ JSON lớn.
Đọc line-by-line, không load toàn bộ file vào RAM.
"""
import csv, re, sys, time

INPUT  = "/home/ubuntu/kg-construct/batch-prompt/output/kg_raw_triplets_4k.json"
OUTPUT = "/home/ubuntu/kg-construct/analysis/output/triplets_extracted.csv"

# Regex patterns cho từng trường (JSON pretty-printed, mỗi field 1 dòng)
PAT = {
    "head":     re.compile(r'"head"\s*:\s*"(.*?)"\s*,?\s*$'),
    "relation": re.compile(r'"relation"\s*:\s*"(.*?)"\s*,?\s*$'),
    "tail":     re.compile(r'"tail"\s*:\s*"(.*?)"\s*,?\s*$'),
    "stage":    re.compile(r'"stage"\s*:\s*"(.*?)"\s*,?\s*$'),
    "source":   re.compile(r'"source"\s*:\s*"(.*?)"\s*,?\s*$'),
}

start = time.time()
count = 0
rec = {}
source_seen = False  # track if we already captured source for this record

with open(INPUT, "r", encoding="utf-8") as fin, \
     open(OUTPUT, "w", newline="", encoding="utf-8") as fout:
    writer = csv.writer(fout)
    writer.writerow(["head", "relation", "tail", "stage", "source"])

    for line in fin:
        stripped = line.strip()

        # Detect record boundary
        if stripped == "{":
            rec = {}
            source_seen = False
            continue
        if stripped in ("}", "},"):
            if len(rec) >= 4:  # head, relation, tail, stage at minimum
                writer.writerow([
                    rec.get("head", ""),
                    rec.get("relation", ""),
                    rec.get("tail", ""),
                    rec.get("stage", ""),
                    rec.get("source", ""),
                ])
                count += 1
                if count % 50000 == 0:
                    elapsed = time.time() - start
                    print(f"  {count:>10,} records  ({elapsed:.1f}s)", flush=True)
            rec = {}
            continue

        # Extract fields
        for key, pat in PAT.items():
            if key == "source" and source_seen:
                continue
            m = pat.search(stripped)
            if m:
                rec[key] = m.group(1)
                if key == "source":
                    source_seen = True
                break

elapsed = time.time() - start
print(f"Done: {count:,} triplets extracted in {elapsed:.1f}s")
print(f"Output: {OUTPUT}")
