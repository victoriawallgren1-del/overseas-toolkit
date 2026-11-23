# overseas-keyword-research-skill

跨境电商关键词与内容词库 Skill：丢来产品图和/或几个基础关键词，就挖海外（美区为主）用户关于这个产品的真实用词，产出可直接用的 TikTok 视频标题、话题标签（hashtag）和关键词库。

## 它能做什么

- 从 TikTok、亚马逊、Google、YouTube、Reddit 等来源挖海外用户真实用词
- 把卖点、关键词、用户原话对应起来，交付一份固定五页的 xlsx：产品概览 / 15 条 TK 视频标题 / 分层关键词 / 卖点 / 分组标签
- 自带扩词脚本：一个种子词扩出上千个真实联想词（Amazon / Google / YouTube / Bing 联想词）
- 自带标签探测脚本：批量查 TikTok 标签的真实监测视频数与播放量，不编数据
- 合规底线内置：材质看不出来就不写、不猜，未确认的材质 / 耐温 / 容量 / 密封 / BPA-free / 销量背书一律不进文案；离题词、竞品词直接删

## 目录

```
overseas-keyword-research/
├── SKILL.md                        # Skill 主文件（规则与流程）
├── references/
│   └── import-formats.md           # 用户导入数据的格式说明
└── scripts/
    ├── expand_keywords.py          # 暴力扩词脚本（仅用标准库）
    ├── probe_tiktok_tags.py        # TikTok 标签数据探测脚本
    └── test_expand.py              # 扩词脚本测试
```

## 怎么用

1. 下载或克隆本仓库，把 `overseas-keyword-research/` 整个文件夹放进你的 AI 助手 skills 目录。
2. 在对话里发产品图和/或基础关键词，提到「关键词」「TK 标题」「标签」「hashtag」「海外用户怎么搜」等即可触发。
3. 扩词脚本可单独运行（只需 Python 3 标准库，不用装依赖）：

```bash
python3 overseas-keyword-research/scripts/expand_keywords.py --seeds "kitchen gadgets" --probe-only
python3 overseas-keyword-research/scripts/expand_keywords.py --seeds "词1" "词2" --level normal --out ./kw
python3 overseas-keyword-research/scripts/probe_tiktok_tags.py kitchengadgets kitchenhacks silicone --out ./tk_tags_raw.csv
```

## 说明

- 标签数据来自第三方监测站点的收录样本，只用来比大小、排先后，不是 TikTok 官方全站总量。
- 抓不到的数据留空，不估数、不编数。

## 直接下载 zip

不想用 git 的话，也可以直接下载打包好的 zip：[海外关键词skill_overseas-keyword-research.zip](https://github.com/user-attachments/files/35071623/skill_overseas-keyword-research.zip)
