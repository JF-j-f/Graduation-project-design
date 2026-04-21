#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_auc_chart.py
生成"不同模型AUC得分"柱状图，保存至 Project/MusicMode/image/ 目录。

开发者：JunFu
"""

import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ── 中文字体配置 ──────────────────────────────────────────────
plt.rcParams['font.family'] = 'Microsoft YaHei'
plt.rcParams['axes.unicode_minus'] = False

# ── 数据 ──────────────────────────────────────────────────────
labels = ['LightGBM\n（粗排）', 'DeepFM\n（精排）', 'BST\n（精排）', 'Stacking\n（集成）']
aucs   = [0.7648, 0.7434, 0.7761, 0.7767]

# ── 颜色（与原图保持一致：浅蓝→中蓝→深蓝→深蓝斜线） ──────────
colors  = ['#89CFF0', '#4A90D9', '#1A3A6B', '#1A3A6B']
hatches = ['', '', '', '///']

# ── 绘图 ──────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 5.5))
fig.patch.set_facecolor('white')
ax.set_facecolor('white')

x = np.arange(len(labels))
bar_width = 0.52

for i, (auc, color, hatch) in enumerate(zip(aucs, colors, hatches)):
    bar = ax.bar(x[i], auc, width=bar_width,
                 color=color, hatch=hatch,
                 edgecolor='white' if hatch == '' else color,
                 linewidth=0.8, zorder=3)
    ax.text(x[i], auc + 0.0008, f'{auc:.4f}',
            ha='center', va='bottom',
            fontweight='bold', fontsize=10.5,
            color='#222222')

# ── 坐标轴 ────────────────────────────────────────────────────
ymin, ymax = 0.69, 0.785
ax.set_ylim(ymin, ymax)
ax.set_yticks(np.arange(0.69, ymax, 0.01))
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f'{v:.2f}'))
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=10.5)
ax.set_ylabel('验证集 AUC', fontsize=11, labelpad=8)

# ── 网格与边框 ────────────────────────────────────────────────
ax.yaxis.grid(True, linestyle='--', alpha=0.55, color='#AAAAAA', zorder=0)
ax.set_axisbelow(True)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#CCCCCC')
ax.spines['bottom'].set_color('#CCCCCC')
ax.tick_params(axis='both', colors='#444444')

plt.tight_layout(pad=1.2)

# ── 保存到仓库根 image/ 目录 ──────────────────────────────────
save_dir = Path(__file__).resolve().parents[4] / "image"
save_dir.mkdir(parents=True, exist_ok=True)
save_path = save_dir / "不同模型AUC得分.png"

plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f'Done. Saved to: {save_path}')
