# Seisei Print Agent

**Developed by Seisei**

Seisei Print Agent 是一个为 Odoo 18 开发的本地打印代理，支持 POS 结算小票和厨房通知单的实时打印。

## 功能特性

- **WebSocket 实时通信** - 通过 Odoo Bus 接收打印任务
- **ESC/POS 解析** - 支持热敏打印机命令解析和图像提取
- **多打印机管理** - 自动发现和管理本地打印机
- **跨平台支持** - 支持 Windows、Linux 和 macOS
- **PDF 输出** - 将 ESC/POS 命令转换为 PDF 文档
- **PyQt6 GUI** - 现代化的图形用户界面

## 项目结构

```
Seisei Print Agent/
├── src/
│   ├── __init__.py           # 模块信息和版本
│   ├── core/
│   │   ├── odoo_client.py    # Odoo HTTP 客户端
│   │   ├── websocket_client.py # WebSocket 客户端
│   │   ├── printer_manager.py  # 打印机管理
│   │   └── print_service.py    # 打印服务主类
│   ├── utils/
│   │   ├── config.py         # 配置管理
│   │   └── escpos_parser.py  # ESC/POS 解析器
│   └── gui/
│       └── main_window.py    # PyQt6 主窗口
├── output/                   # 输出文件目录
├── test_*.py                 # 测试脚本
└── README.md
```

## 快速开始

### 安装依赖

```bash
pip install PyQt6 requests websocket-client cryptography Pillow
```

### 运行测试

```bash
# 通信测试
python test_full_flow.py

# POS 小票打印测试
python test_pos_print.py
```

### 启动 GUI

```bash
python -m src.gui.main_window
```

## 与 Odoo 模块兼容性

Seisei Print Agent 设计为与以下 Odoo 模块兼容：
- `ylhc_print_manager` - 打印管理模块
- `ylhc_pos_printer` - POS 打印机模块

频道前缀可在 `src/__init__.py` 中配置：
```python
DEFAULT_CHANNEL_PREFIX = "ylhc_service"  # 兼容 ylhc 模块
# DEFAULT_CHANNEL_PREFIX = "seisei_service"  # 使用 seisei 模块
```

## 支持的打印类型

| 类型 | 说明 |
|------|------|
| `pos_receipt_print` | POS 结算小票 |
| `kitchen_order` | 厨房通知单 |
| `printer_test` | 打印机测试页 |
| `print_document` | 通用文档打印 |

## 开发者

**Seisei**

## 许可证

MIT License