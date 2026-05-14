# QR Ordering V2 - 部署记录

## 📅 部署信息

- **部署时间**: 2026-01-05 21:00 (UTC+8)
- **部署版本**: V2 Initial Release
- **服务器**: 54.65.127.141
- **Odoo 版本**: 18.0
- **部署方式**: rsync + Docker restart

---

## ✅ 部署内容

### 新增文件 (4个)

1. ✅ `views/qr_ordering_templates_v2.xml` (12.7 KB)
2. ✅ `static/src/css/qr_ordering_v2.css` (16.6 KB)
3. ✅ `static/src/js/qr_ordering_v2.js` (23.9 KB)
4. ✅ `README_V2.md` + `DEPLOY_V2.md` + `V2_CHECKLIST.md`

### 修改文件 (2个)

1. ✅ `controllers/qr_ordering_controller.py` - 添加 feature flag
2. ✅ `__manifest__.py` - 添加 V2 资源声明

---

## 🚀 部署步骤执行记录

```bash
# 1. 文件同步
rsync -avz server-apps/seisei-project/odoo-addons/qr_ordering/ \
  ubuntu@54.65.127.141:/opt/seisei-project/addons/qr_ordering/

# 同步结果：
✅ __manifest__.py (2.3 KB)
✅ static/src/css/qr_ordering_v2.css (16.6 KB)
✅ static/src/js/qr_ordering_v2.js (23.9 KB)
✅ views/qr_ordering_templates_v2.xml (12.7 KB)

# 2. 重启 Odoo 容器
docker restart 4bfd7858876d

# 3. 等待服务启动
sleep 30

✅ 容器已重启，新代码已生效
```

---

## 🧪 验证清单

### 文件验证 ✅

- [x] V2 模板文件存在于服务器
- [x] V2 CSS 文件存在于服务器
- [x] V2 JS 文件存在于服务器
- [x] `__manifest__.py` 已更新

### 功能验证 ⏳

- [ ] 访问 URL 添加 `?menu_ui_v2=1` 能看到 V2 界面
- [ ] V2 资源文件加载正常（无 404）
- [ ] PinnedCarousel 显示（如有 pinned 产品）
- [ ] RecoRail 显示（如有 highlight 产品）
- [ ] ProductGrid 两列布局
- [ ] BottomCartBar 固定底部
- [ ] 加购功能正常

---

## 📱 测试 URL

### V2 测试 URL（临时）
```
https://demo.nagashiro.top/qr/order/<token>?menu_ui_v2=1
```

### 启用全局默认（可选）
```bash
ssh ubuntu@54.65.127.141
docker exec -it 4bfd7858876d odoo shell

>>> env['ir.config_parameter'].sudo().set_param('qr_ordering.menu_ui_v2', 'true')
>>> env.cr.commit()
>>> exit()
```

---

## 🐛 已知问题

### 模块升级

由于 Odoo 正在运行，无法直接使用 `odoo -u qr_ordering --stop-after-init`。

**解决方案**：
1. 重启容器后代码已生效
2. 如需升级模块数据库结构，请登录 Odoo 后台手动操作：
   - 应用 → 扫码点餐 / QR Code Ordering → 升级

---

## 📊 部署状态

| 项目 | 状态 | 说明 |
|------|------|------|
| 文件同步 | ✅ 完成 | 4 files uploaded |
| 容器重启 | ✅ 完成 | Container 4bfd7858876d |
| 代码生效 | ✅ 完成 | 重启后自动加载 |
| 模块升级 | ⏳ 待手动 | 需登录后台操作 |
| 功能测试 | ⏳ 待测试 | 需访问 URL 验证 |
| 性能测试 | ⏳ 待测试 | Lighthouse + iPhone |
| 兼容性测试 | ⏳ 待测试 | Safari + 微信 |

---

## 🔄 回滚方案

如果 V2 出现问题，可以快速回滚：

### 方法 1: 禁用 V2（推荐）

```bash
# 删除系统参数
docker exec -it 4bfd7858876d odoo shell
>>> env['ir.config_parameter'].sudo().search([('key', '=', 'qr_ordering.menu_ui_v2')]).unlink()
>>> env.cr.commit()
>>> exit()

# 或设置为 false
>>> env['ir.config_parameter'].sudo().set_param('qr_ordering.menu_ui_v2', 'false')
>>> env.cr.commit()
```

### 方法 2: 删除 V2 文件

```bash
ssh ubuntu@54.65.127.141
cd /opt/seisei-project/addons/qr_ordering

# 删除 V2 文件
rm views/qr_ordering_templates_v2.xml
rm static/src/css/qr_ordering_v2.css
rm static/src/js/qr_ordering_v2.js

# 恢复 __manifest__.py（从 git）
# 或手动移除 V2 资源声明

# 重启容器
docker restart 4bfd7858876d
```

---

## 📝 后续任务

### 立即任务

1. [ ] **功能验证**: 访问测试 URL，验证 V2 基础功能
2. [ ] **测试产品数据**: 确保至少有 1 个 pinned 和 highlight 产品
3. [ ] **浏览器测试**: iPhone Safari + 微信浏览器

### 短期任务

1. [ ] **性能测试**: Lighthouse 评分 > 90
2. [ ] **完整测试**: 使用 `V2_CHECKLIST.md` 逐项验证
3. [ ] **用户反馈**: 收集真实用户体验反馈

### 长期优化

1. [ ] **ScrollSpy**: CategoryChips 根据滚动自动高亮
2. [ ] **手势支持**: Carousel 左右滑动
3. [ ] **WebP 图片**: 优化图片加载
4. [ ] **A/B 测试**: V1 vs V2 转化率对比

---

## 📞 联系信息

- **部署者**: AI Assistant
- **部署脚本**: `deploy_qr_ordering_v2.sh`
- **文档位置**: 
  - `README_V2.md`
  - `DEPLOY_V2.md`
  - `V2_CHECKLIST.md`
  - `DEPLOYMENT_RECORD.md` (本文件)

---

## 🎉 总结

✅ **QR Ordering V2 部署完成！**

- 文件已同步到服务器
- 容器已重启，代码已生效
- 可通过 URL 参数 `?menu_ui_v2=1` 测试
- V1 仍可用，随时可回滚

**下一步**: 访问测试 URL 验证功能 🚀



