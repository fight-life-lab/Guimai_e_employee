"""
缓存服务
- 缓存JD分析结果
- 缓存大模型调用结果
- 缓存转录数据
"""

import os
import json
import hashlib
import pickle
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class CacheService:
    """缓存服务类"""
    
    def __init__(self, cache_dir: str = "./data/cache"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def _get_cache_key(self, prefix: str, data: str) -> str:
        """生成缓存键"""
        hash_content = hashlib.md5(data.encode('utf-8')).hexdigest()
        return f"{prefix}_{hash_content}"
    
    def _get_cache_path(self, key: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{key}.pickle")
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """获取缓存"""
        try:
            cache_path = self._get_cache_path(key)
            if not os.path.exists(cache_path):
                return None
            
            with open(cache_path, 'rb') as f:
                data = pickle.load(f)
            
            # 检查缓存是否过期（默认24小时）
            if datetime.now().timestamp() - data.get('timestamp', 0) > 24 * 3600:
                os.remove(cache_path)
                return None
            
            return data.get('data')
        except Exception as e:
            print(f"[缓存] 获取缓存失败: {e}")
            return None
    
    def set(self, key: str, data: Any) -> bool:
        """设置缓存"""
        try:
            cache_data = {
                'data': data,
                'timestamp': datetime.now().timestamp()
            }
            cache_path = self._get_cache_path(key)
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
            return True
        except Exception as e:
            print(f"[缓存] 设置缓存失败: {e}")
            return False
    
    def clear(self, key_pattern: str = "*") -> None:
        """清除缓存"""
        try:
            import glob
            pattern = os.path.join(self.cache_dir, f"{key_pattern}.pickle")
            for file in glob.glob(pattern):
                os.remove(file)
        except Exception as e:
            print(f"[缓存] 清除缓存失败: {e}")

    # 便捷方法
    def get_jd_analysis(self, jd_content: str) -> Optional[Dict]:
        """获取JD分析缓存"""
        key = self._get_cache_key("jd_analysis", jd_content[:5000])  # 取前5000字符
        return self.get(key)
    
    def set_jd_analysis(self, jd_content: str, analysis: Dict) -> bool:
        """设置JD分析缓存"""
        key = self._get_cache_key("jd_analysis", jd_content[:5000])
        return self.set(key, analysis)
    
    def get_model_response(self, prompt: str) -> Optional[str]:
        """获取模型响应缓存"""
        key = self._get_cache_key("model", prompt[:3000])  # 取前3000字符
        return self.get(key)
    
    def set_model_response(self, prompt: str, response: str) -> bool:
        """设置模型响应缓存"""
        key = self._get_cache_key("model", prompt[:3000])
        return self.set(key, response)


# 全局缓存实例
cache_service = CacheService()
