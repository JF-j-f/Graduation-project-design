# -*- coding: utf-8 -*-
"""
统一配置加载器 config_loader.py
从项目根目录的 secrets.txt 读取数据库凭据等敏感配置，
与 Java 端 SecretsLoader.java 机制对齐，避免硬编码。

加载优先级：secrets.txt > 环境变量 > 默认值

开发者：JunFu
"""

import os
from pathlib import Path


def _find_secrets_file():
    """
    从当前脚本位置向上逐级查找 secrets.txt，最多上溯12层。
    与 Java 端 SecretsLoader 的查找逻辑一致。

    Returns:
        Path: secrets.txt 的路径，未找到时返回 None
    """
    current = Path(__file__).resolve().parent
    for _ in range(12):
        candidate = current / "secrets.txt"
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _load_secrets():
    """
    解析 secrets.txt 为字典。格式为 KEY=VALUE，忽略 # 注释和空行。
    若 secrets.txt 不存在，回退到环境变量。

    Returns:
        dict: 配置键值对
    """
    secrets = {}
    path = _find_secrets_file()
    if path is not None:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    secrets[key.strip()] = value.strip()
    return secrets


def get_mysql_config():
    """
    获取 MySQL 连接配置字典，可直接用于 pymysql.connect(**config)。

    Returns:
        dict: 包含 host, port, user, password, db, charset 的连接参数
    """
    secrets = _load_secrets()
    return {
        "host": secrets.get("DB_HOST", os.environ.get("DB_HOST", "localhost")),
        "port": int(secrets.get("DB_PORT", os.environ.get("DB_PORT", "3306"))),
        "user": secrets.get("DB_USER", os.environ.get("DB_USER", "")),
        "password": secrets.get("DB_PASSWORD", os.environ.get("DB_PASSWORD", "")),
        "db": secrets.get("DB_NAME", os.environ.get("DB_NAME", "musicweb")),
        "charset": "utf8mb4",
    }


def get_mysql_url(charset="utf8mb4"):
    """
    获取 SQLAlchemy 格式的 MySQL 连接 URL。

    Args:
        charset: 字符集，默认 utf8mb4

    Returns:
        str: 形如 mysql+pymysql://user:pass@host:port/db?charset=utf8mb4
    """
    cfg = get_mysql_config()
    return (
        f"mysql+pymysql://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['db']}?charset={charset}"
    )
