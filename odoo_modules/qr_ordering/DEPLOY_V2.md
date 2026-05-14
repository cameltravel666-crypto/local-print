# QR Ordering V2 - 部署指南

## 📋 快速部署清单

### ✅ 已完成文件

- [x] `views/qr_ordering_templates_v2.xml` - V2 QWeb 模板
- [x] `static/src/css/qr_ordering_v2.css` - V2 样式
- [x] `static/src/js/qr_ordering_v2.js` - V2 JavaScript
- [x] `controllers/qr_ordering_controller.py` - Feature flag 支持
- [x] `__manifest__.py` - 资源声明

### 🚀 部署步骤

#### Step 1: 部署文件到服务器

```bash
# 方法 A: rsync 同步（推荐）
rsync -avz --delete \
  server-apps/seisei-project/odoo-addons/qr_ordering/ \
  ubuntu@54.65.127.141:/opt/seisei-project/odoo-addons/qr_ordering/

# 方法 B: Git 部署
# 1. Commit 并 push 代码
# 2. 在服务器上 pull

# 方法 C: 手动复制
# 使用 SFTP 工具上传以下文件：
# - views/qr_ordering_templates_v2.xml
# - static/src/css/qr_ordering_v2.css
# - static/src/js/qr_ordering_v2.js
# - controllers/qr_ordering_controller.py (已修改)
# - __manifest__.py (已修改)
```

#### Step 2: 升级 Odoo 模块

```bash
# SSH 登录服务器
ssh ubuntu@54.65.127.141

# 查找 Odoo 容器 ID
docker ps | grep odoo

# 升级模块
docker exec -it <container_id> \
  odoo -u qr_ordering --stop-after-init

# 重启容器
docker restart <container_id>
```

#### Step 3: 启用 V2（3 种方法任选）

**方法 1: URL 参数（临时测试）**
```
https://demo.nagashiro.top/qr/order/<token>?menu_ui_v2=1
```

**方法 2: 系统参数（全局默认）**
```python
# Odoo 后台 → 设置 → 技术 → 系统参数
Key: qr_ordering.menu_ui_v2
Value: true

# 或者通过 Odoo Shell
docker exec -it <container_id> odoo shell
>>> env['ir.config_parameter'].sudo().set_param('qr_ordering.menu_ui_v2', 'true')
>>> env.cr.commit()
>>> exit()
```

**方法 3: 修改代码默认值**
```python
# controllers/qr_ordering_controller.py Line 73
use_v2 = request.env['ir.config_parameter'].sudo().get_param('qr_ordering.menu_ui_v2', 'true') == 'true'
#                                                                                            ^^^^^ 改为 'true'
```

---

## 🧪 验证测试

### 1. 基础验证

```bash
# 访问任意 QR 点餐 URL
curl -I "https://demo.nagashiro.top/qr/order/<token>?menu_ui_v2=1"

# 应返回 200 OK
# 检查响应中是否包含 V2 资源
curl "https://demo.nagashiro.top/qr/order/<token>?menu_ui_v2=1" | grep "qr_ordering_v2"
```

### 2. 功能测试清单

- [ ] **页面加载**: 不白屏，BootGuard 3s 内消失
- [ ] **PinnedCarousel**: 有视频的 pinned 商品显示轮播
- [ ] **RecoRail**: 有 highlight 商品显示推荐横滑
- [ ] **CategoryChips**: 吸顶效果正常，点击切换
- [ ] **ProductGrid**: 两列布局，步进器实时更新
- [ ] **BottomCartBar**: 固定底部，不遮挡内容
- [ ] **PiP Video**: 点击推荐卡片打开 PiP，控件可用
- [ ] **购物车**: 加购 → 查看订单 → 提交 → 成功

### 3. 兼容性测试

- [ ] **iPhone Safari** (iOS 15+)
- [ ] **微信浏览器** (iOS + Android)
- [ ] **Chrome Mobile** (Android)
- [ ] **Desktop Chrome** (应正常显示，但非最优)

---

## 🐛 故障排查

### 问题 1: 页面仍是 V1

**可能原因**:
- Feature flag 未生效
- 浏览器缓存

**解决方法**:
```bash
# 1. 检查系统参数
docker exec -it <container_id> odoo shell
>>> env['ir.config_parameter'].sudo().get_param('qr_ordering.menu_ui_v2')
# 应返回 'true'

# 2. 清除浏览器缓存
# 或添加 ?v=123 强制刷新

# 3. 检查 Controller
# 确认 qr_ordering_controller.py Line 70-76 逻辑正确
```

### 问题 2: CSS/JS 404

**可能原因**:
- 文件未同步
- Odoo assets 未更新

**解决方法**:
```bash
# 1. 检查文件是否存在
docker exec -it <container_id> \
  ls -la /opt/seisei-project/odoo-addons/qr_ordering/static/src/css/qr_ordering_v2.css

# 2. 重新升级模块
docker exec -it <container_id> \
  odoo -u qr_ordering --stop-after-init

# 3. 清除 Odoo assets 缓存
docker exec -it <container_id> rm -rf /var/lib/odoo/sessions/*
docker restart <container_id>
```

### 问题 3: 视频不播放

**可能原因**:
- 产品没有 `qr_video_url` 或 `qr_pinned=True`
- 浏览器 Autoplay 策略阻止

**解决方法**:
```bash
# 1. 检查产品数据
docker exec -it <container_id> odoo shell
>>> products = env['product.template'].search([('qr_pinned', '=', True)])
>>> for p in products:
...     print(f"{p.name}: video={bool(p.qr_video_url)}, pinned={p.qr_pinned}")

# 2. 设置测试产品
>>> product = env['product.template'].browse(1)
>>> product.write({
...     'qr_pinned': True,
...     'qr_pinned_sequence': 10,
...     'qr_video_url': 'https://example.com/video.mp4'  # 或上传到 qr_video
... })
>>> env.cr.commit()

# 3. Autoplay 限制
# V2 已默认 muted + playsinline，应能自动播放
# 如果仍失败，会显示封面（poster）
```

### 问题 4: 步进器不更新

**可能原因**:
- JS 错误
- API 调用失败

**解决方法**:
```bash
# 1. 打开浏览器 DevTools Console
# 查找 [QR V2] 开头的日志
# 检查是否有 API 错误

# 2. 测试 API
curl -X POST "https://demo.nagashiro.top/qr/api/cart/add" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "table_token": "<token>",
      "access_token": "<access_token>",
      "product_id": 1,
      "qty": 1
    }
  }'

# 应返回 {"result": {"success": true, "data": {...}}}
```

---

## 📊 监控指标

### 关键日志

```bash
# 查看 Odoo 日志
docker logs -f <container_id> | grep "QR V2\|menu_ui_v2"

# 应看到类似输出:
# [qr_ordering] Using template: qr_ordering.ordering_page_v2, v2=True
# [qr_ordering] QR V2 initialized successfully
```

### 性能监控

```javascript
// 在浏览器 Console 执行
console.log('V2 Build:', window.QR_ORDERING_V2_BUILD);
console.log('Load Time:', performance.timing.loadEventEnd - performance.timing.navigationStart);
```

---

## 🔄 回滚到 V1

如果 V2 出现问题，可以快速回滚：

```python
# 方法 1: 系统参数
env['ir.config_parameter'].sudo().set_param('qr_ordering.menu_ui_v2', 'false')

# 方法 2: URL 参数
# 不添加 ?menu_ui_v2=1，默认使用 V1

# 方法 3: 代码回滚
# 修改 qr_ordering_controller.py Line 73
use_v2 = False  # 强制使用 V1
```

---

## 📞 支持联系

- **文档**: `README_V2.md`
- **部署指南**: `DEPLOY_V2.md`（本文件）
- **问题反馈**: 创建 Issue 或联系开发团队

---

## ✅ 部署完成检查

部署后，请确认以下所有项：

- [ ] 文件已同步到服务器
- [ ] Odoo 模块已升级
- [ ] Feature flag 已启用
- [ ] V2 页面可访问
- [ ] PinnedCarousel 显示（如有 pinned 产品）
- [ ] RecoRail 显示（如有 highlight 产品）
- [ ] CategoryChips 吸顶正常
- [ ] ProductGrid 两列布局
- [ ] BottomCartBar 固定底部
- [ ] 加购功能正常
- [ ] 购物车 Modal 正常
- [ ] 提交订单成功
- [ ] iPhone 测试通过
- [ ] 微信浏览器测试通过

**全部通过 ✅ → 部署成功！🎉**

---

**部署时间**: 预计 15-30 分钟  
**回滚时间**: 预计 1-2 分钟  
**风险等级**: 低（V1 仍可用，随时回滚）



