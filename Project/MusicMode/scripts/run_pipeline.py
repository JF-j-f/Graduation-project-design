#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_pipeline.py — MusicMode 全流程自动训练与评估脚本

执行顺序（严格串行，任一步骤失败立即终止，不跳过后续步骤）：
  1. train_deepfm_v3.py  — DeepFM 5折OOF + 全量训练
  2. train_bst.py        — BST 5折OOF + 全量训练
  3. build_ensemble.py   — SLSQP权重优化 + LR元学习器训练
  4. evaluate_offline.py — 离线排名指标（HR/NDCG/MRR 等）
  5. evaluate_recs.py    — 在线推荐效果（CTR/完播率/多样性等）

用法：
  # 从头完整运行
  python scripts/run_pipeline.py

  # 断点续跑：从第 N 步开始（1 = DeepFM, 2 = BST, 3 = Ensemble, 4 = 离线评估, 5 = 在线评估）
  python scripts/run_pipeline.py --start-from 2

完成后：
  - 全部成功：汇总所有评估结果生成 MD 综合报告，然后60秒后自动关机
    → Document/training_report_<日期时间>.md
  - 中途失败：生成中断报告，终止流水线，提示用户修复后从对应步骤重启
    → Document/training_report_ABORTED_<日期时间>.md
"""

import os
import sys
import argparse
import subprocess
import datetime
import pickle

# ── 路径配置 ────────────────────────────────────────────────────────────
# 本脚本位于 MusicMode/scripts/，故上一级为 MusicMode
SCRIPTS_DIR   = os.path.dirname(os.path.abspath(__file__))
MUSICMODE_DIR = os.path.dirname(SCRIPTS_DIR)          # .../MusicMode
PROJECT_DIR   = os.path.join(MUSICMODE_DIR, "Project") # .../MusicMode/Project
MODE_DIR      = os.path.join(MUSICMODE_DIR, "Mode")    # .../MusicMode/Mode
DOCUMENT_DIR  = os.path.join(MUSICMODE_DIR, "Document")# .../MusicMode/Document

os.makedirs(DOCUMENT_DIR, exist_ok=True)

# ── 待顺序执行的脚本列表（标签, 脚本路径）────────────────────────────────
PIPELINE = [
    ("DeepFM 5折OOF + 全量训练",      os.path.join(PROJECT_DIR, "train_deepfm_v3.py")),
    ("BST 5折OOF + 全量训练",         os.path.join(PROJECT_DIR, "train_bst.py")),
    ("集成层：SLSQP + LR元学习器",    os.path.join(PROJECT_DIR, "build_ensemble.py")),
    ("离线评估（HR/NDCG/MRR）",       os.path.join(PROJECT_DIR, "evaluate_offline.py")),
    ("在线评估（CTR/完播率/多样性）",  os.path.join(PROJECT_DIR, "evaluate_recs.py")),
]

# ── 各脚本生成的报告文件路径 ────────────────────────────────────────────
ENSEMBLE_REPORT_PATH = os.path.join(MODE_DIR, "ensemble", "ensemble_report.txt")
OFFLINE_REPORT_PATH  = os.path.join(MODE_DIR, "offline_evaluation_report.txt")
ONLINE_REPORT_PATH   = os.path.join(MODE_DIR, "evaluation_report.txt")
ENSEMBLE_CONFIG_PATH = os.path.join(MODE_DIR, "ensemble", "ensemble_config.pkl")


# ============================================================
# 工具函数
# ============================================================

def run_script(label: str, script_path: str):
    """
    使用子进程执行单个 Python 脚本，输出实时流向控制台。

    Args:
        label: 步骤描述（用于日志）
        script_path: 脚本绝对路径

    Returns:
        (success: bool, elapsed_seconds: float)
    """
    sep = "=" * 62
    print(f"\n{sep}")
    print(f"  ▶  {label}")
    print(f"  脚本：{os.path.basename(script_path)}")
    print(f"  开始：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(sep, flush=True)

    if not os.path.exists(script_path):
        print(f"  ❌  脚本不存在：{script_path}", flush=True)
        return False, 0.0

    # 构造子进程环境：强制 UTF-8 + 传递 MUSICMODE_DIR 供子脚本使用
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"]       = "1"
    env["PYTHONUNBUFFERED"] = "1"        # 禁用输出缓冲，确保子脚本 print 实时可见
    env["MUSICMODE_DIR"]    = MUSICMODE_DIR

    start_ts = datetime.datetime.now()
    try:
        # stdout/stderr 不捕获，直接继承当前进程的标准输出（实时可见）
        result = subprocess.run(
            [sys.executable, "-X", "utf8", script_path],
            cwd=PROJECT_DIR,
            env=env,
        )
        elapsed = (datetime.datetime.now() - start_ts).total_seconds()
        success = (result.returncode == 0)
        tag = "✅ 成功" if success else f"❌ 失败（returncode={result.returncode}）"
        print(f"\n  {tag}，耗时 {elapsed / 60:.1f} 分钟", flush=True)
        return success, elapsed
    except Exception as exc:
        elapsed = (datetime.datetime.now() - start_ts).total_seconds()
        print(f"\n  ❌  执行异常：{exc}", flush=True)
        return False, elapsed


def read_text_safe(path: str) -> str:
    """安全读取文本文件，文件不存在或读取失败时返回空字符串"""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return ""


def load_ensemble_config() -> dict:
    """
    从 ensemble_config.pkl 解析关键指标，供报告生成使用。

    Returns:
        包含模型AUC、集成权重、元学习器信息等字段的字典；
        若加载失败则含 'error' 字段。
    """
    info = {}
    try:
        with open(ENSEMBLE_CONFIG_PATH, "rb") as fh:
            cfg = pickle.load(fh)
        info["model_aucs"]    = cfg.get("model_aucs", {})
        info["best_weights"]  = cfg.get("best_weights", {})
        info["best_auc"]      = cfg.get("best_overall_auc", 0.0)
        info["meta_auc"]      = cfg.get("meta_auc", 0.0)
        info["meta_avail"]    = cfg.get("meta_learner_available", False)
        info["version"]       = cfg.get("version", "unknown")
        info["calibrated_at"] = cfg.get("calibrated_at", "N/A")
    except Exception as exc:
        info["error"] = str(exc)
    return info


# ============================================================
# 报告生成
# ============================================================

def build_md_report(
    run_results: list,
    start_time: datetime.datetime,
    aborted: bool = False,
    aborted_label: str = "",
    pending_labels: list = None,
) -> str:
    """
    汇总流水线运行结果 + 各评估报告内容，生成 Markdown 综合报告。

    Args:
        run_results:    [(label, success, elapsed_seconds), ...]
        start_time:     流水线开始时间
        aborted:        是否因失败而中止
        aborted_label:  导致中止的步骤名称
        pending_labels: 尚未执行的步骤列表

    Returns:
        Markdown 格式字符串
    """
    end_time   = datetime.datetime.now()
    total_mins = (end_time - start_time).total_seconds() / 60
    pending_labels = pending_labels or []

    lines = []

    # ── 标题
    report_title = "# 音乐推荐系统全流程训练与评估报告（⚠️ 已中断）" if aborted else "# 音乐推荐系统全流程训练与评估报告"
    lines += [
        report_title,
        "",
        f"**生成时间**：{end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**流水线状态**：{'❌ 中途中断（在步骤「' + aborted_label + '」处失败）' if aborted else '✅ 全部完成'}",
        f"**总耗时**：{total_mins:.1f} 分钟",
        f"**OOF折数**：K = 5",
        f"**集成架构**：DeepFM + BST → Stacking（LR元学习器 / SLSQP降级）",
        "",
    ]

    # ── 中断提示块
    if aborted:
        lines += [
            "> [!CAUTION]",
            f"> 流水线在步骤 **「{aborted_label}」** 处失败并已终止。",
            "> 请修复对应脚本中的错误后，**从该步骤重新启动**。",
            "> 未执行的步骤：" + "、".join(f"**{s}**" for s in pending_labels) if pending_labels else "> 未执行的步骤：无",
            "",
        ]

    # ── 一、流水线执行摘要
    lines += [
        "## 一、流水线执行摘要",
        "",
        "| # | 步骤 | 状态 | 耗时 |",
        "|:--:|:-----|:----:|-----:|",
    ]
    executed_count = len(run_results)
    for idx, (label, success, elapsed) in enumerate(run_results, 1):
        status_str  = "✅ 成功" if success else "❌ 失败"
        elapsed_str = f"{elapsed / 60:.1f} min"
        lines.append(f"| {idx} | {label} | {status_str} | {elapsed_str} |")
    # 未执行的步骤
    for idx, label in enumerate(pending_labels, executed_count + 1):
        lines.append(f"| {idx} | {label} | ⏭️ 未执行 | — |")
    lines.append("")

    # ── 二、模型AUC对比（解析 ensemble_config.pkl）
    lines += ["## 二、模型AUC对比", ""]
    cfg = load_ensemble_config()

    if "error" in cfg:
        lines.append(f"> ⚠️ 无法读取 ensemble_config.pkl：{cfg['error']}")
    else:
        model_aucs   = cfg["model_aucs"]
        best_weights = cfg["best_weights"]
        best_auc     = cfg["best_auc"]
        meta_auc     = cfg["meta_auc"]
        meta_avail   = cfg["meta_avail"]

        lines += [
            "| 模型 | 验证集AUC | SLSQP权重 |",
            "|:-----|----------:|----------:|",
        ]
        for name, auc in model_aucs.items():
            w = best_weights.get(name, 0.0)
            lines.append(f"| {name} | {auc:.4f} | {w:.4f} |")

        lines += [
            "",
            f"**SLSQP集成AUC**：{best_auc:.4f}",
        ]

        if meta_avail and meta_auc > 0:
            gain = meta_auc - best_auc
            lines += [
                f"**元学习器AUC（LR Stacking）**：{meta_auc:.4f}",
                f"**Stacking增益**：{gain:+.4f}",
            ]
        else:
            lines.append("**元学习器**：不可用，已降级为SLSQP加权平均")

        best_final = max(best_auc, meta_auc if meta_avail else 0.0)
        if best_final >= 0.80:
            lines.append("")
            lines.append("🎯 **已达到 AUC ≥ 0.80 目标！**")
        else:
            lines.append(f"**距 AUC=0.80 目标差距**：{0.80 - best_final:+.4f}")

        lines += [
            "",
            f"*配置版本：{cfg['version']}，生成于 {cfg['calibrated_at']}*",
            "",
        ]

    # ── 三、集成原始报告
    ensemble_text = read_text_safe(ENSEMBLE_REPORT_PATH)
    if ensemble_text:
        lines += [
            "## 三、集成对比报告（原始输出）",
            "",
            "```text",
            ensemble_text.strip(),
            "```",
            "",
        ]
    else:
        lines += ["## 三、集成对比报告（原始输出）", "", "> ⚠️ 报告文件不存在或为空", ""]

    # ── 四、离线排名指标
    offline_text = read_text_safe(OFFLINE_REPORT_PATH)
    if offline_text:
        lines += [
            "## 四、离线排名指标（KKBox验证集）",
            "",
            "```text",
            offline_text.strip(),
            "```",
            "",
        ]
    else:
        lines += ["## 四、离线排名指标（KKBox验证集）", "", "> ⚠️ 报告文件不存在或为空", ""]

    # ── 五、在线推荐效果
    online_text = read_text_safe(ONLINE_REPORT_PATH)
    if online_text:
        lines += [
            "## 五、在线推荐效果（recommendation_feedback表）",
            "",
            "```text",
            online_text.strip(),
            "```",
            "",
        ]
    else:
        lines += [
            "## 五、在线推荐效果（recommendation_feedback表）",
            "",
            "> ⚠️ 报告文件不存在或为空",
            "",
        ]

    # ── 六、结论
    lines += ["## 六、结论与建议", ""]
    if "error" not in cfg:
        best_final = max(cfg["best_auc"], cfg["meta_auc"] if cfg["meta_avail"] else 0.0)
        if best_final >= 0.80:
            lines.append(
                "本次5折Stacking训练后，集成AUC已达到 **0.80** 阈值，"
                "系统推荐质量满足预设目标。"
            )
        else:
            lines.append(
                f"本次训练最佳集成AUC为 **{best_final:.4f}**，距0.80目标仍有差距，"
                "建议进一步增加特征维度或调整模型超参数。"
            )
    else:
        lines.append("> ⚠️ ensemble_config.pkl 读取失败，无法给出AUC结论。")

    # ── 七、各步骤详细路径（便于排查）
    lines += [
        "",
        "## 七、关键文件路径",
        "",
        f"| 说明 | 路径 |",
        f"|:-----|:-----|",
        f"| 集成配置 | `{ENSEMBLE_CONFIG_PATH}` |",
        f"| 集成报告 | `{ENSEMBLE_REPORT_PATH}` |",
        f"| 离线评估报告 | `{OFFLINE_REPORT_PATH}` |",
        f"| 在线评估报告 | `{ONLINE_REPORT_PATH}` |",
        f"| 综合MD报告目录 | `{DOCUMENT_DIR}` |",
        "",
    ]

    lines += [
        "---",
        f"*本报告由 `run_pipeline.py` 自动生成，生成时间：{end_time.strftime('%Y-%m-%d %H:%M:%S')}*",
    ]

    return "\n".join(lines)


# ============================================================
# 主入口
# ============================================================

def main():
    # ── 解析命令行参数
    parser = argparse.ArgumentParser(
        description="MusicMode 全流程训练与评估流水线",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--start-from",
        type=int,
        default=1,
        metavar="N",
        help=(
            "从第 N 步开始执行（跳过前面已完成的步骤），默认从第 1 步开始。\n"
            "  1 = DeepFM 5折OOF + 全量训练\n"
            "  2 = BST 5折OOF + 全量训练\n"
            "  3 = 集成层：SLSQP + LR元学习器\n"
            "  4 = 离线评估（HR/NDCG/MRR）\n"
            "  5 = 在线评估（CTR/完播率/多样性）"
        ),
    )
    args = parser.parse_args()

    start_step = args.start_from  # 用户指定的起始步骤编号（1-based）
    if not (1 <= start_step <= len(PIPELINE)):
        print(f"  ❌  --start-from 必须在 1~{len(PIPELINE)} 之间，当前值：{start_step}")
        sys.exit(1)

    # ── 诊断路径，启动时提前核验，避免运行几小时后才发现路径错误
    print("=" * 62)
    print("  MusicMode 全流程自动训练与评估")
    print(f"  Python    : {sys.executable}")
    print(f"  MUSICMODE : {MUSICMODE_DIR}")
    print(f"  PROJECT   : {PROJECT_DIR}")
    print(f"  MODE      : {MODE_DIR}")
    print(f"  DOCUMENT  : {DOCUMENT_DIR}")
    if start_step > 1:
        skipped = [f"{i+1}. {lbl}" for i, (lbl, _) in enumerate(PIPELINE) if i < start_step - 1]
        print(f"  断点续跑：从第 {start_step} 步开始，跳过以下已完成步骤：")
        for s in skipped:
            print(f"    ✅ {s}（已跳过）")
    print("=" * 62)

    # 校验脚本是否存在
    missing = [(lbl, p) for lbl, p in PIPELINE if not os.path.exists(p)]
    if missing:
        print("\n  ❌  以下脚本文件不存在，请检查路径后重试：")
        for lbl, p in missing:
            print(f"      [{lbl}] {p}")
        print()

    start_time = datetime.datetime.now()
    print(f"  开始时间：{start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    active_count = len(PIPELINE) - (start_step - 1)
    print(f"  共 {len(PIPELINE)} 个步骤，本次执行第 {start_step}~{len(PIPELINE)} 步（共 {active_count} 步）", flush=True)

    run_results    = []
    aborted        = False
    aborted_label  = ""
    aborted_idx    = -1

    # ── 严格串行执行：任意步骤失败立即终止；start_step 之前的步骤直接跳过
    for step_idx, (label, script_path) in enumerate(PIPELINE):
        # 跳过已完成步骤（step_idx 是 0-based，start_step 是 1-based）
        if step_idx < start_step - 1:
            continue
        success, elapsed = run_script(label, script_path)
        run_results.append((label, success, elapsed))

        if not success:
            aborted       = True
            aborted_label = label
            aborted_idx   = step_idx

            # ── 计算尚未执行的步骤
            pending = [lbl for lbl, _ in PIPELINE[step_idx + 1:]]

            sep = "=" * 62
            print(f"\n{sep}")
            print("  ❌  流水线已终止！")
            print(f"  失败步骤：【{label}】（第 {step_idx + 1} 步，共 {len(PIPELINE)} 步）")
            if pending:
                print("  未执行步骤：")
                for i, p in enumerate(pending, step_idx + 2):
                    print(f"    {i}. {p}")
            print(sep)
            print()
            resume_cmd = f"python scripts\\run_pipeline.py --start-from {step_idx + 1}"
            print("  ╔══════════════════════════════════════════════════════════╗")
            print("  ║             请按以下步骤手动修复并重启                 ║")
            print("  ╠══════════════════════════════════════════════════════════╣")
            print(f"  ║  1. 查看上方报错信息，定位并修复脚本中的问题           ║")
            print(f"  ║  2. 修复完成后，单独运行失败的脚本进行验证：           ║")
            print(f"  ║     python Project\\{os.path.basename(script_path):<44}║")
            print(f"  ║  3. 确认单步正常后，从该步骤断点续跑：                 ║")
            print(f"  ║     {resume_cmd:<56}║")
            print("  ╚══════════════════════════════════════════════════════════╝")
            print(flush=True)

            # ── 生成中断报告
            print("  正在生成中断报告...")
            report_stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            report_path  = os.path.join(DOCUMENT_DIR, f"training_report_ABORTED_{report_stamp}.md")
            md_content   = build_md_report(
                run_results, start_time,
                aborted=True,
                aborted_label=aborted_label,
                pending_labels=pending,
            )
            with open(report_path, "w", encoding="utf-8") as fh:
                fh.write(md_content)
            print(f"  中断报告已保存：{report_path}", flush=True)

            # 失败时不关机，直接退出
            sys.exit(1)

    # ── 全部成功：生成综合 MD 报告
    sep = "=" * 62
    print(f"\n{sep}")
    print("  正在生成综合 MD 报告...")
    report_stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    report_path  = os.path.join(DOCUMENT_DIR, f"training_report_{report_stamp}.md")

    md_content = build_md_report(run_results, start_time)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(md_content)

    print(f"  综合报告已保存：{report_path}")
    print(sep, flush=True)

    # ── 打印最终摘要
    total_mins = (datetime.datetime.now() - start_time).total_seconds() / 60
    print(f"\n  流水线全部完成，总耗时 {total_mins:.1f} 分钟")
    print(f"  报告路径：{report_path}", flush=True)

    # ── 仅全部成功时才执行延迟关机
    print("\n  60秒后自动关机...")
    print("  如需取消，请在命令行执行：shutdown /a", flush=True)
    os.system("shutdown /s /t 60 /c \"MusicMode pipeline finished. Auto shutdown in 60s.\"")


if __name__ == "__main__":
    main()
