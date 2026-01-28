# MusicMode 更新日志 (Changelog)

本文档记录 MusicMode 项目的所有更新历史。

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
