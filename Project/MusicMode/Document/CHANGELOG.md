# MusicMode 更新日志 (Changelog)

本文档记录 MusicMode 项目的所有更新历史。

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

### 📊 模型性能（2026-03-18）

| 模型 | 验证 AUC | 说明 |
|------|---------|------|
| LightGBM（OOF TE）| **0.7063** | OOF Target Encoding 消除泄漏 |
| DeepFM v3（EPOCHS=15）| **0.7548** | GPU AMP，L2 正则，min-count 过滤 |
| DIN（EPOCHS=15）| **0.7602** | 最佳单模型，用户兴趣序列建模 |
| Stacking Ensemble | **0.7607** | LightGBM + DeepFM + DIN 堆叠集成 |
| CatBoost | ~~0.6499~~ | 已移除（过拟合差距 0.306） |
| XGBoost | ~~—~~ | 已移除（与 LightGBM 冗余） |

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

### 📁 新增/修改文件

| 文件 | 改动 |
|------|------|
| `Project/train_catboost.py` | [DELETED] CatBoost 训练脚本已移除 |
| `Project/train_xgboost.py` | [DELETED] XGBoost 训练脚本已移除 |
| `Mode/catboost/` | [DELETED] CatBoost 模型目录已移除 |
| `Mode/xgboost/` | [DELETED] XGBoost 模型目录已移除 |
| `Project/train_lgbm.py` | [UPDATE] 改用 OOF Target Encoding |
| `Project/train_deepfm_v3.py` | [UPDATE] EPOCHS 10→15，L2 正则，min-count |
| `Project/train_din.py` | [UPDATE] EPOCHS 10→15，L2 正则，min-count |
| `Project/build_ensemble.py` | [UPDATE] Stacking 集成：LightGBM + DeepFM + DIN |
| `Project/evaluate_offline.py` | [NEW] KKBOX 离线评估脚本（NDCG@10=0.721，MRR=0.811）|
| `Project/evaluate_recs.py` | [UPDATE] 在线评估标签逻辑更新（CTR=10.39%）|
| `Document/README.md` | [UPDATE] 模型阵容更新，移除 CatBoost/XGBoost |

---

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

| 模型 | 验证 AUC | 说明 |
|------|---------|------|
| LightGBM（无泄漏，B-1+B-2+C）| **0.6798** | 最佳，用户级时序切分 |
| LightGBM（无泄漏，B-2+C）| 0.6717 | 基准无泄漏验证 |
| DeepFM v3 | — | 与 LightGBM 集成后使用 |
| LightGBM（旧，全局切分含隐性泄漏）| 0.9603 | 虚高，已废弃 |

### 📁 新增/修改文件

| 文件 | 改动 |
|------|------|
| `Project/prepare_features_v3.py` | [REWRITE] 特征工程 v3，45维，用户级时序切分 |
| `Project/train_lgbm.py` | [UPDATE] Phase A+B-1+B-2+C，6条验证断言，ALS 子集重训 |
| `Project/train_deepfm_v3.py` | [UPDATE] 同步用户级切分 + Cross TE + 特征剪枝 |
| `Project/build_ensemble.py` | [UPDATE] 网格搜索 α，用户级切分对齐 |
| `Project/sync_recs_v3.py` | [UPDATE] 三通道召回 + 集成精排 + 多样性重排 |
| `scripts/enrich_db.py` | [NEW] 外部歌曲元数据五级补全脚本 |
| `Mode/lgbm_model.pkl` | [UPDATE] 最新 LightGBM 精排模型 |
| `Mode/deepfm_model_v3.pth` | [UPDATE] 最新 DeepFM 排序模型 |
| `Mode/als_model.pkl` | [NEW] ALS 召回模型（rank=50, iter=10）|
| `Mode/candidates.pkl` | [NEW] ALS Top-100 候选集 |
| `Mode/features_v3.pkl` | [UPDATE] 特征矩阵 v3（7.37M 样本，32维）|
| `Mode/ensemble_config.pkl` | [NEW] 最优集成权重 α |
| `Mode/encoders_v3.pkl` | [UPDATE] 标签编码器 v3 |
| `Mode/model_config_v3.pkl` | [UPDATE] 模型特征配置 |
| `Mode/lgbm_metrics.csv` | [UPDATE] 各阶段训练指标记录 |
| `scripts/start_daily_recommend.bat` | [UPDATE] 改为调用 sync_recs_v3.py |

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

| 文件 | 改动 |
|------|------|
| `build_faiss_index.py` | [NEW] FAISS 索引构建脚本 |
| `sync_recs_v2.py` | [NEW] 多通道混合推荐生成脚本 |
| `start_daily_recommend.bat` | [NEW] 定时推荐启动批处理 |
| `data_cleaning.py` | `MIN_SONG_INTERACTIONS` 改为 1 |
| `prepare_features.py` | `SAMPLE_RATE` 改为 1.0 |
| `train_deepfm.py` | `BATCH_SIZE` 改为 256 |

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

| 指标 | 数值 |
|------|------|
| songs 表总记录 | 2,306,827 条 |
| 新增 KKBOX 歌曲 | 2,296,806 条 |
| 元数据更新 | 2,296,833 条 |
| ETL 耗时 | 约 5 分钟 |
| 元数据更新耗时 | 约 13 分钟 |

### 🔧 技术细节

- **PySpark 版本**: 从 3.5.0 升级到 4.0.0（支持 Java 21）
- **Java 多版本共存**: MusicWeb 使用 Java 25，MusicMode 使用 Java 21
- **Genre 映射**: 建立了 30+ 个 genre_id 到中文流派的映射表

### 📁 新增文件

- `scripts/spark_etl_songs.py` - KKBOX 歌曲全量导入脚本
- `scripts/update_song_metadata.py` - 元数据更新脚本
- `scripts/requirements.txt` - Python 依赖配置
- `sql/migration_phase1.sql` - 数据库迁移脚本
