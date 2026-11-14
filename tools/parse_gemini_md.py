"""Parse the per-post MTD tables out of Gemini's report (markdown export of the
Google Doc) into a supplement JSON that refresh.py can overlay.

Usage:  python tools/parse_gemini_md.py <gemini-report.md> <out.json> <source_id>

Only the tables under headings containing "SURYA Coffee Explorers —" and
"Monster and Friends —" in section B.3 are read. Values are copied as written:
"N/A" and "Missing" become absent fields (unknown), never zero.
"""
import json
import re
import sys


def num(s):
    s = s.replace("*", "").replace("\\", "").replace(",", "").replace("%", "").strip()
    if not s or s.upper() == "N/A" or "missing" in s.lower():
        return None
    m = re.match(r"^-?\d+(\.\d+)?", s)
    return float(m.group()) if m else None


def triple(s, n):
    parts = [num(p) for p in s.split("/")]
    return (parts + [None] * n)[:n]


def main(src, out, source_id):
    brand, records = None, []
    for line in open(src, encoding="utf-8"):
        if line.startswith("### "):
            brand = ("SURYA" if "SURYA" in line else
                     "Monster and Friends" if "Monster" in line else None)
            continue
        if line.startswith("# ") or line.startswith("## "):
            if "รายโพสต์" not in line:
                brand = None
            continue
        if not brand or not line.startswith("|"):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) < 12 or c[0] not in ("Instagram", "Facebook"):
            continue
        reactions, comments, shares = triple(c[6], 3)
        rec = {"brand": brand, "platform": c[0], "dt": c[1], "format": c[2],
               "title": re.sub(r"\s+", " ", c[3].replace("\\", "")).strip()}
        vals = {"reach": num(c[4]), "views": num(c[5]), "reactions": reactions,
                "comments": comments, "shares": shares, "er": num(c[10])}
        if c[0] == "Instagram":
            vals["saves"] = num(c[7])
        else:
            vals["post_clicks"], vals["link_clicks"] = triple(c[8], 2)
        rec.update({k: v for k, v in vals.items() if v is not None})
        if "reach" not in rec:
            rec["pending"] = True
        records.append(rec)
    json.dump({"_about": "Parsed from Gemini's report; see sources.json.",
               "source_id": source_id, "records": records},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(records)} rows -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
