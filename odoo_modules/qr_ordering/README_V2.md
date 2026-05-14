# QR Ordering V2 - 移动端极致体验版

## 🎯 设计目标

基于现有 QR Ordering 模块（Odoo 18 + QWeb + Vanilla JS），实现移动端极致体验版 UI，**不引入前端框架，不修改数据库结构**，仅通过前端优化提升用户体验。

---

## 📋 核心特性

### ✅ 已实现功能

1. **PinnedCarousel (置顶视频轮播)**
   - 自动播放，4-6 秒切换
   - 默认静音 + `playsinline`
   - 仅当前 slide 可见时播放
   - Dots 指示器 + 进度条
   - 右下角步进器直接加购
   - 🔇 和 AUTO 标识

2. **RecoRail (推荐横向滑动)**
   - 横向滑动卡片列表
   - 视频封面 + ▶ 图标
   - 点击打开 PiP 浮层

3. **PiP Video Overlay (画中画视频)**
   - 右下角浮层（不遮挡底栏）
   - Play/Pause、Mute、Close 控件
   - 单实例管理
   - 打开时才加载视频资源

4. **StickyCategoryChips (吸顶分类标签)**
   - Sticky 定位，吸顶效果
   - 点击 scrollTo 对应分类
   - 横向滑动支持
   - Active 高亮

5. **ProductGrid (两列商品网格)**
   - Mobile 两列，超小屏 1 列
   - 卡片内步进器（与购物车同步）
   - stopPropagation 避免误触
   - Aspect ratio 1:1 图片

6. **BottomCartBar (固定底栏)**
   - `position: fixed` 底部
   - 显示件数 + 总金额
   - "查看订单 →" 按钮
   - Safe area 支持 (`env(safe-area-inset-bottom)`)
   - 空购物车时按钮禁用但可见

7. **Feature Flag (功能开关)**
   - URL 参数: `?menu_ui_v2=1`
   - 系统参数: `qr_ordering.menu_ui_v2 = true`
   - 默认使用 V1，可手动切换

---

## 🚀 如何启用 V2

### 方法 1: URL 参数（临时）

```
https://demo.nagashiro.top/qr/order/<token>?menu_ui_v2=1
```

### 方法 2: 系统参数（全局默认）

1. 进入 Odoo 后台 → **设置** → **技术** → **系统参数**
2. 创建新参数：
   - **Key**: `qr_ordering.menu_ui_v2`
   - **Value**: `true`
3. 保存后，所有 QR 点餐页面默认使用 V2

### 方法 3: Controller 逻辑（代码级）

在 `qr_ordering_controller.py` 中修改默认值：

```python
# Line 70-73
use_v2 = kwargs.get('menu_ui_v2') == '1' or request.httprequest.args.get('menu_ui_v2') == '1'
if not use_v2:
    use_v2 = request.env['ir.config_parameter'].sudo().get_param('qr_ordering.menu_ui_v2', 'false') == 'true'
```

---

## 📂 文件结构

```
qr_ordering/
├── views/
│   ├── qr_ordering_templates.xml          # V1 模板（原有）
│   ├── qr_ordering_templates_v2.xml       # V2 模板（新增）✅
│   └── ...
├── static/src/
│   ├── css/
│   │   ├── qr_ordering.css                # V1 样式（原有）
│   │   └── qr_ordering_v2.css             # V2 样式（新增）✅
│   └── js/
│       ├── qr_ordering.js                 # V1 逻辑（原有）
│       └── qr_ordering_v2.js              # V2 逻辑（新增）✅
├── controllers/
│   └── qr_ordering_controller.py          # 路由（已修改，支持 feature flag）✅
├── models/
│   └── product_template.py                # 产品模型（已有字段，无需改）✅
└── __manifest__.py                        # 清单（已添加 V2 资源）✅
```

---

## 🎨 UI 结构

### V2 页面布局（从上到下）

```
┌─────────────────────────────────┐
│  Header (店名/桌号 + 搜索)      │  ← Sticky
├─────────────────────────────────┤
│  PinnedCarousel (视频轮播)      │  ← 仅当有 qr_pinned=True 且 video_url 时显示
│  - 自动播放 4-6s                │
│  - 静音 + playsinline           │
│  - Dots + 进度条 + 步进器       │
├─────────────────────────────────┤
│  RecoRail (推荐横向滑动)        │  ← 仅当有 qr_highlight=True 时显示
│  - 横向滑动卡片                │
│  - 点击 → PiP 视频              │
├─────────────────────────────────┤
│  CategoryChips (分类标签)       │  ← Sticky（吸顶）
│  - 横向滑动                    │
│  - 点击 scrollTo 分类          │
├─────────────────────────────────┤
│  ProductGrid (两列商品)         │  ← 主要滚动区域
│  - 2 列（小屏 1 列）           │
│  - 卡片内步进器                │
│  - Aspect ratio 1:1            │
├─────────────────────────────────┤
│  BottomCartBar (固定底栏)       │  ← Fixed（固定）
│  - 件数 + 总金额               │
│  - "查看订单 →" 按钮           │
│  - Safe area 支持              │
└─────────────────────────────────┘

┌──────────┐
│ PiP Video│  ← 右下角浮层（不遮挡底栏）
└──────────┘
```

---

## 🔑 关键技术细节

### 1. 数据分组逻辑

```javascript
// V2 在 JS 中分组，无需后端改动
state.pinnedProducts = state.menu.products
    .filter(p => p.pinned && p.video_url)  // 必须有视频
    .sort((a, b) => a.pinned_sequence - b.pinned_sequence);

state.highlightProducts = state.menu.products
    .filter(p => p.highlight && !p.pinned)  // 去重 pinned
    .slice(0, 10);
```

### 2. 视频自动播放策略

```javascript
// Carousel: 仅当前 slide 播放
function playCarouselVideo(index) {
    const video = $carouselTrack.querySelectorAll('video')[index];
    if (video) {
        video.play().catch(() => {
            console.log('[QR V2] Autoplay blocked, showing poster');
        });
    }
}

// 切换 slide 时暂停前一个
const currentVideos = $carouselTrack.querySelectorAll('video');
currentVideos[state.currentCarouselIndex]?.pause();
```

### 3. PiP Video 单实例

```javascript
// 同一时间只能打开一个 PiP
function openPip(product) {
    state.pipProduct = product;
    state.pipVideoUrl = product.video_url;
    
    $pipVideo.src = state.pipVideoUrl;  // 仅此时加载资源
    $pipVideo.muted = true;
    $pipVideo.play();
    
    $pipOverlay.style.display = 'block';
}

function closePip() {
    $pipVideo.pause();
    $pipVideo.src = '';  // 释放资源
    $pipOverlay.style.display = 'none';
}
```

### 4. Sticky Category Chips

```css
.qr-v2-category-chips {
    position: sticky;
    top: var(--qr-v2-header-height);  /* Header 下方吸顶 */
    z-index: 99;
}
```

### 5. Safe Area 支持

```css
.qr-v2-bottom-bar {
    position: fixed;
    bottom: 0;
    padding-bottom: calc(12px + env(safe-area-inset-bottom, 0px));  /* iPhone X+ */
}

/* HTML meta */
<meta name="viewport" content="viewport-fit=cover"/>
```

### 6. 步进器阻止冒泡

```html
<button onclick="event.stopPropagation(); window.qrV2.incrementProduct(${product.id})">
    +
</button>
```

### 7. 响应式布局

```css
/* 默认两列 */
.qr-v2-product-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
}

/* 超小屏单列 */
@media (max-width: 375px) {
    .qr-v2-product-grid {
        grid-template-columns: 1fr;
    }
}
```

---

## ✅ 自测清单

在部署后，使用以下清单逐项验证：

### iPhone 尺寸测试
- [ ] 布局不挤压、不横向溢出
- [ ] 底栏不被遮挡（Safe area 生效）
- [ ] 地址栏收起/出现时不跳动

### PinnedCarousel
- [ ] 轮播 4-6 秒自动切换
- [ ] 视频默认静音
- [ ] 仅当前 slide 播放，离开停止
- [ ] Autoplay 失败降级为封面
- [ ] Dots 指示器同步
- [ ] 步进器加购实时更新

### RecoRail + PiP
- [ ] 横向滑动流畅
- [ ] 点击卡片打开 PiP
- [ ] PiP 不遮挡底栏
- [ ] Play/Pause/Mute 控件可用
- [ ] Close 关闭并释放资源

### CategoryChips
- [ ] 吸顶效果正常
- [ ] 点击 chip 切换分类
- [ ] 横向滑动流畅
- [ ] Active 高亮正确

### ProductGrid
- [ ] 两列稳定（小屏 1 列）
- [ ] 图片 1:1 不变形
- [ ] 步进器点击不误触卡片
- [ ] 加购后数量实时更新

### BottomCartBar
- [ ] 固定底部，不随滚动移动
- [ ] 件数 + 金额实时更新
- [ ] 空购物车时按钮禁用（但可见）
- [ ] "查看订单" 打开 Modal

### 购物车流程
- [ ] 加购后购物车更新
- [ ] 打开 Modal 显示明细
- [ ] 提交订单成功
- [ ] 刷新后购物车恢复

---

## 🐛 已知问题 & 待优化

### P0（必须修复）
- ✅ 无

### P1（建议优化）
- [ ] **ScrollSpy**: CategoryChips 根据滚动自动高亮当前分类（需 IntersectionObserver）
- [ ] **Carousel 手势**: 支持左右滑动切换 slide
- [ ] **PiP 拖拽**: 允许用户拖动 PiP 位置
- [ ] **离线缓存**: Service Worker 缓存静态资源

### P2（Nice to have）
- [ ] **骨架屏**: 加载时显示骨架屏而非 Spinner
- [ ] **懒加载**: 图片/视频懒加载
- [ ] **动画优化**: 添加页面过渡动画
- [ ] **A/B 测试**: V1 vs V2 转化率对比

---

## 📊 性能指标

### 目标指标（移动端 4G）
- **FCP (First Contentful Paint)**: < 1.5s
- **LCP (Largest Contentful Paint)**: < 2.5s
- **CLS (Cumulative Layout Shift)**: < 0.1
- **TTI (Time to Interactive)**: < 3.5s

### 优化措施
1. ✅ Inline critical CSS（Header + BootGuard）
2. ✅ 延迟加载视频（仅当前 slide 或 PiP 打开时）
3. ✅ 图片使用 Odoo 内置压缩（`image_256`）
4. ✅ Cache-Control headers（CSS/JS 强缓存）
5. ⏳ WebP 图片格式（待添加）
6. ⏳ CDN 加速（待配置）

---

## 🔄 V1 vs V2 对比

| 维度 | V1（原有） | V2（新版） |
|------|-----------|-----------|
| 布局 | 左侧边栏 + 右内容区 | 纯移动端单列流式 |
| 视频 | 无轮播，需点击查看 | 置顶轮播 + PiP 浮层 |
| 推荐 | 无专区 | 横向滑动 RecoRail |
| 分类 | 左侧固定 | 吸顶 Chips |
| 商品 | 2 列（小屏可能 1 列） | 强制 2 列（超小屏 1 列） |
| 底栏 | Sticky | Fixed + Safe area |
| 加购 | 点击卡片 → Modal | 卡片内步进器 |
| 性能 | 良好 | 优化（延迟加载） |
| 兼容性 | 桌面 + 移动 | 移动优先 |

---

## 📝 部署步骤

### 1. 更新模块

```bash
# SSH 登录服务器
ssh ubuntu@54.65.127.141

# 升级模块
cd /opt/seisei-project
docker exec -it <odoo_container> odoo -u qr_ordering --stop-after-init

# 重启服务
docker restart <odoo_container>
```

### 2. 启用 V2（系统参数）

```python
# Odoo Shell
env['ir.config_parameter'].sudo().set_param('qr_ordering.menu_ui_v2', 'true')
```

### 3. 验证

```bash
# 访问任意 QR 点餐页面
# 应自动使用 V2 模板
# 或手动添加 ?menu_ui_v2=1 测试
```

---

## 🤝 贡献指南

### 文件修改记录
- ✅ `views/qr_ordering_templates_v2.xml` - 新建 V2 模板
- ✅ `static/src/css/qr_ordering_v2.css` - 新建 V2 样式
- ✅ `static/src/js/qr_ordering_v2.js` - 新建 V2 逻辑
- ✅ `controllers/qr_ordering_controller.py` - 添加 feature flag
- ✅ `__manifest__.py` - 添加 V2 资源声明
- ✅ `models/product_template.py` - 无需改动（字段已存在）

### 代码规范
- **不引入前端框架**: 保持 Vanilla JS
- **不修改 DB**: 复用现有字段
- **向后兼容**: V1 和 V2 共存，可随时切换
- **移动优先**: 桌面端降级为 V1

---

## 📞 联系方式

- **项目**: QR Ordering for Odoo 18
- **版本**: V2 (2026-01-05)
- **文档**: README_V2.md
- **技术栈**: Odoo 18 + QWeb + Vanilla JS + CSS3

---

## 🎉 总结

V2 版本在不改动后端和数据库的前提下，通过纯前端优化实现了：
- 📹 **沉浸式视频体验**（轮播 + PiP）
- 🎯 **精准推荐展示**（RecoRail）
- 🚀 **极致加购体验**（卡片内步进器）
- 📱 **移动端优先**（Safe area + Sticky）
- 🔀 **灵活切换**（Feature flag）

**现在就访问 `?menu_ui_v2=1` 体验吧！** 🎊



