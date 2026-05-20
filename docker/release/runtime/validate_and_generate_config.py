#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Docker 发布版运行配置生成器。

该脚本在容器业务进程启动前执行，用于统一校验用户必须填写的
Cookie、邮箱授权码与 API Key，并生成 Java、Python、Node 共用的
secrets.txt 与 api_credentials.json。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


REQUIRED_KEYS = [
    "DB_PASSWORD",
    "MYSQL_ROOT_PASSWORD",
    "MAIL_USERNAME",
    "MAIL_PASSWORD",
    "MAIL_FROM",
    "LASTFM_API_KEY",
    "LASTFM_SHARED_SECRET",
    "NETEASE_COOKIE",
    "QQ_MUSIC_COOKIE",
]


def read_env(key: str, default: str = "") -> str:
    """
    读取环境变量并去除首尾空白。

    Args:
        key: 环境变量名
        default: 未设置时使用的默认值

    Returns:
        str: 清洗后的环境变量值
    """
    return os.environ.get(key, default).strip()


def validate_required_keys() -> None:
    """
    校验发布版运行所需的必填环境变量。

    Raises:
        SystemExit: 任一必填项为空时退出进程
    """
    missing_keys = [key for key in REQUIRED_KEYS if not read_env(key)]
    if missing_keys:
        print("MusicWeb Docker release config is incomplete.", file=sys.stderr)
        print("Missing required environment variables:", file=sys.stderr)
        for key in missing_keys:
            print(f"  - {key}", file=sys.stderr)
        raise SystemExit(1)


def write_secrets_file(output_dir: Path) -> None:
    """
    生成后端统一读取的 secrets.txt。

    Args:
        output_dir: 配置输出目录
    """
    db_name = read_env("DB_NAME", "musicweb")
    db_user = read_env("DB_USER", "musicweb")
    lines = [
        "DB_HOST=" + read_env("DB_HOST", "mysql"),
        "DB_PORT=" + read_env("DB_PORT", "3306"),
        "DB_NAME=" + db_name,
        "DB_USER=" + db_user,
        "DB_PASSWORD=" + read_env("DB_PASSWORD"),
        "REDIS_HOST=" + read_env("REDIS_HOST", "redis"),
        "REDIS_PORT=" + read_env("REDIS_PORT", "6379"),
        "MAIL_USERNAME=" + read_env("MAIL_USERNAME"),
        "MAIL_PASSWORD=" + read_env("MAIL_PASSWORD"),
        "MAIL_FROM=" + read_env("MAIL_FROM"),
        "LASTFM_API_KEY=" + read_env("LASTFM_API_KEY"),
        "LASTFM_SHARED_SECRET=" + read_env("LASTFM_SHARED_SECRET"),
        "MUSIC_API_URL=" + read_env("MUSIC_API_URL", "http://music-api:3000"),
        "QQ_API_URL=" + read_env("QQ_API_URL", "http://qq-api:8000"),
        "UNBLOCK_API_URL=" + read_env("UNBLOCK_API_URL", "http://unblock:8081"),
        "SOURCE_WEBAPP_PATH=" + read_env("SOURCE_WEBAPP_PATH"),
    ]
    (output_dir / "secrets.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_api_credentials(output_dir: Path) -> None:
    """
    生成 Node 与 QQ API 共用的音乐平台凭据 JSON。

    Args:
        output_dir: 配置输出目录
    """
    credentials = {
        "netease": {
            "cookie": read_env("NETEASE_COOKIE"),
        },
        "qqmusic": {
            "cookie": read_env("QQ_MUSIC_COOKIE"),
        },
        "netease_cookie": read_env("NETEASE_COOKIE"),
        "qq_cookie": read_env("QQ_MUSIC_COOKIE"),
        "lastfm_api_key": read_env("LASTFM_API_KEY"),
        "lastfm_shared_secret": read_env("LASTFM_SHARED_SECRET"),
    }
    (output_dir / "api_credentials.json").write_text(
        json.dumps(credentials, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """执行配置校验和配置文件生成。"""
    validate_required_keys()
    output_dir = Path(read_env("CONFIG_OUTPUT_DIR", "/config"))
    output_dir.mkdir(parents=True, exist_ok=True)
    write_secrets_file(output_dir)
    write_api_credentials(output_dir)
    print(f"MusicWeb runtime config generated at {output_dir}")


if __name__ == "__main__":
    main()
