# MusicMode 更新日志 (Changelog)

本文档记录 MusicMode 项目的所有更新历史。

## v2.8.1 (2026-04-17) - 消融实验框架重设计与评估指标规范化

### 🚀 新增功能

- **消融实验脚本**（`Project/evaluation/eval_experiment.py`）：新增独立消融实验与模型对比实验模块，在 KKBox 验证集上执行学术标准的五阶段消融实验，实验报告输出至 `Mode/evaluation/eval_experiment_report.txt`，图表输出至根目录 `image/` 文件夹

### ⚡ 性能优化

- **五阶段消融设计**（`eval_experiment.py`）：重新设计消融实验，引入正确的学术对照结构：A0（随机基准下界）→ A1（热度召回，通道B单独）→ A2（+BST粗排）→ A3（+精排集成 Meta-LR）→ A4（+MMR完整管道）。修正原设计中 ALS/SVD 存在闭合世界评估偏差的问题，使 A1→A2 的增量合理反映 BST 粗排层的真实贡献
- **评估指标统一规范**（`eval_experiment.py`）：将消融实验与模型对比实验的评估 K 值从 @10 统一为 @5，消除同一脚本内量纲不一致问题
- **Shannon 熵动态化**（`eval_experiment.py`）：4 处硬编码的 Shannon 熵值全部改为从 MMR 帕累托扫描结果中动态提取，消融报告与图表中的熵值均为 λ=0.7 设计点的实测值
- **AUC 对比图优化**（`eval_experiment.py`）：移除混入 AUC 对比图的 NDCG@10 量纲基线柱，改为仅展示具有真实 AUC 的四个模型，按管道层级排序（BST粗排→DeepFM精排→LightGBM精排→Meta-LR集成），统一学术蓝配色
- **MMR 帕累托图优化**（`eval_experiment.py`）：删除图内红色箭头注释，过滤仅展示 λ=0.4~1.0 的有效设计点，修复 λ=0.4 标注因位于最低精度点而偏移至坐标轴下方的显示问题
- **ALS 辅助函数抽取**（`eval_experiment.py`）：从 `eval_als` 中抽取 `_compute_als_scores()` 辅助函数，避免 ALS 模型在消融实验与对比实验中重复加载，降低内存开销

### 🚧 待解决问题

- `evaluate_offline.py` 仍使用 @K=10 评估，与 `eval_experiment.py` 的 @K=5 口径不一致。两者面向不同分析场景：前者用于系统整体快速评估，后者用于消融对比实验，引用指标时需注明来源脚本

---

## v2.8.0 (2026-04-06) - 两阶段 Stacking 集成：K折OOF + 逻辑回归元学习器

### 🚀 新增功能

- **DeepFM K折OOF交叉验证**（`train_deepfm_v3.py`）：新增顶部开关 `RUN_OOF=True` 和 `N_OOF_SPLITS=2`（正式训练时改为5），以及 `run_kfold_oof()` 函数。训练前自动执行全局时序K折交叉验证，在训练区间（前90%样本）上生成OOF预测，保存到 `Mode/deepfm/deepfm_oof.npy` + `deepfm_oof_idx.npy`
- **BST K折OOF交叉验证**（`train_bst.py`）：同上，新增 `run_kfold_oof()` 函数，保存到 `Mode/bst/bst_oof.npy` + `bst_oof_idx.npy`。两个脚本均使用全局时序切分，确保OOF索引完全对齐
- **逻辑回归元学习器**（`build_ensemble.py`）：新增 `meta_learner_training()` 函数（Step 3.5），在OOF文件存在时自动加载、对齐索引、训练 `LogisticRegression(C=1.0)` 元学习器，在验证集上评估并与SLSQP加权平均对比；保存到 `Mode/ensemble/meta_learner.pkl`，`ensemble_config.pkl` 新增 `meta_learner_available` + `meta_auc` 字段
- **精排推断双路径**（`sync_recs_v3.py`）：新增 `META_LEARNER_PATH` 常量和 `self.meta_lr` 属性；启动时若 `meta_learner_available=True` 则优先加载逻辑回归元学习器，推断时用 `LR.predict_proba([deepfm_score, bst_score])` 输出集成分；元学习器不可用时自动降级到原有SLSQP加权平均

### 📝 执行步骤

**阶段一：K=2 快速验证（约3-5小时）**

```bash
python -X utf8 Project/MusicMode/Project/train_deepfm_v3.py
python -X utf8 Project/MusicMode/Project/train_bst.py
python -X utf8 Project/MusicMode/Project/build_ensemble.py
```

确认 deepfm_oof.npy、bst_oof.npy、meta_learner.pkl 均生成，meta AUC数值合理后进行阶段二。

**阶段二：K=5 正式训练（约30-50小时）**
将两个训练脚本顶部的 `N_OOF_SPLITS = 2` 改为 `N_OOF_SPLITS = 5`，重新执行上述步骤。

### 🚧 待解决问题

- 当前 `N_OOF_SPLITS=2` 为快速验证模式，需主人验证逻辑正确后手动改为5再正式训练
- 元学习器预期AUC提升幅度极小（+0.0000 ~ +0.0005），主要意义在于代码层面具备完整的两阶段Stacking结构

---

## v2.7.2 (2026-03-31) - play_count Bug 修复 + 代码注释清理

### 🐛 Bug 修复

- **Tier3 判断永远返回 0 的关键 Bug**（`prepare_features_v3.py`）：`save_outputs()` 函数保存 `user_basic` 时遗漏了原始 `play_count` 整数字段，只保存了 `user_play_count_log`（对数值），导致 `sync_recs_v3.py` 第899行 `.get("play_count", 0)` 始终返回 0，所有训练集用户被错误降级到 Tier2/1，ALS 通道完全失效。已在 `user_basic` 列列表中补加 `play_count` 字段。

### 🧹 代码清理

- **`train_lgbm.py`**：删除 `v11 调优` 多行历史记录注释块，移除所有 `v11：xxx` / `v11 新增：xxx` 版本号前缀，保留功能说明
- **`train_deepfm_v3.py`**：移除所有 `v12 新增` / `v12：xxx` 版本号前缀
- **`sync_recs_v3.py`**：移除 `v8`、`v11`、`v12` 版本号前缀注释（通道C路由注释、特征说明注释、BST对齐注释等）
- **`build_faiss_index.py`**：修正 `main()` 打印信息中错误的维度说明（`v3（88维）` → `5×32维嵌入，共160维`，与代码中 `EMBEDDING_DIM=160` 一致）

## v2.7.1 (2026-03-30) - Tier 2 用户特征补全 + BST 实时行为序列

### 🚀 新增功能

- **Tier 2 实时 `user_genre_diversity` 计算**（`sync_recs_v3.py` `build_pair_features`）：Tier 2 用户不在 pkl 中，原先固定取默认值 0.5；现在当 `realtime_dists["genre"]` 存在时，直接对已归一化的流派分布计算香农熵并覆盖，无额外 SQL
- **Tier 2 实时 `user_peak_hour` 统计**（`sync_recs_v3.py` `build_pair_features`）：原先对 Tier 2 用户取默认值 0（午夜）；现在当 `realtime_dists` 存在且 `user_history` 非空时，遍历已查出的播放记录统计各小时频次并取高峰时段，覆盖稀疏编码列，无额外 SQL
- **BST 实时行为序列构建**（`sync_recs_v3.py` `rank_with_bst`）：新增可选参数 `db=None`；当 pkl 快照中 `seq_song_ids` 长度不足 5 时，从 `play_history` 表实时查询最近 `seq_len` 条播放记录重建序列，并过滤训练集外的未知歌曲编码，彻底解决 Tier 2 用户 BST 退化为全 0 填充的问题

### ⚡ 性能优化

- `rank_with_bst` 调用方（`generate_recommendations` 行精排阶段）传入 `db` 参数，实现序列实时构建与上层连接池复用

### 🚧 待解决问题

- `user:tier2_dists:{uid}` 实时分布尚未加入 Redis 缓存，每次推荐均重新执行两次 SQL 计算流派/艺术家/语种分布
- `PlayHistoryServlet` 尚未集成 Redis Key 主动删除（`user:faiss:{uid}`），目前依赖 30min TTL 被动失效

### 📝 拟解决方案

- 在 Tier 2 召回路径中加入 `user:tier2_dists:{uid}` Hash 缓存（TTL=10min）
- `PlayHistoryServlet` 在记录播放后调用 `jedis.del("user:faiss:" + userId)` 实现主动失效

---

## v2.7.0 (2026-03-30) - 推荐系统全链路重设计：用户三层分层路由 + Redis 缓存加速

### 🚀 新增功能

- **用户三层分层路由**（`sync_recs_v3.py`）：通道C由原"老用户/新用户"二元切换升级为三层策略：
  - Tier 3（ALS 协同过滤）：在训练集中且训练播放量 ≥ 10 首的高质量老用户
  - Tier 2（多信号多维度内容召回）：有足量行为数据（歌单 ≥5首 或 质量播放 ≥10次）的中间用户，取代之前的无效注册偏好兜底
  - Tier 1（注册偏好冷启动）：纯新用户兜底
- **Tier 2 多维度内容召回**（`sync_recs_v3.py`）：融合歌单（权重0.6）与质量播放（完播率≥30%，权重0.4）两路信号，按艺术家35%/流派40%/语种25%比例分配 RECALL_ALS=200 个召回配额
- **`realtime_dists` 实时分布传递**（`sync_recs_v3.py`）：Tier 2 召回时产出艺术家/流派/语种实时归一化分布，通过 `build_pair_features(realtime_dists=...)` 参数传递给粗排和精排层，使 `user_artist_match` 特征对 Tier 2 用户更准确
- **Redis 用户级缓存层**（`sync_recs_v3.py`）：新增 `_get_user_pref` 和 `_get_user_sati` 两个辅助函数，将每次推荐中对 `users.preferred_genres/artists`（原3次DB查询）和 `user_preference_feedback.satisfaction` 的重复读取改为 Redis Hash/String 缓存；FAISS 画像向量（`user:faiss:{uid}`）写入 Redis 并以 30 分钟 TTL 缓存，重复请求命中时完全跳过全量历史查询

### 🐛 Bug 修复

- **P2 修复：Tier 3 二次校验**（`sync_recs_v3.py`）：仅检查 `_uid_map` 存在性判断 Tier 3 不够严格——训练时播放量为 0 的用户因 ALS 矩阵分解噪声数据被错误路由为 Tier 3，现在增加 `play_count >= 10` 二次校验，不足时自动降级

### ⚡ 性能优化

- **Redis Key 设计**（`sync_recs_v3.py`）：
  - `user:pref:{uid}` — Hash，TTL=24h，缓存注册偏好
  - `user:sati:{uid}` — String，TTL=2h，缓存最新满意度
  - `user:faiss:{uid}` — String（Base64 编码 numpy 向量），TTL=30min，缓存 FAISS 画像向量
- **消除重复 DB 查询**：`build_user_profile`、通道B、通道C（Tier1）、`build_pair_features` 四处对 `preferred_genres/artists` 的独立查询统一走 Redis 缓存；`satisfaction` 查询由 `build_user_profile` 和通道B独立查询改为 `_get_user_sati` 共享缓存

### 🚧 待解决问题

- `user:faiss:{uid}` 缓存失效依赖 `PlayHistoryServlet` 主动删除 Redis Key，该 Java 端集成尚未实现，目前依赖 TTL 被动失效（30min 内新播放不会影响 FAISS 向量）
- Tier 2 实时分布（`user:tier2_dists:{uid}`）尚未加入 Redis 缓存，每次推荐均重新计算两次 SQL

### 📝 拟解决方案

- `PlayHistoryServlet` 在记录播放后调用 `jedis.del("user:faiss:" + userId)` 实现主动失效
- 在 Tier 2 召回路径中加入 `user:tier2_dists:{uid}` Hash 缓存（TTL=10min），可节省两次全量 JOIN 查询

---

## v2.6.0 (2026-03-27) - 推荐流程升级：MMR 重排、满意度感知召回、召回扩容

### 🚀 新增功能

- **新增 `mmr_rerank()` 函数**（`sync_recs_v3.py`）：以 Maximal Marginal Relevance 算法替代原 `diversity_rerank()` 同艺术家硬约束。基于 FAISS 80 维 Embedding 余弦相似度，在精排 150 首候选中贪心选出兼顾相关性（λ=0.7）与多样性的 Top-50 结果
- **通道C新用户冷启动降级**（`sync_recs_v3.py`）：`user_enc is None` 时不再静默跳过，改为从 `users.preferred_artists` 和 `users.preferred_genres` 拉取热门歌曲作为通道C候选，确保新用户首次推荐有效输出

### 🐛 Bug 修复

- **修复通道B/C 对 satisfaction 完全不感知的设计缺陷**（`sync_recs_v3.py`）：通道B依据 `user_preference_feedback.satisfaction` 动态调整 genre_filter 范围与艺术家加权（dissatisfied 扩展全部流派加权+800，very_satisfied 不做流派过滤加权+150）；通道C在 dissatisfied 时对 ALS 分数乘以 0.7 惩罚系数

### ⚡ 性能优化

- **召回层扩容**（`sync_recs_v3.py`）：三路召回各扩展至 200 首（FAISS/Hot/ALS 均为 200），漏斗调整为 ~600 → 粗排 300 → 精排 150 → MMR重排 50，最终推荐数 20 → 50
- **feedback_score 时间衰减**（`sync_recs_v3.py`）：`update_feedback` 执行时对超过 14 天的历史反馈分数乘以 0.9 衰减系数，绝对值低于 0.01 直接归零，防止久远负向行为永久压低歌曲排名
- **重排冷却升级**（`sync_recs_v3.py`）：基于新增字段 `recommendation_feedback.negative_count` 的三档渐进策略（1次→3天软冷却，2次→7天，3次+→14天硬冷却），负向交互定义统一为未播放/完播率<0.2/完播率0.2~0.8，完播率≥80%或已收藏歌曲免除冷却
- **移除无法上线的 OOF Ridge Stacking**（`build_ensemble.py`）：Ridge 元学习器无法转化为线上 `w_deepfm`/`w_bst` 标量权重，删除全部 K-Fold OOF 集成代码，保留 SLSQP vs 等权平均两路对比

### 🚧 待解决问题

- `train_lgbm.py` / `train_deepfm_v3.py` / `train_bst.py` 超参已调整，当前磁盘模型仍为旧超参，需手动重训后模型升级才生效（特征工程和 FAISS/ALS 召回模型无需重训）

### 📝 拟解决方案

- 按顺序重训：`python train_lgbm.py` → `python train_deepfm_v3.py` → `python train_bst.py` → `python build_ensemble.py`，完成后运行 `evaluate_offline.py` 对比新旧 AUC / NDCG 指标

---

## v2.5.0 (2026-03-25) - DIEN 精排模型上线，数据库语种清洗，LightGBM 全面调优

### 🗑️ 移除

- **train_din.py 移除**：原 `train_din.py` 文件名为 DIN，但实际调用的是 `DeepFM` 模型（DNN 层为 256,128,64），与 `train_deepfm_v3.py` 本质重复，无法体现用户兴趣序列建模能力，予以废弃。同步删除 `Mode/din/` 模型目录。

---

### 🚀 新增功能

- **DIEN 精排模型上线** (`train_dien.py`)：采用 Deep Interest Evolution Network（Zhou et al. AAAI 2019）替代伪 DIN，实现真正的用户行为序列建模：

  - 兴趣提取层（IEL）：GRU 网络 + 辅助监督损失，显式建模用户兴趣演化
  - 兴趣演化层（AUGRU）：以候选歌曲 embedding 为查询向量的注意力门控 GRU，动态提取与当前候选相关的兴趣表示
  - Val AUC = **0.7673**（22 epochs），优于旧 DIN 实现
  - 依赖 `Mode/features_seq.pkl`（用户行为序列，由 `prepare_features_v3.py Step 6` 生成）
  - 输出至 `Mode/dien/`（`dien_model.pth` + `model_config.pkl`）
- **特征工程 v3 大幅扩展**（`prepare_features_v3.py`）：

  - 稀疏特征：7 → **14 个**（新增 `year_bucket`, `city`, `gender`, `age_bucket`, `tenure_bucket`, `duration_bucket`, `user_peak_hour`）
  - 稠密特征：扩展至 **57 个**（含 OOF TE 统计量：`user_skip_rate`, `song_skip_rate`；SVD 嵌入降维向量；`days_since_artist_log` 等时序交互特征）
  - 总特征维度：**71 维**（14 sparse + 57 dense），同时兼容 LightGBM / DeepFM / DIEN 三模型

---

### 🐛 Bug 修复

- **修复 LightGBM `user_history_position` 时序泄漏**（`train_lgbm.py` 第 467-471 行）：

  - 根本原因：该特征 = 记录在用户历史中的时序位置（0=最早，1=最近）。由于验证集使用用户最后 10% 交互，训练集 position ∈ [0, 0.9]，验证集 position ∈ [0.9, 1.0]，构成完美的 train/val 区分器，导致 LightGBM 在第 4 轮即学会此规律，之后验证 AUC 从 0.730 持续下滑至 0.704，`best_iter=4` 假早停。
  - 修复方式：`train_lgbm.py` 中永久注释禁用该特征注入，添加根因说明注释。
  - 注：神经网络模型（DeepFM / DIEN）对此特征鲁棒，无需禁用。
- **恢复被意外注释的三个关键特征**（`train_lgbm.py` DENSE_FEATURES）：

  - `user_skip_rate`：用户跳过率，高重要度特征（重要度排名第 4，4.9 万分）
  - `song_skip_rate`：歌曲被跳过率（重要度排名第 5，4.1 万分）
  - `days_since_artist_log`：用户上次收听该艺术家的时间间隔（时序交互强特征）
  - 三个特征均在 v2.4.0 的 0.7933 最优记录中存在，被错误注释后导致 AUC 下降至 0.72。
- **回滚无效的类别权重策略**：

  - 验证了 LightGBM `scale_pos_weight=2` 在第 23 轮即触发早停，val AUC 从 0.7062 下降至 0.6994（下降 0.007）。
  - 根本原因：AUC 是排序指标，与类别平衡无关，`scale_pos_weight` 扭曲梯度方向导致欠训练。三个训练脚本均已回滚至原始损失函数设置。

---

### ⚡ 性能优化

- **LightGBM 超参全面调优**（`train_lgbm.py`）：

  | 参数                      | 旧值 | 新值 | 说明                             |
  | ------------------------- | ---- | ---- | -------------------------------- |
  | `num_leaves`            | 64   | 128  | 提升模型表达能力（≈2^7 叶节点） |
  | `min_child_samples`     | 5000 | 2000 | 放宽叶节点限制，允许更细粒度分裂 |
  | `n_estimators`          | 5000 | 8000 | 配合 early_stopping 延长训练     |
  | `early_stopping_rounds` | 100  | 300  | 充分探索，避免伪早停             |
  | `reg_alpha`             | 0.1  | 1.0  | 加强 L1 正则，促进稀疏           |
  | `reg_lambda`            | 1.0  | 5.0  | 加强 L2 正则，减少方差           |

- **DeepFM 配置升级**（`train_deepfm_v3.py`）：

  | 参数                    | 旧值         | 新值          | 说明                                  |
  | ----------------------- | ------------ | ------------- | ------------------------------------- |
  | `embedding_dim`       | 16           | 32            | 全部 14 个稀疏特征 embedding 维度加倍 |
  | `DNN_HIDDEN_UNITS`    | (256,128,64) | (512,256,128) | 网络容量提升，与 DIEN 对齐            |
  | `EARLY_STOP_PATIENCE` | 10           | 12            | 更充分的收敛探索                      |

- **数据库 language/origin_country 全面清洗**（ISRC 交叉验证）：

  - 通过 ISRC 国家码统计分布发现 KKBOX songs.csv language 字段 10 个编码中 8 个映射错误（如 code 52 旧映射"法语"→实为"英语"，code 31 旧映射"国语"→实为"韩语"）
  - 全量修正 KKBOX 歌曲 language 标签（共 1,419,171 行）
  - code 31（韩语）精确修复：读取原始 songs.csv 精确匹配 39,201 首，无误差
  - 未知语言推断：通过 origin_country 反推语言，未知比例从 **27.85% → 3.09%**（约 494,014 首成功推断）
  - KKBOX popularity 归一化：0~数千 → **0~100**（与网易云 API 热度值统一量纲，供前端热门排行使用）
  - 外部歌曲 origin_country 补全：9,855 首通过 language 字段反推填充

---

### 📊 模型性能（当前存档状态）

> ⚠️ LightGBM 当前模型含 `user_history_position` 时序泄漏（val AUC=0.7237，待重训）

| 模型                 | 验证 AUC         | 状态        | 说明                                        |
| -------------------- | ---------------- | ----------- | ------------------------------------------- |
| LightGBM             | 0.7237           | ⚠️ 待重训 | best_iter=4，user_history_position bug 导致 |
| DeepFM v3            | **0.7610** | ✅ 正常     | 40 epochs，embedding_dim=32                 |
| DIEN                 | **0.7673** | ✅ 正常     | 22 epochs，GRU + AUGRU 序列建模             |
| Weighted Avg（集成） | **0.7878** | ✅ 参考     | best_weights 加权平均                       |
| Stacking (LR)        | ~~0.7892~~      | ⚠️ 含泄漏 | LR 在验证集 fit 后同集预测，不可信          |

---

### 🚧 待解决问题

- **LightGBM 待全量重训**：`user_history_position` bug 修复后，当前磁盘 `lgbm_model.pkl` 为 best_iter=4 的无效模型（val AUC=0.7237），需使用修复后代码重训，预期 val AUC ≥ 0.79。
- **全量集成重建**：LightGBM 重训后需重新执行 `build_ensemble.py` → `evaluate_offline.py`，获取可信集成 AUC。
- **evaluate_offline.py Stacking 集成方式**：当前离线评估使用 LR 元学习器存在轻度泄漏（同集 fit+predict），需改为 best_weights 加权平均以与线上 `sync_recs_v3.py` 行为一致。

---

### 📝 拟解决方案

- LightGBM 重训：`python train_lgbm.py`（修复后代码已就绪，预计约 40 分钟）
- evaluate_offline.py 修复：第 306-322 行改为 best_weights 加权平均（与线上逻辑一致）
- 若重训后集成 AUC < 0.74，优先考虑 AutoInt 替换 DIEN（30 分钟改动，无需修改特征工程）

## v2.4.0 (2026-03-18) - 模型精简：移除 CatBoost/XGBoost，OOF Target Encoding，深度模型增强

### 🗑️ 移除

- **CatBoost 移除** (`train_catboost.py` 已删除)：Val AUC=0.6499，Train AUC=0.9558（过拟合差距 0.306），集成权重仅 0.8%，性价比极低，予以剔除。同步删除 `Mode/catboost/` 目录及 `catboost_train.log`。
- **XGBoost 移除** (`train_xgboost.py` 已删除)：与 LightGBM 高度冗余（均为 GBDT 族），无法提供额外多样性，予以剔除。同步删除 `Mode/xgboost/` 目录及 `xgboost_train.log`。

### 🚨 关键改进：OOF (Out-of-Fold) Target Encoding

- **问题**：旧版 Target Encoding 在全训练集上计算统计量后直接喂回同一训练集，导致 target leakage——训练时模型间接"看见"了标签，造成虚高训练 AUC。
- **修复**：改用 K-Fold OOF 策略：将训练集分为 K 折，每折的 TE 统计量仅从其余 K-1 折计算，验证集 TE 从全训练集计算，彻底消除训练集内数据泄漏。
- **效果**：LightGBM Val AUC 从 0.6798 提升至 **0.7063**。

### 🚀 深度模型优化

- **DeepFM v3 EPOCHS 10→15**：延长训练轮数，充分利用早停（`EarlyStopping patience=3`），Val AUC 达 **0.7548**。
- **DIN EPOCHS 10→15**：同步延长训练，DIN 成为最佳单模型，Val AUC 达 **0.7602**。
- **Embedding L2 正则化**：对 sparse 特征嵌入层新增 L2 正则（`l2_reg_embedding=1e-5`），缓解高基数特征过拟合。
- **min-count 过滤**：对出现频次 < min_count 的 ID 类特征映射为 `<UNK>`，减少噪声嵌入数量。

### 📊 模型性能

| 模型                   | 验证 AUC         | 说明                             |
| ---------------------- | ---------------- | -------------------------------- |
| LightGBM（OOF TE）     | **0.7063** | OOF Target Encoding 消除泄漏     |
| DeepFM v3（EPOCHS=15） | **0.7548** | GPU AMP，L2 正则，min-count 过滤 |
| DIN（EPOCHS=15）       | **0.7602** | 最佳单模型，用户兴趣序列建模     |
| Stacking Ensemble      | **0.7607** | LightGBM + DeepFM + DIN 堆叠集成 |
| CatBoost               | ~~0.6499~~      | 已移除（过拟合差距 0.306）       |
| XGBoost                | ~~—~~          | 已移除（与 LightGBM 冗余）       |

### 📊 双轨评估体系建立

- **离线评估脚本** (`evaluate_offline.py`，全新建立)：面向论文指标，基于 KKBOX 验证集（28,172 用户，726,047 样本）计算 Hit Rate@K、Precision@K、Recall@K、NDCG@K、MRR 五项指标；结果输出至 `Mode/offline_evaluation_report.txt`。
  - NDCG@10 = **0.721**，MRR = **0.811**（Stacking 集成模型）
- **在线评估脚本** (`evaluate_recs.py`，更新评估标签逻辑)：面向系统验证，读取 jf/jf2 真实推荐交互记录（337 条），以播放完成率≥0.3 为正反馈阈值，计算 CTR、平均完播率、NDCG@10；结果输出至 `Mode/online_evaluation_report.txt`。
  - CTR = **10.39%**（基于 jf/jf2 真实播放记录）

### 🧹 清理

- 删除 `Project/__pycache__/`、`scripts/__pycache__/` 等编译缓存
- 删除 `Project/catboost_info/` 临时目录
- 删除 `scripts/test_api_composer.py`、`scripts/test_enrich_100.py` 一次性测试脚本
- 删除 `catboost_train.log`、`xgboost_train.log`、`lgbm_train.log` 训练日志
- **git 历史重写**：从版本历史中彻底清除 `features_v3_cache.npz`（2GB）、`song_index.faiss`（703MB）及历史 `Mode/*.pkl` 大文件，仓库体积从 3.8GB 压缩至 2.1GB（LFS 管理）

## v2.3.0 (2026-03-17) - 推荐系统全面升级：目标泄漏修复、特征工程 v3、集成精排

### 🚨 关键修复：目标泄漏 (Target Leakage)

- **发现 `play_duration` 为累积值**：`play_history.play_duration` 存储的是用户对某首歌所有播放记录的**累积时长**，而非单次播放时长。由此计算的 `this_play_completion = play_duration / duration` 在 99.99% 行达到 ≥1（表明已完整收听），直接导致 AUC = 1.0 的完美泄漏。已从所有特征集中**永久删除**。
- **验证集 AUC 回归真实**：去除泄漏后，无泄漏验证 AUC = **0.6717**（对比旧"干净"基线 0.9603，差距揭示了原有评估方法的隐性泄漏问题）。

### 🚀 新增功能

- **特征工程 v3** (`prepare_features_v3.py` 完全重写)：

  - 45 维特征（14 sparse + 31 dense），移除所有泄漏特征
  - **用户级时序切分**：对每位用户按 `play_time` 排序后取各自最后 10% 作为验证集（`MIN_INTERACTIONS=5`，交互数不足的用户全部归入训练集）
  - 新增 `compute_temporal_features()`：计算 7d/30d 滚动窗口特征（`closed="left"` 防止单行泄漏）
  - 新增 B-3 记忆衰减特征（`user_song_prev_play_days`、`user_song_play_count_before`），后经实验证实为 near-constant 已移除
- **推荐系统 v3.1** (`sync_recs_v3.py`)：三通道混合召回 + 集成精排：

  - **通道 A（FAISS）**：基于用户画像向量召回 150 候选
  - **通道 B（热度兜底）**：按 `popularity DESC, release_year DESC` 补充 100 候选
  - **通道 C（ALS 协同过滤）**：ALS 生成 Top-100 候选融合
  - **精排层**：LightGBM 打分 + DeepFM 打分 + α 加权集成（`final = α×LGBM + (1-α)×DeepFM`）
  - **重排层**：多样性约束（同艺人不超过 3 首）+ 冷却/屏蔽过滤
  - 每日凌晨 4 时生成每用户 20 首个性化推荐
- **集成模型** (`build_ensemble.py`)：

  - 在验证集上网格搜索最优集成权重 α（步长 0.05，范围 [0, 1]）
  - 最优 α 保存至 `ensemble_config.pkl`，供 `sync_recs_v3.py` 加载
- **LightGBM 精排** (`train_lgbm.py`)：

  - 6 条验证断言（时序不重叠、ALS 仅用训练集、分布检查等）防止隐性泄漏
  - **Phase B-2 Cross TE**：将 `user_genre_match`/`user_language_match`/`user_country_match` 从 0/1 布尔值升级为 P(target=1|user,genre/language/country) 条件概率，贝叶斯平滑系数 m=15
  - **Phase B-1 ALS 向量注入**：在 train_idx 子集上重训 ALS（factors=50, iterations=10），仅注入 `als_score`（1维点积），避免 21 维嵌入引发过拟合早停
  - **Phase C 特征剪枝**：移除 5 个零重要性特征（`gender_encoded`、`dow_match`、`user_30d_active_days`、`user_has_in_playlist`、`user_playlist_artist_count_log`）
  - **贝叶斯平滑**：`user_artist_repeat_rate`、`user_target_rate`、`song_target_rate` 仅从 train_idx 子集计算，公式 `TE = (n×mean + 15×prior) / (n+15)`
- **DeepFM v3** (`train_deepfm_v3.py`)：

  - 同步应用用户级时序切分、Phase B-2 Cross TE、Phase C 特征剪枝
  - GPU AMP 加速，与 LightGBM 使用完全相同的 train_idx/val_idx
- **外部歌曲元数据补全** (`scripts/enrich_db.py`)：

  - 五级元数据聚合策略（QQ 音乐 / 网易云 / Last.fm / MusicBrainz / langdetect 本地语种识别）
  - 补全 `songs.origin_country`、`songs.language`（数字代码→中文映射）、`songs.release_year`
  - 修复 bd 城市位置映射错误，解决 collation mismatch 与 SQL_LOG_BIN 权限问题

### ⚡ 优化

- **ALS 召回**：从全量 play_history 召回改为在切分后的训练集子集上重训，消除验证集信息泄露风险
- **特征矩阵维度**：从 45 维精简至 32 维（移除 B-3/B-4 无效特征 + Phase C 零重要性特征）

### 🧪 实验结论（已废弃的方向）

- **B-3 记忆衰减特征**：`user_song_prev_play_days`（-1 占 99.99%）和 `user_song_play_count_before`（0 占 99.99%）因 play_history 中 (user,song) 对几乎唯一，导致两个特征近乎常数，无信息量，已废弃
- **B-4 时间窗口滚动特征**：7d/30d 播放量、平均完播率、trending_ratio 等 6 个特征轻微损害 AUC（0.6798 → 0.6631），已废弃

### 📊 模型性能（2026-03-17）

| 模型                               | 验证 AUC         | 说明                   |
| ---------------------------------- | ---------------- | ---------------------- |
| LightGBM（无泄漏，B-1+B-2+C）      | **0.6798** | 最佳，用户级时序切分   |
| LightGBM（无泄漏，B-2+C）          | 0.6717           | 基准无泄漏验证         |
| DeepFM v3                          | —               | 与 LightGBM 集成后使用 |
| LightGBM（旧，全局切分含隐性泄漏） | 0.9603           | 虚高，已废弃           |

### 📁 新增/修改文件

| 文件                                  | 改动                                                  |
| ------------------------------------- | ----------------------------------------------------- |
| `Project/prepare_features_v3.py`    | [REWRITE] 特征工程 v3，45维，用户级时序切分           |
| `Project/train_lgbm.py`             | [UPDATE] Phase A+B-1+B-2+C，6条验证断言，ALS 子集重训 |
| `Project/train_deepfm_v3.py`        | [UPDATE] 同步用户级切分 + Cross TE + 特征剪枝         |
| `Project/build_ensemble.py`         | [UPDATE] 网格搜索 α，用户级切分对齐                  |
| `Project/sync_recs_v3.py`           | [UPDATE] 三通道召回 + 集成精排 + 多样性重排           |
| `scripts/enrich_db.py`              | [NEW] 外部歌曲元数据五级补全脚本                      |
| `Mode/lgbm_model.pkl`               | [UPDATE] 最新 LightGBM 精排模型                       |
| `Mode/deepfm_model_v3.pth`          | [UPDATE] 最新 DeepFM 排序模型                         |
| `Mode/als_model.pkl`                | [NEW] ALS 召回模型（rank=50, iter=10）                |
| `Mode/candidates.pkl`               | [NEW] ALS Top-100 候选集                              |
| `Mode/features_v3.pkl`              | [UPDATE] 特征矩阵 v3（7.37M 样本，32维）              |
| `Mode/ensemble_config.pkl`          | [NEW] 最优集成权重 α                                 |
| `Mode/encoders_v3.pkl`              | [UPDATE] 标签编码器 v3                                |
| `Mode/model_config_v3.pkl`          | [UPDATE] 模型特征配置                                 |
| `Mode/lgbm_metrics.csv`             | [UPDATE] 各阶段训练指标记录                           |
| `scripts/start_daily_recommend.bat` | [UPDATE] 改为调用 sync_recs_v3.py                     |

---

## v2.2.0 (2026-03-13) - 流派规范化、KKBOX数据导入、GPU加速重训

### 🚀 新增功能

- **GPU AMP 加速训练** (`train_deepfm.py` 完全重写)：

  - 使用 `torch.cuda.amp.autocast` + `GradScaler` 启用 FP16 混合精度，充分利用 RTX 4060 Tensor Core。
  - DataLoader 参数升级：`num_workers=4, pin_memory=True, persistent_workers=True, prefetch_factor=2`。
  - Batch Size 从 256 扩大至 4096（steps/epoch 减少 16x），每步实时 tqdm 进度条显示 loss。
  - 训练完成后自动保存 `deepfm_model.pth`（27.4 MB）和 `model_config.pkl`（特征配置）。
  - 最终验证 AUC 提升至 **0.8053**（Epoch 5）。
- **动态特征配置** (`model_config.pkl`)：保存 `feature_columns` + `dnn_hidden_units` 等关键配置，供 `build_faiss_index.py` 自动重建模型架构，无需手动硬编码特征数。

### ⚡ 优化

- **`build_faiss_index.py` 动态特征加载**：优先读取 `model_config.pkl`，向下兼容缺少配置文件的旧模型（回退至硬编码 5 特征）。
- **`prepare_features.py` 模块路径修复**：在 `extract_primary_genre()` 函数内通过 `sys.path.insert` 动态添加 `scripts/` 目录，解决 `ModuleNotFoundError: update_song_metadata`。
- **`sync_recs_v2.py` 推荐目标限制**：用户查询由 `status='active'` 泛查改为 `username IN ('jf', 'jf2')`，仅为真实业务用户生成推荐，彻底排除 admin 和 3.4 万个 kkbox 训练账号。

### 🗄️ 数据工程（一次性脚本，已删除）

- **流派规范化** (`normalize_genres.py`，已删除)：

  - 扩展 `GENRE_MAP` 至 40 条映射规则（原 16 条），批量重写 `songs.genre` 字段。
  - "其他"类型歌曲占比从 57%（1,316,528 首）降至 11%（258,876 首），1,057,652 首歌曲成功重新分类。
- **KKBOX 用户数据导入** (`import_kkbox_to_db.py`，已删除)：

  - 重写为 Pandas 分块读取（CHUNK_SIZE=200,000），替代因 Java 21 不兼容而崩溃的 PySpark 方案。
  - 成功导入 34,403 个 KKBOX 用户（`username = 'kkbox_xxx'`）和 7,377,416 条播放记录至 MySQL。

### 🐛 Bug 修复

- **BCELoss + AMP 不兼容**：`binary_cross_entropy` 在 `autocast` 内部报错，修复为将 `y_pred.float()` 移出 autocast 上下文再计算 loss。
- **`torch.compile` Windows 崩溃**：`Inductor` 后端需要 Triton（仅 Linux），通过 `sys.platform != 'win32'` 守卫跳过编译。
- **MySQL `local_infile` 被禁**：KKBOX 导入时 `LOAD DATA LOCAL INFILE` 报错 3948，通过 `SET GLOBAL local_infile = 1` 解决。

---

## v2.1.0 (2026-03-12) - 推荐反馈闭环修复与效果评估

### 🚀 新增功能

- **推荐效果评估脚本** (`evaluate_recs.py`)：基于 `recommendation_feedback` 历史数据计算 CTR、平均完播率、收藏率、跳曲率、Precision@10、覆盖度六项指标，结果输出至控制台并写入 `Mode/evaluation_report.txt`。

### ⚡ 优化

- **`sync_recs_v2.py` — `update_feedback()` 数据链路修复**：

  - 步骤 A：通过 JOIN `play_history` 与 `songs`，将实际播放完成率（`play_duration / duration`）同步至 `recommendation_feedback.was_played` 与 `play_completion`，修复了这两字段长期为 0 的根本原因。
  - 步骤 B：通过 JOIN `playlist_songs` + `user_playlists`（`is_default=1`），将收藏行为同步至 `was_favorited` 字段，使收藏信号正式纳入评分。
  - 步骤 D：读取 `user_preference_feedback` 显式满意度，批量施加 +3.0 / +1.5 / 0 / -2.0 分差，高优先级覆盖隐式行为信号。
- **`sync_recs_v2.py` — `get_user_profile()` 画像精度提升**：

  - 引入完播率修正系数（完播率 <20% → ×0.5；20-80% → ×1.0；>80% → ×1.5），跳曲降权，听完加权。
  - 读取 `users.preferred_genres` / `preferred_artists`（分号分隔），匹配 `songs.genre` / `songs.language` / `songs.artist`，以权重 0.2 补充用户画像向量，无论行为数据是否为空均生效。

### 🐛 Bug 修复

- **`start_daily_recommend.bat` 路径硬编码**：将 `cd /d E:\Graduation-project-design\...\Project` 改为 `cd /d "%~dp0..\Project"` 相对路径，修复从工作树目录运行时始终跑主仓库旧脚本的问题。

---

## v2.0.1 (2026-02-26) - 推荐引擎冷启动与覆盖率修复

### 🐛 修复 (Fixed)

- **推荐结果被意外覆盖**: 修复了 `sync_recs_v2.py` 中 `TRUNCATE TABLE` 导致 Java 端冷启动推荐被误删的问题，改为仅清除 `deepfm` 来源的推荐记录。
- **管理员无效计算**: 修复了推荐系统会为 `admin` 账户生成推荐的问题，现已在 SQL 查询中通过 `username != 'admin'` 排除。

### ⚡ 优化 (Optimized)

- **外部歌曲桥接策略 (Genre Bridging)**:
  - 针对用户播放外部音乐（无 FAISS 向量）的情况，新增 `find_genre_proxy` 代理机制。通过歌曲的中文流派在 KKBOX 库中寻找热门代理向量，实现无缝衔接。
- **推荐生成性能大幅提升**:
  - 引入了 `genre_cache` 预加载字典避免在循环内执行上千次慢 SQL。
  - 废弃 `ORDER BY RAND()` 的耗时查询，改用内存预加载候选池进行随机乱序，将百万级数据的热度兜底速度从数分钟降至秒级。
- **纯冷启动支持**:
  - 当新用户无任何播放交互时，算法会自动读取注册时选择的 `preferred_genres` 和 `preferred_artists`，生成初始化画像参与 FAISS 检索。

## v2.0.0-DeepFM-Recommendation (2026-02-25) - 推荐系统全面升级

### 🚀 新增 (Added)

- **DeepFM 模型全量重训**:

  - 使用 350,463 首歌曲的完整 KKBOX 数据集重新训练 DeepFM 深度学习模型。
  - 训练参数优化: `BATCH_SIZE=256`, `SAMPLE_RATE=1.0`, `MIN_SONG_INTERACTIONS=1`。
  - 最终验证 AUC 达到 **0.7933** (Epoch 3)，模型精度显著提升。
- **FAISS 向量检索引擎** (`build_faiss_index.py`):

  - 从 DeepFM 模型中提取 16 维嵌入向量 (歌曲+流派+语言+艺术家)，拼接为 64 维复合向量。
  - 构建 `IndexFlatIP` 索引 (L2 归一化后等价余弦相似度)，单次 Top-20 检索耗时 < 1ms。
  - 产出: `song_index.faiss` + `song_id_map.pkl`。
- **多通道混合推荐脚本** (`sync_recs_v2.py`):

  - **反馈回收**: 回收昨日推荐反馈，根据播放完成率/收藏/忽略动态调整歌曲评分，连续忽略 3 次触发 14 天冷却期。
  - **用户画像**: 加权融合 5 类行为 (昨日播放×3.0、7日播放×2.0、历史×1.0、收藏×2.5、歌单×1.5) 生成 64 维用户偏好向量。
  - **通道 A (FAISS)**: 基于用户画像向量检索 Top-100 相似歌曲，过滤已听/冷却歌曲后取 Top-10。
  - **通道 B (热度兜底)**: FAISS 结果不足时，按 `popularity DESC, release_year DESC` 补充热门歌曲。
  - 每日生成全用户 Top-10 推荐并写入 `recommendations` 表。
- **recommendation_feedback 表**:

  - 新增反馈追踪表，记录每日推荐的用户交互数据 (是否播放、完成率、是否收藏)，支持推荐闭环优化。
- **每日定时推荐脚本** (`start_daily_recommend.bat`):

  - 位于 `MusicMode/scripts/`，可配合 Windows 任务计划程序实现每日凌晨自动更新推荐。

### ⚡ 优化 (Optimized)

- **FAISS 映射性能**: 将 `LabelEncoder.transform()` 替换为字典查询，350,000+ 歌曲的 MySQL ↔ FAISS 双向映射从数小时级降至秒级。

### 📝 技术细节

| 文件                          | 改动                             |
| ----------------------------- | -------------------------------- |
| `build_faiss_index.py`      | [NEW] FAISS 索引构建脚本         |
| `sync_recs_v2.py`           | [NEW] 多通道混合推荐生成脚本     |
| `start_daily_recommend.bat` | [NEW] 定时推荐启动批处理         |
| `data_cleaning.py`          | `MIN_SONG_INTERACTIONS` 改为 1 |
| `prepare_features.py`       | `SAMPLE_RATE` 改为 1.0         |
| `train_deepfm.py`           | `BATCH_SIZE` 改为 256          |

## v2.0.0 (2026-01-22) - 推荐算法引擎升级

### 🎯 主要成果

- ✅ **混合推荐架构**: 成功构建 ALS (召回) + DeepFM (精排) 双塔推荐系统
- ✅ **GPU 加速**: 全面支持 NVIDIA GPU (RTX 4060) 训练，无需繁琐配置
- ✅ **数据治理**:
  - 📊 EDA 分析报告 (`data_analysis.py`)
  - 🔧 自动化数据清洗与样本平衡 (`data_cleaning.py`)
  - ⚙️ 特征工程流水线 (`prepare_features.py`)
- ✅ **自动化**: `run_pipeline.py` 实现从数据处理到模型部署的一键运行

### 📁 新增模块

- `Project/train_deepfm.py`: 深度学习排序模型 (DeepCTR-Torch)
- `Project/train_als.py`: 矩阵分解召回模型 (Implicit)
- `Project/sync_recs.py`: 推荐结果回写 MySQL
- `Mode/`: 独立的模型与特征存储目录

---

## v1.0.0 （2026-01-21）- Phase 1 完成

### 🎯 主要成果

- ✅ **项目结构重组**: 将 Python 脚本从 MusicWeb 移至 MusicMode
- ✅ **数据库迁移**: 为 `songs` 表添加 `kkbox_id`、`genre_ids`、`language`、`popularity` 字段
- ✅ **全量数据导入**: 成功导入 KKBOX 229 万首歌曲（PySpark 4.0 + Java 21）
- ✅ **元数据更新**: 更新 229 万首歌曲的真实歌名和中文流派
- ✅ **环境配置**: 安装 Java 21 LTS、配置 Hadoop winutils

### 📊 数据统计

| 指标            | 数值         |
| --------------- | ------------ |
| songs 表总记录  | 2,306,827 条 |
| 新增 KKBOX 歌曲 | 2,296,806 条 |
| 元数据更新      | 2,296,833 条 |
| ETL 耗时        | 约 5 分钟    |
| 元数据更新耗时  | 约 13 分钟   |

### 🔧 技术细节

- **PySpark 版本**: 从 3.5.0 升级到 4.0.0（支持 Java 21）
- **Java 多版本共存**: MusicWeb 使用 Java 25，MusicMode 使用 Java 21
- **Genre 映射**: 建立了 30+ 个 genre_id 到中文流派的映射表

### 📁 新增文件

- `scripts/spark_etl_songs.py` - KKBOX 歌曲全量导入脚本
- `scripts/update_song_metadata.py` - 元数据更新脚本
- `scripts/requirements.txt` - Python 依赖配置
- `sql/migration_phase1.sql` - 数据库迁移脚本
