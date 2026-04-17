---
name: "python-coding"
description: "Python代码编写规范指南，强调最小耦合、高内聚、函数复用。Invoke when user needs to write Python code, refactor existing code, or improve code quality with best practices."
---

# Python 代码编写规范 Skill

## 核心原则

### 1. 最小耦合原则 (Loose Coupling)

```python
# ❌ 坏示例：高耦合，直接依赖具体实现
class SalaryCalculator:
    def calculate(self, employee):
        db = MySQLDatabase()  # 直接依赖具体数据库
        config = load_config_from_file()  # 直接依赖文件系统
        tax_rate = get_tax_rate_from_api()  # 直接依赖外部API
        
        base_salary = db.query(f"SELECT salary FROM employees WHERE id={employee.id}")
        tax = base_salary * tax_rate
        return base_salary - tax

# ✅ 好示例：依赖注入，低耦合
from typing import Protocol
from dataclasses import dataclass

class Database(Protocol):
    """数据库接口"""
    def query_salary(self, employee_id: int) -> float: ...

class ConfigProvider(Protocol):
    """配置提供者接口"""
    def get_tax_rate(self) -> float: ...

@dataclass
class SalaryCalculator:
    """薪资计算器 - 通过依赖注入解耦"""
    db: Database
    config: ConfigProvider
    
    def calculate(self, employee_id: int) -> float:
        base_salary = self.db.query_salary(employee_id)
        tax_rate = self.config.get_tax_rate()
        tax = base_salary * tax_rate
        return base_salary - tax
```

### 2. 高内聚原则 (High Cohesion)

```python
# ❌ 坏示例：低内聚，一个类做太多事情
class EmployeeManager:
    def create_employee(self, data): ...
    def delete_employee(self, id): ...
    def calculate_salary(self, id): ...
    def generate_report(self): ...
    def send_email(self, to, content): ...
    def backup_database(self): ...

# ✅ 好示例：高内聚，每个类职责单一
class EmployeeRepository:
    """员工数据访问 - 只负责数据CRUD"""
    def create(self, data) -> Employee: ...
    def get_by_id(self, id: int) -> Employee: ...
    def update(self, id: int, data) -> Employee: ...
    def delete(self, id: int) -> bool: ...

class SalaryService:
    """薪资计算服务 - 只负责薪资相关逻辑"""
    def calculate(self, employee: Employee) -> Salary: ...
    def calculate_bonus(self, employee: Employee) -> float: ...

class ReportGenerator:
    """报表生成器 - 只负责报表生成"""
    def generate_employee_report(self, employees: List[Employee]) -> Report: ...
```

### 3. 函数复用原则 (DRY - Don't Repeat Yourself)

```python
# ❌ 坏示例：重复代码
class InterviewEvaluator:
    def evaluate_professional(self, transcript):
        score = 0
        if "专业" in transcript:
            score += 10
        if "技能" in transcript:
            score += 10
        return min(score, 100)
    
    def evaluate_communication(self, transcript):
        score = 0
        if "沟通" in transcript:
            score += 10
        if "表达" in transcript:
            score += 10
        return min(score, 100)

# ✅ 好示例：提取公共逻辑
class InterviewEvaluator:
    """面试评估器 - 复用评分逻辑"""
    
    # 评分规则配置
    SCORING_RULES = {
        "professional": [("专业", 10), ("技能", 10), ("经验", 10)],
        "communication": [("沟通", 10), ("表达", 10), ("逻辑", 10)],
    }
    
    def evaluate_dimension(self, transcript: str, dimension: str) -> int:
        """通用维度评估 - 可复用的核心逻辑"""
        score = 0
        rules = self.SCORING_RULES.get(dimension, [])
        
        for keyword, points in rules:
            if keyword in transcript:
                score += points
        
        return min(score, 100)
    
    def evaluate_professional(self, transcript: str) -> int:
        """专业能力评估"""
        return self.evaluate_dimension(transcript, "professional")
    
    def evaluate_communication(self, transcript: str) -> int:
        """沟通能力评估"""
        return self.evaluate_dimension(transcript, "communication")
```

## 代码组织模式

### 模式1：分层架构 (Layered Architecture)

```python
# project/
# ├── api/              # API层 - 处理HTTP请求
# │   ├── __init__.py
# │   └── employee_routes.py
# ├── services/         # 服务层 - 业务逻辑
# │   ├── __init__.py
# │   ├── employee_service.py
# │   └── salary_service.py
# ├── repositories/     # 数据访问层 - 数据库操作
# │   ├── __init__.py
# │   └── employee_repository.py
# ├── models/           # 模型层 - 数据定义
# │   ├── __init__.py
# │   └── employee.py
# └── utils/            # 工具层 - 通用功能
#     ├── __init__.py
#     └── validators.py

# api/employee_routes.py
from fastapi import APIRouter, Depends
from services.employee_service import EmployeeService
from models.employee import EmployeeCreate

router = APIRouter()

def get_employee_service() -> EmployeeService:
    """依赖注入：创建服务实例"""
    return EmployeeService()

@router.post("/employees")
async def create_employee(
    data: EmployeeCreate,
    service: EmployeeService = Depends(get_employee_service)
):
    """创建员工 - API层只负责请求处理和响应"""
    employee = await service.create(data)
    return {"success": True, "data": employee}

# services/employee_service.py
from repositories.employee_repository import EmployeeRepository
from models.employee import Employee, EmployeeCreate

class EmployeeService:
    """员工服务 - 业务逻辑层"""
    
    def __init__(self, repo: EmployeeRepository = None):
        self.repo = repo or EmployeeRepository()
    
    async def create(self, data: EmployeeCreate) -> Employee:
        """创建员工 - 包含业务规则验证"""
        # 业务规则验证
        if not self._validate_email(data.email):
            raise ValueError("Invalid email")
        
        # 数据转换
        employee_data = data.model_dump()
        employee_data["created_at"] = datetime.now()
        
        # 调用数据层
        return await self.repo.create(employee_data)
    
    def _validate_email(self, email: str) -> bool:
        """邮箱验证 - 私有方法"""
        return "@" in email and "." in email

# repositories/employee_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from models.employee import Employee

class EmployeeRepository:
    """员工数据仓库 - 数据访问层"""
    
    def __init__(self, session: AsyncSession = None):
        self.session = session or get_db_session()
    
    async def create(self, data: dict) -> Employee:
        """创建员工记录"""
        employee = Employee(**data)
        self.session.add(employee)
        await self.session.commit()
        return employee
```

### 模式2：策略模式 (Strategy Pattern)

```python
from typing import Protocol
from dataclasses import dataclass

class ScoringStrategy(Protocol):
    """评分策略接口"""
    def calculate(self, data: dict) -> float: ...

@dataclass
class ProfessionalScoringStrategy:
    """专业能力评分策略"""
    weights: dict
    
    def calculate(self, data: dict) -> float:
        score = 0
        for key, weight in self.weights.items():
            score += data.get(key, 0) * weight
        return min(score, 100)

@dataclass
class ExperienceScoringStrategy:
    """经验评分策略"""
    required_years: int
    
    def calculate(self, data: dict) -> float:
        years = data.get("years", 0)
        if years >= self.required_years:
            return 100
        return (years / self.required_years) * 100

class AlignmentCalculator:
    """适配度计算器 - 使用策略模式"""
    
    def __init__(self):
        self._strategies: dict[str, ScoringStrategy] = {}
    
    def register_strategy(self, name: str, strategy: ScoringStrategy):
        """注册评分策略"""
        self._strategies[name] = strategy
    
    def calculate(self, dimension: str, data: dict) -> float:
        """使用指定策略计算分数"""
        strategy = self._strategies.get(dimension)
        if not strategy:
            raise ValueError(f"Unknown dimension: {dimension}")
        return strategy.calculate(data)

# 使用示例
calculator = AlignmentCalculator()
calculator.register_strategy("professional", ProfessionalScoringStrategy({"skill": 0.6, "cert": 0.4}))
calculator.register_strategy("experience", ExperienceScoringStrategy(required_years=5))

score = calculator.calculate("professional", {"skill": 80, "cert": 90})
```

### 模式3：工厂模式 (Factory Pattern)

```python
from typing import TypeVar, Type, Callable

T = TypeVar('T')

class ServiceFactory:
    """服务工厂 - 集中管理服务创建"""
    
    _registry: dict[str, Callable] = {}
    _singletons: dict[str, object] = {}
    
    @classmethod
    def register(cls, name: str, creator: Callable, singleton: bool = False):
        """注册服务创建器"""
        cls._registry[name] = {"creator": creator, "singleton": singleton}
    
    @classmethod
    def get(cls, name: str) -> T:
        """获取服务实例"""
        if name not in cls._registry:
            raise ValueError(f"Service {name} not registered")
        
        config = cls._registry[name]
        
        if config["singleton"]:
            if name not in cls._singletons:
                cls._singletons[name] = config["creator"]()
            return cls._singletons[name]
        
        return config["creator"]()

# 注册服务
ServiceFactory.register("employee_service", EmployeeService, singleton=True)
ServiceFactory.register("salary_service", SalaryService)

# 使用服务
employee_service = ServiceFactory.get("employee_service")
```

## 函数设计最佳实践

### 1. 单一职责函数

```python
# ❌ 坏示例：函数做太多事情
def process_employee_data(data):
    # 验证数据
    if not data.get("name"):
        raise ValueError("Name required")
    
    # 转换数据
    data["name"] = data["name"].upper()
    data["salary"] = float(data["salary"])
    
    # 保存到数据库
    db = connect_db()
    db.execute(f"INSERT INTO employees ...")
    
    # 发送通知
    send_email(data["email"], "Welcome!")
    
    # 记录日志
    logger.info(f"Employee {data['name']} created")
    
    return data

# ✅ 好示例：拆分为单一职责函数
class EmployeeProcessor:
    """员工数据处理器"""
    
    def process(self, data: dict) -> Employee:
        """主流程 - 协调各个步骤"""
        validated_data = self._validate(data)
        transformed_data = self._transform(validated_data)
        employee = self._save(transformed_data)
        self._notify(employee)
        self._log(employee)
        return employee
    
    def _validate(self, data: dict) -> dict:
        """验证数据 - 单一职责"""
        if not data.get("name"):
            raise ValueError("Name required")
        return data
    
    def _transform(self, data: dict) -> dict:
        """转换数据 - 单一职责"""
        return {
            "name": data["name"].upper(),
            "salary": float(data["salary"]),
        }
    
    def _save(self, data: dict) -> Employee:
        """保存数据 - 单一职责"""
        return self.repository.create(data)
    
    def _notify(self, employee: Employee):
        """发送通知 - 单一职责"""
        self.notification_service.send_welcome(employee)
    
    def _log(self, employee: Employee):
        """记录日志 - 单一职责"""
        logger.info(f"Employee {employee.name} created")
```

### 2. 纯函数与副作用分离

```python
from typing import Callable
from functools import wraps

# 纯函数：无副作用，相同输入总是产生相同输出
def calculate_alignment_score(
    employee_scores: list[float],
    job_requirements: list[float],
    weights: list[float]
) -> float:
    """
    计算适配度分数 - 纯函数
    
    Args:
        employee_scores: 员工各维度得分
        job_requirements: 岗位各维度要求
        weights: 各维度权重
    
    Returns:
        适配度分数 (0-100)
    """
    if len(employee_scores) != len(weights):
        raise ValueError("Scores and weights must have same length")
    
    weighted_sum = sum(s * w for s, w in zip(employee_scores, weights))
    total_weight = sum(weights)
    
    return (weighted_sum / total_weight) if total_weight > 0 else 0

# 副作用函数：明确标记
async def save_alignment_result(result: AlignmentResult) -> None:
    """
    保存适配度结果 - 包含副作用（IO操作）
    """
    async with get_db_session() as session:
        session.add(result)
        await session.commit()
        logger.info(f"Saved alignment result for {result.employee_id}")

# 组合使用
async def analyze_and_save_alignment(employee_id: int) -> AlignmentResult:
    """分析并保存适配度"""
    # 获取数据（副作用）
    employee = await fetch_employee(employee_id)
    
    # 计算分数（纯函数）
    score = calculate_alignment_score(
        employee_scores=employee.scores,
        job_requirements=employee.job.requirements,
        weights=[0.3, 0.2, 0.2, 0.15, 0.15]
    )
    
    # 创建结果
    result = AlignmentResult(
        employee_id=employee_id,
        score=score,
        created_at=datetime.now()
    )
    
    # 保存结果（副作用）
    await save_alignment_result(result)
    
    return result
```

### 3. 函数参数设计

```python
from dataclasses import dataclass
from typing import Optional

# ❌ 坏示例：参数过多，难以维护
def create_employee(
    name: str,
    email: str,
    phone: str,
    department: str,
    position: str,
    salary: float,
    hire_date: str,
    manager_id: Optional[int] = None,
    is_full_time: bool = True,
    benefits: Optional[dict] = None
):
    ...

# ✅ 好示例：使用数据类封装参数
@dataclass
class EmployeeCreateRequest:
    """创建员工请求"""
    name: str
    email: str
    phone: str
    department: str
    position: str
    salary: float
    hire_date: str
    manager_id: Optional[int] = None
    is_full_time: bool = True
    benefits: Optional[dict] = None

def create_employee(request: EmployeeCreateRequest) -> Employee:
    """创建员工 - 参数清晰"""
    ...

# ✅ 好示例：使用Builder模式处理复杂对象
@dataclass
class ScoringConfig:
    """评分配置"""
    weights: dict[str, float]
    thresholds: dict[str, float]
    bonuses: dict[str, float]
    penalties: dict[str, float]

class ScoringConfigBuilder:
    """评分配置构建器"""
    
    def __init__(self):
        self._weights = {}
        self._thresholds = {}
        self._bonuses = {}
        self._penalties = {}
    
    def with_weight(self, dimension: str, weight: float) -> "ScoringConfigBuilder":
        self._weights[dimension] = weight
        return self
    
    def with_threshold(self, dimension: str, threshold: float) -> "ScoringConfigBuilder":
        self._thresholds[dimension] = threshold
        return self
    
    def build(self) -> ScoringConfig:
        return ScoringConfig(
            weights=self._weights,
            thresholds=self._thresholds,
            bonuses=self._bonuses,
            penalties=self._penalties
        )

# 使用
config = (
    ScoringConfigBuilder()
    .with_weight("professional", 0.3)
    .with_weight("experience", 0.2)
    .with_threshold("professional", 60)
    .build()
)
```

## 复用代码的组织方式

### 1. 工具函数库

```python
# utils/validators.py
import re
from typing import Pattern

class Validator:
    """验证工具类"""
    
    EMAIL_PATTERN: Pattern = re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$')
    PHONE_PATTERN: Pattern = re.compile(r'^1[3-9]\d{9}$')
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """验证邮箱格式"""
        return bool(Validator.EMAIL_PATTERN.match(email))
    
    @staticmethod
    def is_valid_phone(phone: str) -> bool:
        """验证手机号格式"""
        return bool(Validator.PHONE_PATTERN.match(phone))

# utils/calculators.py
from typing import Sequence

class Calculator:
    """计算工具类"""
    
    @staticmethod
    def weighted_average(values: Sequence[float], weights: Sequence[float]) -> float:
        """加权平均"""
        if len(values) != len(weights):
            raise ValueError("Values and weights must have same length")
        total_weight = sum(weights)
        if total_weight == 0:
            return 0
        return sum(v * w for v, w in zip(values, weights)) / total_weight
    
    @staticmethod
    def clamp(value: float, min_val: float, max_val: float) -> float:
        """限制数值范围"""
        return max(min_val, min(min_val, max_val))
    
    @staticmethod
    def percentage(value: float, total: float) -> float:
        """计算百分比"""
        return (value / total * 100) if total > 0 else 0

# utils/formatters.py
from datetime import datetime

class Formatter:
    """格式化工具类"""
    
    @staticmethod
    def format_currency(amount: float, currency: str = "¥") -> str:
        """格式化货币"""
        return f"{currency}{amount:,.2f}"
    
    @staticmethod
    def format_date(dt: datetime, fmt: str = "%Y-%m-%d") -> str:
        """格式化日期"""
        return dt.strftime(fmt)
    
    @staticmethod
    def format_score(score: float, precision: int = 1) -> str:
        """格式化分数"""
        return f"{score:.{precision}f}分"
```

### 2. 混入类 (Mixin)

```python
from typing import TypeVar, Generic

T = TypeVar('T')

class TimestampMixin:
    """时间戳混入类 - 提供创建时间和更新时间"""
    
    created_at: datetime
    updated_at: datetime
    
    def touch(self):
        """更新时间戳"""
        self.updated_at = datetime.now()

class ValidatableMixin:
    """可验证混入类"""
    
    def validate(self) -> list[str]:
        """验证对象，返回错误列表"""
        errors = []
        for name, validator in self._get_validators().items():
            value = getattr(self, name, None)
            if not validator(value):
                errors.append(f"{name} is invalid")
        return errors
    
    def _get_validators(self) -> dict[str, Callable]:
        """获取验证器映射 - 子类重写"""
        return {}

class SerializableMixin:
    """可序列化混入类"""
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            k: v for k, v in self.__dict__.items()
            if not k.startswith('_')
        }
    
    @classmethod
    def from_dict(cls: Type[T], data: dict) -> T:
        """从字典创建"""
        return cls(**data)

# 使用混入
@dataclass
class Employee(TimestampMixin, ValidatableMixin, SerializableMixin):
    """员工实体"""
    name: str
    email: str
    salary: float
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def _get_validators(self) -> dict[str, Callable]:
        return {
            "name": lambda x: bool(x and len(x) >= 2),
            "email": Validator.is_valid_email,
            "salary": lambda x: x > 0,
        }
```

### 3. 装饰器复用

```python
from functools import wraps
from typing import Callable, TypeVar
import time
import logging

F = TypeVar("F", bound=Callable)

def retry(max_attempts: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
    """重试装饰器"""
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(delay * (attempt + 1))
                    logging.warning(f"Retry {attempt + 1}/{max_attempts} for {func.__name__}: {e}")
        return wrapper
    return decorator

def cache_result(ttl: int = 300):
    """缓存结果装饰器"""
    def decorator(func: F) -> F:
        _cache = {}
        _cache_time = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            now = time.time()
            
            if key in _cache and now - _cache_time[key] < ttl:
                return _cache[key]
            
            result = func(*args, **kwargs)
            _cache[key] = result
            _cache_time[key] = now
            return result
        
        return wrapper
    return decorator

def log_execution(level: str = "info"):
    """执行日志装饰器"""
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            log_func = getattr(logger, level)
            
            log_func(f"Executing {func.__name__}")
            start = time.time()
            
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                log_func(f"Completed {func.__name__} in {elapsed:.3f}s")
                return result
            except Exception as e:
                elapsed = time.time() - start
                logger.error(f"Failed {func.__name__} in {elapsed:.3f}s: {e}")
                raise
        
        return wrapper
    return decorator

# 使用装饰器
class AlignmentService:
    """适配度服务"""
    
    @retry(max_attempts=3, exceptions=(ConnectionError, TimeoutError))
    @cache_result(ttl=600)
    @log_execution(level="info")
    async def calculate_alignment(self, employee_id: int) -> AlignmentResult:
        """计算适配度 - 带重试、缓存和日志"""
        ...
```

## 错误处理模式

```python
from typing import Optional, TypeVar
from dataclasses import dataclass

T = TypeVar('T')

@dataclass
class Result:
    """操作结果封装"""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    
    @property
    def is_ok(self) -> bool:
        return self.success and self.error is None
    
    @staticmethod
    def ok(data: T) -> "Result[T]":
        return Result(success=True, data=data)
    
    @staticmethod
    def fail(error: str) -> "Result[T]":
        return Result(success=False, error=error)

# 使用Result模式
class EmployeeService:
    """员工服务"""
    
    async def find_by_id(self, id: int) -> Result[Employee]:
        """查找员工 - 返回Result避免异常"""
        try:
            employee = await self.repo.get_by_id(id)
            if not employee:
                return Result.fail(f"Employee {id} not found")
            return Result.ok(employee)
        except DatabaseError as e:
            return Result.fail(f"Database error: {e}")
    
    async def update_salary(self, id: int, new_salary: float) -> Result[Employee]:
        """更新薪资 - 链式处理Result"""
        # 查找员工
        result = await self.find_by_id(id)
        if not result.is_ok:
            return result
        
        employee = result.data
        
        # 验证薪资
        if new_salary <= 0:
            return Result.fail("Salary must be positive")
        
        # 更新
        try:
            employee.salary = new_salary
            updated = await self.repo.update(employee)
            return Result.ok(updated)
        except Exception as e:
            return Result.fail(f"Update failed: {e}")
```

## 配置管理

```python
from dataclasses import dataclass
from typing import Optional
import os
from functools import lru_cache

@dataclass(frozen=True)
class DatabaseConfig:
    """数据库配置"""
    host: str
    port: int
    database: str
    user: str
    password: str
    pool_size: int = 10
    
    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

@dataclass(frozen=True)
class AppConfig:
    """应用配置"""
    debug: bool
    database: DatabaseConfig
    log_level: str
    max_workers: int

class ConfigLoader:
    """配置加载器"""
    
    @staticmethod
    @lru_cache()
    def load() -> AppConfig:
        """加载配置 - 缓存结果"""
        return AppConfig(
            debug=os.getenv("DEBUG", "false").lower() == "true",
            database=DatabaseConfig(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "5432")),
                database=os.getenv("DB_NAME", "app"),
                user=os.getenv("DB_USER", "user"),
                password=os.getenv("DB_PASSWORD", ""),
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            max_workers=int(os.getenv("MAX_WORKERS", "4")),
        )

# 使用配置
config = ConfigLoader.load()
db_url = config.database.url
```

## 总结

遵循以上规范可以写出：

1. **低耦合**：通过依赖注入和接口抽象减少模块间依赖
2. **高内聚**：每个类/函数只负责一个明确的职责
3. **易复用**：公共逻辑抽取为工具函数、混入类或装饰器
4. **易测试**：纯函数与副作用分离，便于单元测试
5. **易维护**：清晰的代码组织和一致的命名规范
