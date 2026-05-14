# QR 点餐购物车价格计算 Bug 分析

## 🐛 问题描述

根据界面截图，购物车显示：
- **商品**: "1番人気 鮭といくらの親子土鍋ごはん"
- **单价**: ¥2760
- **数量**: 2
- **总价显示**: ¥2760 ❌（应该是 ¥5520）

## 🔍 根本原因

### V2 版本代码错误

在 `static/src/js/qr_ordering_v2.js` 中，购物车数据映射使用了错误的字段名：

**第 188-194 行（初始化时）**:
```javascript
state.cart = currentOrder.lines.map(line => ({
    productId: line.product_id,
    name: line.product_name,
    price: line.price,  // ❌ 错误：应该是 line.price_unit
    qty: line.qty,
    note: line.note || ''
}));
```

**第 504-511 行（更新购物车时）**:
```javascript
state.cart = order.lines.map(line => ({
    productId: line.product_id,
    name: line.product_name,
    price: line.price,  // ❌ 错误：应该是 line.price_unit
    qty: line.qty,
    note: line.note || ''
}));
```

### 后端返回的数据结构

在 `controllers/qr_ordering_controller.py` 的 `_serialize_order_line` 方法（第 542-554 行）中：

```python
def _serialize_order_line(self, line):
    """序列化订单行数据"""
    return {
        'id': line.id,
        'product_id': line.product_id.id,
        'product_name': line.product_name,
        'qty': line.qty,
        'price_unit': line.price_unit,  # ✅ 正确的字段名
        'subtotal': line.subtotal,
        'note': line.note or '',
        'batch_number': line.batch_number,
        'state': line.state,
    }
```

**后端返回的字段是 `price_unit`，不是 `price`！**

### V1 版本的正确实现

在 `static/src/js/qr_ordering.js` 中，V1 版本正确使用了 `price_unit`：

```javascript
// 第 717-725 行
state.cart = cartOrder.lines.map(l => ({
    lineId: l.id,
    productId: l.product_id,
    name: l.product_name,
    qty: l.qty,
    price: l.price_unit,  // ✅ 正确
    note: l.note,
}));
```

## 💥 影响

1. **价格计算错误**: `line.price` 为 `undefined`，导致：
   - `item.price * item.qty` = `undefined * 2` = `NaN` 或 `0`
   - 总价计算失败，可能显示为 0 或 NaN

2. **显示错误**: 
   - 购物车弹窗中的单价显示可能为空或错误
   - 底部栏总价显示错误
   - 购物车弹窗总价显示错误

## 🔧 修复方案

### 方案 1: 修改 V2 代码使用正确的字段名（推荐）

修改 `static/src/js/qr_ordering_v2.js` 中的两处：

**修复 1: 第 191 行**
```javascript
// 修改前
price: line.price,

// 修改后
price: line.price_unit,
```

**修复 2: 第 508 行**
```javascript
// 修改前
price: line.price,

// 修改后
price: line.price_unit,
```

### 方案 2: 修改后端返回字段名（不推荐）

修改 `controllers/qr_ordering_controller.py` 的 `_serialize_order_line` 方法，将 `price_unit` 改为 `price`。但这会影响 V1 版本，需要同时修改 V1 代码。

## 📋 修复检查清单

修复后需要验证：

- [ ] 购物车弹窗中单价正确显示
- [ ] 购物车弹窗中单项总价正确（单价 × 数量）
- [ ] 购物车弹窗底部总价正确
- [ ] 底部栏总价正确
- [ ] 数量变化时总价实时更新
- [ ] 多个商品时总价累加正确

## 🧪 测试用例

1. **单个商品，数量 1**:
   - 单价: ¥2760
   - 数量: 1
   - 期望总价: ¥2760

2. **单个商品，数量 2**:
   - 单价: ¥2760
   - 数量: 2
   - 期望总价: ¥5520

3. **多个商品**:
   - 商品 A: ¥2760 × 2 = ¥5520
   - 商品 B: ¥1000 × 1 = ¥1000
   - 期望总价: ¥6520

## 📝 相关代码位置

- **V2 前端代码**: `static/src/js/qr_ordering_v2.js`
  - 第 191 行: 初始化购物车数据映射
  - 第 508 行: 更新购物车数据映射
  - 第 521 行: 总价计算逻辑（正确）
  - 第 582 行: 购物车弹窗总价计算（正确）

- **后端代码**: `controllers/qr_ordering_controller.py`
  - 第 542-554 行: `_serialize_order_line` 方法

- **V1 参考**: `static/src/js/qr_ordering.js`
  - 第 722 行: 正确的字段名使用

## ✅ 修复优先级

**P0 - 紧急**: 这是一个严重的价格显示错误，会导致用户看到错误的总价，可能影响订单金额和用户体验。

