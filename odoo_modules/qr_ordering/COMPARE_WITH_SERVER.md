# 本地与服务器版本对比报告

**生成时间**: 2026-01-06 23:08:33  
**服务器**: ubuntu@54.65.127.141  
**服务器路径**: /opt/seisei-project/odoo-addons/qr_ordering

## 📊 对比总结

- ✅ **相同文件**: 5 个
- ⚠️ **有差异文件**: 0 个
- ❌ **服务器缺失文件**: 6 个（本地新增）

## 📁 文件对比详情

### ✅ 相同文件（5个）

这些文件在本地和服务器上完全相同：

1. `__init__.py`
2. `__manifest__.py`
3. `controllers/qr_ordering_controller.py`
4. `static/src/js/qr_ordering.js`
5. `security/ir.model.access.csv`

### ❌ 服务器缺失文件（6个）

这些文件在本地存在，但服务器上还没有：

1. **`controllers/pos_print_controller.py`** - POS 打印控制器
2. **`models/pos_print_job.py`** - POS 打印任务模型
3. **`static/src/js/pos_print_consumer.js`** - POS 打印任务消费者（前端）
4. **`static/src/js/qr_ordering_v2.js`** - QR 点餐 V2 版本 JavaScript
5. **`static/src/css/qr_ordering_v2.css`** - QR 点餐 V2 版本样式
6. **`static/src/pos/qr_print_service.js`** - QR 打印服务

### 📋 服务器上的文件（11个）

服务器上存在的所有代码文件：

```
__init__.py
__manifest__.py
controllers/__init__.py
controllers/qr_ordering_controller.py
models/__init__.py
models/product_template.py
models/qr_order.py
models/qr_session.py
models/qr_table.py
static/src/css/qr_ordering.css
static/src/js/qr_ordering.js
```

### 📋 本地文件（18个）

本地存在的所有代码文件：

```
__init__.py
__manifest__.py
controllers/__init__.py
controllers/pos_print_controller.py          ← 服务器缺失
controllers/qr_ordering_controller.py
models/__init__.py
models/pos_order.py
models/pos_print_job.py                       ← 服务器缺失
models/product_template.py
models/qr_order.py
models/qr_session.py
models/qr_table.py
static/src/css/qr_ordering.css
static/src/css/qr_ordering_v2.css             ← 服务器缺失
static/src/js/pos_print_consumer.js           ← 服务器缺失
static/src/js/qr_ordering.js
static/src/js/qr_ordering_v2.js               ← 服务器缺失
static/src/pos/qr_print_service.js            ← 服务器缺失
```

## 🚀 部署建议

### 需要部署的新文件

以下文件是新增功能，需要部署到服务器：

1. **POS 打印系统相关**:
   - `controllers/pos_print_controller.py` - 打印任务 API 控制器
   - `models/pos_print_job.py` - 打印任务数据模型
   - `static/src/js/pos_print_consumer.js` - 前端打印消费者
   - `static/src/pos/qr_print_service.js` - 打印服务

2. **QR 点餐 V2 版本**:
   - `static/src/js/qr_ordering_v2.js` - V2 JavaScript
   - `static/src/css/qr_ordering_v2.css` - V2 样式

### 部署命令

```bash
# 使用 rsync 同步所有文件到服务器
rsync -avz --progress \
  -e "ssh -i ~/Projects/Pem/odoo-2025.pem" \
  /Users/taozhang/Projects/server-apps/seisei-project/odoo-addons/qr_ordering/ \
  ubuntu@54.65.127.141:/opt/seisei-project/odoo-addons/qr_ordering/

# 或者使用部署脚本
cd /Users/taozhang/Projects/server-apps/seisei-project
./sync_to_server.sh --addons-only
```

### 部署后操作

1. **升级 Odoo 模块**:
   ```bash
   ssh -i ~/Projects/Pem/odoo-2025.pem ubuntu@54.65.127.141
   docker exec -it <container_id> odoo -u qr_ordering --stop-after-init
   docker restart <container_id>
   ```

2. **验证部署**:
   - 检查新文件是否存在
   - 检查 Odoo 日志是否有错误
   - 测试新功能是否正常

## 📝 注意事项

- 所有新增文件都已添加到 Git（状态为 `A`）
- 部署前建议先备份服务器上的现有文件
- 如果使用 V2 功能，需要启用 feature flag（见 `DEPLOY_V2.md`）

