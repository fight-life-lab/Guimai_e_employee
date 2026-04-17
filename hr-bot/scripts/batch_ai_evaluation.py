#!/usr/bin/env python3
"""
离线批量AI评估脚本
- 批量为所有候选人调用AI评估
- 获取6维度分数并存储到缓存目录
"""

import os
import sys
import json
import asyncio
import aiohttp
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings

# API配置
BASE_URL = "http://localhost:3111"
PROJECT_NAME = "20260401战略招聘"

# 评估缓存目录
EVALUATIONS_DIR = Path("/root/shijingjing/e-employee/hr-bot/data/interview") / PROJECT_NAME / "evaluations"


async def get_candidates(session: aiohttp.ClientSession) -> List[Dict]:
    """获取所有候选人列表"""
    url = f"{BASE_URL}/api/v1/interview-batch/candidates/{PROJECT_NAME}"
    
    try:
        async with session.get(url, timeout=30) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("candidates", [])
            else:
                print(f"❌ 获取候选人列表失败: HTTP {response.status}")
                return []
    except Exception as e:
        print(f"❌ 获取候选人列表异常: {e}")
        return []


async def check_evaluation_cache(session: aiohttp.ClientSession, candidate_name: str) -> Optional[Dict]:
    """检查候选人是否已有评估缓存"""
    url = f"{BASE_URL}/api/v1/interview-evaluation/evaluation-cache"
    params = {
        "candidate_name": candidate_name,
        "project": PROJECT_NAME
    }
    
    try:
        async with session.get(url, params=params, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("cached"):
                    return data.get("evaluation")
            return None
    except Exception as e:
        print(f"⚠️ 检查缓存异常 {candidate_name}: {e}")
        return None


async def evaluate_candidate(session: aiohttp.ClientSession, candidate_name: str) -> Optional[Dict]:
    """调用AI评估API评估单个候选人"""
    url = f"{BASE_URL}/api/v1/interview-evaluation/evaluate"
    
    # 准备请求数据
    form_data = aiohttp.FormData()
    form_data.add_field("candidate_name", candidate_name)
    form_data.add_field("project", PROJECT_NAME)
    
    try:
        print(f"🤖 正在评估: {candidate_name}...")
        
        async with session.post(url, data=form_data, timeout=300) as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ {candidate_name} 评估完成 - 综合评分: {data.get('overall_score', 'N/A')}")
                return data
            else:
                error_text = await response.text()
                print(f"❌ {candidate_name} 评估失败: HTTP {response.status} - {error_text[:200]}")
                return None
                
    except asyncio.TimeoutError:
        print(f"❌ {candidate_name} 评估超时")
        return None
    except Exception as e:
        print(f"❌ {candidate_name} 评估异常: {e}")
        return None


def save_evaluation_cache(candidate_name: str, evaluation: Dict):
    """保存评估结果到本地缓存文件"""
    try:
        # 确保目录存在
        EVALUATIONS_DIR.mkdir(parents=True, exist_ok=True)
        
        # 构建缓存文件路径
        cache_file = EVALUATIONS_DIR / f"{candidate_name}_evaluation.json"
        
        # 准备缓存数据
        cache_data = {
            "candidate_name": candidate_name,
            "project": PROJECT_NAME,
            "evaluation": evaluation,
            "cached_at": datetime.now().isoformat()
        }
        
        # 写入文件
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 已保存缓存: {cache_file}")
        return True
        
    except Exception as e:
        print(f"❌ 保存缓存失败 {candidate_name}: {e}")
        return False


def print_evaluation_summary(evaluation: Dict):
    """打印评估结果摘要"""
    if not evaluation:
        return
    
    overall_score = evaluation.get('overall_score', 'N/A')
    evaluation_level = evaluation.get('evaluation_level', 'N/A')
    dimensions = evaluation.get('dimensions', [])
    
    print(f"   综合评分: {overall_score} ({evaluation_level})")
    
    if dimensions:
        print(f"   6维度评分:")
        for dim in dimensions:
            name = dim.get('name', '未知')
            score = dim.get('score', 'N/A')
            print(f"     • {name}: {score}分")


async def batch_evaluate(skip_existing: bool = True, max_candidates: Optional[int] = None):
    """批量评估所有候选人
    
    Args:
        skip_existing: 是否跳过已有缓存的候选人
        max_candidates: 最大评估数量（用于测试）
    """
    print("=" * 70)
    print("🚀 离线批量AI评估")
    print("=" * 70)
    print(f"项目: {PROJECT_NAME}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"跳过已有缓存: {skip_existing}")
    print("-" * 70)
    
    async with aiohttp.ClientSession() as session:
        # 1. 获取所有候选人
        print("\n📋 获取候选人列表...")
        candidates = await get_candidates(session)
        
        if not candidates:
            print("❌ 未找到候选人")
            return
        
        print(f"✅ 找到 {len(candidates)} 个候选人")
        
        # 2. 筛选需要评估的候选人
        candidates_to_evaluate = []
        skipped_count = 0
        
        for candidate in candidates:
            name = candidate.get('name', '')
            has_transcription = candidate.get('has_transcription', False)
            
            # 检查是否有转录数据
            if not has_transcription:
                print(f"⏭️ 跳过 {name}: 无转录数据")
                skipped_count += 1
                continue
            
            # 检查是否已有缓存
            if skip_existing:
                existing_cache = await check_evaluation_cache(session, name)
                if existing_cache:
                    print(f"⏭️ 跳过 {name}: 已有评估缓存")
                    skipped_count += 1
                    continue
            
            candidates_to_evaluate.append(candidate)
        
        # 限制评估数量
        if max_candidates and len(candidates_to_evaluate) > max_candidates:
            candidates_to_evaluate = candidates_to_evaluate[:max_candidates]
            print(f"\n⚠️ 限制评估数量为前 {max_candidates} 个候选人")
        
        print(f"\n📊 统计:")
        print(f"   候选人总数: {len(candidates)}")
        print(f"   需要评估: {len(candidates_to_evaluate)}")
        print(f"   跳过: {skipped_count}")
        
        if not candidates_to_evaluate:
            print("\n✅ 所有候选人都已完成评估")
            return
        
        # 3. 批量评估
        print(f"\n🤖 开始批量评估 ({len(candidates_to_evaluate)} 个候选人)...")
        print("-" * 70)
        
        success_count = 0
        failed_count = 0
        
        for i, candidate in enumerate(candidates_to_evaluate, 1):
            name = candidate.get('name', '')
            
            print(f"\n[{i}/{len(candidates_to_evaluate)}] {name}")
            
            # 调用AI评估
            evaluation = await evaluate_candidate(session, name)
            
            if evaluation:
                # 打印评估摘要
                print_evaluation_summary(evaluation)
                
                # 保存到本地缓存
                save_evaluation_cache(name, evaluation)
                success_count += 1
            else:
                failed_count += 1
            
            # 添加短暂延迟，避免API过载
            if i < len(candidates_to_evaluate):
                await asyncio.sleep(1)
        
        # 4. 输出总结
        print("\n" + "=" * 70)
        print("📈 评估完成总结")
        print("=" * 70)
        print(f"✅ 成功: {success_count}")
        print(f"❌ 失败: {failed_count}")
        print(f"⏭️ 跳过: {skipped_count}")
        print(f"📁 缓存目录: {EVALUATIONS_DIR}")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='离线批量AI评估脚本')
    parser.add_argument('--skip-existing', action='store_true', default=True,
                        help='跳过已有缓存的候选人（默认开启）')
    parser.add_argument('--no-skip-existing', action='store_true',
                        help='不跳过已有缓存的候选人，重新评估')
    parser.add_argument('--max', type=int, default=None,
                        help='最大评估数量（用于测试）')
    
    args = parser.parse_args()
    
    # 处理参数
    skip_existing = not args.no_skip_existing
    
    # 运行批量评估
    asyncio.run(batch_evaluate(
        skip_existing=skip_existing,
        max_candidates=args.max
    ))


if __name__ == "__main__":
    main()
