# 海外热门标签抓取 Skill

上传产品图片或输入关键词，快速了解海外市场，获取热门关键词、TikTok 标签及产品卖点。

## 能做什么？

**1. 海外热门产品**
了解热门产品、用户需求和真实用户用词。

**2. 视频选题和关键词**
自动生成 TikTok 视频标题及海量关键词。

**3. TikTok 热门标签**
获取热标签，查看关联视频及播放数据。

**4. Excel 报告**
自动整理产品概况、关键词、产品卖点、视频选题和热门标签。

**5. 过滤无效信息**
去除无关词，不编造产品卖点和数据。

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
