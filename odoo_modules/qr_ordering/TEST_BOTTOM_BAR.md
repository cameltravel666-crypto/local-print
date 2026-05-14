# QR 点餐底部栏 - 测试验证清单

## 🎯 测试目标

验证四态状态机在实际环境中的表现，确保用户体验符合预期。

---

## 📋 四态测试清单

### ✅ 状态 A: 空购物车 + 未下单

**前置条件**:
- 首次访问 QR 点餐页面
- 或清空购物车后且无历史订单

**操作步骤**:
1. 扫描二维码或访问: `https://demo.nagashiro.top/qr/order/[TOKEN]`
2. 页面加载完成，不添加任何商品

**预期结果**:

| 元素 | 状态 | 验证点 |
|------|------|--------|
| **购物车图标** | 显示 | 徽章显示 `0` |
| **金额/件数** | 显示 | `¥0 · 0 件` |
| **状态徽章** | 隐藏 | `display: none` |
| **主按钮** | 禁用 | 文字: `提交订单`, `disabled=true`, 灰色 |
| **次按钮** | 隐藏 | `display: none` |
| **提示语** | 显示 | `请选择菜品` (底部中央) |

**交互测试**:
- [ ] 点击主按钮 → 无反应（已禁用）
- [ ] 点击购物车图标 → 打开购物车弹窗（空态）

**截图标记**: `A_empty_disabled.png`

---

### ✅ 状态 B: 有购物车 + 未下单

**前置条件**:
- 从状态 A 继续
- 或清空购物车后添加商品

**操作步骤**:
1. 点击任意商品的 `+` 按钮，添加 2-3 个商品
2. 观察底栏变化

**预期结果**:

| 元素 | 状态 | 验证点 |
|------|------|--------|
| **购物车图标** | 更新 | 徽章显示实际数量 (如 `3`) |
| **金额/件数** | 更新 | `¥150 · 3 件` (实际金额) |
| **状态徽章** | 隐藏 | `display: none` |
| **主按钮** | 启用 | 文字: `提交订单`, 橙色, 可点击 |
| **次按钮** | 显示 | 文字: `查看购物车`, 可点击 |
| **提示语** | 隐藏 | `display: none` |

**交互测试**:
- [ ] 点击主按钮 → 打开购物车弹窗（显示已添加商品）
- [ ] 点击次按钮 → 打开购物车弹窗
- [ ] 在弹窗中点击 `提交订单` → 提交成功
- [ ] 提交后自动跳转到状态 C

**截图标记**: `B_cart_enabled.png`

---

### ✅ 状态 C: 空购物车 + 已下单

**前置条件**:
- 从状态 B 提交订单成功
- 或有历史订单且购物车为空

**操作步骤**:
1. 在状态 B 完成订单提交
2. 观察底栏变化

**预期结果**:

| 元素 | 状态 | 验证点 |
|------|------|--------|
| **购物车图标** | 重置 | 徽章显示 `0` |
| **金额/件数** | 重置 | `¥0 · 0 件` |
| **状态徽章** | 显示 | `已下单 · #QR001` (绿色徽章) |
| **主按钮** | 启用 | 文字: `去前台支付`, 橙色, 可点击 |
| **次按钮** | 显示 | 文字: `查看订单`, 可点击 |
| **提示语** | 隐藏 | `display: none` |

**交互测试**:
- [ ] 点击主按钮 → 打开"前台结账"弹窗
  - [ ] 弹窗标题: `💳 前台结账`
  - [ ] 显示桌号: `[实际桌号]`
  - [ ] 显示订单号: `QR001`
  - [ ] 显示金额: `¥150` (之前提交的订单金额)
  - [ ] "复制桌号" 按钮可点击 → 点击后显示 `已复制` toast
  - [ ] "复制订单号" 按钮可点击 → 点击后显示 `已复制` toast
  - [ ] "我知道了" 按钮可点击 → 关闭弹窗
- [ ] 点击次按钮 → 打开订单列表（显示刚提交的订单）
- [ ] 点击购物车图标 → 打开购物车弹窗（空态）

**截图标记**: `C_ordered_pay.png`, `C_pay_modal.png`

---

### ✅ 状态 D: 有购物车 + 已下单

**前置条件**:
- 从状态 C 继续
- 订单已存在，再次添加商品

**操作步骤**:
1. 在状态 C 基础上，点击商品 `+` 添加新商品
2. 观察底栏变化

**预期结果**:

| 元素 | 状态 | 验证点 |
|------|------|--------|
| **购物车图标** | 更新 | 徽章显示新添加数量 (如 `2`) |
| **金额/件数** | 更新 | `¥80 · 2 件` (新添加商品金额) |
| **状态徽章** | 显示 | `已下单 · #QR001（可追加）` (绿色徽章) |
| **主按钮** | 启用 | 文字: `追加下单`, 橙色, 可点击 |
| **次按钮** | 显示 | 文字: `查看购物车`, 可点击 |
| **提示语** | 隐藏 | `display: none` |

**交互测试**:
- [ ] 点击主按钮 → 打开购物车弹窗（显示新添加商品）
- [ ] 在弹窗中点击 `提交订单` → 提交成功
- [ ] 提交后返回状态 C（订单号更新为 `QR002`）
- [ ] 点击次按钮 → 打开购物车弹窗
- [ ] 点击购物车图标 → 打开购物车弹窗

**截图标记**: `D_add_more.png`

---

## 🎨 UI 细节验证

### 底栏布局

**桌面端 (>768px)**:
- [ ] 底栏高度: >= 72px
- [ ] 左侧购物车图标 + 金额显示正常
- [ ] 中间状态徽章（如果有）不换行
- [ ] 右侧按钮并排显示，间距合理 (6px)

**移动端 (<=768px)**:
- [ ] 底栏固定在屏幕底部
- [ ] 底部安全区域适配正常（iPhone X/11/12/13/14 系列）
- [ ] 按钮文字不换行
- [ ] 状态徽章不遮挡其他元素

### 按钮样式

**主按钮**:
- [ ] 背景色: `#ff6b35` (橙色)
- [ ] 文字: 白色, 14px, 居中
- [ ] 最小尺寸: 120px × 44px
- [ ] 禁用态: 50% 透明度, 不可点击

**次按钮**:
- [ ] 背景色: 透明
- [ ] 边框: 1px solid `#ddd`
- [ ] 文字: `#333`, 14px, 居中
- [ ] 最小尺寸: 90px × 44px

**状态徽章**:
- [ ] 背景色: `#e8f5e9` (绿色浅)
- [ ] 文字: `#2e7d32` (绿色深), 12px
- [ ] 圆角: 16px
- [ ] 内边距: 4px 10px

### 提示语

- [ ] 位置: 底栏正下方，居中
- [ ] 背景: 半透明黑色 `rgba(0,0,0,0.7)`
- [ ] 文字: 白色, 12px
- [ ] 显示时机: 仅状态 A

---

## 🌍 多语言验证

### 中文 (zh_CN)

- [ ] 提交订单
- [ ] 查看购物车
- [ ] 查看订单
- [ ] 去前台支付
- [ ] 追加下单
- [ ] 已下单
- [ ] （可追加）
- [ ] 请选择菜品
- [ ] 请到前台出示桌号/订单号完成结账
- [ ] 已复制

### 日文 (ja_JP)

切换语言: URL 添加 `?lang=ja_JP` 或页面内切换

- [ ] 注文する (提交订单)
- [ ] カートを見る (查看购物车)
- [ ] 注文を見る (查看订单)
- [ ] レジで支払う (去前台支付)
- [ ] 追加注文 (追加下单)
- [ ] 注文済み (已下单)
- [ ] （追加可） (可追加)

### 英文 (en_US)

切换语言: URL 添加 `?lang=en_US`

- [ ] Submit Order
- [ ] View Cart
- [ ] View Order
- [ ] Pay at Counter
- [ ] Add to Order
- [ ] Ordered
- [ ] (add more)

---

## 📱 设备兼容性

### iOS 设备

| 设备 | Safari | 微信 | 状态 |
|------|--------|------|------|
| iPhone 14 Pro | [ ] | [ ] | - |
| iPhone 13 | [ ] | [ ] | - |
| iPhone SE 2022 | [ ] | [ ] | - |
| iPad Pro 11" | [ ] | [ ] | - |

### Android 设备

| 设备 | Chrome | 微信 | 状态 |
|------|--------|------|------|
| Pixel 7 | [ ] | [ ] | - |
| Samsung S22 | [ ] | [ ] | - |
| 小米 13 | [ ] | [ ] | - |

---

## 🐛 边界情况测试

### 1. 订单号过长

**测试步骤**:
1. 后台修改订单编号规则，生成超长订单号 (如 `QR-2025-01-06-1234567890`)
2. 提交订单，进入状态 C
3. 观察状态徽章显示

**预期结果**:
- [ ] 订单号不换行
- [ ] 超出部分使用 `text-overflow: ellipsis` 省略
- [ ] 或自动缩小字体

### 2. 桌号过长

**测试步骤**:
1. 创建桌号为 `VIP贵宾包厢A区8号桌` 的餐桌
2. 扫码进入
3. 提交订单，打开"前台结账"弹窗

**预期结果**:
- [ ] 桌号完整显示
- [ ] 或换行显示
- [ ] 不遮挡其他元素

### 3. 极大金额

**测试步骤**:
1. 添加高价商品 (如 ¥9999/件)
2. 数量设为 10
3. 提交订单

**预期结果**:
- [ ] 金额显示正常: `¥99990`
- [ ] 不溢出容器
- [ ] 前台支付弹窗金额显示正常

### 4. 网络延迟

**测试步骤**:
1. Chrome DevTools → Network → Throttling → Slow 3G
2. 添加商品到购物车
3. 点击"提交订单"

**预期结果**:
- [ ] 提交中显示 loading 状态
- [ ] 按钮禁用，防止重复提交
- [ ] 提交成功后正确进入状态 C
- [ ] 提交失败显示错误提示

### 5. 多次追加下单

**测试步骤**:
1. 提交第一个订单 (状态 C)
2. 添加商品，提交第二个订单 (状态 C)
3. 再添加商品，提交第三个订单
4. 点击"查看订单"

**预期结果**:
- [ ] 状态徽章始终显示最新订单号
- [ ] 订单列表显示所有订单 (3 个)
- [ ] 每个订单金额正确
- [ ] 总金额 = 所有订单金额之和

---

## 🔍 开发者工具验证

### Console 日志

打开 Chrome DevTools → Console，观察日志输出：

**初始化**:
```javascript
QR Ordering initialized successfully. Build: 2026-01-05T17:25
```

**状态变化**:
```javascript
[Footer State] { state: 'A', cartCount: 0, orderRef: '', totalOrderAmount: 0 }
[Footer State] { state: 'B', cartCount: 3, orderRef: '', totalOrderAmount: 0 }
[Footer State] { state: 'C', cartCount: 0, orderRef: 'QR001', totalOrderAmount: 150 }
[Footer State] { state: 'D', cartCount: 2, orderRef: 'QR001', totalOrderAmount: 150 }
```

**按钮点击**:
```javascript
[Primary Btn] action: submit
[Primary Btn] action: pay
[Secondary Btn] action: cart
[Secondary Btn] action: orders
```

### Network 请求

**提交订单**:
```
POST /qr/api/order/submit
Request: { "note": "" }
Response: { "success": true, "data": { "id": 123, "name": "QR001", "total_amount": 150, ... } }
```

**获取订单列表**:
```
GET /qr/api/orders?access_token=...
Response: { "success": true, "data": [ { "id": 123, "name": "QR001", ... } ] }
```

### 元素检查

**状态 A**:
```html
<button id="qr-primary-btn" class="qr-cart-btn primary" disabled data-action="submit">提交订单</button>
<button id="qr-secondary-btn" style="display: none;" data-action="cart">查看购物车</button>
<div id="qr-order-status-badge" style="display: none;">...</div>
<div id="qr-footer-hint" style="display: block;">请选择菜品</div>
```

**状态 C**:
```html
<button id="qr-primary-btn" class="qr-cart-btn primary" data-action="pay">去前台支付</button>
<button id="qr-secondary-btn" style="display: block;" data-action="orders">查看订单</button>
<div id="qr-order-status-badge" style="display: flex;">
    <span id="qr-status-text">已下单 · #QR001</span>
</div>
<div id="qr-footer-hint" style="display: none;">...</div>
```

---

## ✅ 验收标准

### 必须通过 (P0)

- [ ] 四个状态 (A/B/C/D) 全部正常切换
- [ ] 主按钮文字与功能符合预期
- [ ] 次按钮文字与功能符合预期
- [ ] "去前台支付" 弹窗显示正确信息
- [ ] 复制功能正常工作
- [ ] 移动端底部安全区域适配
- [ ] 中文界面文案正确

### 应该通过 (P1)

- [ ] 日文、英文界面文案正确
- [ ] 所有边界情况处理正确
- [ ] Console 无错误日志
- [ ] 网络延迟情况下体验良好

### 可选通过 (P2)

- [ ] 动画流畅
- [ ] 点击反馈明显
- [ ] 字体大小最优

---

## 📊 测试报告模板

### 测试环境

- **测试日期**: 2025-01-XX
- **测试人员**: [姓名]
- **测试设备**: iPhone 14 / Chrome 120
- **测试环境**: https://demo.nagashiro.top/qr/order/[TOKEN]

### 测试结果

| 测试项 | 状态 | 备注 |
|--------|------|------|
| 状态 A | ✅ / ❌ | - |
| 状态 B | ✅ / ❌ | - |
| 状态 C | ✅ / ❌ | - |
| 状态 D | ✅ / ❌ | - |
| 多语言 | ✅ / ❌ | - |
| 移动端适配 | ✅ / ❌ | - |
| 边界情况 | ✅ / ❌ | - |

### 发现的问题

1. **问题描述**: [详细描述]
   - **重现步骤**: [1. ... 2. ... 3. ...]
   - **预期结果**: [应该...]
   - **实际结果**: [实际上...]
   - **严重程度**: P0 / P1 / P2
   - **截图**: [附件]

### 总结

- **通过率**: XX / YY (ZZ%)
- **总体评价**: ✅ 通过 / ⚠️ 有待改进 / ❌ 未通过
- **建议**: [改进建议]

---

## 🚀 快速测试命令

### 生成测试 token

```bash
# SSH 登录服务器
ssh -i ~/Projects/Pem/odoo-2025.pem ubuntu@54.65.127.141

# 进入 Odoo shell
docker exec -it seisei-project-web-1 odoo shell -d "opss.seisei.tokyo"

# 查询测试餐桌 token
env['qr.table'].search([('name', '=', '测试桌')]).qr_token
```

### 测试 URL 模板

```
基础 URL: https://demo.nagashiro.top/qr/order/[TOKEN]

中文: https://demo.nagashiro.top/qr/order/[TOKEN]?lang=zh_CN
日文: https://demo.nagashiro.top/qr/order/[TOKEN]?lang=ja_JP
英文: https://demo.nagashiro.top/qr/order/[TOKEN]?lang=en_US
调试: https://demo.nagashiro.top/qr/order/[TOKEN]?debug=1
```

### 清除缓存

```bash
# 浏览器强制刷新
Ctrl/Cmd + Shift + R

# 清除本地存储
localStorage.clear()
sessionStorage.clear()
```

---

## 📞 联系支持

- **技术文档**: `/BOTTOM_BAR_REFACTOR_REPORT.md`
- **调试日志**: Chrome DevTools → Console
- **服务器日志**: `docker logs seisei-project-web-1 --tail 100`


