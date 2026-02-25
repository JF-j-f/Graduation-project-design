# MusicMode 更新日志 (Changelog)

本文档记录 MusicMode 项目的所有更新历史。

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
