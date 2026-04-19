import os
import yaml
import logging
from logging.handlers import RotatingFileHandler

# 默认配置
DEFAULT_CONFIG = {
    'scheduler': {
        'poll_interval': 5,
        'cli': 'claude',
        'heartbeat_interval': 30,
        'stale_threshold': 120
    },
    'executor': {
        'timeout': 1800,
        'max_auto_retries': 3,
        'auto_retry_delay': 180
    },
    'log': {
        'level': 'INFO',
        'file': 'server.log',
        'max_bytes': 10485760,  # 10MB
        'backup_count': 5
    }
}

_config = None

def load_config():
    """加载配置文件"""
    global _config
    if _config is not None:
        return _config

    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            _config = yaml.safe_load(f)
            # 合并默认配置
            for key, default_val in DEFAULT_CONFIG.items():
                if key not in _config:
                    _config[key] = default_val
                elif isinstance(default_val, dict):
                    for k, v in default_val.items():
                        if k not in _config[key]:
                            _config[key][k] = v
    else:
        _config = DEFAULT_CONFIG.copy()

    return _config

def setup_logging():
    """设置日志"""
    config = load_config()
    log_config = config.get('log', {})

    level = getattr(logging, log_config.get('level', 'INFO').upper())
    log_file = log_config.get('file', 'server.log')
    max_bytes = log_config.get('max_bytes', 10485760)  # 10MB
    backup_count = log_config.get('backup_count', 5)

    # 日志文件路径
    log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_path = os.path.join(log_dir, log_file)

    # 使用 RotatingFileHandler 实现日志回滚
    rotating_handler = RotatingFileHandler(
        log_path,
        encoding='utf-8',
        mode='a',
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    rotating_handler.setFormatter(
        logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    )

    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            rotating_handler,
            logging.StreamHandler()
        ]
    )

    return logging.getLogger(__name__)

def get_logger(name=None):
    """获取日志器"""
    return logging.getLogger(name)
