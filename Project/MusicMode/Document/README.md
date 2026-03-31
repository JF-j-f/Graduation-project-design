# MusicMode 项目文档

## 项目概述

MusicMode 是一个基于大数据技术的**个性化音乐推荐系统后端引擎**，与 MusicWeb（Java 前端）配合使用，实现"千人千面"的音乐推荐体验。项目采用 Python + PyTorch 技术栈，负责大规模数据的 ETL 处理、特征工程以及深度学习模型的离线训练。

## 技术栈

### 数据处理

- **Python 3.12** - 主要编程语言
- **Pandas 2.2+** - 大规模数据 ETL
- **NumPy 1.24+** - 数值计算

### 数据库连接

- **PyMySQL 1.1+** - Python MySQL 驱动
- **SQLAlchemy 2.0+** - ORM 工具，用于结果回写
- **MySQL Connector/J 8.0.30** - JDBC 驱动（PySpark 使用）

### 算法模型

- **LightGBM** - 梯度提升粗排模型（OOF Target Encoding，num_leaves=128）
- **DeepFM v3** - 高阶交叉特征深度精排（GPU AMP 加速，embedding_dim=32）
- **BST (Behavior Sequence Transformer)** - 用户行为序列精排（Transformer + MLP 四层）
- **SLSQP Ensemble** - LightGBM + DeepFM + BST 权重优化集成（SLSQP vs 等权平均取优）
- **FAISS** - 高性能向量相似度检索引擎（召回层）
- **Spark MLlib ALS** - 协同过滤召回（新用户冷启动降级至注册偏好内容召回）
- **MMR（最大边际相关）** - 多样性重排（替代同艺术家硬约束）

## 项目核心结构

```
MusicMode/
├── Document/                    # 项目文档目录
│   ├── README.md                 # 项目文档
│   ├── CHANGELOG.md              # 项目更新日志
│   ├── Data_Description.md       # 数据集说明文档
│   └── evaluation_report.txt     # 在线评估报告备份
├── scripts/                     # 运维脚本目录
│   ├── spark_etl_songs.py        # KKBOX 歌曲全量导入脚本
│   ├── update_song_metadata.py   # 歌曲元数据更新脚本
│   ├── enrich_db.py              # 外部歌曲元数据补全及数据库字段扩充脚本
│   ├── start_daily_recommend.bat # 每日推荐定时任务脚本
│   └── requirements.txt          # Python 依赖配置
├── sql/                         # SQL 脚本目录
│   └── migration_phase1.sql      # 数据库迁移脚本
├── Project/                     # 算法源码
│   ├── data_analysis.py          # EDA 数据分析
│   ├── data_cleaning.py          # 数据清洗与采样
│   ├── prepare_features_v3.py    # 特征工程 v3（71 维：14 sparse + 57 dense，含 SVD 嵌入 + OOF TE）
│   ├── train_als.py              # ALS 召回模型
│   ├── train_deepfm_v3.py        # DeepFM 精排模型 v3（GPU AMP，embedding_dim=32，Val AUC=0.7610）
│   ├── train_dien.py             # DIEN 精排模型（GRU+AUGRU 序列建模，Val AUC=0.7673）
│   ├── train_lgbm.py             # LightGBM 粗排模型（OOF TE，num_leaves=128）
│   ├── build_ensemble.py         # 集成：LightGBM + DeepFM + BST，SLSQP vs 等权平均取优
│   ├── build_faiss_index.py      # FAISS 向量索引构建
│   ├── sync_recs_v3.py           # 三通道召回 + 集成精排推荐脚本 v3（当前版）
│   ├── evaluate_offline.py       # KKBOX 用户离线评估脚本（Hit Rate/Precision/Recall/NDCG/MRR）
│   ├── evaluate_recs.py          # 在线评估脚本（jf/jf2 真实用户，CTR/完播率/NDCG）
│   └── run_pipeline.py           # 一键运行脚本
└── Mode/                         # 模型产物（运行时生成，不纳入版本库）
    ├── features_v3.pkl           # 预处理特征矩阵 v3（7.37M 样本，71 维）
    ├── features_v3_cache.npz     # features_v3.pkl 的 NumPy 快速加载缓存
    ├── encoders_v3.pkl           # 标签编码器 v3
    ├── lgbm/lgbm_model.pkl       # LightGBM 精排模型（待重训）
    ├── lgbm/lgbm_importance.png  # LightGBM 特征重要度图
    ├── lgbm/lgbm_metrics.csv     # LightGBM 训练指标记录
    ├── deepfm/deepfm_model.pth   # DeepFM 精排模型（Val AUC=0.7610）
    ├── deepfm/model_config.pkl   # DeepFM 模型架构配置
    ├── deepfm/training_progress.png  # DeepFM 训练曲线
    ├── deepfm/deepfm_metrics.csv     # DeepFM 逐 epoch 指标
    ├── dien/dien_model.pth       # DIEN 精排模型（Val AUC=0.7673）
    ├── dien/model_config.pkl     # DIEN 模型架构配置
    ├── dien/training_progress.png    # DIEN 训练曲线
    ├── dien/dien_metrics.csv         # DIEN 逐 epoch 指标
    ├── dien/dien_val_preds.npy       # DIEN 验证集预测分数
    ├── ensemble/ensemble_config.pkl  # 集成配置（best_weights 加权平均）
    ├── ensemble/ensemble_metrics.csv # 各模型及集成 AUC 对比
    ├── ensemble/ensemble_report.txt  # 集成评估文字报告
    ├── evaluation_report.txt     # 在线评估报告（jf/jf2 真实交互数据）
    ├── als_model.pkl             # ALS 召回模型（rank=50, iter=10）
    ├── candidates.pkl            # ALS Top-100 候选集缓存
    ├── song_index.faiss          # FAISS 向量索引
    ├── song_id_map.pkl           # FAISS ID ↔ MySQL ID 映射
    ├── song_stats.pkl            # 歌曲统计特征缓存
    └── user_stats.pkl            # 用户统计特征缓存
```

## 数据流程

系统遵循以下"数据闭环"流程实现 Java 前端与 Python 模型的联动：

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   用户行为   │───▶│   MySQL     │───▶│   PySpark   │
│  (MusicWeb) │    │  数据存储    │    │   ETL处理   │
└─────────────┘    └─────────────┘    └─────────────┘
                                              │
┌─────────────┐    ┌─────────────┐    ┌───────▼─────┐
│   用户界面   │◀───│ 推荐结果表   │◀───│  算法模型   │
│  (MusicWeb) │    │  (MySQL)    │    │ (DeepFM等)  │
└─────────────┘    └─────────────┘    └─────────────┘
```

### 详细流程

1. **行为日志采集**: MusicWeb 通过 `PlayHistoryDAO` 实时记录用户行为至 MySQL
2. **大数据同步 (ETL)**: PySpark 使用 JDBC 抽取交互数据，或直接读取 CSV 文件
3. **混合推荐计算（四层漏斗）**:
   - **三路召回（~600）**: 通道A FAISS 向量召回 + 通道B 满意度感知热度召回 + 通道C ALS 协同过滤召回（各 200 首，新用户通道C降级至注册偏好内容召回）
   - **粗排（→300）**: LightGBM 筛选
   - **精排（→150）**: DeepFM + BST 双模型加权集成
   - **MMR 重排（→50）**: Maximal Marginal Relevance 兼顾相关性与多样性
4. **反馈闭环**: `recommendation_feedback` 表追踪交互，feedback_score 14 天衰减；`negative_count` 字段触发三档渐进冷却（3/7/14 天）
5. **结果回传**: `sync_recs_v3.py` 将 Top-50 推荐写入 `recommendations` 表
6. **实时渲染**: 用户访问页面时，Java 端调用推荐逻辑展示个性化内容

## 环境配置

### 前置要求

- **Java 21 LTS** (Eclipse Adoptium) - PySpark 4.0 要求
- **Python 3.12** - 主要运行环境
- **Hadoop winutils** - Windows 下 Spark 运行必需

### 环境变量

```powershell
# Java 21 (供 PySpark 使用)
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-21.0.9.10-hotspot"

# Hadoop winutils
$env:HADOOP_HOME = "E:\毕业论文\Graduation-project-design\hadoop\bin"
```

### 安装依赖

```powershell
cd E:\毕业论文\Project\MusicMode\scripts
pip install -r requirements.txt -i https://pypi.org/simple/
```

## 脚本说明

### spark_etl_songs.py

**功能**: 全量导入 KKBOX 歌曲数据集到 MySQL

```powershell
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-21.0.9.10-hotspot"
$env:HADOOP_HOME = "E:\毕业论文\Graduation-project-design\hadoop\bin"
python spark_etl_songs.py
```

**处理逻辑**:

- 读取 KKBOX `songs.csv`（229 万首歌曲）
- 读取 `train.csv` 统计歌曲热度（popularity）
- 增量导入：通过 `kkbox_id` 去重，不覆盖已有数据
- 批量写入 MySQL `songs` 表

### update_song_metadata.py

**功能**: 更新歌曲的真实歌名和中文流派

```powershell
python update_song_metadata.py
```

**处理逻辑**:

- 用 Spark 读取 `song_extra_info.csv` 获取真实歌名
- 将 `genre_ids` 映射为中文流派
- 通过 `kkbox_id` 匹配更新 MySQL

---

*本文档最后更新时间：2026年3月27日*
