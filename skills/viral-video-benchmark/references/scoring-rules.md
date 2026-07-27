# 评分与采集契约

## 浏览器观测

目标作品至少记录：

- `platform`、`post_id`、规范链接、标题、作者、`author_id`、发布日期、内容类型。
- 点赞、评论、收藏、分享的页面原始字符串。
- 作者粉丝量原始字符串。
- 若可信来源明确显示真实播放量，记录播放量原始字符串；不可见时留空，不反推、不估算。

每轮首次处理一个平台时，另从用户自己的同平台创作者后台首页读取当前总粉丝数和采集时间。首页当前值优先于数据中心昨日值、历史缓存和用户口述值。同一轮同平台可复用本次实时观测，跨轮必须重读。

目标基线按发布时间从新到旧读取最近 20 条有效非置顶作品，排除目标、重复项和置顶作品。账号扫描另取主页最新 20 条有效非置顶作品的固定窗口，窗口内保留目标。不足 20 条就用全部可见有效作品。抖音每条必须有点赞；小红书每条必须同时有点赞和收藏。看不到必填值时停止，不猜测。

## 计算输入

`calculate_virality.py` 只接受 schema version 1：

```json
{
  "schema_version": 1,
  "platform": "douyin",
  "followers_raw": "8.6万",
  "benchmark_context": {
    "own_followers_raw": "1003",
    "own_followers_observed_at": "2026-07-17T22:30:00+08:00"
  },
  "target": {
    "post_id": "7340000000000000000",
    "likes_raw": "2.1万",
    "collects_raw": null,
    "views_raw": "180万"
  },
  "recent_posts": [
    {"post_id": "7339", "likes_raw": "2300", "pinned": false}
  ]
}
```

小红书使用 `platform: "xiaohongshu"`，目标和每条基线都必须提供 `collects_raw`。`benchmark_context` 和 `views_raw` 都是 schema v1 的可选字段；前者存在时必须同时提供实时粉丝原始值和采集时间。脚本支持非负整数、逗号分隔整数、中文 `万`、英文 `w/W` 和末尾 `+`；不支持模糊区间或没有单位的小数。

## 账号扫描输入

`scan_recent_posts.py` 使用同一套显示值和平台口径：

```json
{
  "schema_version": 1,
  "platform": "douyin",
  "followers_raw": "8.6万",
  "benchmark_context": {
    "own_followers_raw": "1003",
    "own_followers_observed_at": "2026-07-17T22:30:00+08:00"
  },
  "recent_posts": [
    {"post_id": "7340", "title": "页面标题", "likes_raw": "2.1万", "views_raw": "180万", "pinned": false}
  ]
}
```

脚本先收集所有置顶 ID，排除置顶项及其任何重复形态，再排除普通重复项并截取最新 20 条固定窗口。每条候选调用 `calculate_virality.py`，并从其基线中排除自己，因此 20 条窗口对应每条 19 个比较样本。脚本根据平台与 `post_id` 生成规范链接，输出保留完整 `results` 和 `baseline_post_ids` 审计信息，并单列 `qualifying`、`benchmark_candidates`、`inspiration_candidates`、`view_filter_rejected`、`small_hits`、`grade_counts` 和 `excluded`。

少于 6 条窗口时，每条排除自己后不足 5 个基线样本，不能产生正式扫描等级。6 至 10 条窗口通常产生低置信结果；11 至 20 条产生正常置信结果。扫描结果只负责发现候选，任何候选进入转写前都必须由用户选择。

## 阶段对标与播放初筛

这层只决定候选放在哪个对标池，不替代下方 `R + M` 正式判级：

- 主对标池上限 = 用户自己的同平台实时粉丝数 × 20。
- 作者粉丝数 `<=` 上限：`account_pool.status = main_pool`。
- 作者粉丝数 `>` 上限：`account_pool.status = inspiration_pool`，保留为跨级灵感，不直接丢弃。
- 真实播放量存在时，同时满足 `播放量 >= 1万` 且 `播放量 / 作者粉丝数 >= 20` 才得到 `view_breakout.status = passed`。
- 播放量存在但未同时满足两个条件：`view_breakout.status = failed`。
- 播放量不可见：`view_breakout.status = unavailable`，明确回退到 `R + M`，不因缺失播放量降级。

`benchmark.candidate_status` 使用以下固定值：

- `main_pool_candidate`：`R + M` 判为爆款/现象级，账号在主对标池，播放初筛通过或不可用。
- `inspiration_pool_candidate`：`R + M` 判为爆款/现象级，账号在跨级灵感池，播放初筛通过或不可用。
- `rejected_by_view_filter`：`R + M` 合格，但可信播放量未通过初筛。
- `unclassified_candidate`：`R + M` 合格，但未取得用户自己的实时粉丝数。
- `not_eligible_by_R_M`：正式等级不是爆款/现象级。

阶段对标和播放初筛不得修改 `grade`、`eligible_for_deep_process`、`requires_confirmation` 或 `deep_process`；这些字段仍只由 `R + M` 和基线置信度决定。

## 唯一计算口径

- 抖音核心指标：点赞。
- 小红书核心指标：点赞 + 收藏。
- 账号基线：有效近期作品核心指标的中位数。
- `R = 目标作品核心指标 / 账号基线`。
- `M = 目标作品点赞 / 当前粉丝数`。小红书的 `M` 也只用点赞。

粉丝体量：

| 层级 | 粉丝范围 | M 基准 |
|---|---:|---:|
| S | `< 1万` | 0.30 |
| A | `>= 1万 且 < 10万` | 0.15 |
| B | `>= 10万 且 < 100万` | 0.08 |
| C | `>= 100万` | 0.04 |

等级从高到低检查，`R` 和 `M` 必须共同满足：

| 等级 | R | M |
|---|---:|---:|
| 现象级 | `>= 8` | `>= 3.0 × M基准` |
| 爆款 | `>= 4` | `>= 1.5 × M基准` |
| 小爆 | `>= 2` | `>= 1.0 × M基准` |
| 普通 | 其余 | 其余 |

脚本使用未四舍五入的内部数值比较，输出仅用于展示。页面出现 `万/w` 时标记 `source_precision: contains_rounded_values`。

## 样本置信度与分流

- 10 至 20 条：`normal`，正常判级。
- 5 至 9 条：`low`，仍输出等级；若等级为爆款或现象级，深度处理前必须确认。
- 少于 5 条：`insufficient`，`grade` 和 `R` 为 `null`，只报告 `M`。

只有爆款和现象级可能进入深度处理。严格遵循输出布尔值：

- `eligible_for_deep_process`：等级是否合格。
- `requires_confirmation`：低置信合格项是否需要确认。
- `deep_process`：是否可以立即进入转写。

## 基线复用

缓存是按需观测，不是每日快照。使用缓存前展示 `observed_at`、样本数、粉丝原始值和最近一次扫描摘要，让用户选择复用或刷新。计算成功后立即保存本次验证过的基线，即使目标结果是普通或小爆；完成账号扫描后同时保存 `recent_scan`。缓存不自动失效。
