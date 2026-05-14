/**
 * QR Ordering Frontend Application
 * Mobile-first ordering interface
 * Build: 2026-01-07T19:00
 */

(function() {
    'use strict';

    // ==================== 防重复执行保护 ====================
    // 如果已经初始化过，直接返回（防止 assets 和直接引用导致的双重加载）
    if (window.__qrOrderingInitialized) {
        console.warn('[QR Ordering] skip second boot');
        return;
    }
    window.__qrOrderingInitialized = true;

    // Build version marker (for debug panel and cache-busting verification)
    // This MUST be set before any other code runs so the boot guard can detect it
    window.QR_ORDERING_BUILD = '2026-01-07T18:00';

    // ==================== 全局错误边界 ====================
    // 捕获所有未处理的错误，确保永不白屏

    const ERROR_OVERLAY_ID = 'qr-error-overlay';
    let hasShownError = false;

    function showFatalError(message, traceId) {
        if (hasShownError) return;
        hasShownError = true;

        // 移除加载状态
        const loadingEl = document.querySelector('.qr-loading');
        if (loadingEl) loadingEl.style.display = 'none';

        // 检查是否已有错误覆盖层
        let overlay = document.getElementById(ERROR_OVERLAY_ID);
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = ERROR_OVERLAY_ID;
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: #f8f9fa;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                z-index: 99999;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                padding: 20px;
                text-align: center;
            `;
            document.body.appendChild(overlay);
        }

        overlay.innerHTML = `
            <div style="font-size: 48px; margin-bottom: 16px;">⚠️</div>
            <h2 style="font-size: 20px; color: #333; margin-bottom: 8px;">加载失败</h2>
            <p style="font-size: 14px; color: #666; margin-bottom: 24px; max-width: 300px;">${message}</p>
            <button onclick="location.reload()" style="
                background: #FF6B35;
                color: white;
                border: none;
                padding: 12px 32px;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
            ">重试</button>
            ${traceId ? `<p style="font-size: 12px; color: #999; margin-top: 16px;">错误ID: ${traceId}</p>` : ''}
            <p style="font-size: 10px; color: #ccc; margin-top: 8px;">Build: ${QR_ORDERING_BUILD}</p>
        `;
    }

    // 全局错误处理器
    window.onerror = function(message, source, lineno, colno, error) {
        console.error('QR Ordering Error:', message, source, lineno, colno, error);
        showFatalError('页面加载出错，请刷新重试', null);
        return true; // 阻止默认错误处理
    };

    // Promise 未捕获异常处理器
    window.addEventListener('unhandledrejection', function(event) {
        console.error('QR Ordering Unhandled Rejection:', event.reason);
        showFatalError('网络请求失败，请检查网络后重试', null);
    });

    // ==================== i18n ====================
    const i18n = {
        zh_CN: {
            all: '全部',
            search: '搜索菜品...',
            loading: '加载中...',
            total: '小计',
            view_cart: '查看已选',
            continue_order: '继续点餐',
            checkout: '买单',
            cart: '已选菜品',
            note_placeholder: '备注（忌口、口味等）...',
            submit_order: '下单',
            my_orders: '已点菜品',
            add_more: '继续点餐',
            add_to_cart: '加入',
            sold_out: '售罄',
            added: '已加入',
            order_submitted: '下单成功',
            order_failed: '下单失败',
            cart_empty: '还没有选择菜品',
            cart_empty_hint: '去看看有什么好吃的吧',
            go_to_menu: '去点餐',
            no_products: '暂无菜品',
            back_to_all: '返回全部',
            view_recommended: '查看推荐',
            view_orders: '查看已点',
            just_now: '刚刚',
            minutes_ago: '分钟前',
            qty: '份',
            note: '备注',
            batch: '批次',
            status_cart: '已选',
            status_ordered: '已下单',
            status_cooking: '制作中',
            status_serving: '可加菜',
            status_paid: '已结账',
            currency: '¥',
            call_waiter: '请联系服务员买单',
            // 状态机
            select_items: '请选择菜品',
            view_selection: '查看已选',
            view_order: '查看已点',
            go_pay: '去买单',
            add_order: '追加下单',
            ordered: '已下单',
            can_add_more: '（可追加）',
            copy_success: '已复制',
            // 前台买单界面
            pay_title: '前台买单',
            pay_instruction: '请到前台出示以下信息完成买单',
            pay_table: '桌号',
            pay_order: '订单号',
            pay_subtotal: '未税金额',
            pay_tax: '税额',
            pay_total_incl_tax: '含税合计',
            table_number: '桌号',
            order_number: '订单号',
            amount: '金额',
            got_it: '我知道了',
            done: '我知道了',
            copy: '复制',
            front_desk_checkout: '前台买单',
            // 税相关
            tax_excluded: '(税別)',
            tax_included: '(税込)',
            tax: '税额',
            total_incl: '合计(税込)',
            amount_incl: '金额(税込)',
            // 紧凑 chip
            chip_ordered: '已下单',
            chip_can_add: '可追加',
            order_submitted_title: '下单成功',
            can_add_hint: '可继续点餐追加到同一订单',
            // 时间格式
            order_time: '下单时间',
        },
        ja_JP: {
            all: 'すべて',
            search: '料理を検索...',
            loading: '読み込み中...',
            total: '小計',
            view_cart: 'お選びを見る',
            continue_order: '追加注文',
            checkout: 'お会計',
            cart: 'お選びの料理',
            note_placeholder: '備考（アレルギー、味の好みなど）...',
            submit_order: '注文する',
            my_orders: '注文済み',
            add_more: '追加注文',
            add_to_cart: '追加',
            sold_out: '売り切れ',
            added: '追加しました',
            order_submitted: '注文しました',
            order_failed: '注文に失敗しました',
            cart_empty: 'まだ料理を選んでいません',
            cart_empty_hint: 'メニューをご覧ください',
            go_to_menu: 'メニューへ',
            no_products: '料理がありません',
            back_to_all: 'すべてに戻る',
            view_recommended: 'おすすめを見る',
            view_orders: '注文を見る',
            just_now: 'たった今',
            minutes_ago: '分前',
            qty: '品',
            note: '備考',
            batch: 'バッチ',
            status_cart: 'お選び中',
            status_ordered: '注文済み',
            status_cooking: '調理中',
            status_serving: '追加可能',
            status_paid: '会計済み',
            currency: '¥',
            call_waiter: 'スタッフをお呼びください',
            // 状態機
            select_items: '料理を選んでください',
            view_selection: 'お選びを見る',
            view_order: '注文を見る',
            go_pay: 'お会計へ',
            add_order: '追加注文',
            ordered: '注文済み',
            can_add_more: '（追加可）',
            copy_success: 'コピーしました',
            // 前台買単界面
            pay_title: 'レジでお会計',
            pay_instruction: 'レジで以下の情報をご提示ください',
            pay_table: 'テーブル',
            pay_order: '注文番号',
            pay_subtotal: '税抜金額',
            pay_tax: '消費税',
            pay_total_incl_tax: '合計（税込）',
            table_number: 'テーブル番号',
            order_number: '注文番号',
            amount: '金額',
            got_it: '了解しました',
            done: '了解しました',
            copy: 'コピー',
            front_desk_checkout: 'レジでお会計',
            // 税関連
            tax_excluded: '(税別)',
            tax_included: '(税込)',
            tax: '税額',
            total_incl: '合計(税込)',
            amount_incl: '金額(税込)',
            // 紧凑 chip
            chip_ordered: '注文済',
            chip_can_add: '追加可',
            order_submitted_title: '注文しました',
            can_add_hint: '追加注文ができます',
            // 時間フォーマット
            order_time: '注文時間',
        },
        en_US: {
            all: 'All',
            search: 'Search dishes...',
            loading: 'Loading...',
            total: 'Subtotal',
            view_cart: 'View Selection',
            continue_order: 'Add More',
            checkout: 'Pay',
            cart: 'Selected Items',
            note_placeholder: 'Notes (allergies, preferences)...',
            submit_order: 'Place Order',
            my_orders: 'My Orders',
            add_more: 'Order More',
            add_to_cart: 'Add',
            sold_out: 'Sold Out',
            added: 'Added',
            order_submitted: 'Order Placed',
            order_failed: 'Order Failed',
            cart_empty: 'No items selected',
            cart_empty_hint: 'Browse our menu to add dishes',
            go_to_menu: 'Browse Menu',
            no_products: 'No dishes available',
            back_to_all: 'Back to All',
            view_recommended: 'View Recommended',
            view_orders: 'View Orders',
            just_now: 'Just now',
            minutes_ago: ' min ago',
            qty: '',
            note: 'Note',
            batch: 'Batch',
            status_cart: 'Selected',
            status_ordered: 'Ordered',
            status_cooking: 'Preparing',
            status_serving: 'Ready',
            status_paid: 'Paid',
            currency: '¥',
            call_waiter: 'Please call staff to pay',
            // State machine
            select_items: 'Please select dishes',
            view_selection: 'View Selection',
            view_order: 'View Orders',
            go_pay: 'Go to Pay',
            add_order: 'Add to Order',
            ordered: 'Ordered',
            can_add_more: ' (add more)',
            copy_success: 'Copied',
            // Pay at counter
            pay_title: 'Pay at Counter',
            pay_instruction: 'Please show the information below at the counter to pay.',
            pay_table: 'Table',
            pay_order: 'Order ID',
            pay_subtotal: 'Subtotal (excl. tax)',
            pay_tax: 'Tax',
            pay_total_incl_tax: 'Total (incl. tax)',
            got_it: 'Got it',
            done: 'Got it',
            table_number: 'Table',
            order_number: 'Order No.',
            amount: 'Amount',
            got_it: 'Got it',
            copy: 'Copy',
            front_desk_checkout: 'Pay at Counter',
            // Tax related
            tax_excluded: '(excl. tax)',
            tax_included: '(incl. tax)',
            tax: 'Tax',
            total_incl: 'Total (incl. tax)',
            amount_incl: 'Amount (incl. tax)',
            // chip
            chip_ordered: 'Ordered',
            chip_can_add: 'Add more',
            order_submitted_title: 'Order Placed',
            can_add_hint: 'You can add more items to this order',
            // Time format
            order_time: 'Order Time',
        }
    };

    // ==================== State ====================
    const state = {
        tableToken: '',
        accessToken: '',
        tableName: '',
        lang: 'zh_CN',
        categories: [],
        products: [],
        cart: [],           // 已选菜品（未下单）
        orders: [],         // 已下单列表
        selectedCategory: 'all',
        selectedProduct: null,
        isSubmitting: false, // 防止重复提交
    };

    // ==================== OverlayManager 单例管理器 ====================
    // P0-2: 弹窗栈治理 - 任意时刻只允许一个主 overlay
    const OverlayManager = {
        current: null,  // 当前激活的 overlay: 'cart' | 'order' | 'pay' | 'product' | null

        /**
         * 打开 overlay（自动关闭当前的）
         * @param {string} name - 'cart' | 'order' | 'pay' | 'product'
         */
        open(name) {
            // 如果已有不同的 overlay，先关闭
            if (this.current && this.current !== name) {
                this._hide(this.current);
            }

            this.current = name;
            this._show(name);

            // P0-3: 隐藏底部栏
            const $footer = document.getElementById('qr-cart-footer');
            if ($footer) {
                $footer.classList.add('qr-hidden');
            }

            // 锁定滚动
            ScrollLock.lock('overlay-' + name);

            console.log('[OverlayManager] Opened:', name);
        },

        /**
         * 关闭当前 overlay
         */
        close() {
            if (this.current) {
                const name = this.current;
                this._hide(name);
                this.current = null;

                // P0-3: 恢复底部栏
                const $footer = document.getElementById('qr-cart-footer');
                if ($footer) {
                    $footer.classList.remove('qr-hidden');
                }

                // 解锁滚动
                ScrollLock.unlock('overlay-' + name);

                console.log('[OverlayManager] Closed:', name);
            }
        },

        /**
         * 替换当前 overlay（原子操作）
         */
        replace(name) {
            this.open(name);
        },

        /**
         * 检查是否有 overlay 打开
         */
        isOpen() {
            return this.current !== null;
        },

        _show(name) {
            const modalId = this._getModalId(name);
            const el = document.getElementById(modalId);
            if (el) {
                el.classList.add('active');
            }
        },

        _hide(name) {
            const modalId = this._getModalId(name);
            const el = document.getElementById(modalId);
            if (el) {
                el.classList.remove('active');
            }
        },

        _getModalId(name) {
            const map = {
                'cart': 'qr-cart-modal',
                'order': 'qr-order-modal',
                'pay': 'qr-pay-modal',
                'product': 'qr-product-modal'
            };
            return map[name] || 'qr-' + name + '-modal';
        }
    };

    // ==================== DOM Elements ====================
    let $app, $categories, $products, $cartBadge, $cartAmount;
    let $productModal, $cartModal, $orderModal, $toast;

    // ==================== Init ====================
    function init() {
        $app = document.getElementById('qr-ordering-app');
        if (!$app) return;

        // P0: 强制页面结构 - 确保 class 存在
        if (!$app.classList.contains('qr-page')) {
            $app.classList.add('qr-page');
        }
        
        // P0: 确保底部栏存在且可见
        const footer = document.getElementById('qr-cart-footer');
        if (footer) {
            if (!footer.classList.contains('qr-bottom-bar')) {
                footer.classList.add('qr-bottom-bar');
            }
            // 强制显示
            footer.style.display = 'flex';
            footer.style.visibility = 'visible';
            footer.style.opacity = '1';
        }

        // Get data attributes
        state.tableToken = $app.dataset.tableToken;
        state.accessToken = $app.dataset.accessToken;
        state.tableName = $app.dataset.tableName;
        state.lang = $app.dataset.lang || 'zh_CN';

        // Cache DOM elements
        $categories = document.getElementById('qr-categories');
        $products = document.getElementById('qr-products');
        $cartBadge = document.getElementById('qr-cart-badge');
        $cartAmount = document.getElementById('qr-cart-amount');
        $productModal = document.getElementById('qr-product-modal');
        $cartModal = document.getElementById('qr-cart-modal');
        $orderModal = document.getElementById('qr-order-modal');
        $toast = document.getElementById('qr-toast');

        // Setup event listeners
        setupEventListeners();

        // 立即显示根节点（移除 display: none）
        // 这样做是为了避免 visibility check 失败
        $app.style.display = '';

        // Load data
        loadInitData();

        // Apply i18n
        applyI18n();
        
        // 标记初始化完成（通知 Boot Guard）
        if (window.__qrOrderingMarkInit) {
            window.__qrOrderingMarkInit();
        }
        // 触发自定义事件
        window.dispatchEvent(new Event('qr-ordering-initialized'));
        console.log('QR Ordering initialized successfully. Build:', window.QR_ORDERING_BUILD || 'unknown');

        // ==================== 滚动状态诊断 ====================
        const diagOverflow = {
            htmlStyleAttr: document.documentElement.getAttribute('style'),
            bodyStyleAttr: document.body.getAttribute('style'),
            htmlInlineOverflow: document.documentElement.style.overflow,
            bodyInlineOverflow: document.body.style.overflow,
            htmlComputedOverflow: getComputedStyle(document.documentElement).overflow,
            bodyComputedOverflow: getComputedStyle(document.body).overflow,
            scrollLockClass: document.documentElement.classList.contains('qr-scroll-locked'),
        };
        console.log('[QR Ordering] Scroll Diagnostic:', diagOverflow);

        // 验收检查：html/body 默认不应该是 hidden
        if (diagOverflow.htmlComputedOverflow === 'hidden' || diagOverflow.bodyComputedOverflow === 'hidden') {
            console.warn('[QR Ordering] ⚠️ WARNING: html/body has overflow:hidden at init!', diagOverflow);
        }

        // Debug panel update
        updateDebugPanel();

        // ==================== 挂载后自检 ====================
        // 1s 和 3s 后检查根节点状态
        setTimeout(() => checkRootVisibility('1s'), 1000);
        setTimeout(() => checkRootVisibility('3s'), 3000);

        // 设置 MutationObserver 监听 DOM 变化
        setupDomObserver($app);

        // debug 模式显示状态 badge
        if (isDebugMode()) {
            showDebugBadge($app);
        }
    }

    // ==================== 根节点可见性检查 ====================
    function checkRootVisibility(timing) {
        const $app = document.getElementById('qr-ordering-app');
        if (!$app) {
            console.error(`[QR Ordering] [${timing}] Root element #qr-ordering-app not found!`);
            showFatalError('页面根节点丢失，可能被其他脚本移除', null);
            return;
        }

        const rect = $app.getBoundingClientRect();
        const style = window.getComputedStyle($app);
        const childCount = $app.children.length;

        const issues = [];

        // 检查子元素
        if (childCount === 0) {
            issues.push('children=0');
        }

        // 检查尺寸
        if (rect.height === 0 || rect.width === 0) {
            issues.push(`rect=${Math.round(rect.width)}x${Math.round(rect.height)}`);
            
            // ========== 诊断 0x0 的元凶 ==========
            console.error(`[QR Ordering] [${timing}] 🔍 DIAGNOSIS: Root is 0x0, investigating...`);
            
            // 打印 root 的样式信息
            console.error(`[QR Ordering] Root (#qr-ordering-app) styles:`, {
                display: style.display,
                visibility: style.visibility,
                position: style.position,
                width: style.width,
                height: style.height,
                minWidth: style.minWidth,
                minHeight: style.minHeight,
                maxWidth: style.maxWidth,
                maxHeight: style.maxHeight,
                overflow: style.overflow,
                opacity: style.opacity,
                zIndex: style.zIndex,
                rect: {
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    top: Math.round(rect.top),
                    left: Math.round(rect.left),
                },
                children: childCount,
            });
            
            // 检查父节点链条（往上 6 层）
            let parent = $app.parentElement;
            let level = 1;
            while (parent && level <= 6) {
                const parentStyle = window.getComputedStyle(parent);
                const parentRect = parent.getBoundingClientRect();
                
                const parentIssues = [];
                if (parentStyle.display === 'none') parentIssues.push('display:none');
                if (parentStyle.visibility === 'hidden') parentIssues.push('visibility:hidden');
                if (parentRect.height === 0) parentIssues.push(`height:0 (${Math.round(parentRect.height)}px)`);
                if (parentRect.width === 0) parentIssues.push(`width:0 (${Math.round(parentRect.width)}px)`);
                
                if (parentIssues.length > 0 || level === 1) {
                    console.error(`[QR Ordering] Parent #${level} (${parent.tagName}${parent.id ? '#' + parent.id : ''}${parent.className ? '.' + parent.className.split(' ')[0] : ''}):`, {
                        display: parentStyle.display,
                        visibility: parentStyle.visibility,
                        position: parentStyle.position,
                        width: parentStyle.width,
                        height: parentStyle.height,
                        rect: {
                            width: Math.round(parentRect.width),
                            height: Math.round(parentRect.height),
                        },
                        issues: parentIssues.length > 0 ? parentIssues : 'OK',
                    });
                }
                
                // 找到第一个有问题的节点就停止
                if (parentIssues.length > 0) {
                    console.error(`[QR Ordering] 🎯 FOUND CULPRIT: Parent #${level} has issues:`, parentIssues);
                    break;
                }
                
                parent = parent.parentElement;
                level++;
            }
        }

        // 检查 CSS 可见性
        if (style.display === 'none') {
            issues.push('display:none');
        }
        if (style.visibility === 'hidden') {
            issues.push('visibility:hidden');
        }
        if (style.opacity === '0') {
            issues.push('opacity:0');
        }

        if (issues.length > 0) {
            console.error(`[QR Ordering] [${timing}] Root visibility check failed:`, issues.join(', '));
            // 3s 检查失败时才显示错误覆盖层
            if (timing === '3s') {
                showFatalError(
                    '页面内容不可见，可能被 CSS 隐藏或内容未加载',
                    null
                );
            }
        } else {
            console.log(`[QR Ordering] [${timing}] Root visibility check passed: children=${childCount}, rect=${Math.round(rect.width)}x${Math.round(rect.height)}`);
        }
    }

    // ==================== DOM 监听 - 自愈机制 ====================
    function setupDomObserver($app) {
        if (!$app || !window.MutationObserver) return;

        let previousChildCount = $app.children.length;

        const observer = new MutationObserver((mutations) => {
            const currentChildCount = $app.children.length;

            // 检测从有到无的变化
            if (previousChildCount > 0 && currentChildCount === 0) {
                console.error('[QR Ordering] DOM cleared detected! previousChildren:', previousChildCount, '-> currentChildren:', currentChildCount);
                showFatalError(
                    '检测到页面内容被清空，可能是重复初始化或主题 CSS 冲突',
                    null
                );
            }

            previousChildCount = currentChildCount;
        });

        observer.observe($app, {
            childList: true,
            subtree: false
        });

        // 同时监听根节点是否被移除
        const parentObserver = new MutationObserver((mutations) => {
            if (!document.getElementById('qr-ordering-app')) {
                console.error('[QR Ordering] Root element removed from DOM!');
                showFatalError(
                    '页面根节点被移除，可能是脚本冲突',
                    null
                );
            }
        });

        if ($app.parentNode) {
            parentObserver.observe($app.parentNode, {
                childList: true
            });
        }
    }

    // ==================== Debug Badge ====================
    function isDebugMode() {
        return window.location.search.includes('debug=1') ||
               document.getElementById('qr-debug-panel') !== null;
    }

    function showDebugBadge($app) {
        const rect = $app ? $app.getBoundingClientRect() : { width: 0, height: 0 };
        const childCount = $app ? $app.children.length : 0;

        const badge = document.createElement('div');
        badge.id = 'qr-debug-badge';
        badge.style.cssText = `
            position: fixed;
            bottom: 60px;
            right: 10px;
            background: rgba(0, 0, 0, 0.85);
            color: #0f0;
            padding: 8px 12px;
            font-size: 11px;
            font-family: monospace;
            z-index: 100001;
            border-radius: 4px;
            line-height: 1.5;
            pointer-events: none;
        `;
        badge.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 4px; color: #fff;">QR Ordering Status</div>
            <div>Build: ${window.QR_ORDERING_BUILD || 'unknown'}</div>
            <div>Booted: <span style="color: #0f0;">true</span></div>
            <div>Root children: ${childCount}</div>
            <div>Root rect: ${Math.round(rect.width)}x${Math.round(rect.height)}</div>
        `;
        document.body.appendChild(badge);

        // 每 2 秒更新一次
        setInterval(() => {
            const $appNow = document.getElementById('qr-ordering-app');
            const rectNow = $appNow ? $appNow.getBoundingClientRect() : { width: 0, height: 0 };
            const childCountNow = $appNow ? $appNow.children.length : 0;
            const existing = document.getElementById('qr-debug-badge');
            if (existing) {
                existing.innerHTML = `
                    <div style="font-weight: bold; margin-bottom: 4px; color: #fff;">QR Ordering Status</div>
                    <div>Build: ${window.QR_ORDERING_BUILD || 'unknown'}</div>
                    <div>Booted: <span style="color: #0f0;">true</span></div>
                    <div>Root children: ${childCountNow}</div>
                    <div>Root rect: ${Math.round(rectNow.width)}x${Math.round(rectNow.height)}</div>
                `;
            }
        }, 2000);
    }

    // ==================== Event Listeners ====================
    function setupEventListeners() {
        // Language selector
        document.getElementById('qr-lang-select')?.addEventListener('change', (e) => {
            state.lang = e.target.value;
            applyI18n();
            loadMenu();
        });

        // Search
        document.getElementById('qr-search-input')?.addEventListener('input', (e) => {
            filterProducts(e.target.value);
        });

        // ========== 新版状态机按钮事件 ==========
        // 主按钮（提交订单/追加下单/去前台支付）
        document.getElementById('qr-primary-btn')?.addEventListener('click', handlePrimaryBtnClick);

        // 次按钮（查看购物车/查看订单）
        document.getElementById('qr-secondary-btn')?.addEventListener('click', handleSecondaryBtnClick);

        // 购物车图标点击
        document.getElementById('qr-cart-icon-btn')?.addEventListener('click', openCartModal);

        // 支付弹窗关闭
        document.getElementById('qr-pay-close')?.addEventListener('click', closePayModal);
        document.getElementById('qr-pay-done')?.addEventListener('click', closePayModal);

        // 复制按钮
        document.getElementById('qr-copy-table')?.addEventListener('click', () => copyToClipboard(state.tableName, t('copy_success')));
        document.getElementById('qr-copy-order')?.addEventListener('click', () => {
            const footerState = getFooterState();
            copyToClipboard(footerState.orderRef, t('copy_success'));
        });

        // ========== 订单状态 chip 点击（显示完整信息 toast）==========
        document.getElementById('qr-order-status-badge')?.addEventListener('click', handleStatusChipClick);

        // ========== 订单状态 toast 事件 ==========
        document.getElementById('qr-order-toast-close')?.addEventListener('click', hideOrderStatusToast);
        document.getElementById('qr-order-toast-copy-ref')?.addEventListener('click', () => {
            const $ref = document.getElementById('qr-order-toast-ref');
            if ($ref) copyToClipboard($ref.textContent, t('copy_success'));
        });

        // 兼容旧按钮 ID（如果存在）
        document.getElementById('qr-view-cart-btn')?.addEventListener('click', openCartModal);
        document.getElementById('qr-view-orders-btn')?.addEventListener('click', openOrderModal);
        document.getElementById('qr-checkout-btn')?.addEventListener('click', handleCheckout);

        // Cart modal close
        document.getElementById('qr-cart-close')?.addEventListener('click', closeCartModal);

        // Product modal close
        document.getElementById('qr-modal-close')?.addEventListener('click', closeProductModal);

        // Order modal close
        document.getElementById('qr-order-close')?.addEventListener('click', closeOrderModal);

        // Submit order
        document.getElementById('qr-submit-order-btn')?.addEventListener('click', submitOrder);

        // Add more (from order modal)
        document.getElementById('qr-add-more-btn')?.addEventListener('click', () => {
            closeOrderModal();
        });

        // Click outside modal to close - 使用 OverlayManager
        document.querySelectorAll('.qr-modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    // P0-2: 使用 OverlayManager 统一关闭
                    OverlayManager.close();
                }
            });
        });
    }

    // ==================== API Calls ====================
    async function apiCall(endpoint, data = {}) {
        try {
            const params = {
                table_token: state.tableToken,
                lang: state.lang,
                ...data,
            };
            // 只在 access_token 存在时传递
            if (state.accessToken) {
                params.access_token = state.accessToken;
            }
            
            const response = await fetch(`/qr/api/${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: params,
                    id: Date.now(),
                }),
            });
            const result = await response.json();
            if (result.error) {
                throw new Error(result.error.message || 'API Error');
            }
            return result.result;
        } catch (error) {
            console.error('API call failed:', error);
            throw error;
        }
    }

    // 加载超时设置（15秒）
    const LOAD_TIMEOUT_MS = 15000;

    async function loadInitData() {
        // 设置加载超时
        const timeoutId = setTimeout(() => {
            console.error('Load init data timeout');
            showFatalError('加载超时，请检查网络后重试', null);
        }, LOAD_TIMEOUT_MS);

        try {
            if (!state.tableToken) {
                clearTimeout(timeoutId);
                console.error('Table token not found');
                showFatalError('餐桌信息错误，请重新扫码', null);
                return;
            }

            const result = await apiCall('init');

            // 清除超时计时器
            clearTimeout(timeoutId);

            if (result && result.success) {
                state.accessToken = result.data.access_token;
                state.categories = result.data.menu.categories || [];
                state.products = result.data.menu.products || [];
                state.orders = result.data.current_order || [];

                // Load cart from existing orders
                const cartOrder = state.orders ? state.orders.find(o => o.state === 'cart') : null;
                if (cartOrder && cartOrder.lines) {
                    state.cart = cartOrder.lines.map(l => ({
                        lineId: l.id,
                        productId: l.product_id,
                        name: l.product_name,
                        qty: l.qty,
                        price: l.price_unit,
                        note: l.note,
                    }));
                }

                renderCategories();
                renderProducts();
                updateCartUI();

                // 隐藏加载状态
                const loadingEl = document.querySelector('.qr-loading');
                if (loadingEl) loadingEl.style.display = 'none';

                // 显示根节点（移除 display: none）
                const rootEl = document.getElementById('qr-ordering-app');
                if (rootEl) {
                    rootEl.style.display = '';
                }

                // 隐藏 Boot Guard
                const bootGuard = document.getElementById('qr-boot-guard');
                if (bootGuard) {
                    bootGuard.style.display = 'none';
                }

                // 触发初始化完成事件（供 Boot Guard 使用）
                if (window.__qrOrderingMarkInit) {
                    window.__qrOrderingMarkInit();
                }
                window.dispatchEvent(new Event('qr-ordering-initialized'));

                console.log(`QR Ordering loaded successfully. Build: ${window.QR_ORDERING_BUILD || 'unknown'}`);

            } else {
                const errorMsg = result?.message || 'Failed to load data';
                const errorCode = result?.error || 'UNKNOWN_ERROR';
                const traceId = result?.trace_id || null;
                console.error('Load init data failed:', errorCode, errorMsg, traceId);

                // 显示错误（使用全局错误覆盖层）
                showFatalError(errorMsg, traceId);
            }
        } catch (error) {
            clearTimeout(timeoutId);
            console.error('Load init data error:', error);
            showFatalError('加载失败，请检查网络后重试', null);
        }
    }

    async function loadMenu() {
        try {
            const result = await apiCall('menu');
            if (result.success) {
                state.categories = result.data.categories;
                state.products = result.data.products;
                renderCategories();
                renderProducts();
            }
        } catch (error) {
            console.error('Load menu failed:', error);
        }
    }

    async function addToCart(productId, qty, note) {
        try {
            const result = await apiCall('cart/add', {
                product_id: productId,
                qty: qty,
                note: note,
            });
            if (result.success) {
                // Update local cart from response
                state.cart = result.data.lines.filter(l => l.state === 'pending').map(l => ({
                    lineId: l.id,
                    productId: l.product_id,
                    name: l.product_name,
                    qty: l.qty,
                    price: l.price_unit,
                    note: l.note,
                }));
                updateCartUI();
                showToast(t('added'));
                return true;
            } else {
                showToast(result.message);
                return false;
            }
        } catch (error) {
            showToast('添加失败');
            return false;
        }
    }

    async function updateCartItem(lineId, qty) {
        try {
            const result = await apiCall('cart/update', {
                line_id: lineId,
                qty: qty,
            });
            if (result.success) {
                state.cart = result.data.lines.filter(l => l.state === 'pending').map(l => ({
                    lineId: l.id,
                    productId: l.product_id,
                    name: l.product_name,
                    qty: l.qty,
                    price: l.price_unit,
                    note: l.note,
                }));
                updateCartUI();
                renderCartItems();
            }
        } catch (error) {
            showToast('更新失败');
        }
    }

    async function submitOrder() {
        if (state.cart.length === 0) {
            showToast(t('cart_empty'));
            return;
        }

        // P0-2: 防止重复提交
        if (state.isSubmitting) {
            console.log('[submitOrder] Already submitting, skipped');
            return;
        }
        state.isSubmitting = true;

        // 禁用下单按钮
        const $submitBtn = document.getElementById('qr-submit-order-btn');
        if ($submitBtn) {
            $submitBtn.disabled = true;
            $submitBtn.textContent = t('loading');
        }

        try {
            const note = document.getElementById('qr-cart-note')?.value || '';
            const result = await apiCall('order/submit', { note });

            if (result.success) {
                // P0-1: 下单成功后清空购物车
                state.cart = [];
                if (result.data) {
                    state.orders.unshift(result.data);
                }

                // P0-1: 更新底部栏（金额清零）
                updateCartUI();

                // P0-2: 使用 OverlayManager 关闭弹层
                OverlayManager.close();

                // 更新底部栏状态
                updateFooterState();

                // P1-2: 更新菜品卡片（清除已加购数量 badge）
                renderProducts();

                // P0-2: 显示成功 Toast
                const footerState = getFooterState();
                showOrderStatusToast({
                    orderRef: footerState.orderRef || result.data?.name,
                    tableName: state.tableName,
                    canAdd: true,
                    autoHide: true
                });
            } else {
                showToast(result.message || t('order_failed'));
            }
        } catch (error) {
            console.error('[submitOrder] Error:', error);
            showToast(t('order_failed'));
        } finally {
            // 恢复按钮状态
            state.isSubmitting = false;
            if ($submitBtn) {
                $submitBtn.disabled = false;
                $submitBtn.textContent = t('submit_order');
            }
        }
    }

    // ==================== Render Functions ====================
    function renderCategories() {
        const allCategory = `
            <div class="qr-category ${state.selectedCategory === 'all' ? 'active' : ''}" 
                 data-category-id="all" onclick="QrOrdering.selectCategory('all')">
                <span class="qr-category-icon">📋</span>
                <span class="qr-category-name">${t('all')}</span>
            </div>
        `;

        const categoryHtml = state.categories.map(cat => `
            <div class="qr-category ${state.selectedCategory === cat.id ? 'active' : ''}" 
                 data-category-id="${cat.id}" onclick="QrOrdering.selectCategory(${cat.id})">
                <span class="qr-category-icon">${getCategoryIcon(cat.name)}</span>
                <span class="qr-category-name">${cat.name}</span>
            </div>
        `).join('');

        $categories.innerHTML = allCategory + categoryHtml;
    }

    function renderProducts(filter = '') {
        let products = state.products;

        // Filter by category
        if (state.selectedCategory !== 'all') {
            products = products.filter(p => p.category_id === state.selectedCategory);
        }

        // Filter by search
        if (filter) {
            const lowerFilter = filter.toLowerCase();
            products = products.filter(p =>
                p.name.toLowerCase().includes(lowerFilter) ||
                (p.description && p.description.toLowerCase().includes(lowerFilter))
            );
        }

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
            return;
        }

        // P1-2: 获取已选菜品数量 map
        const cartQtyMap = {};
        state.cart.forEach(item => {
            cartQtyMap[item.productId] = (cartQtyMap[item.productId] || 0) + item.qty;
        });

        $products.innerHTML = products.map(p => {
            const inCartQty = cartQtyMap[p.id] || 0;
            return `
            <div class="qr-product-card ${p.sold_out ? 'sold-out' : ''} ${p.highlight ? 'highlight' : ''}"
                 onclick="QrOrdering.openProduct(${p.id})">
                <div class="qr-product-image-container">
                    <img class="qr-product-image" src="${p.image_url}" alt="${p.name}" loading="lazy"/>
                    ${p.video_url ? '<div class="qr-product-video-indicator">🎬</div>' : ''}
                    ${p.sold_out ? `<div class="qr-sold-out-badge">${t('sold_out')}</div>` : ''}
                    ${inCartQty > 0 ? `<div class="qr-product-qty-badge">${inCartQty}</div>` : ''}
                    <div class="qr-product-tags">
                        ${(p.tags || []).map(tag => `
                            <span class="qr-product-tag" style="background-color: ${tag.color}">${tag.name}</span>
                        `).join('')}
                    </div>
                </div>
                <div class="qr-product-info">
                    <div class="qr-product-name">${p.name}</div>
                    <div class="qr-product-desc">${p.description || ''}</div>
                    <div class="qr-product-price-row">
                        <span class="qr-product-price">${t('currency')}${p.price.toFixed(0)} <span class="qr-tax-hint">${t('tax_excluded')}</span></span>
                        ${!p.sold_out ? `
                            <button class="qr-add-btn" onclick="event.stopPropagation(); QrOrdering.quickAdd(${p.id})">+</button>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
        }).join('');
    }

    function renderCartItems() {
        const $cartItems = document.getElementById('qr-cart-items');
        const $submitBtn = document.getElementById('qr-submit-order-btn');
        const $cartNote = document.querySelector('.qr-cart-note');
        if (!$cartItems) return;

        // P0-1: 空态处理
        if (state.cart.length === 0) {
            $cartItems.innerHTML = `
                <div class="qr-cart-empty">
                    <div class="qr-cart-empty-icon">🍽️</div>
                    <div class="qr-cart-empty-title">${t('cart_empty')}</div>
                    <div class="qr-cart-empty-hint">${t('cart_empty_hint')}</div>
                    <button class="qr-cart-empty-btn" onclick="OverlayManager.close()">${t('go_to_menu')}</button>
                </div>
            `;
            // P0-1: 隐藏备注区和禁用下单按钮，主CTA变为"去点餐"
            if ($cartNote) $cartNote.style.display = 'none';
            if ($submitBtn) {
                $submitBtn.disabled = true;
                $submitBtn.textContent = t('go_to_menu');
                $submitBtn.onclick = () => OverlayManager.close();
            }
            // P0-1: 确保合计显示为 0
            const $totalAmount = document.getElementById('qr-cart-total-amount');
            if ($totalAmount) $totalAmount.textContent = `${t('currency')}0`;
            return;
        }

        // 有菜品时恢复显示
        if ($cartNote) $cartNote.style.display = 'block';
        if ($submitBtn) {
            $submitBtn.disabled = false;
            $submitBtn.textContent = t('submit_order');
            $submitBtn.onclick = null; // 恢复默认事件
        }

        $cartItems.innerHTML = state.cart.map(item => {
            const product = state.products.find(p => p.id === item.productId) || {};
            // 税前小计
            const subtotal = item.price * item.qty;
            return `
                <div class="qr-cart-item">
                    <img class="qr-cart-item-image" src="${product.image_url || ''}" alt="${item.name}"/>
                    <div class="qr-cart-item-info">
                        <div class="qr-cart-item-name">${item.name}</div>
                        ${item.note ? `<div class="qr-cart-item-note">${item.note}</div>` : ''}
                        <div class="qr-cart-item-price">${t('currency')}${subtotal.toFixed(0)} <span class="qr-tax-hint">${t('tax_excluded')}</span></div>
                    </div>
                    <div class="qr-cart-item-qty">
                        <button class="qr-cart-qty-btn" onclick="QrOrdering.updateCart(${item.lineId}, ${item.qty - 1})">-</button>
                        <span>${item.qty}</span>
                        <button class="qr-cart-qty-btn" onclick="QrOrdering.updateCart(${item.lineId}, ${item.qty + 1})">+</button>
                    </div>
                </div>
            `;
        }).join('');

        // 计算税前总额、税额、含税总额
        let totalExcl = 0;
        let totalTax = 0;
        state.cart.forEach(item => {
            const product = state.products.find(p => p.id === item.productId) || {};
            const subtotalExcl = item.price * item.qty;
            const subtotalIncl = (product.price_with_tax || item.price) * item.qty;
            totalExcl += subtotalExcl;
            totalTax += (subtotalIncl - subtotalExcl);
        });
        const totalIncl = totalExcl + totalTax;

        // 更新合计显示（显示税前、税额、含税）
        const $totalRow = document.querySelector('.qr-cart-total-row');
        if ($totalRow) {
            $totalRow.innerHTML = `
                <div class="qr-cart-tax-breakdown">
                    <div class="qr-cart-subtotal-row">
                        <span>${t('total')}</span>
                        <span>${t('currency')}${totalExcl.toFixed(0)}</span>
                    </div>
                    <div class="qr-cart-tax-row">
                        <span>${t('tax')}</span>
                        <span>${t('currency')}${totalTax.toFixed(0)}</span>
                    </div>
                </div>
                <div class="qr-cart-total-incl">
                    <span>${t('total_incl')}</span>
                    <span class="qr-cart-total-amount" id="qr-cart-total-amount">${t('currency')}${totalIncl.toFixed(0)}</span>
                </div>
            `;
        }
    }

    function renderOrders() {
        const $orderList = document.getElementById('qr-order-list');
        if (!$orderList) return;

        // 过滤掉 cart 和 paid 状态的订单（已结账的订单不再显示）
        const activeOrders = state.orders.filter(o => o.state !== 'cart' && o.state !== 'paid' && o.state !== 'cancelled');

        if (activeOrders.length === 0) {
            $orderList.innerHTML = `
                <div class="qr-order-empty">
                    <div class="qr-order-empty-icon">📋</div>
                    <div class="qr-order-empty-title">${t('cart_empty')}</div>
                </div>
            `;
            return;
        }

        // P1-7: 已下单列表 - 合并所有订单，只显示商品名+数量，底部汇总金额
        // 合并所有订单的商品
        const allLines = [];
        let totalUntaxed = 0;
        let totalTax = 0;
        let totalIncl = 0;

        activeOrders.forEach(order => {
            order.lines.forEach(l => {
                allLines.push({
                    name: l.product_name,
                    qty: l.qty
                });
            });
            // 累加金额（从 POS 订单获取）
            const orderTotalIncl = order.amount_total_incl || order.total_amount || 0;
            const orderTax = order.amount_tax || 0;
            totalIncl = orderTotalIncl; // 使用最新的 POS 订单金额（因为是同一个 POS 订单）
            totalTax = orderTax;
            totalUntaxed = orderTotalIncl - orderTax;
        });

        // 渲染商品明细（只显示名称和数量）
        const linesHtml = allLines.map(l => `
            <div class="qr-order-line">
                <span class="qr-order-line-name">${l.name}</span>
                <span class="qr-order-line-qty">×${l.qty}</span>
            </div>
        `).join('');

        $orderList.innerHTML = `
            <div class="qr-order-card">
                <div class="qr-order-lines">
                    ${linesHtml}
                </div>
                <div class="qr-order-summary">
                    <div class="qr-order-summary-row">
                        <span>${t('total')}</span>
                        <span>${t('currency')}${totalUntaxed.toFixed(0)}</span>
                    </div>
                    <div class="qr-order-summary-row">
                        <span>${t('tax')}</span>
                        <span>${t('currency')}${totalTax.toFixed(0)}</span>
                    </div>
                    <div class="qr-order-summary-row qr-order-summary-total">
                        <span>${t('total_incl')}</span>
                        <span>${t('currency')}${totalIncl.toFixed(0)}</span>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * P1-3: 格式化订单时间
     */
    function formatOrderTime(timestamp) {
        if (!timestamp) return '';
        const orderDate = new Date(timestamp);
        const now = new Date();
        const diffMs = now - orderDate;
        const diffMins = Math.floor(diffMs / 60000);

        if (diffMins < 1) {
            return t('just_now');
        } else if (diffMins < 60) {
            return `${diffMins}${t('minutes_ago')}`;
        } else {
            // 显示时:分
            return orderDate.toLocaleTimeString(state.lang.replace('_', '-'), {
                hour: '2-digit',
                minute: '2-digit'
            });
        }
    }

    // ==================== UI Updates ====================

    /**
     * 四态状态机：
     * A) cart_count == 0 且未下单：主按钮"提交订单"禁用；显示提示"请选择菜品"
     * B) cart_count > 0 且未下单：主按钮"提交订单"(primary)；次按钮"查看购物车"(secondary)
     * C) cart_count == 0 且已下单：显示状态"已下单 · #<order_ref>"；主按钮"去前台支付"；次按钮"查看订单"
     * D) cart_count > 0 且已下单：显示状态"已下单 · #<order_ref>（可追加）"；主按钮"追加下单"；次按钮"查看购物车"
     */
    function getFooterState() {
        const cartCount = state.cart.reduce((sum, item) => sum + item.qty, 0);
        const activeOrders = state.orders.filter(o =>
            o.state !== 'cart' && o.state !== 'paid' && o.state !== 'cancelled'
        );
        const hasOrdered = activeOrders.length > 0;
        const lastOrder = hasOrdered ? activeOrders[activeOrders.length - 1] : null;
        const orderRef = lastOrder ? lastOrder.name : '';
        
        // 计算未结订单的含税合计、税额和税前合计
        const totalOrderAmountInclTax = activeOrders.reduce((sum, o) => {
            return sum + (o.amount_total_incl || o.total_amount || 0);
        }, 0);
        const totalOrderTaxAmount = activeOrders.reduce((sum, o) => {
            return sum + (o.amount_tax || 0);
        }, 0);
        const totalOrderAmountUntaxed = activeOrders.reduce((sum, o) => {
            // 优先使用后端返回的 amount_untaxed（来自 POS 订单），回退到 total_amount
            return sum + (o.amount_untaxed || o.total_amount || 0);
        }, 0);
        
        // 兼容旧字段（向后兼容）
        const totalOrderAmount = totalOrderAmountInclTax;

        if (cartCount === 0 && !hasOrdered) return { 
            state: 'A', 
            cartCount, 
            orderRef, 
            totalOrderAmount,
            totalOrderAmountInclTax,
            totalOrderTaxAmount,
            totalOrderAmountUntaxed
        };
        if (cartCount > 0 && !hasOrdered) return { 
            state: 'B', 
            cartCount, 
            orderRef, 
            totalOrderAmount,
            totalOrderAmountInclTax,
            totalOrderTaxAmount,
            totalOrderAmountUntaxed
        };
        if (cartCount === 0 && hasOrdered) return { 
            state: 'C', 
            cartCount, 
            orderRef, 
            totalOrderAmount,
            totalOrderAmountInclTax,
            totalOrderTaxAmount,
            totalOrderAmountUntaxed
        };
        return { 
            state: 'D', 
            cartCount, 
            orderRef, 
            totalOrderAmount,
            totalOrderAmountInclTax,
            totalOrderTaxAmount,
            totalOrderAmountUntaxed
        };
    }

    function updateCartUI() {
        const totalQty = state.cart.reduce((sum, item) => sum + item.qty, 0);
        // P0-1: 确保空购物车时金额为0
        const totalAmount = state.cart.length === 0 ? 0 : state.cart.reduce((sum, item) => sum + item.price * item.qty, 0);

        // 更新购物车徽章和金额
        if ($cartBadge) $cartBadge.textContent = totalQty;
        if ($cartAmount) $cartAmount.textContent = `${t('currency')}${totalAmount.toFixed(0)}`;

        // 更新件数显示
        const $cartCount = document.getElementById('qr-cart-count');
        if ($cartCount) $cartCount.textContent = `${totalQty} ${t('qty') || '件'}`;

        // 获取状态机元素
        const $primaryBtn = document.getElementById('qr-primary-btn');
        const $secondaryBtn = document.getElementById('qr-secondary-btn');
        const $statusBadge = document.getElementById('qr-order-status-badge');
        const $statusText = document.getElementById('qr-status-text');
        const $footerHint = document.getElementById('qr-footer-hint');
        const footer = document.getElementById('qr-cart-footer');

        // 确保底部栏始终可见
        if (footer) {
            footer.style.display = 'flex';
            footer.style.visibility = 'visible';
            footer.style.opacity = '1';
        }

        // 获取当前状态
        const footerState = getFooterState();
        console.log('[Footer State]', footerState);

        // 根据状态更新 UI
        switch (footerState.state) {
            case 'A': // 空购物车，未下单
                if ($primaryBtn) {
                    $primaryBtn.textContent = t('submit_order');
                    $primaryBtn.disabled = true;
                    $primaryBtn.dataset.action = 'submit';
                }
                if ($secondaryBtn) {
                    $secondaryBtn.textContent = t('view_cart');
                    $secondaryBtn.style.display = 'none'; // 隐藏次按钮
                    $secondaryBtn.dataset.action = 'cart';
                }
                if ($statusBadge) $statusBadge.style.display = 'none';
                if ($footerHint) {
                    $footerHint.textContent = t('select_items');
                    $footerHint.style.display = 'block';
                }
                break;

            case 'B': // 有购物车，未下单
                if ($primaryBtn) {
                    $primaryBtn.textContent = t('submit_order');
                    $primaryBtn.disabled = false;
                    $primaryBtn.dataset.action = 'submit';
                }
                if ($secondaryBtn) {
                    $secondaryBtn.textContent = t('view_cart');
                    $secondaryBtn.style.display = 'block';
                    $secondaryBtn.dataset.action = 'cart';
                }
                if ($statusBadge) $statusBadge.style.display = 'none';
                if ($footerHint) $footerHint.style.display = 'none';
                break;

            case 'C': // 空购物车，已下单
                if ($primaryBtn) {
                    $primaryBtn.textContent = t('go_pay');
                    $primaryBtn.disabled = false;
                    $primaryBtn.dataset.action = 'pay';
                }
                if ($secondaryBtn) {
                    $secondaryBtn.textContent = t('view_order');
                    $secondaryBtn.style.display = 'block';
                    $secondaryBtn.dataset.action = 'orders';
                }
                if ($statusBadge) {
                    $statusBadge.style.display = 'flex';
                    $statusBadge.dataset.orderRef = footerState.orderRef;
                    $statusBadge.dataset.canAdd = 'false';
                }
                if ($statusText) {
                    // 紧凑显示：只显示 "已下单" + 末尾4位订单号
                    const shortRef = getShortOrderRef(footerState.orderRef);
                    $statusText.textContent = `${t('chip_ordered')} #${shortRef}`;
                }
                if ($footerHint) $footerHint.style.display = 'none';
                break;

            case 'D': // 有购物车，已下单
                if ($primaryBtn) {
                    $primaryBtn.textContent = t('add_order');
                    $primaryBtn.disabled = false;
                    $primaryBtn.dataset.action = 'submit'; // 追加下单也是提交
                }
                if ($secondaryBtn) {
                    $secondaryBtn.textContent = t('view_cart');
                    $secondaryBtn.style.display = 'block';
                    $secondaryBtn.dataset.action = 'cart';
                }
                if ($statusBadge) {
                    $statusBadge.style.display = 'flex';
                    $statusBadge.dataset.orderRef = footerState.orderRef;
                    $statusBadge.dataset.canAdd = 'true';
                }
                if ($statusText) {
                    // 紧凑显示：只显示 "可追加"
                    $statusText.textContent = t('chip_can_add');
                }
                if ($footerHint) $footerHint.style.display = 'none';
                break;
        }
    }

    // ==================== 状态机按钮事件处理 ====================

    /**
     * 主按钮点击处理
     * - submit: 提交订单 / 追加下单
     * - pay: 去前台支付（打开支付弹窗）
     */
    function handlePrimaryBtnClick() {
        const $primaryBtn = document.getElementById('qr-primary-btn');
        const action = $primaryBtn?.dataset.action;

        console.log('[Primary Btn] action:', action);

        switch (action) {
            case 'submit':
                // 打开购物车弹窗，让用户确认后提交
                openCartModal();
                break;
            case 'pay':
                openPayModal();
                break;
            default:
                console.warn('[Primary Btn] Unknown action:', action);
        }
    }

    /**
     * 次按钮点击处理
     * - cart: 查看购物车
     * - orders: 查看订单
     */
    function handleSecondaryBtnClick() {
        const $secondaryBtn = document.getElementById('qr-secondary-btn');
        const action = $secondaryBtn?.dataset.action;

        console.log('[Secondary Btn] action:', action);

        switch (action) {
            case 'cart':
                openCartModal();
                break;
            case 'orders':
                openOrderModal();
                break;
            default:
                console.warn('[Secondary Btn] Unknown action:', action);
        }
    }

    /**
     * 打开前台买单弹窗 - 使用 i18n 和含税金额
     */
    function openPayModal() {
        const $payModal = document.getElementById('qr-pay-modal');
        if (!$payModal) return;

        const footerState = getFooterState();

        // DEBUG: 输出订单数据（从 POS 获取）
        console.log('[PayModal] footerState:', footerState);
        console.log('[PayModal] orders:', state.orders);
        if (state.orders.length > 0) {
            const o = state.orders[0];
            console.log('[PayModal] order[0]:', {
                amount_untaxed: o.amount_untaxed,
                amount_tax: o.amount_tax,
                amount_total_incl: o.amount_total_incl,
                total_amount: o.total_amount
            });
        }

        // 先应用 i18n 翻译（避免闪烁）
        applyI18n($payModal);
        
        // 特殊处理标题（保留emoji）
        const $payTitle = $payModal.querySelector('.qr-pay-header h2');
        if ($payTitle) {
            $payTitle.textContent = `💳 ${t('pay_title')}`;
        }

        // 填充买单信息
        const $payTable = document.getElementById('qr-pay-table');
        const $payOrder = document.getElementById('qr-pay-order');
        const $paySubtotal = document.getElementById('qr-pay-subtotal');
        const $payTax = document.getElementById('qr-pay-tax');
        const $payAmount = document.getElementById('qr-pay-amount');

        if ($payTable) $payTable.textContent = state.tableName || '---';
        if ($payOrder) $payOrder.textContent = footerState.orderRef || '---';

        // 显示未税金额、税额和含税合计（来自未结订单聚合）
        const subtotal = footerState.totalOrderAmountUntaxed || 0;
        const taxAmount = footerState.totalOrderTaxAmount || 0;
        const totalInclTax = footerState.totalOrderAmountInclTax || 0;

        if ($paySubtotal) $paySubtotal.textContent = `${t('currency')}${subtotal.toFixed(0)}`;
        if ($payTax) $payTax.textContent = `${t('currency')}${taxAmount.toFixed(0)}`;
        if ($payAmount) $payAmount.textContent = `${t('currency')}${totalInclTax.toFixed(0)}`;

        // P0-2: 使用 OverlayManager
        OverlayManager.open('pay');
    }

    /**
     * 关闭前台买单弹窗
     */
    function closePayModal() {
        // P0-2: 使用 OverlayManager
        OverlayManager.close();
    }

    /**
     * 复制文本到剪贴板
     */
    function copyToClipboard(text, successMsg) {
        if (!text) return;

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(() => {
                showToast(successMsg || '已复制');
            }).catch(err => {
                console.error('[Copy] Failed:', err);
                fallbackCopy(text, successMsg);
            });
        } else {
            fallbackCopy(text, successMsg);
        }
    }

    /**
     * 兼容模式复制
     */
    function fallbackCopy(text, successMsg) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();

        try {
            document.execCommand('copy');
            showToast(successMsg || '已复制');
        } catch (err) {
            console.error('[Copy Fallback] Failed:', err);
            showToast('复制失败，请手动复制');
        }

        document.body.removeChild(textArea);
    }

    // ==================== 订单状态 Toast 功能 ====================

    /**
     * 获取订单号末尾4-6位
     */
    function getShortOrderRef(orderRef) {
        if (!orderRef) return '---';
        // 如果是 QRO-20260105-XXXX 格式，取最后4位
        const parts = orderRef.split('-');
        if (parts.length >= 3) {
            return parts[parts.length - 1]; // 最后一段
        }
        // 否则取末尾6个字符
        return orderRef.slice(-6);
    }

    let orderToastTimer = null;

    /**
     * 显示订单状态 Toast
     * @param {Object} info - { orderRef, tableName, canAdd, autoHide }
     */
    function showOrderStatusToast(info = {}) {
        const $toast = document.getElementById('qr-order-toast');
        if (!$toast) return;

        const footerState = getFooterState();
        const orderRef = info.orderRef || footerState.orderRef || '---';
        const tableName = info.tableName || state.tableName || '---';
        const canAdd = info.canAdd !== undefined ? info.canAdd : (footerState.state === 'D');
        const autoHide = info.autoHide !== false; // 默认自动隐藏

        // 更新 Toast 内容
        const $title = document.getElementById('qr-order-toast-title');
        const $ref = document.getElementById('qr-order-toast-ref');
        const $table = document.getElementById('qr-order-toast-table');
        const $hintRow = document.getElementById('qr-order-toast-hint-row');

        if ($title) $title.textContent = t('order_submitted_title');
        if ($ref) $ref.textContent = orderRef;
        if ($table) $table.textContent = tableName;
        if ($hintRow) $hintRow.style.display = canAdd ? 'flex' : 'none';

        // 显示 Toast
        $toast.classList.add('show');

        // 清除之前的定时器
        if (orderToastTimer) {
            clearTimeout(orderToastTimer);
            orderToastTimer = null;
        }

        // 自动隐藏（3秒后）
        if (autoHide) {
            orderToastTimer = setTimeout(() => {
                hideOrderStatusToast();
            }, 4000);
        }
    }

    /**
     * 隐藏订单状态 Toast
     */
    function hideOrderStatusToast() {
        const $toast = document.getElementById('qr-order-toast');
        if ($toast) {
            $toast.classList.remove('show');
        }
        if (orderToastTimer) {
            clearTimeout(orderToastTimer);
            orderToastTimer = null;
        }
    }

    /**
     * 状态 chip 点击处理 - 展示完整订单信息
     */
    function handleStatusChipClick() {
        const $statusBadge = document.getElementById('qr-order-status-badge');
        if (!$statusBadge) return;

        const orderRef = $statusBadge.dataset.orderRef || '';
        const canAdd = $statusBadge.dataset.canAdd === 'true';

        if (orderRef) {
            showOrderStatusToast({
                orderRef: orderRef,
                canAdd: canAdd,
                autoHide: false // 点击打开的不自动关闭
            });
        }
    }

    // ==================== Modal Functions ====================

    // ========== ScrollLock 工具：带引用计数，防止多弹层互相干扰 ==========
    const ScrollLock = {
        _lockCount: 0,
        _lockReasons: new Map(), // reason -> count
        _scrollY: 0,

        // 锁定滚动
        lock(reason = 'default') {
            const prevCount = this._lockCount;

            // 更新引用计数
            this._lockReasons.set(reason, (this._lockReasons.get(reason) || 0) + 1);
            this._lockCount++;

            // 只在首次锁定时添加 class
            if (prevCount === 0) {
                this._scrollY = window.scrollY;
                document.documentElement.classList.add('qr-scroll-locked');
                document.body.classList.add('qr-scroll-locked');
                console.log(`[ScrollLock] Locked (reason: ${reason}, count: ${this._lockCount})`);
            } else {
                console.log(`[ScrollLock] Already locked, added reason: ${reason} (count: ${this._lockCount})`);
            }
        },

        // 解锁滚动
        unlock(reason = 'default') {
            // 更新引用计数
            const reasonCount = this._lockReasons.get(reason) || 0;
            if (reasonCount > 0) {
                this._lockReasons.set(reason, reasonCount - 1);
                if (this._lockReasons.get(reason) === 0) {
                    this._lockReasons.delete(reason);
                }
                this._lockCount = Math.max(0, this._lockCount - 1);
            }

            // 只有计数归零才移除 class
            if (this._lockCount === 0) {
                document.documentElement.classList.remove('qr-scroll-locked');
                document.body.classList.remove('qr-scroll-locked');
                console.log(`[ScrollLock] Unlocked (reason: ${reason})`);
            } else {
                console.log(`[ScrollLock] Still locked (remaining: ${this._lockCount}, reasons: ${Array.from(this._lockReasons.keys()).join(', ')})`);
            }
        },

        // 强制解锁（用于错误恢复）
        forceUnlock() {
            this._lockCount = 0;
            this._lockReasons.clear();
            document.documentElement.classList.remove('qr-scroll-locked');
            document.body.classList.remove('qr-scroll-locked');
            console.log('[ScrollLock] Force unlocked');
        },

        // 检查是否锁定
        isLocked() {
            return this._lockCount > 0;
        }
    };

    // 兼容旧代码的包装函数
    function lockBodyScroll() {
        ScrollLock.lock('modal');
    }

    function unlockBodyScroll() {
        ScrollLock.unlock('modal');
    }

    // ==================== Modal Functions (使用 OverlayManager) ====================

    function openProductModal(productId) {
        const product = state.products.find(p => p.id === productId);
        if (!product) return;

        state.selectedProduct = product;

        const $detail = document.getElementById('qr-product-detail');
        $detail.innerHTML = `
            ${product.video_url ? `
                <video class="qr-product-detail-video" controls>
                    <source src="${product.video_url}" type="video/mp4"/>
                </video>
            ` : `
                <img class="qr-product-detail-image" src="${product.image_url}" alt="${product.name}"/>
            `}
            <div class="qr-product-detail-name">${product.name}</div>
            <div class="qr-product-detail-desc">${product.description || ''}</div>
            <div class="qr-product-detail-price">${t('currency')}${product.price.toFixed(0)}</div>
            <div class="qr-qty-control">
                <button class="qr-qty-btn" onclick="QrOrdering.changeQty(-1)">-</button>
                <span class="qr-qty-value" id="qr-detail-qty">1</span>
                <button class="qr-qty-btn" onclick="QrOrdering.changeQty(1)">+</button>
            </div>
            <input type="text" class="qr-note-input" id="qr-detail-note" placeholder="${t('note_placeholder')}"/>
            <button class="qr-add-to-cart-btn" onclick="QrOrdering.addFromDetail()">${t('add_to_cart')}</button>
        `;

        // P0-2: 使用 OverlayManager
        OverlayManager.open('product');
    }

    function closeProductModal() {
        state.selectedProduct = null;
        // P0-2: 使用 OverlayManager
        OverlayManager.close();
    }

    function openCartModal() {
        renderCartItems();
        // P0-2: 使用 OverlayManager
        OverlayManager.open('cart');
    }

    function closeCartModal() {
        // P0-2: 使用 OverlayManager
        OverlayManager.close();
    }

    function openOrderModal() {
        renderOrders();
        // P0-2: 使用 OverlayManager
        OverlayManager.open('order');
    }

    function closeOrderModal() {
        // P0-2: 使用 OverlayManager
        OverlayManager.close();
    }

    function handleCheckout() {
        // 显示提示信息，让用户联系服务员结账
        showToast(t('call_waiter'));
        // 也可以打开订单弹窗让用户查看
        openOrderModal();
    }

    // ==================== Helper Functions ====================
    function t(key) {
        return i18n[state.lang]?.[key] || i18n.zh_CN[key] || key;
    }

    function applyI18n(root) {
        // Update placeholders and text
        const container = root || document;
        container.querySelectorAll('[data-i18n]').forEach(el => {
            el.textContent = t(el.dataset.i18n);
        });
        container.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            el.placeholder = t(el.dataset.i18nPlaceholder);
        });
    }

    function showToast(message) {
        const $msg = document.getElementById('qr-toast-message');
        $msg.textContent = message;
        $toast.classList.add('show');
        setTimeout(() => {
            $toast.classList.remove('show');
        }, 2000);
    }

    function getCategoryIcon(name) {
        const icons = {
            '热菜': '🍲',
            '凉菜': '🥗',
            '主食': '🍚',
            '饮品': '🥤',
            '酒水': '🍺',
            '甜点': '🍰',
            '汤类': '🍜',
            '小吃': '🍟',
        };
        for (const [key, icon] of Object.entries(icons)) {
            if (name.includes(key)) return icon;
        }
        return '🍽️';
    }

    function filterProducts(query) {
        renderProducts(query);
    }

    // ==================== Debug Panel ====================
    function updateDebugPanel() {
        const debugPanel = document.getElementById('qr-debug-panel');
        if (!debugPanel) return;
        
        // Update assets status
        const assetsEl = document.getElementById('qr-debug-assets');
        if (assetsEl) {
            assetsEl.textContent = typeof odoo !== 'undefined' ? '✓ loaded' : '✗ failed';
        }
        
        // Update JS status
        const jsEl = document.getElementById('qr-debug-js');
        if (jsEl) {
            jsEl.textContent = window.QR_ORDERING_BUILD ? '✓ ' + window.QR_ORDERING_BUILD : '✗ failed';
        }
    }
    
    // Wrap apiCall to update debug panel
    const originalApiCall = apiCall;
    apiCall = async function(endpoint, data) {
        try {
            const result = await originalApiCall(endpoint, data);
            const apiEl = document.getElementById('qr-debug-api');
            if (apiEl) {
                apiEl.textContent = result && result.success ? '✓ success' : '✗ ' + (result?.error || 'failed');
            }
            return result;
        } catch (error) {
            const apiEl = document.getElementById('qr-debug-api');
            if (apiEl) {
                apiEl.textContent = '✗ error: ' + error.message;
            }
            throw error;
        }
    };

    // ==================== Public API ====================
    window.QrOrdering = {
        selectCategory(categoryId) {
            state.selectedCategory = categoryId;
            renderCategories();
            renderProducts();
        },

        openProduct(productId) {
            openProductModal(productId);
        },

        quickAdd(productId) {
            addToCart(productId, 1, '');
        },

        changeQty(delta) {
            const $qty = document.getElementById('qr-detail-qty');
            let qty = parseInt($qty.textContent) + delta;
            if (qty < 1) qty = 1;
            if (qty > 99) qty = 99;
            $qty.textContent = qty;
        },

        addFromDetail() {
            if (!state.selectedProduct) return;
            const qty = parseInt(document.getElementById('qr-detail-qty').textContent);
            const note = document.getElementById('qr-detail-note').value;
            addToCart(state.selectedProduct.id, qty, note).then(success => {
                if (success) closeProductModal();
            });
        },

        updateCart(lineId, qty) {
            updateCartItem(lineId, qty);
        },
        
        filterHighlight() {
            // P1-5: 筛选推荐菜品
            const highlightProducts = state.products.filter(p => p.highlight);
            if (highlightProducts.length > 0) {
                state.products = highlightProducts;
                renderProducts();
            }
        },
    };

    // Initialize when DOM is ready
    try {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
        } else {
            init();
        }
    } catch (error) {
        console.error('QR Ordering initialization error:', error);
        // Try to show error to user
        const $app = document.getElementById('qr-ordering-app');
        if ($app) {
            $app.innerHTML = '<div style="padding: 20px; text-align: center;"><p>页面加载失败，请刷新重试</p><p style="color: #999; font-size: 12px;">' + error.message + '</p></div>';
        }
    }

})();

