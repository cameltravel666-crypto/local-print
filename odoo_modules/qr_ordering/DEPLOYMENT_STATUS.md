# QR 点餐三语化与金额修复部署状态

**部署时间**: 2026-01-07 06:56  
**服务器**: ubuntu@54.65.127.141  
**环境**: 测试环境 (seisei-test)  
**容器**: seisei-test-web-1

## ✅ 部署完成

### 已同步的文件

1. **`views/qr_ordering_templates.xml`** (36K)
   - 前台买单弹窗三语化（添加 data-i18n 属性）
   - 新增税额行（qr-pay-tax）
   - 金额标签改为"含税合计"（pay_total_incl_tax）

2. **`static/src/js/qr_ordering.js`** (77K)
   - i18n 字典新增：pay_table, pay_order, pay_tax, pay_total_incl_tax, done
   - `getFooterState()` 计算含税合计和税额（totalOrderAmountInclTax, totalOrderTaxAmount）
   - `openPayModal()` 应用 i18n 并填充税额和含税合计
   - `applyI18n()` 支持传入 root 参数

3. **`static/src/css/qr_ordering.css`** (33K)
   - `.qr-cart-btn` 添加居中样式（display: inline-flex + align-items: center）
   - `.qr-copy-btn` 添加居中样式
   - `.qr-lang-select` 添加居中样式和原生样式移除

### 部署步骤

1. ✅ 使用 `scp` 复制文件到服务器 `/tmp` 目录
2. ✅ 使用 `docker cp` 将文件复制到容器内 `/mnt/extra-addons/qr_ordering/`
3. ✅ 执行 `docker exec seisei-test-web-1 odoo -u qr_ordering --stop-after-init` 升级模块
4. ✅ 重启容器 `docker restart seisei-test-web-1`
5. ✅ 验证部署成功（模板中包含 pay_tax 和 pay_total_incl_tax）

### 本次修复内容

#### 任务 1：前台买单界面三语化
- ✅ QWeb 模板所有文案添加 `data-i18n` 属性
- ✅ i18n 字典补充三语翻译（zh_CN, ja_JP, en_US）
- ✅ `openPayModal()` 调用 `applyI18n($payModal)` 实现即时翻译

#### 任务 2：按钮文字居中
- ✅ `.qr-cart-btn`、`.qr-copy-btn`、`.qr-lang-select` 使用 flexbox 居中
- ✅ 设置 `line-height: 1` 避免继承导致偏移
- ✅ 语言选择器移除原生样式（appearance: none）

#### 任务 3：前台买单金额改为含税合计 + 税额
- ✅ QWeb 模板新增税额行（`qr-pay-tax`）
- ✅ 金额标签改为"含税合计"（`pay_total_incl_tax`）
- ✅ `getFooterState()` 计算 `totalOrderAmountInclTax` 和 `totalOrderTaxAmount`
- ✅ `openPayModal()` 填充税额和含税合计（来自未结订单聚合）

### 验证清单

请在移动端和桌面端验证以下功能：

#### 语言切换测试
- [ ] 切换到日语（日本語）→ 打开前台买单弹窗
  - 验证：标题显示"レジでお会計"，所有文案为日语
  - 验证：按钮文字水平垂直居中（尤其日语长文本）
- [ ] 切换到英语（English）→ 打开前台买单弹窗
  - 验证：标题显示"Pay at Counter"，所有文案为英语
  - 验证：按钮文字居中
- [ ] 切换回中文 → 打开前台买单弹窗
  - 验证：所有文案恢复中文
  - 验证：语言切换后无需刷新页面即可生效

#### 金额计算测试
- [ ] 有未结订单时 → 打开前台买单
  - 验证：显示"税额"行，数值 = 所有未结订单的 `amount_tax` 之和
  - 验证：显示"含税合计"行，数值 = 所有未结订单的 `amount_total_incl` 之和
  - 验证：税额 + 税前合计 = 含税合计（数学验证）
- [ ] 无未结订单时 → 打开前台买单
  - 验证：税额显示 ¥0，含税合计显示 ¥0

#### 按钮居中与触控测试
- [ ] iPhone Safari（或移动端浏览器）
  - 验证：复制按钮文字居中，点击热区正常
  - 验证：底部"我知道了"按钮文字居中，min-height ≥ 44px
  - 验证：语言选择器文字居中，无偏移/遮挡
- [ ] 桌面浏览器
  - 验证：所有按钮文字水平垂直居中
  - 验证：日语长文本（如"了解しました"）不换行，居中显示

### 访问地址

- 测试环境: http://54.65.127.141:8070
- 生产环境: http://54.65.127.141:8069

### 注意事项

- 如果页面有缓存，请强制刷新（Ctrl+F5 或 Cmd+Shift+R）
- 建议清除浏览器缓存后测试
- 所有修改已记录在代码注释中

### 技术细节

- **文件路径**: `/mnt/extra-addons/qr_ordering/`
- **容器名称**: `seisei-test-web-1`
- **Odoo 版本**: 18.0-20251208
- **数据库**: `default@seisei-test-db-1:default`
