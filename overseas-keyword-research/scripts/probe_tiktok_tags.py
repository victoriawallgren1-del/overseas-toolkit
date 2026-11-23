# -*- coding: utf-8 -*-
"""
TikTok 标签真实数据探测（只用标准库）。

逐个抓 https://toklytics.app/hashtag/<tag>，取 "used in N TikTok videos" 与 "X total views"。
抓不到就记 fail 并在输出里留空，绝不估数。

用法：
  python3 probe_tiktok_tags.py kitchengadgets spoonrest lidholder
  python3 probe_tiktok_tags.py --tags-file tags.txt --out ./tk_tags_raw.csv

输出 CSV 列：tag, videos, views, views_raw, note
口径提醒：这是第三方监测平台收录的样本量，不是官方全站总量，只能用来比大小。
"""
import argparse, csv, re, time, urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
URL = "https://toklytics.app/hashtag/{}"


def fetch(tag, timeout=22):
    req = urllib.request.Request(URL.format(tag), headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def to_num(s):
    if not s:
        return None
    s = s.replace(",", "").upper().strip()
    m = re.match(r"([\d.]+)([KMB]?)", s)
    if not m:
        return None
    return float(m.group(1)) * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2)]


def probe(tag, retries=2):
    for _ in range(retries):
        try:
            html = fetch(tag.lower().lstrip("#"))
        except Exception:
            time.sleep(1)
            continue
        vids = re.search(r"used in\s+([\d,]+)\s+TikTok videos", html, re.I)
        views = re.search(r"([\d.,]+[KMB]?)\s+total views", html, re.I)
        nv, nw = to_num(vids.group(1)) if vids else None, to_num(views.group(1)) if views else None
        if nv or nw:
            return [tag.lower().lstrip("#"), int(nv) if nv else "", int(nw) if nw else "",
                    views.group(1) if views else "", ""]
        time.sleep(1)
    return [tag.lower().lstrip("#"), "", "", "", "fail"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tags", nargs="*", help="要查的标签，可带 #，可空格分隔")
    ap.add_argument("--tags-file", help="从文件读标签，每行一个")
    ap.add_argument("--out", default="./tk_tags_raw.csv", help="输出 CSV")
    args = ap.parse_args()

    tags = list(args.tags)
    if args.tags_file:
        with open(args.tags_file, encoding="utf-8") as f:
            tags += [line.strip() for line in f if line.strip()]
    if not tags:
        ap.error("至少给一个标签，或用 --tags-file")

    rows = []
    for tag in tags:
        row = probe(tag)
        rows.append(row)
        print(f"{row[0]}\t{row[1]}\t{row[2]}\t{row[4]}", flush=True)
        time.sleep(0.5)

    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["tag", "videos", "views", "views_raw", "note"])
        w.writerows(rows)
    print(f"done {len(rows)} -> {args.out}")


if __name__ == "__main__":
    main()
