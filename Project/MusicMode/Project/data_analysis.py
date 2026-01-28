# -*- coding: utf-8 -*-
"""
数据分析脚本 (EDA - Exploratory Data Analysis)
功能：
1. 加载 KKBOX 数据集
2. 生成数据统计报告
3. 可视化关键特征分布
4. 输出图表用于论文

作者：MusicMode 推荐系统
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# ============================================
# 配置
# ============================================

# 数据路径
DATA_DIR = r"E:\毕业论文\Data"
TRAIN_CSV = os.path.join(DATA_DIR, "train.csv")
SONGS_CSV = os.path.join(DATA_DIR, "songs.csv")
MEMBERS_CSV = os.path.join(DATA_DIR, "members.csv")

# 输出路径
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

# 采样比例（用于快速分析）
SAMPLE_RATE = 0.1  # 10% 采样用于 EDA


def load_data():
    """加载数据集"""
    print("\n" + "=" * 60)
    print("📂 [Step 1/5] 加载数据集")
    print("=" * 60)
    
    # 加载训练数据
    print(f"\n📥 正在加载 train.csv...")
    train_df = pd.read_csv(TRAIN_CSV, dtype={'msno': str, 'song_id': str})
    print(f"   ✅ 训练数据: {len(train_df):,} 条记录")
    
    # 采样以加快分析
    if SAMPLE_RATE < 1.0:
        sample_size = int(len(train_df) * SAMPLE_RATE)
        train_sample = train_df.sample(n=sample_size, random_state=42)
        print(f"   📊 采样: {len(train_sample):,} 条 ({SAMPLE_RATE*100:.0f}%)")
    else:
        train_sample = train_df
    
    # 加载歌曲数据
    print(f"\n📥 正在加载 songs.csv...")
    songs_df = pd.read_csv(SONGS_CSV, dtype={'song_id': str, 'genre_ids': str, 'language': str})
    print(f"   ✅ 歌曲数据: {len(songs_df):,} 首歌曲")
    
    # 加载用户数据
    members_df = None
    if os.path.exists(MEMBERS_CSV):
        print(f"\n📥 正在加载 members.csv...")
        members_df = pd.read_csv(MEMBERS_CSV, dtype={'msno': str})
        print(f"   ✅ 用户数据: {len(members_df):,} 个用户")
    
    return train_sample, songs_df, members_df, train_df


def basic_statistics(train_df, songs_df, members_df, full_train_df):
    """基础统计信息"""
    print("\n" + "=" * 60)
    print("📊 [Step 2/5] 基础统计")
    print("=" * 60)
    
    stats = {}
    
    # 数据规模
    print("\n📐 数据规模:")
    print(f"   - 总交互记录: {len(full_train_df):,}")
    print(f"   - 唯一用户数: {full_train_df['msno'].nunique():,}")
    print(f"   - 唯一歌曲数: {full_train_df['song_id'].nunique():,}")
    print(f"   - 歌曲库总量: {len(songs_df):,}")
    
    stats['total_interactions'] = len(full_train_df)
    stats['unique_users'] = full_train_df['msno'].nunique()
    stats['unique_songs'] = full_train_df['song_id'].nunique()
    stats['total_songs'] = len(songs_df)
    
    # 正负样本比例
    print("\n🎯 正负样本分布:")
    target_counts = train_df['target'].value_counts()
    positive_ratio = target_counts.get(1, 0) / len(train_df) * 100
    negative_ratio = target_counts.get(0, 0) / len(train_df) * 100
    print(f"   - 正样本 (target=1): {target_counts.get(1, 0):,} ({positive_ratio:.1f}%)")
    print(f"   - 负样本 (target=0): {target_counts.get(0, 0):,} ({negative_ratio:.1f}%)")
    
    stats['positive_ratio'] = positive_ratio
    stats['negative_ratio'] = negative_ratio
    
    # 缺失值统计
    print("\n❓ 缺失值统计 (songs.csv):")
    for col in ['artist_name', 'genre_ids', 'language', 'song_length']:
        if col in songs_df.columns:
            missing = songs_df[col].isna().sum()
            missing_pct = missing / len(songs_df) * 100
            print(f"   - {col}: {missing:,} ({missing_pct:.2f}%)")
    
    return stats


def visualize_distributions(train_df, songs_df, stats):
    """可视化分布"""
    print("\n" + "=" * 60)
    print("📈 [Step 3/5] 可视化分析")
    print("=" * 60)
    
    os.makedirs(MODE_DIR, exist_ok=True)
    
    # 创建画布
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('KKBOX 数据集分析报告', fontsize=16, fontweight='bold')
    
    # 1. 正负样本分布
    ax1 = axes[0, 0]
    target_counts = train_df['target'].value_counts()
    colors = ['#ff6b6b', '#4ecdc4']
    ax1.pie(target_counts.values, labels=['负样本 (0)', '正样本 (1)'], 
            autopct='%1.1f%%', colors=colors, explode=(0, 0.05))
    ax1.set_title('正负样本分布', fontsize=12, fontweight='bold')
    
    # 2. 用户交互次数分布
    ax2 = axes[0, 1]
    user_interactions = train_df.groupby('msno').size()
    ax2.hist(user_interactions.clip(upper=100), bins=50, color='#5f27cd', alpha=0.7, edgecolor='white')
    ax2.set_xlabel('交互次数')
    ax2.set_ylabel('用户数')
    ax2.set_title('用户交互次数分布 (截断至100)', fontsize=12, fontweight='bold')
    ax2.axvline(user_interactions.median(), color='red', linestyle='--', label=f'中位数: {user_interactions.median():.0f}')
    ax2.legend()
    
    # 3. 歌曲热度分布
    ax3 = axes[1, 0]
    song_popularity = train_df.groupby('song_id').size()
    ax3.hist(song_popularity.clip(upper=50), bins=50, color='#ff9f43', alpha=0.7, edgecolor='white')
    ax3.set_xlabel('被听次数')
    ax3.set_ylabel('歌曲数')
    ax3.set_title('歌曲热度分布 (截断至50)', fontsize=12, fontweight='bold')
    ax3.axvline(song_popularity.median(), color='red', linestyle='--', label=f'中位数: {song_popularity.median():.0f}')
    ax3.legend()
    
    # 4. 语言分布
    ax4 = axes[1, 1]
    if 'language' in songs_df.columns:
        lang_counts = songs_df['language'].value_counts().head(10)
        colors_bar = plt.cm.Set3(np.linspace(0, 1, len(lang_counts)))
        bars = ax4.barh(lang_counts.index.astype(str), lang_counts.values, color=colors_bar)
        ax4.set_xlabel('歌曲数量')
        ax4.set_title('歌曲语言分布 (Top 10)', fontsize=12, fontweight='bold')
        ax4.invert_yaxis()
        
        # 添加数值标签
        for bar, count in zip(bars, lang_counts.values):
            ax4.text(bar.get_width() + 1000, bar.get_y() + bar.get_height()/2, 
                    f'{count:,}', va='center', fontsize=9)
    
    plt.tight_layout()
    
    # 保存图表
    output_path = os.path.join(MODE_DIR, "eda_distribution.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"   ✅ 分布图已保存: {output_path}")
    
    return output_path


def analyze_data_quality(train_df, songs_df):
    """数据质量分析"""
    print("\n" + "=" * 60)
    print("🔍 [Step 4/5] 数据质量分析")
    print("=" * 60)
    
    issues = []
    
    # 检查重复
    duplicates = train_df.duplicated().sum()
    print(f"\n📋 重复记录: {duplicates:,} ({duplicates/len(train_df)*100:.2f}%)")
    if duplicates > 0:
        issues.append(f"存在 {duplicates:,} 条重复记录")
    
    # 检查冷门歌曲
    song_counts = train_df['song_id'].value_counts()
    cold_songs = (song_counts == 1).sum()
    print(f"📋 冷门歌曲 (仅出现1次): {cold_songs:,} ({cold_songs/len(song_counts)*100:.1f}%)")
    
    # 检查低活跃用户
    user_counts = train_df['msno'].value_counts()
    inactive_users = (user_counts <= 3).sum()
    print(f"📋 低活跃用户 (≤3次交互): {inactive_users:,} ({inactive_users/len(user_counts)*100:.1f}%)")
    
    # 样本不平衡评估
    pos_ratio = train_df['target'].mean()
    print(f"\n⚖️ 样本平衡性:")
    print(f"   - 正样本比例: {pos_ratio:.2%}")
    if pos_ratio < 0.3 or pos_ratio > 0.7:
        print(f"   - ⚠️ 样本不平衡，建议进行重采样处理")
        issues.append("样本不平衡")
    else:
        print(f"   - ✅ 样本相对平衡")
    
    return issues


def generate_report(stats, issues):
    """生成分析报告"""
    print("\n" + "=" * 60)
    print("📝 [Step 5/5] 生成报告")
    print("=" * 60)
    
    report_path = os.path.join(MODE_DIR, "eda_report.md")
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# KKBOX 数据集分析报告\n\n")
        f.write(f"生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## 1. 数据规模\n\n")
        f.write(f"| 指标 | 数值 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| 总交互记录 | {stats['total_interactions']:,} |\n")
        f.write(f"| 唯一用户数 | {stats['unique_users']:,} |\n")
        f.write(f"| 唯一歌曲数 | {stats['unique_songs']:,} |\n")
        f.write(f"| 歌曲库总量 | {stats['total_songs']:,} |\n\n")
        
        f.write("## 2. 样本分布\n\n")
        f.write(f"- 正样本比例: {stats['positive_ratio']:.1f}%\n")
        f.write(f"- 负样本比例: {stats['negative_ratio']:.1f}%\n\n")
        
        f.write("## 3. 数据质量问题\n\n")
        if issues:
            for issue in issues:
                f.write(f"- ⚠️ {issue}\n")
        else:
            f.write("- ✅ 未发现重大问题\n")
        
        f.write("\n## 4. 可视化\n\n")
        f.write("![分布图](eda_distribution.png)\n")
    
    print(f"   ✅ 报告已保存: {report_path}")
    
    return report_path


def main():
    """主函数"""
    print("\n" + "🎵" * 30)
    print("   MusicMode 数据分析 (EDA)")
    print("🎵" * 30)
    
    # 1. 加载数据
    train_sample, songs_df, members_df, full_train_df = load_data()
    
    # 2. 基础统计
    stats = basic_statistics(train_sample, songs_df, members_df, full_train_df)
    
    # 3. 可视化
    visualize_distributions(train_sample, songs_df, stats)
    
    # 4. 数据质量分析
    issues = analyze_data_quality(train_sample, songs_df)
    
    # 5. 生成报告
    report_path = generate_report(stats, issues)
    
    print("\n" + "=" * 60)
    print("✅ 数据分析完成!")
    print("=" * 60)
    print(f"\n📁 输出文件:")
    print(f"   - 报告: {report_path}")
    print(f"   - 图表: {os.path.join(MODE_DIR, 'eda_distribution.png')}")
    print(f"\n🚀 下一步: 运行 data_cleaning.py 进行数据清洗")


if __name__ == "__main__":
    main()
