/**
 * QR Ordering V2 - Mobile Optimized JavaScript
 * 移动端极致体验版
 * Build: 2026-01-05
 */

(function() {
    'use strict';

    // Build version
    window.QR_ORDERING_V2_BUILD = '2026-01-05T18:00';

    // ==================== State Management ====================
    const state = {
        tableToken: '',
        accessToken: '',
        tableName: '',
        lang: 'zh_CN',
        session: null,
        menu: {
            categories: [],
            products: []
        },
        cart: [],
        orders: [],
        currentCategory: 'all',
        // V2 specific
        pinnedProducts: [],
        highlightProducts: [],
        currentCarouselIndex: 0,
        carouselTimer: null,
        pipVideoUrl: null,
        pipProduct: null,
    };

    // ==================== DOM Elements ====================
    let $app, $pinnedCarousel, $carouselTrack, $carouselDots, $carouselProgress,
        $recoRail, $recoScroll, $categoryChips, $chipsScroll,
        $productGrid, $bottomBar, $cartBadge, $cartItems, $cartTotal,
        $reviewBtn, $pipOverlay, $pipVideo, $pipPlay, $pipMute, $pipClose,
        $cartModal, $cartModalBody, $cartModalTotal, $checkoutBtn, $cartCloseBtn,
        $ordersModal, $ordersModalBody, $ordersCloseBtn,
        $toast, $searchInput;

    // ==================== Init ====================
    function init() {
        console.log('[QR V2] Initializing...', window.QR_ORDERING_V2_BUILD);

        $app = document.getElementById('qr-app-v2');
        if (!$app) {
            console.error('[QR V2] App container not found!');
            return;
        }

        // Get data attributes
        state.tableToken = $app.dataset.tableToken;
        state.accessToken = $app.dataset.accessToken;
        state.tableName = $app.dataset.tableName;
        state.lang = $app.dataset.lang || 'zh_CN';

        // Cache DOM elements
        cacheElements();

        // Setup event listeners
        setupEventListeners();

        // Load data
        loadInitData();

        // Dispatch ready event
        window.dispatchEvent(new Event('qr-v2-ready'));
        console.log('[QR V2] Initialized successfully');
    }

    function cacheElements() {
        $pinnedCarousel = document.getElementById('qr-v2-pinned-carousel');
        $carouselTrack = document.getElementById('qr-v2-carousel-track');
        $carouselDots = document.getElementById('qr-v2-carousel-dots');
        $carouselProgress = document.getElementById('qr-v2-carousel-progress');
        
        $recoRail = document.getElementById('qr-v2-reco-rail');
        $recoScroll = document.getElementById('qr-v2-reco-scroll');
        
        $categoryChips = document.getElementById('qr-v2-category-chips');
        $chipsScroll = document.getElementById('qr-v2-chips-scroll');
        
        $productGrid = document.getElementById('qr-v2-product-grid');
        
        $bottomBar = document.getElementById('qr-v2-bottom-bar');
        $cartBadge = document.getElementById('qr-v2-cart-badge');
        $cartItems = document.getElementById('qr-v2-cart-items');
        $cartTotal = document.getElementById('qr-v2-cart-total');
        $reviewBtn = document.getElementById('qr-v2-review-btn');
        
        $pipOverlay = document.getElementById('qr-v2-pip-overlay');
        $pipVideo = document.getElementById('qr-v2-pip-video');
        $pipPlay = document.getElementById('qr-v2-pip-play');
        $pipMute = document.getElementById('qr-v2-pip-mute');
        $pipClose = document.getElementById('qr-v2-pip-close');
        
        $cartModal = document.getElementById('qr-v2-cart-modal');
        $cartModalBody = document.getElementById('qr-v2-cart-items-list');
        $cartModalTotal = document.getElementById('qr-v2-cart-modal-total');
        $checkoutBtn = document.getElementById('qr-v2-checkout-btn');
        $cartCloseBtn = document.getElementById('qr-v2-cart-close');
        
        $ordersModal = document.getElementById('qr-v2-orders-modal');
        $ordersModalBody = document.getElementById('qr-v2-orders-list');
        $ordersCloseBtn = document.getElementById('qr-v2-orders-close');
        
        $toast = document.getElementById('qr-v2-toast');
        $searchInput = document.getElementById('qr-v2-search-input');
    }

    function setupEventListeners() {
        // Review button
        $reviewBtn.addEventListener('click', openCartModal);
        
        // PiP controls
        $pipPlay.addEventListener('click', togglePipPlay);
        $pipMute.addEventListener('click', togglePipMute);
        $pipClose.addEventListener('click', closePip);
        
        // Cart modal
        $cartCloseBtn.addEventListener('click', closeCartModal);
        $checkoutBtn.addEventListener('click', submitOrder);
        
        // Orders modal
        $ordersCloseBtn.addEventListener('click', closeOrdersModal);
        
        // Search
        $searchInput.addEventListener('input', handleSearch);
        
        // Modal backdrop click
        $cartModal.addEventListener('click', (e) => {
            if (e.target === $cartModal) closeCartModal();
        });
        $ordersModal.addEventListener('click', (e) => {
            if (e.target === $ordersModal) closeOrdersModal();
        });
    }

    // ==================== API Calls ====================
    async function apiCall(endpoint, data = {}) {
        try {
            const response = await fetch(`/qr/api/${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        table_token: state.tableToken,
                        access_token: state.accessToken,
                        ...data
                    }
                })
            });

            const result = await response.json();
            
            if (result.error) {
                console.error('[QR V2] API Error:', result.error);
                return null;
            }

            return result.result;
        } catch (error) {
            console.error('[QR V2] Network Error:', error);
            showToast('网络错误，请重试');
            return null;
        }
    }

    async function loadInitData() {
        const result = await apiCall('init', { lang: state.lang });
        
        if (result && result.success) {
            state.session = result.data.session;
            state.menu = result.data.menu;
            state.accessToken = result.data.access_token;
            
            // Get current order
            const currentOrder = result.data.current_order;
            if (currentOrder && currentOrder.lines) {
                state.cart = currentOrder.lines.map(line => ({
                    productId: line.product_id,
                    name: line.product_name,
                    price: line.price_unit,  // 修复：使用正确的字段名 price_unit
                    qty: line.qty,
                    note: line.note || ''
                }));
            }

            // Process products
            processProducts();
            
            // Render UI
            renderCarousel();
            renderRecoRail();
            renderCategoryChips();
            renderProductGrid();
            updateCartUI();
        } else {
            showToast('加载失败，请刷新重试');
        }
    }

    function processProducts() {
        // Separate pinned and highlighted products
        state.pinnedProducts = state.menu.products
            .filter(p => p.pinned && p.video_url)
            .sort((a, b) => a.pinned_sequence - b.pinned_sequence);
        
        state.highlightProducts = state.menu.products
            .filter(p => p.highlight && !p.pinned)
            .slice(0, 10);
    }

    // ==================== Carousel ====================
    function renderCarousel() {
        if (state.pinnedProducts.length === 0) {
            $pinnedCarousel.style.display = 'none';
            return;
        }

        $pinnedCarousel.style.display = 'block';
        $carouselTrack.innerHTML = '';
        $carouselDots.innerHTML = '';

        state.pinnedProducts.forEach((product, index) => {
            // Create slide
            const slide = document.createElement('div');
            slide.className = 'qr-v2-carousel-slide';
            slide.innerHTML = `
                <video class="qr-v2-carousel-video" 
                       src="${product.video_url}" 
                       muted 
                       playsinline 
                       webkit-playsinline
                       loop
                       preload="metadata"
                       poster="${product.image_url}"></video>
                <div class="qr-v2-carousel-content">
                    <div class="qr-v2-carousel-title">${product.name}</div>
                    <div class="qr-v2-carousel-price">¥${product.price_with_tax.toFixed(0)}</div>
                    <div class="qr-v2-carousel-stepper">
                        <button class="qr-v2-carousel-stepper-btn" onclick="window.qrV2.carouselDecrement(${product.id})">-</button>
                        <span class="qr-v2-carousel-stepper-qty" id="carousel-qty-${product.id}">${getProductQty(product.id)}</span>
                        <button class="qr-v2-carousel-stepper-btn" onclick="window.qrV2.carouselIncrement(${product.id})">+</button>
                    </div>
                </div>
            `;
            $carouselTrack.appendChild(slide);

            // Create dot
            const dot = document.createElement('div');
            dot.className = 'qr-v2-carousel-dot' + (index === 0 ? ' active' : '');
            dot.addEventListener('click', () => goToSlide(index));
            $carouselDots.appendChild(dot);
        });

        // Start auto-play
        startCarouselAutoPlay();

        // Play first video
        playCarouselVideo(0);
    }

    function startCarouselAutoPlay() {
        if (state.carouselTimer) {
            clearInterval(state.carouselTimer);
        }

        let progress = 0;
        const duration = 5000; // 5 seconds
        const interval = 50;

        state.carouselTimer = setInterval(() => {
            progress += interval;
            const percent = (progress / duration) * 100;
            $carouselProgress.style.width = `${percent}%`;

            if (progress >= duration) {
                progress = 0;
                nextSlide();
            }
        }, interval);
    }

    function nextSlide() {
        const nextIndex = (state.currentCarouselIndex + 1) % state.pinnedProducts.length;
        goToSlide(nextIndex);
    }

    function goToSlide(index) {
        // Pause current video
        const currentVideos = $carouselTrack.querySelectorAll('video');
        currentVideos[state.currentCarouselIndex]?.pause();

        // Update index
        state.currentCarouselIndex = index;

        // Move track
        $carouselTrack.style.transform = `translateX(-${index * 100}%)`;

        // Update dots
        const dots = $carouselDots.querySelectorAll('.qr-v2-carousel-dot');
        dots.forEach((dot, i) => {
            dot.classList.toggle('active', i === index);
        });

        // Play new video
        playCarouselVideo(index);

        // Reset progress
        $carouselProgress.style.width = '0%';
    }

    function playCarouselVideo(index) {
        const video = $carouselTrack.querySelectorAll('video')[index];
        if (video) {
            video.play().catch(() => {
                console.log('[QR V2] Autoplay blocked, showing poster');
            });
        }
    }

    // Expose carousel methods
    window.qrV2 = window.qrV2 || {};
    window.qrV2.carouselIncrement = function(productId) {
        addToCart(productId, 1, '');
    };
    window.qrV2.carouselDecrement = function(productId) {
        const item = state.cart.find(i => i.productId === productId);
        if (item && item.qty > 0) {
            addToCart(productId, -1, '');
        }
    };

    // ==================== Reco Rail ====================
    function renderRecoRail() {
        if (state.highlightProducts.length === 0) {
            $recoRail.style.display = 'none';
            return;
        }

        $recoRail.style.display = 'block';
        $recoScroll.innerHTML = '';

        state.highlightProducts.forEach(product => {
            const card = document.createElement('div');
            card.className = 'qr-v2-reco-card';
            card.innerHTML = `
                <div class="qr-v2-reco-thumb">
                    <img src="${product.image_url}" alt="${product.name}">
                    ${product.video_url ? '<div class="qr-v2-reco-play">▶</div>' : ''}
                </div>
                <div class="qr-v2-reco-info">
                    <div class="qr-v2-reco-name">${product.name}</div>
                    <div class="qr-v2-reco-price">¥${product.price_with_tax.toFixed(0)}</div>
                </div>
            `;

            card.addEventListener('click', () => {
                if (product.video_url) {
                    openPip(product);
                }
            });

            $recoScroll.appendChild(card);
        });
    }

    // ==================== PiP Video ====================
    function openPip(product) {
        state.pipProduct = product;
        state.pipVideoUrl = product.video_url;
        
        $pipVideo.src = state.pipVideoUrl;
        $pipVideo.muted = true;
        $pipVideo.play();
        
        $pipOverlay.style.display = 'block';
        $pipPlay.textContent = '⏸';
    }

    function closePip() {
        $pipVideo.pause();
        $pipVideo.src = '';
        $pipOverlay.style.display = 'none';
        state.pipProduct = null;
        state.pipVideoUrl = null;
    }

    function togglePipPlay() {
        if ($pipVideo.paused) {
            $pipVideo.play();
            $pipPlay.textContent = '⏸';
        } else {
            $pipVideo.pause();
            $pipPlay.textContent = '▶';
        }
    }

    function togglePipMute() {
        $pipVideo.muted = !$pipVideo.muted;
        $pipMute.textContent = $pipVideo.muted ? '🔇' : '🔊';
    }

    // ==================== Category Chips ====================
    function renderCategoryChips() {
        $chipsScroll.innerHTML = '';

        // Add "All" chip
        const allChip = document.createElement('div');
        allChip.className = 'qr-v2-chip active';
        allChip.textContent = '全部';
        allChip.dataset.categoryId = 'all';
        allChip.addEventListener('click', () => selectCategory('all'));
        $chipsScroll.appendChild(allChip);

        // Add category chips
        state.menu.categories.forEach(cat => {
            const chip = document.createElement('div');
            chip.className = 'qr-v2-chip';
            chip.textContent = cat.name;
            chip.dataset.categoryId = cat.id;
            chip.addEventListener('click', () => selectCategory(cat.id));
            $chipsScroll.appendChild(chip);
        });
    }

    function selectCategory(categoryId) {
        state.currentCategory = categoryId;

        // Update chips
        $chipsScroll.querySelectorAll('.qr-v2-chip').forEach(chip => {
            chip.classList.toggle('active', chip.dataset.categoryId == categoryId);
        });

        // Re-render products
        renderProductGrid();
    }

    // ==================== Product Grid ====================
    function renderProductGrid() {
        const products = state.currentCategory === 'all'
            ? state.menu.products
            : state.menu.products.filter(p => p.category_id == state.currentCategory);

        $productGrid.innerHTML = '';

        // P1-5: 类别空态增强
        if (products.length === 0) {
            const hasHighlight = state.menu.products.some(p => p.highlight);
            const hasOrders = state.orders && state.orders.length > 0;
            $productGrid.innerHTML = `
                <div class="qr-v2-empty-state">
                    <div class="qr-v2-empty-icon">🍽️</div>
                    <div class="qr-v2-empty-title">暂无菜品</div>
                    <div class="qr-v2-empty-actions">
                        <button class="qr-v2-empty-btn" onclick="window.qrV2.selectCategory('all')">返回全部</button>
                        ${hasHighlight ? `<button class="qr-v2-empty-btn" onclick="window.qrV2.selectCategory('all'); window.qrV2.filterHighlight();">查看推荐</button>` : ''}
                        ${hasOrders ? `<button class="qr-v2-empty-btn" onclick="window.qrV2.openOrdersModal();">查看已点</button>` : ''}
                    </div>
                </div>
            `;
            return;
        }

        products.forEach(product => {
            const card = document.createElement('div');
            card.className = 'qr-v2-product-card';
            
            const qty = getProductQty(product.id);
            
            card.innerHTML = `
                <div class="qr-v2-product-image">
                    <img src="${product.image_url}" alt="${product.name}">
                    ${product.highlight ? '<div class="qr-v2-product-badge">推荐</div>' : ''}
                </div>
                <div class="qr-v2-product-info">
                    <div class="qr-v2-product-name">${product.name}</div>
                    ${product.description ? `<div class="qr-v2-product-desc">${product.description}</div>` : ''}
                    <div class="qr-v2-product-footer">
                        <div class="qr-v2-product-price">¥${product.price_with_tax.toFixed(0)}</div>
                        <div class="qr-v2-product-stepper">
                            ${qty > 0 ? `
                                <button class="qr-v2-stepper-btn" onclick="event.stopPropagation(); window.qrV2.decrementProduct(${product.id})">-</button>
                                <span class="qr-v2-stepper-qty" id="product-qty-${product.id}">${qty}</span>
                            ` : ''}
                            <button class="qr-v2-stepper-btn" onclick="event.stopPropagation(); window.qrV2.incrementProduct(${product.id})">+</button>
                        </div>
                    </div>
                </div>
            `;

            $productGrid.appendChild(card);
        });
    }

    // Expose product methods
    window.qrV2.incrementProduct = function(productId) {
        addToCart(productId, 1, '');
    };
    window.qrV2.decrementProduct = function(productId) {
        addToCart(productId, -1, '');
    };
    
    // P1-5: 暴露类别和筛选方法
    window.qrV2.selectCategory = function(categoryId) {
        selectCategory(categoryId);
    };
    
    window.qrV2.filterHighlight = function() {
        // P1-5: 筛选推荐菜品
        const highlightProducts = state.menu.products.filter(p => p.highlight);
        if (highlightProducts.length > 0) {
            state.menu.products = highlightProducts;
            renderProductGrid();
        }
    };
    
    window.qrV2.openOrdersModal = function() {
        // P1-5: 打开已下单列表
        OverlayManager.open('order');
        // 如果有订单列表渲染函数，调用它
        if (typeof renderOrders === 'function') {
            renderOrders();
        }
    };

    // ==================== Cart ====================
    async function addToCart(productId, qty, note) {
        const result = await apiCall('cart/add', {
            product_id: productId,
            qty: qty,
            note: note
        });

        if (result && result.success) {
            const order = result.data;
            state.cart = order.lines.map(line => ({
                productId: line.product_id,
                name: line.product_name,
                price: line.price_unit,  // 修复：使用正确的字段名 price_unit
                qty: line.qty,
                note: line.note || ''
            }));

            updateCartUI();
            renderProductGrid();
            updateCarouselSteppers();
        }
    }

    function updateCartUI() {
        const totalQty = state.cart.reduce((sum, item) => sum + item.qty, 0);
        // P0-1: 确保空购物车时金额为0
        const totalAmount = state.cart.length === 0 ? 0 : state.cart.reduce((sum, item) => sum + item.price * item.qty, 0);

        if ($cartBadge) $cartBadge.textContent = totalQty;
        if ($cartItems) $cartItems.textContent = `${totalQty} 件`;
        if ($cartTotal) $cartTotal.textContent = `¥${totalAmount.toFixed(0)}`;

        if ($reviewBtn) {
            $reviewBtn.disabled = totalQty === 0;
            if (totalQty === 0) {
                $reviewBtn.classList.add('qr-v2-disabled');
            } else {
                $reviewBtn.classList.remove('qr-v2-disabled');
            }
        }
    }

    function updateCarouselSteppers() {
        state.pinnedProducts.forEach(product => {
            const qtyEl = document.getElementById(`carousel-qty-${product.id}`);
            if (qtyEl) {
                qtyEl.textContent = getProductQty(product.id);
            }
        });
    }

    function getProductQty(productId) {
        const item = state.cart.find(i => i.productId === productId);
        return item ? item.qty : 0;
    }

    // ==================== Modals ====================
    // ==================== OverlayManager 单例管理器 ====================
    // P0-2: 弹窗栈治理 - 任意时刻只允许一个主 overlay
    const OverlayManager = {
        current: null,

        open(name) {
            // 如果已有不同的 overlay，先关闭
            if (this.current && this.current !== name) {
                this._hide(this.current);
            }

            this.current = name;
            this._show(name);

            // P0-2: 隐藏底部栏
            const $footer = document.getElementById('qr-v2-bottom-bar');
            if ($footer) {
                $footer.classList.add('qr-v2-hidden');
            }

            lockScroll();
        },

        close() {
            if (this.current) {
                const name = this.current;
                this._hide(name);
                this.current = null;

                // P0-2: 恢复底部栏
                const $footer = document.getElementById('qr-v2-bottom-bar');
                if ($footer) {
                    $footer.classList.remove('qr-v2-hidden');
                }

                unlockScroll();
            }
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
                'cart': 'qr-v2-cart-modal',
                'order': 'qr-v2-orders-modal',
            };
            return map[name] || name;
        }
    };

    function openCartModal() {
        // P0-2: 使用 OverlayManager（会自动隐藏底部栏）
        OverlayManager.open('cart');
        // P0-1: 确保渲染时更新空态和合计
        renderCartItems();
    }

    function closeCartModal() {
        // P0-2: 使用 OverlayManager
        OverlayManager.close();
    }

    function closeOrdersModal() {
        // P0-2: 使用 OverlayManager
        OverlayManager.close();
    }

    function renderCartItems() {
        // P0-1: 空态处理
        if (state.cart.length === 0) {
            $cartModalBody.innerHTML = '<div class="qr-v2-loading">购物车是空的</div>';
            // P0-1: 确保合计显示为 0
            if ($cartModalTotal) $cartModalTotal.textContent = '¥0';
            // P0-1: 禁用下单按钮，主CTA变为"去点餐"
            if ($checkoutBtn) {
                $checkoutBtn.disabled = true;
                $checkoutBtn.textContent = '去点餐';
                $checkoutBtn.onclick = () => closeCartModal();
            }
            return;
        }

        // 有菜品时恢复显示
        if ($checkoutBtn) {
            $checkoutBtn.disabled = false;
            $checkoutBtn.textContent = '提交订单';
            $checkoutBtn.onclick = () => submitOrder();
        }

        $cartModalBody.innerHTML = state.cart.map(item => `
            <div class="qr-v2-cart-item">
                <div class="qr-v2-cart-item-name">${item.name}</div>
                <div class="qr-v2-cart-item-footer">
                    <div class="qr-v2-cart-item-price">¥${item.price.toFixed(0)} × ${item.qty}</div>
                    <div class="qr-v2-cart-item-total">¥${(item.price * item.qty).toFixed(0)}</div>
                </div>
            </div>
        `).join('');

        // P0-1: 确保金额从 state.cart 计算
        const totalAmount = state.cart.reduce((sum, item) => sum + item.price * item.qty, 0);
        if ($cartModalTotal) $cartModalTotal.textContent = `¥${totalAmount.toFixed(0)}`;
    }

    async function submitOrder() {
        if (state.cart.length === 0) {
            showToast('购物车是空的');
            return;
        }

        const result = await apiCall('cart/submit');
        
        if (result && result.success) {
            // P0-1: 下单成功后清空购物车
            state.cart = [];
            state.orders.unshift(result.data);
            
            // P0-1: 更新底部栏（金额清零）
            updateCartUI();
            
            // P0-2: 使用 OverlayManager 关闭弹层
            OverlayManager.close();
            
            // P1-2: 更新菜品卡片（清除已加购数量 badge）
            renderProductGrid();
            updateCarouselSteppers();
            
            // P0-3: 显示成功 Toast（不叠加modal）
            showToast('订单已提交！');
        }
    }

    // ==================== Search ====================
    function handleSearch(e) {
        const query = e.target.value.trim().toLowerCase();
        
        if (!query) {
            renderProductGrid();
            return;
        }

        const filtered = state.menu.products.filter(p => 
            p.name.toLowerCase().includes(query) ||
            (p.description && p.description.toLowerCase().includes(query))
        );

        renderFilteredProducts(filtered);
    }

    function renderFilteredProducts(products) {
        $productGrid.innerHTML = '';

        if (products.length === 0) {
            $productGrid.innerHTML = '<div class="qr-v2-loading">未找到相关菜品</div>';
            return;
        }

        products.forEach(product => {
            const card = document.createElement('div');
            card.className = 'qr-v2-product-card';
            
            const qty = getProductQty(product.id);
            
            card.innerHTML = `
                <div class="qr-v2-product-image">
                    <img src="${product.image_url}" alt="${product.name}">
                </div>
                <div class="qr-v2-product-info">
                    <div class="qr-v2-product-name">${product.name}</div>
                    <div class="qr-v2-product-footer">
                        <div class="qr-v2-product-price">¥${product.price_with_tax.toFixed(0)}</div>
                        <div class="qr-v2-product-stepper">
                            ${qty > 0 ? `
                                <button class="qr-v2-stepper-btn" onclick="event.stopPropagation(); window.qrV2.decrementProduct(${product.id})">-</button>
                                <span class="qr-v2-stepper-qty">${qty}</span>
                            ` : ''}
                            <button class="qr-v2-stepper-btn" onclick="event.stopPropagation(); window.qrV2.incrementProduct(${product.id})">+</button>
                        </div>
                    </div>
                </div>
            `;

            $productGrid.appendChild(card);
        });
    }

    // ==================== Utilities ====================
    function showToast(message) {
        $toast.textContent = message;
        $toast.classList.add('show');
        setTimeout(() => $toast.classList.remove('show'), 2000);
    }

    function lockScroll() {
        document.documentElement.classList.add('qr-v2-scroll-locked');
    }

    function unlockScroll() {
        document.documentElement.classList.remove('qr-v2-scroll-locked');
    }

    // ==================== Initialize ====================
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
