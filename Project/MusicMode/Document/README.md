# MusicMode 项目文档

## 项目概述

MusicMode 是一个基于大数据技术的**个性化音乐推荐系统后端引擎**，与 MusicWeb（Java 前端）配合使用，实现"千人千面"的音乐推荐体验。项目采用 Python + PySpark 技术栈，负责大规模数据的 ETL 处理、特征工程以及深度学习模型的离线训练。

### 项目定位

| 项目 | 职责 | 技术栈 |
|------|------|--------|
| **MusicWeb** | 前端交互、用户管理、音乐播放 | Java 23 + Servlet + JSP |
| **MusicMode** | 数据处理、算法训练、推荐计算 | Python 3.12 + PySpark 4.0 |

## 技术栈

### 数据处理

- **Python 3.12** - 主要编程语言
- **PySpark 4.0.0** - 大规模数据处理（支持 Java 21+）
- **Pandas 2.0+** - 数据分析与处理
- **NumPy 1.24+** - 数值计算

### 数据库连接

- **PyMySQL 1.1+** - Python MySQL 驱动
- **SQLAlchemy 2.0+** - ORM 工具，用于结果回写
- **MySQL Connector/J 8.0.30** - JDBC 驱动（PySpark 使用）

### 算法模型

- **DeepCTR-Torch** - 基于 PyTorch 的深度兴趣网络
- **DeepFM** - 高阶交叉特征排序 (已训练, AUC=0.7933)
- **FAISS** - 高性能向量相似度检索引擎
- **Spark MLlib ALS** - 协同过滤召回

## 项目核心结构

```
MusicMode/
├── Document/                    # 项目文档目录
│   ├── README.md                 # 项目文档
│   ├── CHANGELOG.md              # 项目更新日志
│   └── Data_Description.md       # 数据集说明文档
├── scripts/                     # 运维脚本目录
│   ├── spark_etl_songs.py        # KKBOX 歌曲全量导入脚本
│   ├── update_song_metadata.py   # 歌曲元数据更新脚本
│   ├── start_daily_recommend.bat # 每日推荐定时任务脚本
│   └── requirements.txt          # Python 依赖配置
├── sql/                         # SQL 脚本目录
│   └── migration_phase1.sql      # 数据库迁移脚本
├── Project/                     # 算法源码
│   ├── data_analysis.py          # EDA 数据分析
│   ├── data_cleaning.py          # 数据清洗与采样
│   ├── prepare_features.py       # 特征工程
│   ├── train_als.py              # ALS 召回模型
│   ├── train_deepfm.py           # DeepFM 精排模型
│   ├── build_faiss_index.py      # FAISS 向量索引构建
│   ├── sync_recs.py              # 旧版结果同步
│   ├── sync_recs_v2.py           # 多通道混合推荐脚本
│   └── run_pipeline.py           # 一键运行脚本
└── Mode/                         # 模型产物
    ├── features.pkl              # 预处理特征
    ├── encoders.pkl              # 标签编码器
    ├── deepfm_model.pth          # DeepFM 训练模型
    ├── song_index.faiss          # FAISS 向量索引
    ├── song_id_map.pkl           # FAISS ID ↔ MySQL ID 映射
    ├── als_model.pkl             # ALS 召回模型
    ├── candidates.pkl            # 候选集缓存
    ├── cleaned_songs.pkl         # 清洗后的歌曲数据
    ├── cleaned_train.pkl         # 清洗后的训练数据
    ├── eda_distribution.png      # EDA 分布可视化图
    ├── eda_report.md             # EDA 分析报告
    └── training_progress.png     # 训练过程可视化图
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
3. **混合推荐计算**:
   - **DeepFM 精排**: 全量训练后提取歌曲嵌入向量 (64维)
   - **FAISS 检索**: 根据用户画像向量从索引中召回 Top-100 候选
   - **热度兜底**: FAISS 结果不足时按 popularity + release_year 补充
4. **反馈闭环**: `recommendation_feedback` 表追踪推荐交互，动态调整评分与冷却
5. **结果回传**: `sync_recs_v2.py` 将 Top-10 推荐批量写入 `recommendations` 表
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

*本文档最后更新时间：2026年2月26日 00:30*
