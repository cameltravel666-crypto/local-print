# QR Code Ordering / 扫码点餐模块

**Version**: 18.0.1.0.0  
**Compatibility**: Odoo 18.0  
**License**: LGPL-3

---

## 功能概述

扫码点餐模块允许客户通过扫描餐桌二维码在移动设备上自助点餐，订单实时同步到 Odoo POS 系统。

### 核心功能

- ✅ 每个餐桌生成唯一二维码
- ✅ 移动端友好的点餐界面（参考 EasyEat 设计）
- ✅ 左侧分类栏 + 右侧菜品列表布局
- ✅ 菜品支持图片和视频展示
- ✅ 购物车和加菜功能
- ✅ 订单实时同步到 POS 系统
- ✅ 自动触发小票打印（通过 YLHC 打印路由）
- ✅ 多语言支持（中文/日文/英文）
- ✅ 防恶意点餐机制（动态 Token + Session 有效期）
- ✅ 订单批次管理（区分首次下单和加菜）

---

## 安装

### 依赖模块

- `point_of_sale` - POS 基础模块
- `pos_restaurant` - POS 餐厅模块（餐桌管理）
- `bus` - 实时通知

### 安装步骤

1. 将 `qr_ordering` 文件夹放置在 `odoo-addons` 目录下
2. 重启 Odoo 服务
3. 更新应用列表：**应用** > **更新应用列表**
4. 搜索 "QR Ordering" 或 "扫码点餐" 并安装

---

## 使用指南

### 1. 创建餐桌二维码

1. 进入 **扫码点餐** > **餐桌**
2. 点击 **创建** 按钮
3. 填写餐桌名称（如 A1, A2, 包厢1 等）
4. 选择关联的 POS 配置
5. 可选：关联 POS 餐厅餐桌
6. 保存后，系统自动生成二维码

### 2. 打印二维码

1. 打开餐桌记录
2. 点击 **打印二维码** 按钮
3. 打印并张贴到对应餐桌

### 3. 客户点餐流程

1. 客户扫描餐桌二维码
2. 自动打开点餐页面（无需登录）
3. 浏览菜品，添加到购物车
4. 提交订单
5. 订单自动同步到 POS，触发小票打印
6. 可继续加菜
7. 用餐完毕后在前台结账

### 4. 查看订单

1. 进入 **扫码点餐** > **订单**
2. 查看所有扫码点餐订单
3. 可按状态、餐桌、日期筛选

---

## 数据模型

### qr.table - 二维码餐桌

| 字段 | 类型 | 说明 |
|------|------|------|
| name | Char | 餐桌名称 |
| pos_config_id | Many2one | 关联的 POS 配置 |
| pos_table_id | Many2one | 关联的 POS 餐桌（可选） |
| qr_token | Char | 二维码唯一标识 |
| qr_url | Char | 点餐链接 |
| state | Selection | 状态（空闲/使用中/已预订） |

### qr.session - 点餐会话

| 字段 | 类型 | 说明 |
|------|------|------|
| name | Char | 会话 ID |
| table_id | Many2one | 关联餐桌 |
| access_token | Char | 访问令牌（防恶意） |
| state | Selection | 状态 |
| expire_time | Datetime | 过期时间（默认4小时） |

### qr.order - 扫码订单

| 字段 | 类型 | 说明 |
|------|------|------|
| name | Char | 订单号 |
| session_id | Many2one | 关联会话 |
| table_id | Many2one | 关联餐桌 |
| pos_order_id | Many2one | 关联的 POS 订单 |
| state | Selection | 状态（购物车/已下单/制作中/可加菜/已结账） |
| line_ids | One2many | 订单行 |
| total_amount | Float | 总金额 |

### qr.order.line - 订单行

| 字段 | 类型 | 说明 |
|------|------|------|
| order_id | Many2one | 关联订单 |
| product_id | Many2one | 菜品 |
| qty | Float | 数量 |
| price_unit | Float | 单价 |
| subtotal | Float | 小计 |
| batch_number | Integer | 批次号（1=首次，2+=加菜） |
| note | Char | 备注 |

---

## API 接口

### 初始化

```
POST /qr/api/init
Params: table_token, access_token, lang
```

### 获取菜单

```
POST /qr/api/menu
Params: table_token, access_token, lang
```

### 添加到购物车

```
POST /qr/api/cart/add
Params: table_token, access_token, product_id, qty, note
```

### 更新购物车

```
POST /qr/api/cart/update
Params: table_token, access_token, line_id, qty
```

### 提交订单

```
POST /qr/api/order/submit
Params: table_token, access_token, note
```

### 加菜

```
POST /qr/api/order/add_items
Params: table_token, access_token, items
```

### 获取订单状态

```
POST /qr/api/order/status
Params: table_token, access_token
```

---

## 产品配置

### 启用扫码点餐

1. 编辑产品
2. 切换到 **QR Ordering / 扫码点餐** 标签页
3. 勾选 **Available for QR Ordering**
4. 可选：添加简短描述、视频、标签

### 菜品标签

预设标签：
- 🌶️ 辣
- 🥬 素食
- 👍 推荐
- ✨ 新品
- 🔥 人气
- 💚 健康

可在 **扫码点餐** > **配置** > **菜品标签** 中管理

---

## 订单状态流程

```
购物车(cart) → 已下单(ordered) → 制作中(cooking) → 可加菜(serving) → 已结账(paid)
```

- **购物车**: 客户正在选菜
- **已下单**: 客户提交订单，等待打印
- **制作中**: 小票已打印，厨房制作中
- **可加菜**: 可继续点餐
- **已结账**: POS 结账完成

---

## 防恶意点餐机制

1. **动态 Token**: 每次扫码生成新的 session，包含唯一 access_token
2. **有效期限制**: session 默认 4 小时有效
3. **单桌单会话**: 同一餐桌同时只能有一个活跃会话
4. **定时清理**: 每小时自动清理过期会话

---

## 与 YLHC 打印集成

模块通过 `_trigger_print` 方法触发打印。需要配置：

1. 确保 `ylhc_print_manager` 模块已安装
2. 配置打印路由规则
3. 订单提交/加菜时自动触发打印

---

## 多语言支持

支持语言：
- 🇨🇳 中文 (zh_CN)
- 🇯🇵 日本語 (ja_JP)
- 🇺🇸 English (en_US)

客户端自动检测浏览器语言，也可手动切换。

---

## 技术栈

- **后端**: Odoo 18.0 (Python)
- **前端**: 原生 JavaScript + CSS
- **模板**: QWeb
- **实时通信**: Odoo Bus

---

## 文件结构

```
qr_ordering/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── qr_table.py          # 餐桌模型
│   ├── qr_session.py        # 会话模型
│   ├── qr_order.py          # 订单模型
│   └── product_template.py  # 产品扩展
├── controllers/
│   ├── __init__.py
│   └── qr_ordering_controller.py  # API 控制器
├── views/
│   ├── qr_table_views.xml
│   ├── qr_session_views.xml
│   ├── qr_order_views.xml
│   ├── product_views.xml
│   ├── qr_ordering_menus.xml
│   └── qr_ordering_templates.xml
├── static/
│   └── src/
│       ├── css/
│       │   └── qr_ordering.css
│       └── js/
│           └── qr_ordering.js
├── security/
│   └── ir.model.access.csv
└── data/
    └── qr_ordering_data.xml
```

---

## 开发说明

### 自定义样式

编辑 `static/src/css/qr_ordering.css`

### 自定义逻辑

编辑 `static/src/js/qr_ordering.js`

### 添加新 API

在 `controllers/qr_ordering_controller.py` 中添加新路由

---

## 常见问题

### Q: 二维码被分享后会有安全问题吗？

A: 每次扫码会创建新的会话，旧的会话会被关闭。同时有 4 小时有效期限制。

### Q: 如何处理网络断开的情况？

A: 前端会缓存购物车数据，重新连接后可继续操作。

### Q: 能否支持在线支付？

A: 当前版本支持到店支付。在线支付功能可后续扩展。

---

## 版本历史

### 18.0.1.0.0 (2026-01-05)
- 初始版本
- 基础点餐功能
- POS 集成
- 多语言支持
- 防恶意机制

---

## License

LGPL-3



