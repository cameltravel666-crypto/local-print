#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时测试打印 - 保持代理运行等待 Odoo 测试打印
"""

import sys
import time
import signal
from pathlib import Path

# Force unbuffered output
import functools
print = functools.partial(print, flush=True)

sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.print_service import PrintService, ServiceState

# 配置 - 使用已存在的工作站
SERVER_URL = "https://demo.nagashiro.top"
DATABASE = "test001"
USERNAME = "test"
PASSWORD = "test"
MACHINE_ID = "8ea2847f"  # josh-laptop 工作站

running = True

def signal_handler(sig, frame):
    global running
    print("\n\n正在停止...")
    running = False

signal.signal(signal.SIGINT, signal_handler)

def main():
    global running

    print("=" * 60)
    print("  实时打印测试 - 等待 Odoo 测试打印")
    print("=" * 60)
    print(f"  工作站: {MACHINE_ID}")
    print(f"  服务器: {SERVER_URL}")
    print("=" * 60)

    service = PrintService(
        machine_name="Live Print Agent",
        machine_id=MACHINE_ID,
        location_tag="测试位置"
    )

    service.add_server(
        server_id="demo",
        server_name="Demo Server",
        server_url=SERVER_URL,
        database=DATABASE,
        username=USERNAME,
        password=PASSWORD,
        http_port=443,
        websocket_port=443,
    )

    def on_log(level, msg):
        print(f"[{level.upper():5}] {msg}")

    def on_job_received(data):
        print(f"\n>>> 收到任务: {data.get('id', 'unknown')}")
        print(f"    类型: {data.get('type', 'unknown')}")
        print(f"    打印机: {data.get('printer_name', 'unknown')}")

    def on_job_completed(job_id, success, message):
        status = "成功" if success else "失败"
        print(f"\n<<< 任务完成: {job_id}")
        print(f"    状态: {status}")
        print(f"    消息: {message}")

    service.on_log(on_log)
    service.on_job_received(on_job_received)
    service.on_job_completed(on_job_completed)

    print("\n启动服务...")
    if not service.start():
        print("启动失败!")
        return 1

    print("\n" + "=" * 60)
    print("  代理已启动！")
    print("  现在可以在 Odoo 中点击 '测试打印' 按钮")
    print("  按 Ctrl+C 停止")
    print("=" * 60 + "\n")

    while running:
        time.sleep(1)

    service.stop()
    print("\n代理已停止")
    return 0

if __name__ == "__main__":
    sys.exit(main())
