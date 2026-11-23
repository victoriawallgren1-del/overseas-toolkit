#!/usr/bin/env python3
"""
海外关键词暴力扩词（只用标准库，不用 pip install）。

用搜索框联想接口（Amazon / Google / YouTube / Bing）把种子词扩成几百上千个真实被搜过的词：
  种子词 + a~z / 0~9 / 疑问词 / 介词 / 人群 / 场景 ...  （后缀）
  疑问词 / 人群 / 场景 + 种子词                          （前缀，full 档）
  对高频联想词再扩一轮                                   （depth 2，full 档）
另外会输出 title_words.csv：高频词排行，写 TikTok 标题时按它挑词。

某个来源连续失败就自动停用并在报告里写明（对应"抓不到就换"）。
热度说明：联想排名只是热度的代理，不是搜索量。

用法：
  python3 expand_keywords.py --seeds "food storage container" "lunch box" --level full --out ./kw
  python3 expand_keywords.py --seeds "lunch box" --probe-only     # 先测各来源通不通，几秒出结果
  python3 expand_keywords.py --seeds-file seeds.txt --sources amazon google --market us --dry-run
  python3 expand_keywords.py --seeds "lunch box" --merge helium10.csv 卖家精灵.csv --out ./kw
"""
import argparse, csv, json, os, random, re, string, sys, threading, time
import urllib.parse, urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

AMAZON_MARKETS = {  # tld, mid, 旧接口 mkt
    "us": ("com", "ATVPDKIKX0DER", 1),
    "uk": ("co.uk", "A1F83G8C2ARO7P", 3),
    "de": ("de", "A1PA6795UKMFR9", 4),
    "ca": ("ca", "A2EUQ1WTGCTBG2", 7),
}
LANG = {"us": ("en", "us"), "uk": ("en", "gb"), "de": ("de", "de"), "ca": ("en", "ca")}

WORD_MODS = ["how to", "how", "what", "why", "can", "does", "is", "are", "which", "best", "top",
             "cheap", "for", "with", "without", "vs", "versus", "or", "near me", "review",
             "reviews", "problems", "complaints", "worth it", "alternative", "set", "kit",
             "gift", "sale", "deals", "amazon", "tiktok", "reddit", "walmart", "target"]
CONTEXT_MODS = ["men", "women", "kids", "toddler", "baby", "mom", "dad", "teen", "student",
                "seniors", "dog", "cat", "beginner", "small", "large", "big", "mini",
                "portable", "travel", "office", "school", "work", "gym", "camping", "picnic",
                "outdoor", "car", "home", "kitchen", "bathroom", "bedroom", "garden",
                "christmas", "halloween", "valentines", "birthday", "gift for"]

PAIN = ["leak", "smell", "stink", "odor", "stain", "crack", "break", "broke", "warp", "melt",
        "rust", "peel", "fade", "loose", "stuck", "hard to clean", "flimsy", "cheap quality",
        "toxic", "bpa", "chemical", "not safe", "doesn't work", "stopped working", "problem",
        "complaint", "issue", "worst", "disappoint", "return", "refund", "fall apart"]
SCENE = ["for work", "for school", "for office", "for travel", "for camping", "for picnic",
         "for kids", "for baby", "for gym", "for car", "meal prep", "lunch", "dinner", "breakfast",
         "freezer", "fridge", "microwave", "dishwasher", "oven", "outdoor", "kitchen", "pantry",
         "organization", "organizer", "gift", "christmas", "halloween", "birthday", "wedding",
         "party", "daily", "morning", "weekend", "small space", "apartment", "dorm"]
QUESTION = ("how", "what", "why", "can", "does", "is", "are", "which", "do", "where", "when")


# ---------- 抓取 ----------
def build_url(source, q, market):
    qq = urllib.parse.quote(q)
    hl, gl = LANG.get(market, ("en", "us"))
    if source == "google":
        return f"https://suggestqueries.google.com/complete/search?client=firefox&hl={hl}&gl={gl}&q={qq}"
    if source == "youtube":
        return f"https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl={hl}&gl={gl}&q={qq}"
    if source == "bing":
        return f"https://api.bing.com/osjson.aspx?query={qq}"
    if source == "amazon":
        tld, mid, _ = AMAZON_MARKETS.get(market, AMAZON_MARKETS["us"])
        return (f"https://completion.amazon.{tld}/api/2017/suggestions?mid={mid}"
                f"&alias=aps&prefix={qq}&limit=11")
    raise ValueError(source)


def amazon_legacy_url(q, market):
    tld, _, mkt = AMAZON_MARKETS.get(market, AMAZON_MARKETS["us"])
    return (f"https://completion.amazon.{tld}/search/complete?search-alias=aps"
            f"&client=amazon-search-ui&mkt={mkt}&q={urllib.parse.quote(q)}")


def fetch_text(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def parse_suggestions(text):
    """兼容 [q, [s1, s2...]] 和 {"suggestions":[{"value":..}]} 两种格式。"""
    data = json.loads(text)
    out = []
    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
        for s in data[1]:
            out.append(s if isinstance(s, str) else (s.get("value") or s.get("suggestion") or ""))
    elif isinstance(data, dict):
        for s in data.get("suggestions", []):
            out.append(s.get("value", "") if isinstance(s, dict) else str(s))
    return [norm(s) for s in out if s and norm(s)]


def norm(s):
    return re.sub(r"\s+", " ", s.strip().lower())


class Runner:
    def __init__(self, market, delay, workers, timeout=6, deadline=None, fail_limit=3):
        self.market, self.delay, self.workers = market, delay, workers
        self.timeout, self.deadline, self.fail_limit = timeout, deadline, fail_limit
        self.lock = threading.Lock()
        self.ok = defaultdict(int)
        self.fail = defaultdict(int)
        self.streak = defaultdict(int)
        self.disabled = set()
        self.last_error = {}
        self.timed_out = False

    def one(self, source, q, probe=False):
        if source in self.disabled:
            return source, q, None
        if self.deadline and time.time() > self.deadline:
            self.timed_out = True
            return source, q, None
        if not probe:
            time.sleep(self.delay * (0.5 + random.random()))
        err = None
        attempts = 1 if probe else 2
        for attempt in range(attempts):
            try:
                url = build_url(source, q, self.market)
                try:
                    res = parse_suggestions(fetch_text(url, self.timeout))
                except Exception as e:
                    if source == "amazon":  # 新接口不行就试旧接口
                        res = parse_suggestions(fetch_text(amazon_legacy_url(q, self.market), self.timeout))
                    else:
                        raise e
                with self.lock:
                    self.ok[source] += 1
                    self.streak[source] = 0
                return source, q, res
            except Exception as e:  # noqa
                err = e
                if attempt < attempts - 1:
                    time.sleep(0.5)
        with self.lock:
            self.fail[source] += 1
            self.streak[source] += 1
            self.last_error[source] = repr(err)[:200]
            if self.streak[source] >= self.fail_limit and self.ok[source] == 0:
                self.disabled.add(source)
        return source, q, None

    def probe(self, sources, q):
        """正式开跑前，每个来源先试一次（几秒内出结果），不通的直接停用。"""
        alive = []
        with ThreadPoolExecutor(max_workers=max(1, len(sources))) as ex:
            futs = {ex.submit(self.one, s, q, True): s for s in sources}
            for f in as_completed(futs):
                s = futs[f]
                if f.result()[2] is None:
                    self.disabled.add(s)
                else:
                    alive.append(s)
        return [s for s in sources if s in alive]

    def run(self, jobs, progress=True):
        """jobs: [(source, query, pattern)] -> [(source, query, pattern, [suggestions])]"""
        results, done, t0 = [], 0, time.time()
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = {ex.submit(self.one, s, q): (s, q, p) for s, q, p in jobs}
            for f in as_completed(futs):
                s, q, p = futs[f]
                _, _, res = f.result()
                if res is not None:
                    results.append((s, q, p, res))
                done += 1
                if progress and done % 25 == 0:
                    print(f"  {done}/{len(jobs)}  已用 {int(time.time()-t0)}s  "
                          f"已得 {len(results)} 批结果  停用来源: {sorted(self.disabled) or '无'}",
                          file=sys.stderr, flush=True)
        return results


# ---------- 构造查询 ----------
def build_jobs(seeds, sources, level):
    jobs = []
    letters = list(string.ascii_lowercase)
    digits = list(string.digits)
    for seed in seeds:
        for src in sources:
            jobs.append((src, seed, "seed"))
            for ch in letters:
                jobs.append((src, f"{seed} {ch}", "letter"))
            if level in ("normal", "full"):
                for d in digits:
                    jobs.append((src, f"{seed} {d}", "digit"))
                for m in WORD_MODS:
                    jobs.append((src, f"{seed} {m}", "suffix"))
            if level == "full":
                for m in CONTEXT_MODS:
                    jobs.append((src, f"{seed} {m}", "context"))
                for m in WORD_MODS + CONTEXT_MODS:
                    jobs.append((src, f"{m} {seed}", "prefix"))
    return jobs


def add_results(store, results, seeds):
    for src, q, pattern, sugg in results:
        for rank, kw in enumerate(sugg, 1):
            e = store.setdefault(kw, {"sources": set(), "best_rank": 99, "patterns": set(),
                                      "seeds": set(), "hits": 0})
            e["sources"].add(src)
            e["best_rank"] = min(e["best_rank"], rank)
            e["patterns"].add(pattern)
            e["hits"] += 1
            for s in seeds:
                if q == s or q.startswith(s + " ") or q.endswith(" " + s):
                    e["seeds"].add(s)


def second_round_seeds(store, seeds, top_k):
    picks = []
    for seed in seeds:
        cands = [(k, v) for k, v in store.items()
                 if seed in v["seeds"] and k != seed and len(k.split()) <= len(seed.split()) + 3]
        cands.sort(key=lambda kv: (-len(kv[1]["sources"]), kv[1]["best_rank"], -kv[1]["hits"]))
        picks += [k for k, _ in cands[:top_k]]
    return list(dict.fromkeys(picks))


# ---------- 导入用户贴来的数据 ----------
KW_COLS = ["keyword", "keywords", "keyword phrase", "search term", "search terms", "query",
           "关键词", "搜索词", "关键字", "词", "hashtag", "话题"]


def merge_csv(store, path):
    n = 0
    for enc in ("utf-8-sig", "gbk", "utf-8"):
        try:
            with open(path, newline="", encoding=enc) as f:
                rows = list(csv.reader(f))
            break
        except UnicodeDecodeError:
            rows = None
    if not rows:
        return 0
    header = [h.strip().lower() for h in rows[0]]
    idx = next((header.index(c) for c in KW_COLS if c in header), 0)
    label = "import:" + os.path.basename(path)
    for r in rows[1:]:
        if len(r) > idx and r[idx].strip():
            kw = norm(r[idx].lstrip("#"))
            e = store.setdefault(kw, {"sources": set(), "best_rank": 99, "patterns": set(),
                                      "seeds": set(), "hits": 0})
            e["sources"].add(label)
            e["patterns"].add("import")
            e["hits"] += 1
            n += 1
    return n


# ---------- 标注 ----------
def tag(kw):
    if any(p in kw for p in PAIN):
        return "痛点候选"
    if kw.split()[0] in QUESTION:
        return "问题词"
    if any(s in kw for s in SCENE):
        return "场景候选"
    return "搜索词"


def heat(e):
    if e["best_rank"] <= 3 and len(e["sources"]) >= 2:
        return "高"
    if e["best_rank"] <= 6 or len(e["sources"]) >= 2:
        return "中"
    if e["best_rank"] == 99:
        return "未知"
    return "低"


def on_topic(kw, seeds):
    for s in seeds:
        toks = [t for t in s.split() if len(t) > 2]
        if toks and all(t.rstrip("s") in kw for t in toks):
            return True
    return False


TITLE_STOP = {"a", "an", "the", "for", "and", "or", "of", "to", "in", "on", "at", "with", "without",
              "how", "what", "why", "can", "does", "is", "are", "which", "do", "where", "when",
              "vs", "versus", "near", "me", "my", "i", "you", "your", "best", "top", "cheap",
              "review", "reviews", "amazon", "tiktok", "reddit", "walmart", "target", "sale",
              "deals", "worth", "it", "problems", "complaints", "alternative", "youtube", "bing",
              "google", "from", "that", "this", "get", "buy", "made", "make"}


def title_words(rows, seeds):
    """从贴题词里统计高频单词，给写标题用：哪些词最常和产品一起出现。"""
    seed_toks = {t for s in seeds for t in s.split()}
    cnt, wt, ex = defaultdict(int), defaultdict(int), defaultdict(list)
    for r in rows:
        if not r["on_topic"]:
            continue
        for tok in set(re.findall(r"[a-z][a-z\-']+", r["keyword"])):
            if tok in TITLE_STOP or len(tok) < 3:
                continue
            cnt[tok] += 1
            wt[tok] += r["source_count"]
            if len(ex[tok]) < 3:
                ex[tok].append(r["keyword"])
    out = [{"word": t, "keyword_count": cnt[t], "weighted": wt[t],
            "is_seed_word": t in seed_toks, "examples": " | ".join(ex[t])} for t in cnt]
    out.sort(key=lambda x: (-x["weighted"], -x["keyword_count"], x["word"]))
    return out


def write_outputs(store, seeds, outdir, report):
    os.makedirs(outdir, exist_ok=True)
    rows = []
    for kw, e in store.items():
        rows.append({
            "keyword": kw, "tag": tag(kw), "heat_proxy": heat(e),
            "best_rank": "" if e["best_rank"] == 99 else e["best_rank"],
            "source_count": len(e["sources"]), "sources": "|".join(sorted(e["sources"])),
            "patterns": "|".join(sorted(e["patterns"])), "on_topic": on_topic(kw, seeds),
            "words": len(kw.split()),
        })
    rows.sort(key=lambda r: (-r["source_count"], r["best_rank"] if r["best_rank"] != "" else 99, r["keyword"]))
    cols = list(rows[0].keys()) if rows else ["keyword"]
    with open(os.path.join(outdir, "keywords.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    tw = title_words(rows, seeds)
    if tw:
        with open(os.path.join(outdir, "title_words.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(tw[0].keys()))
            w.writeheader()
            w.writerows(tw)
    with open(os.path.join(outdir, "keywords.json"), "w", encoding="utf-8") as f:
        json.dump({"seeds": seeds, "report": report, "keywords": rows}, f, ensure_ascii=False, indent=1)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", nargs="*", default=[], help="种子词（英文），可多个")
    ap.add_argument("--seeds-file", help="每行一个种子词")
    ap.add_argument("--sources", nargs="*", default=["amazon", "google", "youtube", "bing"],
                    choices=["amazon", "google", "youtube", "bing"])
    ap.add_argument("--market", default="us", choices=list(AMAZON_MARKETS))
    ap.add_argument("--level", default="normal", choices=["quick", "normal", "full"])
    ap.add_argument("--depth2-top", type=int, default=12, help="full 档：每个种子取前N个联想词再扩一轮")
    ap.add_argument("--delay", type=float, default=0.25, help="每次请求前的平均等待秒数")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-requests", type=int, default=20000)
    ap.add_argument("--merge", nargs="*", default=[], help="并入你从 Helium10/卖家精灵等导出的 csv")
    ap.add_argument("--out", default="./kw_out")
    ap.add_argument("--dry-run", action="store_true", help="只估算请求数，不发请求")
    ap.add_argument("--probe-only", action="store_true", help="只测各来源通不通（几秒），不扩词")
    ap.add_argument("--timeout", type=float, default=6, help="单次请求超时秒数")
    ap.add_argument("--max-minutes", type=float, default=5,
                    help="总时间上限，到点就停并输出已有结果（0 = 不限）")
    a = ap.parse_args(argv)

    seeds = [norm(s) for s in a.seeds]
    if a.seeds_file:
        seeds += [norm(l) for l in open(a.seeds_file, encoding="utf-8") if l.strip()]
    seeds = list(dict.fromkeys(seeds))
    if not seeds and not a.merge:
        ap.error("至少给一个 --seeds 或 --merge")

    jobs = build_jobs(seeds, a.sources, a.level)
    print(f"种子词 {len(seeds)} 个，来源 {a.sources}，档位 {a.level}：第一轮 {len(jobs)} 次请求", file=sys.stderr)
    if a.dry_run:
        return 0
    if len(jobs) > a.max_requests:
        print(f"超过 --max-requests {a.max_requests}，已截断", file=sys.stderr)
        jobs = jobs[: a.max_requests]

    deadline = time.time() + a.max_minutes * 60 if a.max_minutes > 0 else None
    store, runner = {}, Runner(a.market, a.delay, a.workers, timeout=a.timeout, deadline=deadline)
    probe_q = seeds[0] if seeds else "food container"
    alive = runner.probe(a.sources, probe_q)
    print(f"来源探测：可用 {alive or '无'}，不通 {sorted(runner.disabled) or '无'}", file=sys.stderr, flush=True)
    if a.probe_only:
        print(json.dumps({"alive": alive, "dead": sorted(runner.disabled),
                          "last_error": runner.last_error}, ensure_ascii=False, indent=1))
        return 0
    if seeds and not alive:
        print("所有联想来源都连不上（可能是当前环境没有外网或被拦截）。"
              "请在能联网的电脑上跑，或改用搜索/贴数据。", file=sys.stderr)
    jobs = [j for j in jobs if j[0] in alive]
    print(f"实际请求数 {len(jobs)}，时间上限 {a.max_minutes} 分钟", file=sys.stderr, flush=True)
    add_results(store, runner.run(jobs), seeds)

    if a.level == "full" and store and not runner.timed_out:
        seeds2 = second_round_seeds(store, seeds, a.depth2_top)
        srcs2 = [s for s in a.sources if s in ("amazon", "google") and s not in runner.disabled]
        jobs2 = [(s, f"{k} {ch}", "depth2") for k in seeds2 for s in srcs2 for ch in string.ascii_lowercase]
        jobs2 = jobs2[: max(0, a.max_requests - len(jobs))]
        print(f"第二轮：{len(seeds2)} 个高频联想词，{len(jobs2)} 次请求", file=sys.stderr)
        add_results(store, runner.run(jobs2), seeds)

    for p in a.merge:
        print(f"并入 {p}: {merge_csv(store, p)} 行", file=sys.stderr)

    report = {"ok": dict(runner.ok), "fail": dict(runner.fail),
              "disabled": sorted(runner.disabled), "last_error": runner.last_error,
              "timed_out": runner.timed_out}
    rows = write_outputs(store, seeds, a.out, report)
    print(json.dumps({"total_keywords": len(rows), **report}, ensure_ascii=False, indent=1))
    print(f"已写入 {a.out}/keywords.csv、title_words.csv、keywords.json", file=sys.stderr)
    if runner.timed_out:
        print(f"已到时间上限 {a.max_minutes} 分钟，输出的是已抓到的部分；想要更多可调大 --max-minutes。",
              file=sys.stderr)
    if runner.disabled:
        print(f"注意：{sorted(runner.disabled)} 连续失败已停用，可能被拦截或网络不通；"
              f"请改用搜索/让用户贴数据。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
