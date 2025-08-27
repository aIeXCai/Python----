#!/bin/bash
# 一键启动Python学习网站服务器

cd "$(dirname "$0")"

# 检查Python环境
if ! command -v python3 &>/dev/null; then
    echo "未检测到python3，请先安装Python3。"
    exit 1
fi

# 启动服务器
python3 server.py
