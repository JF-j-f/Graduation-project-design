# -*- coding: utf-8 -*-
"""
一键运行完整推荐流程
功能：
1. 特征工程
2. ALS 召回模型训练
3. DeepFM 精排模型训练
4. 推荐结果回写

作者：MusicMode 推荐系统
使用方式: python run_pipeline.py
"""

import os
import sys
import time
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_step(step_name, script_name):
    """运行单个步骤"""
    print("\n" + "🔷" * 30)
    print(f"   {step_name}")
    print("🔷" * 30)
    
    script_path = os.path.join(PROJECT_DIR, script_name)
    
    if not os.path.exists(script_path):
        print(f"   ❌ 脚本不存在: {script_path}")
        return False
    
    start_time = time.time()
    
    # 使用 exec 运行脚本
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # 创建新的命名空间
        namespace = {
            '__name__': '__main__',
            '__file__': script_path,
        }
        
        exec(compile(code, script_path, 'exec'), namespace)
        
        elapsed = time.time() - start_time
        print(f"\n   ⏱️ 耗时: {elapsed:.1f} 秒")
        return True
        
    except Exception as e:
        print(f"\n   ❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    start_time = datetime.now()
    
    print("\n" + "🎵" * 40)
    print("   MusicMode 推荐系统完整流程")
    print(f"   开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎵" * 40)
    
    # 定义流程
    steps = [
        ("Step 1: 特征工程", "prepare_features.py"),
        ("Step 2: ALS 召回模型", "train_als.py"),
        ("Step 3: DeepFM 精排模型", "train_deepfm.py"),
        ("Step 4: 推荐结果回写", "sync_recs.py"),
    ]
    
    # 执行流程
    results = []
    for step_name, script_name in steps:
        success = run_step(step_name, script_name)
        results.append((step_name, success))
        
        if not success:
            print(f"\n   ⚠️ {step_name} 失败，继续执行下一步...")
    
    # 汇总
    end_time = datetime.now()
    total_time = (end_time - start_time).total_seconds()
    
    print("\n" + "=" * 60)
    print("📊 执行汇总")
    print("=" * 60)
    
    for step_name, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"   {step_name}: {status}")
    
    print(f"\n⏱️ 总耗时: {total_time:.1f} 秒 ({total_time/60:.1f} 分钟)")
    print(f"🏁 结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查是否全部成功
    all_success = all(success for _, success in results)
    
    if all_success:
        print("\n" + "🎉" * 20)
        print("   所有步骤执行成功！")
        print("   推荐系统已就绪，请访问 MusicWeb 查看效果")
        print("🎉" * 20)
    else:
        print("\n" + "⚠️" * 20)
        print("   部分步骤执行失败，请检查错误日志")
        print("⚠️" * 20)


if __name__ == "__main__":
    main()
