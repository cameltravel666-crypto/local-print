# QR 点餐修复报告

## A. 代码定位

### 关键词搜索结果

#### 1. "购物车为空 / cart empty"
- **位置**: `static/src/js/qr_ordering.js:1119-1134`
  - 函数: `renderCartItems()`
  - 空态处理逻辑已存在，但需要确保合计强制为0

#### 2. "合计 / total / subtotal"
- **位置**: 
  - `views/qr_ordering_templates.xml:220-221` - 合计显示节点
  - `static/src/js/qr_ordering.js:1161-1162` - 合计计算逻辑
  - `static/src/js/qr_ordering.js:1258` - 底部栏金额计算

#### 3. "已下单 / orders / order list"
- **位置**:
  - `views/qr_ordering_templates.xml:228-240` - 已下单Modal模板
  - `static/src/js/qr_ordering.js:1165-1205` - `renderOrders()` 函数
  - `static/src/js/qr_ordering.js:1184` - 短订单号处理

#### 4. "前台结账 / checkout"
- **位置**:
  - `views/qr_ordering_templates.xml:167-197` - 前台买单弹窗模板
  - `static/src/js/qr_ordering.js:1423-1448` - `openPayModal()` / `closePayModal()`

#### 5. "QRO- / orderId"
- **位置**:
  - `static/src/js/qr_ordering.js:1496-1505` - `getShortOrderRef()` 函数
  - `models/qr_order.py:155` - 订单号生成逻辑

#### 6. 底部固定条
- **位置**:
  - `views/qr_ordering_templates.xml:140-165` - 底部栏HTML结构
  - `static/src/js/qr_ordering.js:290-380` - `OverlayManager` 单例管理器
  - `static/src/css/qr_ordering.css:369-385` - 底部栏样式

### 关键文件列表

#### QWeb 模板文件
1. **`views/qr_ordering_templates.xml`**
   - 第 140-165 行: 底部固定条结构
   - 第 167-197 行: 前台买单弹窗
   - 第 208-226 行: 已选菜品Modal（购物车）
   - 第 228-240 行: 已点菜品Modal（已下单列表）
   - 第 220-221 行: 合计显示节点

#### JavaScript 文件
1. **`static/src/js/qr_ordering.js`**
   - 第 290-380 行: `OverlayManager` 单例管理器
   - 第 958-1023 行: `submitOrder()` - 提交订单
   - 第 1115-1163 行: `renderCartItems()` - 渲染购物车
   - 第 1165-1205 行: `renderOrders()` - 渲染已下单列表
   - 第 1242-1368 行: `getFooterState()` / `updateCartUI()` - 底部栏状态管理
   - 第 1378-1418 行: 按钮事件处理
   - 第 1423-1448 行: `openPayModal()` / `closePayModal()`
   - 第 1496-1505 行: `getShortOrderRef()` - 短订单号
   - 第 1696-1715 行: `openCartModal()` / `closeCartModal()` / `openOrderModal()`

#### CSS 文件
1. **`static/src/css/qr_ordering.css`**
   - 第 369-385 行: 底部栏基础样式
   - 第 1301 行: `.qr-hidden` 隐藏类

### 关键函数/模板节点

| 功能 | 文件 | 位置 | 说明 |
|------|------|------|------|
| 购物车空态处理 | `qr_ordering.js` | `renderCartItems()`:1119-1134 | 需要确保合计强制为0 |
| 合计计算 | `qr_ordering.js` | `renderCartItems()`:1161-1162 | 从state.cart计算 |
| 底部栏隐藏 | `qr_ordering.js` | `OverlayManager.open()`:308-312 | 打开overlay时隐藏 |
| 底部栏显示 | `qr_ordering.js` | `OverlayManager.close()`:329-333 | 关闭overlay时显示 |
| 弹窗单例管理 | `qr_ordering.js` | `OverlayManager`:290-380 | 确保只有一个overlay |
| 短订单号 | `qr_ordering.js` | `getShortOrderRef()`:1496-1505 | 提取短号显示 |
| 已下单列表渲染 | `qr_ordering.js` | `renderOrders()`:1165-1205 | 需要优化显示格式 |
| 类别空态 | `qr_ordering.js` | `renderProducts()`:1064-1073 | 已有部分实现，需增强 |
| 菜品数量badge | `qr_ordering.js` | `renderProducts()`:1082-1090 | 已有部分实现 |

---

## B. 实现改动

### P0-1: 购物车空态合计不为0的bug修复

**修改文件**: `static/src/js/qr_ordering.js`

1. **`renderCartItems()` 函数 (1119-1134行)**
   - 空态时强制合计为0
   - 隐藏备注区
   - 禁用下单按钮，主CTA变为"去点餐"
   ```javascript
   // P0-1: 确保合计显示为 0
   const $totalAmount = document.getElementById('qr-cart-total-amount');
   if ($totalAmount) $totalAmount.textContent = `${t('currency')}0`;
   
   // 主CTA变为"去点餐"
   if ($submitBtn) {
       $submitBtn.disabled = true;
       $submitBtn.textContent = t('go_to_menu');
       $submitBtn.onclick = () => OverlayManager.close();
   }
   ```

2. **`updateCartUI()` 函数 (1272-1274行)**
   - 确保空购物车时金额为0
   ```javascript
   const totalAmount = state.cart.length === 0 ? 0 : state.cart.reduce((sum, item) => sum + item.price * item.qty, 0);
   ```

### P0-2: 底部固定条与sheet同时存在导致遮挡

**修改文件**: `static/src/js/qr_ordering.js`, `static/src/css/qr_ordering.css`

1. **`OverlayManager.open()` 函数 (308-312行)**
   - 打开overlay时自动隐藏底部栏
   ```javascript
   // P0-3: 隐藏底部栏
   const $footer = document.getElementById('qr-cart-footer');
   if ($footer) {
       $footer.classList.add('qr-hidden');
   }
   ```

2. **`OverlayManager.close()` 函数 (329-333行)**
   - 关闭overlay时恢复底部栏
   ```javascript
   // P0-3: 恢复底部栏
   const $footer = document.getElementById('qr-cart-footer');
   if ($footer) {
       $footer.classList.remove('qr-hidden');
   }
   ```

3. **CSS样式 (1301-1303行)**
   ```css
   .qr-bottom-bar.qr-hidden {
       display: none !important;
   }
   ```

### P0-3: 弹窗叠层问题修复

**修改文件**: `static/src/js/qr_ordering.js`

- **`OverlayManager` 单例管理器 (290-380行)**
  - 已实现：打开新overlay前自动关闭旧overlay
  - 下单成功使用toast（`showOrderStatusToast()`），不叠加modal

### P0-4: 金额口径一致

**修改文件**: `static/src/js/qr_ordering.js`

1. **底部条金额代表【当前购物车】**
   - `updateCartUI()` 从 `state.cart` 计算
   - 下单成功后 `state.cart = []`，金额自动清零

2. **前台结账sheet打开时底部条隐藏**
   - `openPayModal()` 通过 `OverlayManager.open('pay')` 自动隐藏底部条
   - 结账金额从 `footerState.totalOrderAmount` 获取（所有未结订单总额）

### P1-5: 类别空态增强

**修改文件**: `static/src/js/qr_ordering.js`, `static/src/css/qr_ordering.css`

1. **`renderProducts()` 函数 (1064-1073行)**
   ```javascript
   // P1-5: 类别空态增强
   if (products.length === 0) {
       const hasHighlight = state.products.some(p => p.highlight);
       const hasOrders = state.orders && state.orders.length > 0;
       $products.innerHTML = `
           <div class="qr-empty-state">
               <div class="qr-empty-icon">🍽️</div>
               <div class="qr-empty-title">${t('no_products')}</div>
               <div class="qr-empty-actions">
                   <button class="qr-empty-btn" onclick="QrOrdering.selectCategory('all')">${t('back_to_all')}</button>
                   ${hasHighlight ? `<button class="qr-empty-btn" onclick="QrOrdering.selectCategory('all'); QrOrdering.filterHighlight();">${t('view_recommended')}</button>` : ''}
                   ${hasOrders ? `<button class="qr-empty-btn" onclick="QrOrdering.openOrderModal();">${t('view_orders')}</button>` : ''}
               </div>
           </div>
       `;
   }
   ```

2. **CSS样式 (1347-1362行)**
   ```css
   .qr-empty-actions {
       display: flex;
       flex-direction: column;
       gap: 12px;
       margin-top: 24px;
       width: 100%;
       max-width: 280px;
   }
   ```

3. **新增公共API方法**
   ```javascript
   filterHighlight() {
       const highlightProducts = state.products.filter(p => p.highlight);
       if (highlightProducts.length > 0) {
           state.products = highlightProducts;
           renderProducts();
       }
   }
   ```

### P1-6: 菜品卡片显示已点数量

**修改文件**: `static/src/js/qr_ordering.js`

- **`renderProducts()` 函数 (1075-1090行)**
  - 已实现：通过 `cartQtyMap` 显示已加购数量badge
  ```javascript
  const cartQtyMap = {};
  state.cart.forEach(item => {
      cartQtyMap[item.productId] = (cartQtyMap[item.productId] || 0) + item.qty;
  });
  
  ${inCartQty > 0 ? `<div class="qr-product-qty-badge">${inCartQty}</div>` : ''}
  ```

### P1-7: 已下单列表不展示长订单号为主视觉

**修改文件**: `static/src/js/qr_ordering.js`

- **`renderOrders()` 函数 (1211-1235行)**
  ```javascript
  // P1-7: 已下单列表优化（短号/时间/状态/金额，不展示长订单号为主视觉）
  const shortRef = getShortOrderRef(order.name);
  const timeDisplay = formatOrderTime(order.order_time || order.create_time);
  // P1-7: 确保不显示内部编码（下划线、数字key等）
  const displayName = order.name && !order.name.includes('_') ? order.name : shortRef;
  
  // 显示：短号 + 时间 + 状态 + 金额
  // 长订单号只在复制按钮的title中
  <button class="qr-order-copy-btn" ... title="${order.name}">${t('copy')}</button>
  ```

### i18n 文本补充

**修改文件**: `static/src/js/qr_ordering.js`

- 添加缺失的多语言文本：
  - `no_products`, `back_to_all`, `view_recommended`, `view_orders`
  - `just_now`, `minutes_ago`
  - `cart_empty_hint`, `go_to_menu`

---

## C. 回归验证

### 最小手工测试清单（移动端为主）

#### 1. 新进入菜单 → 打开购物车（空）→ 合计=0、无下单按钮
- [ ] 进入点餐页面
- [ ] 点击底部栏"查看已选"或购物车图标
- [ ] 验证：购物车sheet显示"还没有选择菜品"
- [ ] 验证：合计显示 ¥0
- [ ] 验证：备注区隐藏
- [ ] 验证：主CTA按钮显示"去点餐"且禁用
- [ ] 验证：底部固定条已隐藏（不遮挡sheet）

#### 2. 加购 1 个商品 → 打开购物车 → 合计正确 → 下单
- [ ] 在菜单页面点击商品"+"按钮
- [ ] 验证：商品卡片显示数量badge（如"1"）
- [ ] 验证：底部栏金额更新
- [ ] 打开购物车sheet
- [ ] 验证：合计 = 单价 × 数量
- [ ] 验证：备注区显示
- [ ] 验证：主CTA按钮显示"下单"且可用
- [ ] 点击"下单"按钮
- [ ] 验证：下单成功toast出现（2-3秒自动消失）
- [ ] 验证：购物车清零
- [ ] 验证：底部栏金额清零
- [ ] 验证：商品卡片数量badge消失

#### 3. 下单成功 toast 出现且不叠层 → 购物车清零
- [ ] 提交订单后
- [ ] 验证：只显示一个toast（订单已提交）
- [ ] 验证：toast自动消失（约4秒）
- [ ] 验证：购物车sheet已关闭
- [ ] 验证：底部栏恢复显示
- [ ] 验证：`state.cart.length === 0`
- [ ] 验证：底部栏金额为 ¥0

#### 4. 打开已下单列表 → 不出现双关闭按钮 → 不展示长订单号为主
- [ ] 点击底部栏"查看已点"按钮
- [ ] 验证：只显示一个关闭按钮（×）
- [ ] 验证：订单列表显示格式：`#XXXX` + 时间 + 状态 + 金额
- [ ] 验证：不显示完整订单号（如 `QRO-20260105-XXXX`）为主视觉
- [ ] 验证：长订单号只在复制按钮的title中
- [ ] 验证：底部栏已隐藏
- [ ] 点击关闭按钮
- [ ] 验证：底部栏恢复显示

#### 5. 打开前台结账 sheet → 底部条隐藏 → 结账金额单口径展示
- [ ] 在有已下单订单的情况下
- [ ] 点击底部栏"去买单"按钮
- [ ] 验证：前台结账sheet打开
- [ ] 验证：底部栏已隐藏
- [ ] 验证：结账金额 = 所有未结订单总额（`totalOrderAmount`）
- [ ] 验证：不出现两个不同金额（底部栏金额已隐藏）
- [ ] 点击"我知道了"关闭
- [ ] 验证：底部栏恢复显示

#### 6. 类别空态增强
- [ ] 选择一个没有商品的类别
- [ ] 验证：显示空态提示"暂无菜品"
- [ ] 验证：显示"返回全部"按钮
- [ ] 如果有推荐商品，验证：显示"查看推荐"按钮
- [ ] 如果有已下单订单，验证：显示"查看已点"按钮
- [ ] 点击"返回全部"，验证：返回全部类别

#### 7. 弹窗叠层测试
- [ ] 打开购物车sheet
- [ ] 在购物车sheet打开状态下，点击"查看已点"
- [ ] 验证：购物车sheet自动关闭，只显示已点sheet
- [ ] 验证：只有一个关闭按钮
- [ ] 验证：底部栏保持隐藏

#### 8. 金额计算准确性
- [ ] 加购商品A（¥100 × 2）
- [ ] 加购商品B（¥50 × 1）
- [ ] 验证：底部栏金额 = ¥250
- [ ] 打开购物车sheet
- [ ] 验证：合计 = ¥250
- [ ] 修改商品A数量为1
- [ ] 验证：合计 = ¥150
- [ ] 验证：底部栏金额同步更新 = ¥150

---

## 修改文件清单

1. **`static/src/js/qr_ordering.js`**
   - 添加i18n文本（3处）
   - 修复 `renderCartItems()` 空态处理
   - 修复 `updateCartUI()` 金额计算
   - 增强 `renderProducts()` 类别空态
   - 优化 `renderOrders()` 订单列表显示
   - 添加 `filterHighlight()` 公共API

2. **`static/src/css/qr_ordering.css`**
   - 添加 `.qr-empty-actions` 样式
   - 优化 `.qr-empty-btn` 样式

---

## 验证要点

- ✅ 购物车空态时合计强制为0
- ✅ 底部栏在overlay打开时隐藏
- ✅ 弹窗单例管理（不叠层）
- ✅ 金额口径一致（底部条=当前购物车）
- ✅ 类别空态有明确下一步操作
- ✅ 菜品卡片显示已点数量
- ✅ 已下单列表不展示长订单号为主视觉

