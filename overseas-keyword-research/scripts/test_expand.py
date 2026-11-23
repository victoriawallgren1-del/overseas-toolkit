#!/usr/bin/env python3
"""离线自测：用假数据验证扩词、去重、停用失败来源、导入csv、标注逻辑（不联网）。"""
import csv, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import expand_keywords as ek

def fake_fetch(url, timeout=10):
    if "api.bing.com" in url:
        raise OSError("blocked")          # bing 全部失败 -> 应被停用
    q = ek.urllib.parse.unquote(url.split("q=")[-1].split("&")[0] if "suggestqueries" in url or "legacy" in url
        else (url.split("prefix=")[-1].split("&")[0] if "prefix=" in url else url.split("q=")[-1]))
    sugg = [f"{q} leaks", f"{q} for work", f"{q} set"]
    if "completion.amazon" in url and "api/2017" in url:
        return json.dumps({"suggestions": [{"value": s} for s in sugg]})
    return json.dumps([q, sugg])

ek.fetch_text = fake_fetch
ek.time.sleep = lambda *_: None

def main():
    # 解析两种格式
    assert ek.parse_suggestions('["a b",["A  B c","x"]]') == ["a b c", "x"]
    assert ek.parse_suggestions('{"suggestions":[{"value":"Foo Bar"}]}') == ["foo bar"]

    d = tempfile.mkdtemp()
    imp = os.path.join(d, "h10.csv")
    with open(imp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["Keyword Phrase", "Volume"]); w.writerow(["Leakproof Lunch Box", 900])
    out = os.path.join(d, "out")
    ek.main(["--seeds", "lunch box", "--level", "full", "--sources", "amazon", "google", "bing",
             "--merge", imp, "--out", out, "--workers", "2", "--delay", "0"])
    rows = list(csv.DictReader(open(os.path.join(out, "keywords.csv"), encoding="utf-8-sig")))
    kws = {r["keyword"]: r for r in rows}
    assert len(rows) == len(kws), "应已去重"
    assert len(rows) > 100, f"扩词量太少: {len(rows)}"
    assert "leakproof lunch box" in kws and kws["leakproof lunch box"]["sources"].startswith("import:")
    assert kws["lunch box a leaks"]["tag"] == "痛点候选"
    assert kws["lunch box for work"]["tag"] in ("场景候选", "搜索词")
    rep = json.load(open(os.path.join(out, "keywords.json")))["report"]
    assert "bing" in rep["disabled"], "全失败的来源应被停用"
    assert not any("bing" in r["sources"] for r in rows)
    assert any("depth2" in r["patterns"] for r in rows), "full 档应有第二轮"
    tw = list(csv.DictReader(open(os.path.join(out, "title_words.csv"), encoding="utf-8-sig")))
    words = {r["word"] for r in tw}
    assert "leaks" in words and "for" not in words and "best" not in words, "标题词统计/停用词有误"
    # 总时间上限：到点必须正常收尾并写出文件
    out2 = os.path.join(d, "out2")
    ek.main(["--seeds", "lunch box", "--level", "full", "--sources", "google", "--max-minutes", "0.00001",
             "--out", out2, "--workers", "2", "--delay", "0"])
    assert json.load(open(os.path.join(out2, "keywords.json")))["report"]["timed_out"] is True
    # 只探测
    assert ek.main(["--seeds", "lunch box", "--sources", "amazon", "bing", "--probe-only"]) == 0
    print(f"OK  共 {len(rows)} 个词，停用来源: {rep['disabled']}")

if __name__ == "__main__":
    main()
