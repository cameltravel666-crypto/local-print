#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的打印机测试脚本
1. 启动本地打印代理
2. 连接到 Odoo
3. 触发测试打印
4. 等待并验证结果
"""

import sys
import time
import signal
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.odoo_client import OdooClient
from core.print_service import PrintService, ServiceState

# 配置
SERVER_URL = "https://demo.nagashiro.top"
DATABASE = "test001"
USERNAME = "test"
PASSWORD = "test"
MACHINE_ID = "8ea2847f"  # 已存在的工作站代码


def main():
    print("\n" + "=" * 60)
    print("  完整打印机测试 (代理 + Odoo)")
    print("=" * 60)

    # 1. 启动本地打印代理
    print("\n[1] 启动本地打印代理...")

    service = PrintService(
        machine_name="Test Print Agent",
        machine_id=MACHINE_ID,
        location_tag="测试位置"
    )

    # 添加服务器
    service.add_server(
        server_id="test_server",
        server_name="Test Odoo Server",
        server_url=SERVER_URL,
        database=DATABASE,
        username=USERNAME,
        password=PASSWORD,
        http_port=443,
        websocket_port=443,
    )

    # 日志回调
    def on_log(level, message):
        print(f"  [代理-{level}] {message}")

    def on_job_received(data):
        print(f"\n  >>> 收到打印任务: {data.get('id', 'unknown')} - 类型: {data.get('type', 'unknown')}")

    def on_job_completed(job_id, success, message):
        status = "成功" if success else "失败"
        print(f"  <<< 打印任务完成: {job_id} - {status} - {message}")

    service.on_log(on_log)
    service.on_job_received(on_job_received)
    service.on_job_completed(on_job_completed)

    # 启动服务
    if not service.start():
        print("  启动代理失败!")
        return 1

    print("  代理已启动")

    # 等待连接稳定
    time.sleep(3)

    # 2. 连接 Odoo 并触发测试打印
    print("\n[2] 连接 Odoo 触发测试打印...")

    client = OdooClient(SERVER_URL, DATABASE)
    if not client.authenticate(USERNAME, PASSWORD):
        print("  认证失败!")
        service.stop()
        return 1

    print(f"  已登录 Odoo (uid: {client.session.uid})")

    # 获取打印机
    stations = client.search_read('seisei.station', [('code', '=', MACHINE_ID)], ['id', 'name'])
    if not stations:
        print(f"  未找到工作站: {MACHINE_ID}")
        client.logout()
        service.stop()
        return 1

    station = stations[0]
    print(f"  工作站: {station['name']}")

    printers = client.search_read(
        'seisei.printer',
        [('station_id', '=', station['id'])],
        ['id', 'name', 'status']
    )

    if not printers:
        print("  没有找到打印机!")
        client.logout()
        service.stop()
        return 1

    # 选择一台打印机测试
    printer = printers[0]
    print(f"  测试打印机: {printer['name']}")

    # 3. 触发测试打印
    print("\n[3] 触发测试打印...")

    try:
        result = client.call('seisei.printer', 'action_test_print', [[printer['id']]])
        print(f"  已发送测试打印请求")
    except Exception as e:
        print(f"  错误: {e}")

    # 4. 等待处理
    print("\n[4] 等待打印任务处理 (10秒)...")
    for i in range(10):
        time.sleep(1)
        print(f"  等待中... {i+1}/10")

    # 5. 检查结果
    print("\n[5] 检查打印任务状态...")

    recent_jobs = client.search_read(
        'seisei.print.job',
        [('type', '=', 'printer_test'), ('printer_id', '=', printer['id'])],
        ['name', 'status', 'error_message', 'create_date'],
        limit=1,
        order='id desc'
    )

    if recent_jobs:
        job = recent_jobs[0]
        status_icon = "✓" if job['status'] == 'completed' else ("✗" if job['status'] == 'failed' else "◎")
        print(f"\n  {status_icon} {job['name']}")
        print(f"      状态: {job['status']}")
        if job.get('error_message'):
            print(f"      错误: {job['error_message']}")
    else:
        print("  未找到测试打印任务")

    # 6. 清理
    print("\n[6] 清理...")
    client.logout()
    service.stop()

    print("\n" + "=" * 60)
    print("  测试完成!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
