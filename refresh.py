"""Creative Performance Intelligence - refresh.

Rebuilds data/dashboard-data.js from every source listed in data/raw/sources.json.
The dashboard (index.html) never changes; only the data file does.

    python refresh.py

Standard library only. Raw files are read, never modified.
Rules that matter:
  * missing stays missing (None), never 0
  * duplicates removed by platform + post URL
  * when two sources describe one post, the later as_of wins field by field
  * every post keeps the id of the source its numbers came from
"""
import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "dashboard-data.js"
ICT = timezone(timedelta(hours=7))
METRICS = ["reach", "views", "reactions", "comments", "shares", "saves",
           "post_clicks", "link_clicks", "er"]
PLATFORM = {"facebook": "Facebook", "instagram": "Instagram", "tiktok": "TikTok"}


def brand_of(account):
    return "SURYA" if account.upper().startswith("SURYA") else "Monster and Friends"


def num(v):
    if v is None:
        return None
    v = str(v).replace(",", "").strip()
    if v == "" or v.lower() in ("n/a", "nan", "-"):
        return None
    try:
        f = float(v)
    except ValueError:
        return None
    return int(f) if f.is_integer() else f


def norm_url(u):
    return (u or "").split("?")[0].rstrip("/").lower()


def parse_dt(s):
    return datetime.strptime(s.strip()[:16], "%Y-%m-%d %H:%M")


def load_publer_csv(path):
    """Publer UI 'Post Insights' CSV: 5 preamble lines, then a header row."""
    lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    start = next(i for i, l in enumerate(lines) if l.startswith("Date,"))
    rows = list(csv.DictReader(io.StringIO("".join(lines[start:]))))
    seen_exact, out, exact_dupes = set(), [], 0
    for r in rows:
        sig = tuple(r.values())
        if sig in seen_exact:
            exact_dupes += 1
            continue
        seen_exact.add(sig)
        out.append({
            "brand": brand_of(r["Social account"]),
            "platform": PLATFORM.get(r["Social network"].lower(), r["Social network"]),
            "dt": r["Date"].strip()[:16],
            "format": (r["Post type"] or "Unknown").strip().title(),
            "url": r["Post link"].strip(),
            "text": r["Post text"] or "",
            "reach": num(r["Reach"]), "views": num(r["Video views"]),
            "reactions": num(r["Reactions"]), "comments": num(r["Comments"]),
            "shares": num(r["Shares"]), "er": num(r["Engagement rate (%)"]),
            "link_clicks": num(r["Link clicks"]),
        })
    return out, {"raw_rows": len(rows), "exact_duplicates": exact_dupes}


def classify(rules, brand, text, date="", overrides=()):
    for o in overrides:  # manual tags win over caption rules
        if o["brand"] == brand and o["from"] <= date <= o["to"] and o["contains"] in text:
            o["_hits"] = o.get("_hits", 0) + 1
            return o["pillar"]
    for rule in rules.get(brand, []):
        if rule["_re"].search(text):
            return rule["pillar"]
    return "Other"


def main():
    manifest = json.loads((RAW / "sources.json").read_text(encoding="utf-8"))
    sources = sorted(manifest["sources"], key=lambda s: s["as_of"])
    pillars = json.loads((ROOT / "config" / "pillars.json").read_text(encoding="utf-8"))
    rules = {b: [dict(r, _re=re.compile(r["pattern"], re.I | re.M)) for r in rs]
             for b, rs in pillars["brands"].items()}

    ov_path = ROOT / "config" / "pillar_overrides.json"
    overrides = json.loads(ov_path.read_text(encoding="utf-8"))["overrides"] if ov_path.exists() else []

    th_path = ROOT / "config" / "thumbnails.json"
    thumbs = json.loads(th_path.read_text(encoding="utf-8"))["thumbnails"] if th_path.exists() else {}

    posts, by_url, quality, account_rows = [], {}, {"sources": []}, []

    def find(rec):
        key = (rec["platform"], norm_url(rec.get("url")))
        if key[1] and key in by_url:
            return by_url[key]
        t = parse_dt(rec["dt"])
        for p in posts:  # fallback: same brand + platform within 3 minutes
            if (p["brand"] == rec["brand"] and p["platform"] == rec["platform"]
                    and abs((parse_dt(p["dt"]) - t).total_seconds()) <= 180):
                return p
        return None

    for src in sources:
        path = RAW / src["file"]
        stat = {"id": src["id"], "label": src["label"], "as_of": src["as_of"],
                "covers_from": src["covers_from"], "covers_to": src["covers_to"],
                "trust": src["trust"], "note": src.get("note", ""), "file": src["file"]}
        if src["type"] == "account_followers":
            accounts = json.loads(path.read_text(encoding="utf-8"))["accounts"]
            for a in accounts:
                a["as_of"], a["src"] = src["as_of"], src["id"]
            account_rows.extend(accounts)
            stat.update({"raw_rows": len(accounts), "new_posts": 0, "updated_posts": 0,
                         "duplicate_keys_dropped": 0, "kind": "account"})
            quality["sources"].append(stat)
            continue
        if src["type"] == "publer_csv":
            recs, s = load_publer_csv(path)
            stat.update(s)
        else:
            recs = json.loads(path.read_text(encoding="utf-8"))["records"]
            stat["raw_rows"] = len(recs)
        new = updated = key_dupes = 0
        touched = set()
        for rec in recs:
            p = find(rec)
            if p is None:
                p = {"brand": rec["brand"], "platform": rec["platform"], "dt": rec["dt"],
                     "format": rec.get("format", "Unknown"), "url": rec.get("url", ""),
                     "text": rec.get("text") or rec.get("title", ""),
                     "src": src["id"], "as_of": src["as_of"], "fields": {}}
                posts.append(p)
                if norm_url(p["url"]):
                    by_url[(p["platform"], norm_url(p["url"]))] = p
                new += 1
            elif id(p) in touched:
                key_dupes += 1  # same post listed twice in one source
                continue
            else:
                updated += 1
                if rec.get("url") and not p["url"]:
                    p["url"] = rec["url"]
                    by_url[(p["platform"], norm_url(p["url"]))] = p
            touched.add(id(p))
            for m in METRICS:
                if rec.get(m) is not None:
                    p[m] = rec[m]
                    p["fields"][m] = src["id"]
            if any(rec.get(m) is not None for m in METRICS):
                p["src"], p["as_of"] = src["id"], src["as_of"]
        stat.update({"new_posts": new, "updated_posts": updated,
                     "duplicate_keys_dropped": key_dupes})
        quality["sources"].append(stat)

    out_posts = []
    for i, p in enumerate(sorted(posts, key=lambda x: x["dt"])):
        text = p["text"].strip()
        hook = next((l.strip() for l in text.splitlines() if l.strip()), "")[:110]
        age = (datetime.fromisoformat(p["as_of"]) - parse_dt(p["dt"])).total_seconds() / 86400
        rec = {"id": i, "brand": p["brand"], "platform": p["platform"], "dt": p["dt"],
               "format": p["format"], "pillar": classify(rules, p["brand"], text, p["dt"][:10], overrides),
               "hook": hook, "url": p["url"], "src": p["src"], "as_of": p["as_of"],
               "age": round(age, 1), "pending": p.get("reach") is None}
        th = thumbs.get(p["platform"] + "|" + norm_url(p["url"]))
        if th and (ROOT / th["file"]).exists():
            rec["thumb"], rec["thumb_from"] = th["file"], th.get("cover_from")
        for m in METRICS:
            rec[m] = p.get(m)  # None = unknown / not reported
        out_posts.append(rec)

    latest_post = max(p["dt"] for p in out_posts)
    with_reach = [p for p in out_posts if p["reach"] is not None]
    coverage = {}
    for p in out_posts:
        c = coverage.setdefault(f'{p["brand"]} | {p["platform"]}',
                                {"posts": 0, "first": p["dt"], "last": p["dt"],
                                 "last_with_reach": None, "missing_reach": 0, "as_of": p["as_of"]})
        c["posts"] += 1
        c["last"] = max(c["last"], p["dt"])
        c["as_of"] = max(c["as_of"], p["as_of"])
        if p["reach"] is None:
            c["missing_reach"] += 1
        else:
            c["last_with_reach"] = max(c["last_with_reach"] or "", p["dt"])
    other = {}
    for p in out_posts:
        o = other.setdefault(p["brand"], [0, 0])
        o[0] += p["pillar"] == "Other"
        o[1] += 1

    insights_path = ROOT / "config" / "insights.th.json"
    insights = json.loads(insights_path.read_text(encoding="utf-8")) if insights_path.exists() else {}

    data = {
        "meta": {
            "generated_at": datetime.now(ICT).strftime("%Y-%m-%dT%H:%M"),
            "timezone": manifest["timezone"],
            "latest_post": latest_post,
            "latest_post_with_reach": max(p["dt"] for p in with_reach),
            "latest_source_as_of": max(s["as_of"] for s in sources if s["type"] != "account_followers"),
            "accounts": account_rows,
            "posts": len(out_posts),
            "coverage": coverage,
            "sources": quality["sources"],
            "pillar_other_share": {b: {"other": o[0], "total": o[1]} for b, o in other.items()},
            "pillar_overrides": {
                "posts": sum(o.get("_hits", 0) for o in overrides),
                "proposed": sum(o.get("_hits", 0) for o in overrides if o.get("status") != "confirmed"),
                "unused": [o["contains"] for o in overrides if not o.get("_hits")]},
            "pillar_labels": {b: {r["pillar"]: r["label"] for r in rs}
                              for b, rs in pillars["brands"].items()},
        },
        "insights": insights,
        "posts": out_posts,
    }
    OUT.write_text("window.CPI_DATA = " + json.dumps(data, ensure_ascii=False,
                   separators=(",", ":")) + ";\n", encoding="utf-8")

    print(f"posts: {len(out_posts)} | latest post: {latest_post} | "
          f"latest source as_of: {data['meta']['latest_source_as_of']}")
    for s in quality["sources"]:
        print(f"  {s['id']}: rows={s['raw_rows']} exact_dupes={s.get('exact_duplicates', 0)} "
              f"key_dupes={s['duplicate_keys_dropped']} new={s['new_posts']} updated={s['updated_posts']}")
    for k, c in sorted(coverage.items()):
        print(f"  {k}: n={c['posts']} last={c['last']} missing_reach={c['missing_reach']}")
    print("  pillar 'Other':", {b: f"{o[0]}/{o[1]}" for b, o in other.items()})
    print("  pillar overrides:", data["meta"]["pillar_overrides"])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
