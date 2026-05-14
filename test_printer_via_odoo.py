#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过 Odoo 18 打印模块测试打印机
Trigger printer test via Odoo 18 Print Module

Developed by Seisei
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.odoo_client import OdooClient


def main():
    # 服务器配置 - 根据你的 Odoo 服务器修改
    server_url = "https://demo.nagashiro.top"
    database = "test001"
    username = "test"
    password = "test"
    machine_id = "MAC001"  # 你的工作站代码

    print("\n" + "=" * 60)
    print("  通过 Odoo 18 打印模块测试打印机")
    print("  Test Printer via Odoo 18 Print Module")
    print("=" * 60)

    # 1. 认证
    print("\n[1] 正在连接 Odoo 服务器...")
    client = OdooClient(server_url, database)
    if not client.authenticate(username, password):
        print("  失败: 认证失败!")
        return 1
    print(f"  成功: 已登录 (uid: {client.session.uid})")

    # 2. 获取工作站信息
    print("\n[2] 获取工作站信息...")
    stations = client.search_read(
        'seisei.station',
        [('code', '=', machine_id)],
        ['id', 'name', 'code']
    )
    if not stations:
        print(f"  未找到工作站: {machine_id}")
        # 列出所有可用的工作站
        all_stations = client.search_read('seisei.station', [], ['id', 'name', 'code'])
        if all_stations:
            print("\n  可用的工作站:")
            for s in all_stations:
                print(f"    - {s['name']} (代码: {s['code']})")
        return 1

    station = stations[0]
    print(f"  工作站: {station['name']} (代码: {station['code']})")

    # 3. 获取打印机列表
    print("\n[3] 获取打印机列表...")
    printers = client.search_read(
        'seisei.printer',
        [('station_id', '=', station['id'])],
        ['id', 'name', 'display_name', 'status', 'is_default']
    )

    if not printers:
        print("  该工作站没有打印机!")
        return 1

    print(f"  找到 {len(printers)} 台打印机:")
    for i, p in enumerate(printers, 1):
        default_mark = " [默认]" if p.get('is_default') else ""
        print(f"    {i}. {p['name']} - 状态: {p['status']}{default_mark}")

    # 4. 选择打印机
    print("\n[4] 选择要测试的打印机:")
    for i, p in enumerate(printers, 1):
        print(f"    {i}. {p['name']}")
    print(f"    0. 测试所有打印机")

    try:
        choice = input("\n请输入选择 [1]: ").strip() or "1"
        choice = int(choice)
    except ValueError:
        choice = 1

    printers_to_test = []
    if choice == 0:
        printers_to_test = printers
    elif 1 <= choice <= len(printers):
        printers_to_test = [printers[choice - 1]]
    else:
        print("  无效选择!")
        return 1

    # 5. 触发测试打印
    print("\n[5] 触发测试打印...")

    for printer in printers_to_test:
        printer_id = printer['id']
        printer_name = printer['name']

        print(f"\n  正在测试打印机: {printer_name}")

        try:
            # 调用 action_test_print 方法
            result = client.call(
                'seisei.printer',
                'action_test_print',
                [[printer_id]]
            )
            print(f"    已发送测试打印请求")

            if result and isinstance(result, dict):
                msg = result.get('params', {}).get('message', '')
                if msg:
                    print(f"    服务器响应: {msg}")

        except Exception as e:
            print(f"    错误: {e}")

            # 尝试手动创建测试打印任务
            print("    尝试手动创建测试打印任务...")
            try:
                job_data = {
                    'name': f'测试打印 - {printer_name}',
                    'report_name': 'printer_test',
                    'type': 'printer_test',
                    'printer_id': printer_id,
                    'status': 'pending',
                    'is_test': True,
                }
                job_id = client.create('seisei.print.job', job_data)
                print(f"    创建打印任务: {job_id}")

                # 触发处理
                client.call('seisei.print.job', 'action_process', [[job_id]])
                print(f"    已触发打印任务处理")

            except Exception as e2:
                print(f"    手动创建也失败: {e2}")

    # 6. 等待并检查状态
    print("\n[6] 等待打印任务处理 (3秒)...")
    time.sleep(3)

    print("\n[7] 检查打印任务状态...")
    recent_jobs = client.search_read(
        'seisei.print.job',
        [('type', '=', 'printer_test')],
        ['name', 'status', 'error_message', 'create_date'],
        limit=len(printers_to_test),
        order='id desc'
    )

    for job in recent_jobs:
        status_icon = "✓" if job['status'] == 'completed' else ("✗" if job['status'] == 'failed' else "◎")
        print(f"  {status_icon} {job['name']}: {job['status']}")
        if job.get('error_message'):
            print(f"      错误: {job['error_message']}")

    # 8. 清理
    client.logout()

    print("\n" + "=" * 60)
    print("  测试完成!")
    print("  如果本地打印代理正在运行，它应该已收到测试打印任务。")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
