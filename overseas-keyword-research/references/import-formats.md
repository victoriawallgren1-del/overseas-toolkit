# 用户贴数据 / 导出文件怎么并进来

脚本的 `--merge` 会自动识别 csv 里的关键词列，列名认这些（不区分大小写）：
keyword / keywords / keyword phrase / search term / query / 关键词 / 搜索词 / 关键字 / hashtag / 话题。
都不匹配就取第一列。utf-8 和 gbk 编码都能读。

常见来源：
- Helium10 Magnet / Cerebro 导出的 csv
- 卖家精灵 关键词挖掘、反查 导出的 csv
- TikTok Creative Center：热门话题标签、热门关键词，复制成 csv 即可
- 亚马逊后台：品牌分析 搜索词报告

导入的词来源会标成 `import:文件名`。这些文件里如果带搜索量，脚本不会读，由你在最终整理时自己对照。
