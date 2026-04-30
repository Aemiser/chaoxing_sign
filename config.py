"""全局配置模块 — 从 config.json 加载，可在任意模块中导入使用"""
import json
import logging
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

logger = logging.getLogger(__name__)

_DEFAULT = {
    "location": {"longitude": "116.404", "latitude": "39.915", "name": "北京市"},
    "amap_version": "2.0",
}


class AppConfig(dict):
    """应用配置（dict 子类，支持 reload）"""

    def __init__(self):
        super().__init__(_DEFAULT)
        self._reload()

    def _reload(self):
        if CONFIG_PATH.exists():
            try:
                self.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("配置文件加载失败: %s", e)
        else:
            logger.debug("配置文件 %s 不存在，使用默认值", CONFIG_PATH)

    def reload(self):
        """重新加载配置文件"""
        self.clear()
        self.update(_DEFAULT)
        self._reload()
        logger.info("配置已重新加载")


# 全局单例 — 可跨模块共享
config = AppConfig()
