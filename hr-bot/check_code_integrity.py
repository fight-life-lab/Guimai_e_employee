#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代码完整性检查脚本

用于检查本地代码是否完整，并与远程服务器进行对比

使用方法:
    cd /Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot
    python3 check_code_integrity.py
"""

import os
import sys
import hashlib
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Set

# 关键文件列表 - 服务启动必需的
CRITICAL_FILES = [
    # 主入口
    "app/main.py",
    
    # 配置文件
    "app/config.py",
    "app/__init__.py",
    
    # API路由
    "app/api/__init__.py",
    "app/api/alignment_routes.py",
    "app/api/detailed_alignment_routes.py",
    "app/api/jd_match_routes.py",
    "app/api/feishu_webhook.py",
    
    # Agent模块
    "app/agent/__init__.py",
    "app/agent/alignment_agent.py",
    "app/agent/hr_agent.py",
    "app/agent/state.py",
    "app/agent/prompts.py",
    "app/agent/query_planner.py",
    
    # 数据库
    "app/database/__init__.py",
    "app/database/models.py",
    "app/database/crud.py",
    
    # 服务层
    "app/services/jd_matcher.py",
    "app/services/file_parser.py",
    "app/services/llm_client.py",
    "app/services/ai_scorer.py",
    "app/services/ai_scorer_v2.py",
    "app/services/alignment_advisor.py",
    "app/services/jd_analyzer.py",
    
    # 知识库
    "app/knowledge/__init__.py",
    "app/knowledge/builder.py",
    "app/knowledge/simple_kb.py",
    "app/knowledge/qa_knowledge.py",
    
    # 工具
    "app/tools/__init__.py",
    "app/tools/hr_tools.py",
    
    # 数据处理
    "app/data_processing/__init__.py",
    "app/data_processing/data_models.py",
    "app/data_processing/data_ingestion.py",
    "app/data_processing/excel_reader.py",
    "app/data_processing/conversation_processor.py",
]

# 需要检查的导入依赖
REQUIRED_IMPORTS = {
    "app/main.py": [
        "fastapi",
        "app.api",
        "app.config",
        "app.database.models",
    ],
    "app/api/alignment_routes.py": [
        "fastapi",
        "app.agent.alignment_agent",
        "app.database.models",
    ],
    "app/api/detailed_alignment_routes.py": [
        "fastapi",
        "app.database.models",
        "app.services.ai_scorer_v2",
    ],
    "app/api/jd_match_routes.py": [
        "fastapi",
        "app.services.jd_matcher",
    ],
}


class CodeIntegrityChecker:
    """代码完整性检查器"""
    
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.ok_items: List[str] = []
        
    def check_file_exists(self, file_path: str) -> bool:
        """检查文件是否存在"""
        full_path = self.base_path / file_path
        return full_path.exists() and full_path.is_file()
    
    def check_file_size(self, file_path: str) -> int:
        """检查文件大小"""
        full_path = self.base_path / file_path
        if full_path.exists():
            return full_path.stat().st_size
        return 0
    
    def check_file_content(self, file_path: str) -> Tuple[bool, str]:
        """检查文件内容是否完整"""
        full_path = self.base_path / file_path
        if not full_path.exists():
            return False, "文件不存在"
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 检查文件是否为空
            if not content.strip():
                return False, "文件为空"
            
            # 检查Python文件是否有语法错误
            if file_path.endswith('.py'):
                import ast
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    return False, f"语法错误: {e}"
                
                # 检查关键函数/类是否存在
                if 'def ' not in content and 'class ' not in content:
                    return False, "没有函数或类定义"
            
            return True, "OK"
            
        except Exception as e:
            return False, f"读取错误: {e}"
    
    def check_imports(self, file_path: str) -> List[str]:
        """检查文件的导入是否可用"""
        issues = []
        full_path = self.base_path / file_path
        
        if not full_path.exists():
            return ["文件不存在"]
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取所有导入语句
            import re
            imports = re.findall(r'^(?:from|import)\s+([\w.]+)', content, re.MULTILINE)
            
            # 检查项目内部导入
            for imp in imports:
                if imp.startswith('app.'):
                    # 转换导入路径为文件路径
                    parts = imp.split('.')
                    if len(parts) > 1:
                        # from app.xxx.yyy -> app/xxx/yyy.py
                        check_path = '/'.join(parts) + '.py'
                        if not self.check_file_exists(check_path):
                            # 也可能是目录导入
                            check_path = '/'.join(parts) + '/__init__.py'
                            if not self.check_file_exists(check_path):
                                issues.append(f"导入缺失: {imp}")
            
        except Exception as e:
            issues.append(f"检查导入时出错: {e}")
        
        return issues
    
    def run_syntax_check(self) -> bool:
        """运行Python语法检查"""
        print("\n  正在检查Python语法...")
        
        py_files = list(self.base_path.rglob("*.py"))
        errors = []
        
        for py_file in py_files:
            # 跳过缓存文件
            if '__pycache__' in str(py_file):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                import ast
                ast.parse(content)
                
            except SyntaxError as e:
                rel_path = py_file.relative_to(self.base_path)
                errors.append(f"    {rel_path}: 第{e.lineno}行 - {e.msg}")
        
        if errors:
            print("  ❌ 发现语法错误:")
            for error in errors[:10]:  # 只显示前10个
                print(error)
            if len(errors) > 10:
                print(f"    ... 还有 {len(errors) - 10} 个错误")
            return False
        else:
            print(f"  ✅ 所有 {len(py_files)} 个Python文件语法正确")
            return True
    
    def check_critical_files(self):
        """检查关键文件"""
        print("\n" + "="*60)
        print("  1. 检查关键文件")
        print("="*60)
        
        missing_files = []
        empty_files = []
        
        for file_path in CRITICAL_FILES:
            exists = self.check_file_exists(file_path)
            size = self.check_file_size(file_path)
            
            if not exists:
                missing_files.append(file_path)
                self.issues.append(f"关键文件缺失: {file_path}")
            elif size == 0:
                empty_files.append(file_path)
                self.issues.append(f"关键文件为空: {file_path}")
            else:
                # 检查内容完整性
                ok, msg = self.check_file_content(file_path)
                if ok:
                    self.ok_items.append(f"{file_path} ({size} bytes)")
                else:
                    self.issues.append(f"{file_path}: {msg}")
        
        if missing_files:
            print(f"\n  ❌ 缺失 {len(missing_files)} 个关键文件:")
            for f in missing_files:
                print(f"    - {f}")
        
        if empty_files:
            print(f"\n  ❌ {len(empty_files)} 个关键文件为空:")
            for f in empty_files:
                print(f"    - {f}")
        
        if not missing_files and not empty_files:
            print(f"\n  ✅ 所有 {len(CRITICAL_FILES)} 个关键文件存在且非空")
    
    def check_import_dependencies(self):
        """检查导入依赖"""
        print("\n" + "="*60)
        print("  2. 检查导入依赖")
        print("="*60)
        
        all_issues = []
        
        for file_path, required_imports in REQUIRED_IMPORTS.items():
            if not self.check_file_exists(file_path):
                continue
            
            issues = self.check_imports(file_path)
            if issues:
                all_issues.extend([f"{file_path}: {issue}" for issue in issues])
        
        if all_issues:
            print(f"\n  ❌ 发现 {len(all_issues)} 个导入问题:")
            for issue in all_issues[:10]:
                print(f"    - {issue}")
            if len(all_issues) > 10:
                print(f"    ... 还有 {len(all_issues) - 10} 个")
        else:
            print("\n  ✅ 所有导入依赖正常")
    
    def check_service_startup(self) -> bool:
        """尝试检查服务是否可以启动"""
        print("\n" + "="*60)
        print("  3. 检查服务启动能力")
        print("="*60)
        
        # 检查main.py是否可以导入
        print("\n  检查主模块导入...")
        
        try:
            # 切换到项目目录
            original_dir = os.getcwd()
            os.chdir(self.base_path)
            
            # 尝试导入main模块
            sys.path.insert(0, str(self.base_path))
            
            # 先检查关键依赖
            try:
                import fastapi
                print("  ✅ FastAPI 已安装")
            except ImportError:
                print("  ❌ FastAPI 未安装")
                return False
            
            try:
                import sqlalchemy
                print("  ✅ SQLAlchemy 已安装")
            except ImportError:
                print("  ❌ SQLAlchemy 未安装")
                return False
            
            try:
                from app import main
                print("  ✅ 主模块可以导入")
            except Exception as e:
                print(f"  ❌ 主模块导入失败: {e}")
                return False
            
            # 检查FastAPI应用实例
            try:
                app = main.app
                print(f"  ✅ FastAPI应用实例存在")
                print(f"     路由数量: {len(app.routes)}")
            except Exception as e:
                print(f"  ⚠️  获取应用实例时警告: {e}")
            
            os.chdir(original_dir)
            return True
            
        except Exception as e:
            print(f"  ❌ 检查失败: {e}")
            return False
    
    def compare_with_remote(self, remote_host: str = "121.229.172.161"):
        """与远程服务器对比关键文件"""
        print("\n" + "="*60)
        print(f"  4. 与远程服务器对比 ({remote_host})")
        print("="*60)
        
        print("\n  使用 scp 从远程服务器获取文件列表...")
        
        try:
            # 获取远程文件列表
            result = subprocess.run(
                ["ssh", f"root@{remote_host}", "find /root/shijingjing/e-employee/hr-bot/app -name '*.py' | head -20"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                print(f"  ⚠️  无法连接远程服务器: {result.stderr}")
                return
            
            remote_files = set(result.stdout.strip().split('\n'))
            
            # 获取本地文件列表
            local_files = set()
            for f in CRITICAL_FILES:
                if self.check_file_exists(f):
                    local_files.add(f"/root/shijingjing/e-employee/hr-bot/{f}")
            
            # 对比
            remote_relative = set(f.replace('/root/shijingjing/e-employee/hr-bot/', '') for f in remote_files if f)
            local_relative = set(CRITICAL_FILES)
            
            only_remote = remote_relative - local_relative
            only_local = local_relative - remote_relative
            
            if only_remote:
                print(f"\n  ⚠️  远程有但本地没有的文件 ({len(only_remote)}个):")
                for f in list(only_remote)[:10]:
                    print(f"    - {f}")
            
            if only_local:
                print(f"\n  ⚠️  本地有但远程没有的文件 ({len(only_local)}个):")
                for f in list(only_local)[:10]:
                    print(f"    - {f}")
            
            if not only_remote and not only_local:
                print("\n  ✅ 关键文件列表一致")
            
        except subprocess.TimeoutExpired:
            print("  ⚠️  连接远程服务器超时")
        except Exception as e:
            print(f"  ⚠️  对比失败: {e}")
    
    def generate_report(self):
        """生成检查报告"""
        print("\n" + "="*60)
        print("  检查报告总结")
        print("="*60)
        
        total_issues = len(self.issues)
        total_warnings = len(self.warnings)
        total_ok = len(self.ok_items)
        
        print(f"\n  关键文件总数: {len(CRITICAL_FILES)}")
        print(f"  ✅ 正常: {total_ok}")
        print(f"  ⚠️  警告: {total_warnings}")
        print(f"  ❌ 问题: {total_issues}")
        
        if self.issues:
            print("\n  问题列表:")
            for i, issue in enumerate(self.issues[:10], 1):
                print(f"    {i}. {issue}")
            if len(self.issues) > 10:
                print(f"    ... 还有 {len(self.issues) - 10} 个问题")
        
        print("\n" + "="*60)
        
        if total_issues == 0:
            print("  ✅ 代码完整性检查通过！")
            print("  服务应该可以正常启动")
        else:
            print(f"  ❌ 发现 {total_issues} 个问题需要修复")
            print("  建议在启动服务前修复上述问题")
        
        print("="*60)
        
        return total_issues == 0
    
    def run_all_checks(self):
        """运行所有检查"""
        print("\n" + "="*60)
        print("  HR-Bot 代码完整性检查")
        print("="*60)
        
        self.check_critical_files()
        self.check_import_dependencies()
        syntax_ok = self.run_syntax_check()
        startup_ok = self.check_service_startup()
        self.compare_with_remote()
        
        all_ok = self.generate_report()
        
        return all_ok and syntax_ok and startup_ok


def main():
    """主函数"""
    # 确定检查路径
    if len(sys.argv) > 1:
        check_path = sys.argv[1]
    else:
        # 默认检查当前目录下的 hr-bot
        check_path = "."
    
    checker = CodeIntegrityChecker(check_path)
    success = checker.run_all_checks()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
