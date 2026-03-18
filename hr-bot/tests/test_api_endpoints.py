#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HR-Bot API 接口测试脚本

测试范围：
1. 人岗适配分析接口 (/api/v1/alignment/*)
2. 详细人岗适配分析接口 (/api/v1/alignment/detailed-analysis)
3. JD匹配接口 (/api/v1/jd-match/*)
4. 健康检查接口 (/health)

使用方法：
    cd /Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot
    python tests/test_api_endpoints.py

环境要求：
    - 服务必须已启动 (uvicorn app.main:app --host 0.0.0.0 --port 3111)
    - 需要安装 requests: pip install requests
"""

import requests
import json
import sys
import time
from typing import Dict, Any, Optional
from datetime import datetime

# 测试配置
BASE_URL = "http://localhost:3111"  # 服务基础URL
TIMEOUT = 30  # 请求超时时间（秒）

# 测试数据
TEST_EMPLOYEE_NAME = "石京京"  # 测试员工姓名
TEST_JD_CONTENT = """
岗位名称：Python开发工程师
岗位职责：
1. 负责后端服务开发和维护
2. 参与系统架构设计
3. 编写技术文档

任职要求：
1. 3年以上Python开发经验
2. 熟悉FastAPI/Django框架
3. 熟悉MySQL/Redis
4. 良好的沟通能力
"""

TEST_RESUME_CONTENT = """
姓名：张三
学历：本科
专业：计算机科学
工作经验：5年
技能：Python, FastAPI, MySQL, Redis
"""


class APITester:
    """API测试器类"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.passed = 0
        self.failed = 0
        self.errors = []
        
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        stream: bool = False,
        use_form: bool = False
    ) -> tuple[bool, Any]:
        """
        发送HTTP请求
        
        Args:
            method: 请求方法 (GET/POST)
            endpoint: API端点路径
            data: 请求体数据
            files: 上传的文件
            stream: 是否流式响应
            use_form: 是否使用Form格式（而非JSON）
            
        Returns:
            (是否成功, 响应数据或错误信息)
        """
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"} if data and not use_form else {}
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, timeout=TIMEOUT)
            elif method.upper() == "POST":
                if files:
                    # 文件上传时不设置Content-Type，让requests自动处理
                    headers.pop("Content-Type", None)
                    response = self.session.post(
                        url,
                        data=data,
                        files=files,
                        timeout=TIMEOUT
                    )
                elif use_form:
                    # 使用Form格式（用于JD匹配接口）
                    response = self.session.post(
                        url,
                        data=data,
                        timeout=TIMEOUT
                    )
                else:
                    response = self.session.post(
                        url,
                        json=data,
                        headers=headers,
                        timeout=TIMEOUT,
                        stream=stream
                    )
            else:
                return False, f"不支持的HTTP方法: {method}"
            
            # 检查响应状态
            if response.status_code == 200:
                if stream:
                    return True, response
                try:
                    return True, response.json()
                except json.JSONDecodeError:
                    return True, response.text
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.ConnectionError:
            return False, "连接失败，请检查服务是否已启动"
        except requests.exceptions.Timeout:
            return False, f"请求超时（>{TIMEOUT}秒）"
        except Exception as e:
            return False, f"请求异常: {str(e)}"
    
    def _print_result(self, test_name: str, success: bool, message: str = ""):
        """打印测试结果"""
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {status} - {test_name}")
        if message and not success:
            print(f"      错误: {message}")
            self.errors.append(f"{test_name}: {message}")
        
        if success:
            self.passed += 1
        else:
            self.failed += 1
    
    def _print_section(self, title: str):
        """打印测试章节标题"""
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    
    # ==================== 基础接口测试 ====================
    
    def test_health_check(self):
        """测试健康检查接口"""
        self._print_section("1. 健康检查接口测试")
        
        success, result = self._make_request("GET", "/health")
        if success and isinstance(result, dict) and result.get("status") == "healthy":
            self._print_result("健康检查", True)
            print(f"      服务名称: {result.get('service', 'N/A')}")
            print(f"      版本: {result.get('version', 'N/A')}")
        else:
            self._print_result("健康检查", False, str(result))
    
    def test_root_endpoint(self):
        """测试根端点"""
        success, result = self._make_request("GET", "/")
        if success and isinstance(result, dict) and "name" in result:
            self._print_result("根端点", True)
            print(f"      应用名称: {result.get('name', 'N/A')}")
        else:
            self._print_result("根端点", False, str(result))
    
    def test_config_endpoint(self):
        """测试配置端点"""
        success, result = self._make_request("GET", "/api/v1/config")
        if success and isinstance(result, dict):
            self._print_result("配置端点", True)
            print(f"      模型: {result.get('vllm_model', 'N/A')}")
        else:
            self._print_result("配置端点", False, str(result))
    
    # ==================== 人岗适配接口测试 ====================
    
    def test_alignment_analyze(self):
        """测试人岗适配分析接口"""
        self._print_section("2. 人岗适配分析接口测试")
        
        data = {
            "employee_name": TEST_EMPLOYEE_NAME,
            "include_details": True
        }
        
        success, result = self._make_request(
            "POST",
            "/api/v1/alignment/analyze",
            data=data
        )
        
        if success and isinstance(result, dict):
            # 检查error字段是否存在且不为None/空
            error_value = result.get("error")
            if error_value is None or error_value == "":
                self._print_result("人岗适配分析", True)
                print(f"      员工: {result.get('employee_name', 'N/A')}")
                print(f"      综合得分: {result.get('overall_score', 'N/A')}")
                print(f"      适配等级: {result.get('alignment_level', 'N/A')}")
            else:
                self._print_result("人岗适配分析", False, str(error_value))
        else:
            self._print_result("人岗适配分析", False, str(result))
    
    def test_alignment_chat(self):
        """测试人岗适配对话接口"""
        data = {
            "message": f"{TEST_EMPLOYEE_NAME}的绩效怎么样？",
            "session_id": "test_session_001"
        }
        
        success, result = self._make_request(
            "POST",
            "/api/v1/alignment/chat",
            data=data
        )
        
        if success and isinstance(result, dict) and "reply" in result:
            self._print_result("对话咨询", True)
            reply_preview = result.get("reply", "")[:50]
            print(f"      回复预览: {reply_preview}...")
        else:
            self._print_result("对话咨询", False, str(result))
    
    def test_alignment_dimensions(self):
        """测试评估维度定义接口"""
        success, result = self._make_request(
            "GET",
            "/api/v1/alignment/dimensions"
        )
        
        if success and isinstance(result, dict) and "dimensions" in result:
            self._print_result("评估维度定义", True)
            dimensions = result.get("dimensions", {})
            print(f"      维度数量: {len(dimensions)}")
        else:
            self._print_result("评估维度定义", False, str(result))
    
    # ==================== 详细人岗适配接口测试 ====================
    
    def test_detailed_alignment_analysis(self):
        """测试详细人岗适配分析接口"""
        self._print_section("3. 详细人岗适配分析接口测试")
        
        # 测试AI评分方式
        data = {
            "employee_name": TEST_EMPLOYEE_NAME,
            "scoring_method": "ai"
        }
        
        print(f"\n  测试员工: {TEST_EMPLOYEE_NAME}")
        success, result = self._make_request(
            "POST",
            "/api/v1/alignment/detailed-analysis",
            data=data
        )
        
        if success and isinstance(result, dict):
            if "error" not in result:
                self._print_result("详细分析 (AI评分)", True)
                
                # 打印关键信息
                employee_info = result.get("employee_info", {})
                match_analysis = result.get("match_analysis", {})
                
                print(f"      部门: {employee_info.get('department', 'N/A')}")
                print(f"      岗位: {employee_info.get('position', 'N/A')}")
                print(f"      综合匹配度: {match_analysis.get('overall_match', 'N/A')}%")
                print(f"      匹配等级: {match_analysis.get('match_level', 'N/A')}")
                
                # 检查六维匹配分数
                match_scores = match_analysis.get("match_scores", {})
                if match_scores:
                    print(f"      六维匹配分数:")
                    for dim, score in list(match_scores.items())[:3]:
                        print(f"        - {dim}: {score}%")
                    if len(match_scores) > 3:
                        print(f"        ... 共{len(match_scores)}个维度")
            else:
                self._print_result("详细分析 (AI评分)", False, result.get("error"))
        else:
            self._print_result("详细分析 (AI评分)", False, str(result))
        
        # 测试规则评分方式
        data["scoring_method"] = "rule"
        success, result = self._make_request(
            "POST",
            "/api/v1/alignment/detailed-analysis",
            data=data
        )
        
        if success and isinstance(result, dict) and "error" not in result:
            self._print_result("详细分析 (规则评分)", True)
        else:
            error_msg = result.get("error", str(result)) if isinstance(result, dict) else str(result)
            self._print_result("详细分析 (规则评分)", False, error_msg)
    
    def test_position_requirements(self):
        """测试岗位要求获取接口"""
        data = {
            "position": "Python开发工程师",
            "department": "技术部"
        }
        
        success, result = self._make_request(
            "POST",
            "/api/v1/alignment/position-requirements",
            data=data
        )
        
        if success and isinstance(result, dict):
            if "error" not in result:
                self._print_result("岗位要求获取", True)
                position_model = result.get("position_model", {})
                print(f"      岗位: {position_model.get('position_name', 'N/A')}")
            else:
                self._print_result("岗位要求获取", False, result.get("error"))
        else:
            self._print_result("岗位要求获取", False, str(result))
    
    def test_employee_performance(self):
        """测试员工表现获取接口"""
        data = {
            "employee_name": TEST_EMPLOYEE_NAME,
            "scoring_method": "ai"
        }
        
        success, result = self._make_request(
            "POST",
            "/api/v1/alignment/employee-performance",
            data=data
        )
        
        if success and isinstance(result, dict):
            if "error" not in result:
                self._print_result("员工表现获取", True)
                emp_info = result.get("employee_info", {})
                print(f"      姓名: {emp_info.get('name', 'N/A')}")
            else:
                self._print_result("员工表现获取", False, result.get("error"))
        else:
            self._print_result("员工表现获取", False, str(result))
    
    def test_employee_info(self):
        """测试员工信息获取接口"""
        data = {
            "employee_name": TEST_EMPLOYEE_NAME
        }
        
        success, result = self._make_request(
            "POST",
            "/api/v1/alignment/employee-info",
            data=data
        )
        
        if success and isinstance(result, dict):
            if "error" not in result:
                self._print_result("员工信息获取", True)
                emp_info = result.get("employee_info", {})
                print(f"      ID: {emp_info.get('id', 'N/A')}")
                print(f"      姓名: {emp_info.get('name', 'N/A')}")
                print(f"      部门: {emp_info.get('department', 'N/A')}")
                print(f"      岗位: {emp_info.get('position', 'N/A')}")
            else:
                self._print_result("员工信息获取", False, result.get("error"))
        else:
            self._print_result("员工信息获取", False, str(result))
    
    # ==================== JD匹配接口测试 ====================
    
    def test_jd_match_employees(self):
        """测试员工列表获取接口"""
        self._print_section("4. JD匹配接口测试")
        
        success, result = self._make_request(
            "GET",
            "/api/v1/jd-match/employees"
        )
        
        if success and isinstance(result, dict) and result.get("success"):
            employees = result.get("employees", [])
            self._print_result("员工列表获取", True)
            print(f"      员工总数: {len(employees)}")
            if employees:
                print(f"      示例: {employees[0].get('name', 'N/A')} ({employees[0].get('department', 'N/A')})")
        else:
            self._print_result("员工列表获取", False, str(result))
    
    def test_jd_match_analyze_text(self):
        """测试JD文本匹配分析接口"""
        data = {
            "jd_content": TEST_JD_CONTENT,
            "resume_content": TEST_RESUME_CONTENT
        }
        
        success, result = self._make_request(
            "POST",
            "/api/v1/jd-match/analyze-text",
            data=data,
            use_form=True  # JD匹配接口使用Form格式
        )
        
        if success and isinstance(result, dict) and result.get("success"):
            self._print_result("JD文本匹配分析", True)
            print(f"      综合得分: {result.get('overall_score', 'N/A')}")
            print(f"      匹配等级: {result.get('match_level', 'N/A')}")
            
            dimensions = result.get("dimensions", [])
            if dimensions:
                print(f"      维度数量: {len(dimensions)}")
        else:
            error_msg = result.get("detail", str(result)) if isinstance(result, dict) else str(result)
            self._print_result("JD文本匹配分析", False, error_msg)
    
    def test_jd_match_analyze_with_employee(self):
        """测试JD与数据库员工匹配分析接口"""
        data = {
            "jd_content": TEST_JD_CONTENT,
            "employee_name": TEST_EMPLOYEE_NAME
        }
        
        success, result = self._make_request(
            "POST",
            "/api/v1/jd-match/analyze",
            data=data,
            use_form=True  # JD匹配接口使用Form格式
        )
        
        if success and isinstance(result, dict):
            if result.get("success"):
                self._print_result("JD员工匹配分析", True)
                print(f"      综合得分: {result.get('overall_score', 'N/A')}")
            else:
                self._print_result("JD员工匹配分析", False, result.get("detail", "未知错误"))
        else:
            self._print_result("JD员工匹配分析", False, str(result))
    
    # ==================== 流式接口测试 ====================
    
    def test_alignment_chat_stream(self):
        """测试流式对话接口"""
        self._print_section("5. 流式接口测试")
        
        data = {
            "message": f"分析一下{TEST_EMPLOYEE_NAME}的人岗适配情况",
            "session_id": "test_stream_001"
        }
        
        print(f"  正在测试流式对话接口（可能需要等待）...")
        
        success, response = self._make_request(
            "POST",
            "/api/v1/alignment/chat/stream",
            data=data,
            stream=True
        )
        
        if success and hasattr(response, 'iter_content'):
            try:
                chunk_count = 0
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            chunk_count += 1
                
                if chunk_count > 0:
                    self._print_result("流式对话", True)
                    print(f"      接收数据块: {chunk_count}个")
                else:
                    self._print_result("流式对话", False, "未接收到数据")
            except Exception as e:
                self._print_result("流式对话", False, f"流式读取失败: {str(e)}")
        else:
            self._print_result("流式对话", False, str(response))
    
    # ==================== 测试运行控制 ====================
    
    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*60)
        print("  HR-Bot API 接口测试")
        print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  服务地址: {self.base_url}")
        print("="*60)
        
        start_time = time.time()
        
        # 基础接口测试
        self.test_health_check()
        self.test_root_endpoint()
        self.test_config_endpoint()
        
        # 人岗适配接口测试
        self.test_alignment_analyze()
        self.test_alignment_chat()
        self.test_alignment_dimensions()
        
        # 详细人岗适配接口测试
        self.test_detailed_alignment_analysis()
        self.test_position_requirements()
        self.test_employee_performance()
        self.test_employee_info()
        
        # JD匹配接口测试
        self.test_jd_match_employees()
        self.test_jd_match_analyze_text()
        self.test_jd_match_analyze_with_employee()
        
        # 流式接口测试
        self.test_alignment_chat_stream()
        
        # 测试总结
        elapsed_time = time.time() - start_time
        self._print_summary(elapsed_time)
    
    def _print_summary(self, elapsed_time: float):
        """打印测试总结"""
        print("\n" + "="*60)
        print("  测试总结")
        print("="*60)
        print(f"  总测试数: {self.passed + self.failed}")
        print(f"  ✅ 通过: {self.passed}")
        print(f"  ❌ 失败: {self.failed}")
        print(f"  通过率: {self.passed/(self.passed + self.failed)*100:.1f}%")
        print(f"  耗时: {elapsed_time:.2f}秒")
        
        if self.errors:
            print("\n  错误详情:")
            for i, error in enumerate(self.errors[:5], 1):
                print(f"    {i}. {error}")
            if len(self.errors) > 5:
                print(f"    ... 还有 {len(self.errors) - 5} 个错误")
        
        print("="*60)
        
        # 返回退出码
        return 0 if self.failed == 0 else 1


def main():
    """主函数"""
    # 检查命令行参数
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = BASE_URL
    
    # 创建测试器并运行
    tester = APITester(base_url)
    exit_code = tester.run_all_tests()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
