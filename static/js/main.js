// SIZZLING_SETTINGS is injected inline by index.html before this file loads.

function waLink(message){
  return `https://wa.me/${SIZZLING_SETTINGS.whatsapp_number}?text=${encodeURIComponent(message)}`;
}

// ======================================================================
// TOAST NOTIFICATIONS
// ======================================================================
function showToast(message, icon = "✓") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerHTML = `<span class="toast-icon">${icon}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("toast-out");
    setTimeout(() => toast.remove(), 300);
  }, 2800);
}

// ======================================================================
// CART (stored in the browser via localStorage — works across pages)
// ======================================================================
const CART_KEY = "sizzling_cart";

function getCart(){
  try {
    const raw = localStorage.getItem(CART_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function saveCart(cart){
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
  updateCartBadge();
}

const COUPON_KEY = "sizzling_coupon";

function getAppliedCoupon(){
  try {
    return localStorage.getItem(COUPON_KEY) || null;
  } catch (e) {
    return null;
  }
}

function setAppliedCoupon(code){
  try {
    if (code) localStorage.setItem(COUPON_KEY, code.toUpperCase());
    else localStorage.removeItem(COUPON_KEY);
  } catch (e) {}
}

function calculateDiscount(subtotal){
  const code = getAppliedCoupon();
  if (code === "KBA200" && subtotal > 0) {
    return Math.min(200, subtotal);
  }
  return 0;
}

function addToCart({ id, name, category, price, image, size, stock }){
  if (stock === 0 || stock === "0") {
    showToast(`"${name}" is currently out of stock.`, "🚫");
    return getCart();
  }
  const cart = getCart();
  const existing = cart.find(item => item.id === id && item.size === size);
  if (existing) {
    existing.qty += 1;
  } else {
    cart.push({ id, name, category, price: parseFloat(price), image, size, qty: 1 });
  }
  saveCart(cart);
  showToast(`Added <strong>${name}</strong> (Size ${size}) to cart`);
  return cart;
}

function updateCartQty(index, newQty){
  const cart = getCart();
  if (newQty < 1) {
    cart.splice(index, 1);
  } else {
    cart[index].qty = newQty;
  }
  saveCart(cart);
  renderCartDrawer();
}

function removeFromCart(index){
  const cart = getCart();
  const item = cart[index];
  cart.splice(index, 1);
  saveCart(cart);
  renderCartDrawer();
  if (item) showToast(`Removed ${item.name} from cart`, "✕");
}

function cartTotal(cart){
  return cart.reduce((sum, item) => sum + item.price * item.qty, 0);
}

function cartCount(cart){
  return cart.reduce((sum, item) => sum + item.qty, 0);
}

function updateCartBadge(){
  const el = document.getElementById("cartCount");
  if (el) {
    const count = cartCount(getCart());
    el.textContent = count;
    el.style.transform = "scale(1.25)";
    setTimeout(() => el.style.transform = "scale(1)", 200);
  }
}

function renderCartDrawer(){
  const container = document.getElementById("cartItemsContainer");
  const foot = document.getElementById("cartFoot");
  if (!container) return;

  const cart = getCart();

  if (cart.length === 0) {
    container.innerHTML = '<div class="cart-drawer-empty">Your cart is empty.</div>';
    if (foot) foot.style.display = "none";
    return;
  }

  container.innerHTML = cart.map((item, index) => `
    <div class="cart-item">
      <img src="${item.image}" alt="${item.name}">
      <div class="cart-item-info">
        <h4>${item.name}</h4>
        <div class="cart-item-meta">Size ${item.size} &middot; ₹${item.price.toLocaleString('en-IN')} each</div>
        <div class="cart-qty-row">
          <button class="qty-btn" data-action="dec" data-index="${index}">−</button>
          <span>${item.qty}</span>
          <button class="qty-btn" data-action="inc" data-index="${index}">+</button>
          <button class="cart-item-remove" data-action="remove" data-index="${index}">Remove</button>
        </div>
      </div>
      <div class="cart-item-price">₹${(item.price * item.qty).toLocaleString('en-IN')}</div>
    </div>
  `).join("");

  const subtotal = cartTotal(cart);
  const discount = calculateDiscount(subtotal);
  const finalTotal = Math.max(0, subtotal - discount);

  if (foot) {
    foot.style.display = "block";
    const subtotalEl = document.getElementById("cartSubtotal");
    const discountRow = document.getElementById("cartDiscountRow");
    const discountAmtEl = document.getElementById("cartDiscountAmount");
    const discountLabelEl = document.getElementById("cartDiscountLabel");
    const finalTotalEl = document.getElementById("cartFinalTotal");
    const couponInputRow = document.getElementById("couponInputRow");
    const couponAppliedTag = document.getElementById("couponAppliedTag");
    const appliedCodeEl = document.getElementById("appliedCouponCode");

    if (subtotalEl) subtotalEl.textContent = `₹${subtotal.toLocaleString('en-IN')}`;

    const appliedCode = getAppliedCoupon();
    if (appliedCode && discount > 0) {
      if (discountRow) discountRow.style.display = "flex";
      if (discountAmtEl) discountAmtEl.textContent = `-₹${discount.toLocaleString('en-IN')}`;
      if (discountLabelEl) discountLabelEl.textContent = appliedCode;
      if (couponInputRow) couponInputRow.style.display = "none";
      if (couponAppliedTag) couponAppliedTag.style.display = "flex";
      if (appliedCodeEl) appliedCodeEl.textContent = appliedCode;
    } else {
      if (discountRow) discountRow.style.display = "none";
      if (couponInputRow) couponInputRow.style.display = "flex";
      if (couponAppliedTag) couponAppliedTag.style.display = "none";
    }

    if (finalTotalEl) finalTotalEl.textContent = `₹${finalTotal.toLocaleString('en-IN')}`;
  }

  // Bind coupon actions
  const applyBtn = document.getElementById("couponApplyBtn");
  const couponInput = document.getElementById("couponInput");
  const removeBtn = document.getElementById("removeCouponBtn");
  const couponStatus = document.getElementById("couponStatus");

  if (applyBtn && couponInput) {
    applyBtn.onclick = () => {
      const code = couponInput.value.trim().toUpperCase();
      if (!code) return;
      if (code === "KBA200") {
        setAppliedCoupon("KBA200");
        if (couponStatus) {
          couponStatus.style.display = "block";
          couponStatus.style.color = "#22c55e";
          couponStatus.textContent = "✓ Coupon KBA200 applied: ₹200 off!";
        }
        showToast("Coupon KBA200 applied: ₹200 off!", "🏷️");
        renderCartDrawer();
      } else {
        if (couponStatus) {
          couponStatus.style.display = "block";
          couponStatus.style.color = "#ef4444";
          couponStatus.textContent = "Invalid coupon code. Try KBA200.";
        }
      }
    };
    couponInput.onkeyup = (e) => {
      if (e.key === "Enter") applyBtn.click();
    };
  }

  if (removeBtn) {
    removeBtn.onclick = () => {
      setAppliedCoupon(null);
      if (couponStatus) {
        couponStatus.style.display = "none";
      }
      showToast("Coupon removed", "✕");
      renderCartDrawer();
    };
  }

  container.querySelectorAll("[data-action]").forEach(btn => {
    btn.addEventListener("click", () => {
      const index = parseInt(btn.dataset.index, 10);
      const action = btn.dataset.action;
      const cart = getCart();
      if (action === "inc") updateCartQty(index, cart[index].qty + 1);
      else if (action === "dec") updateCartQty(index, cart[index].qty - 1);
      else if (action === "remove") removeFromCart(index);
    });
  });
}

function openCartDrawer(){
  renderCartDrawer();
  document.getElementById("cartDrawer")?.classList.add("open");
  document.getElementById("cartOverlay")?.classList.add("open");
}

function closeCartDrawer(){
  document.getElementById("cartDrawer")?.classList.remove("open");
  document.getElementById("cartOverlay")?.classList.remove("open");
}

// ======================================================================
// MODAL CONTROLS: QUICK VIEW & SIZE GUIDE
// ======================================================================
let currentQuickViewProduct = null;

function openQuickView(prodData) {
  currentQuickViewProduct = prodData;
  const overlay = document.getElementById("quickViewOverlay");
  if (!overlay) return;

  document.getElementById("qvImage").src = prodData.image;
  document.getElementById("qvImage").alt = prodData.name;
  document.getElementById("qvCategory").textContent = prodData.category.toUpperCase();
  document.getElementById("qvTitle").textContent = prodData.name;
  document.getElementById("qvDesc").textContent = prodData.desc || "Bespoke Karol Bagh craftsmanship.";
  document.getElementById("qvPrice").textContent = prodData.price > 0 ? `₹${parseFloat(prodData.price).toLocaleString('en-IN')}` : "Price on Request";

  // Stock & Bestseller badge & buttons state
  const tagChip = document.getElementById("qvTagChip");
  const addCartBtn = document.getElementById("qvAddCartBtn");
  const buyNowBtn = document.getElementById("qvBuyNowBtn");

  if (prodData.stock === 0 || prodData.stock === "0") {
    if (tagChip) {
      tagChip.textContent = "OUT OF STOCK";
      tagChip.style.borderColor = "#ef4444";
      tagChip.style.color = "#fca5a5";
      tagChip.style.background = "rgba(239,68,68,0.18)";
    }
    if (addCartBtn) {
      addCartBtn.disabled = true;
      addCartBtn.textContent = "Currently Sold Out";
      addCartBtn.style.opacity = "0.5";
      addCartBtn.style.cursor = "not-allowed";
    }
    if (buyNowBtn) {
      buyNowBtn.disabled = true;
      buyNowBtn.textContent = "Sold Out";
      buyNowBtn.style.opacity = "0.5";
      buyNowBtn.style.cursor = "not-allowed";
    }
  } else if (prodData.bestseller === 1 || prodData.bestseller === "1") {
    if (tagChip) {
      tagChip.textContent = "★ BESTSELLER";
      tagChip.style.borderColor = "var(--brass)";
      tagChip.style.color = "var(--brass-light)";
      tagChip.style.background = "rgba(197,160,89,0.22)";
    }
    if (addCartBtn) {
      addCartBtn.disabled = false;
      addCartBtn.textContent = "Add to Cart";
      addCartBtn.style.opacity = "1";
      addCartBtn.style.cursor = "pointer";
    }
    if (buyNowBtn) {
      buyNowBtn.disabled = false;
      buyNowBtn.textContent = "⚡ Buy Now";
      buyNowBtn.style.opacity = "1";
      buyNowBtn.style.cursor = "pointer";
    }
  } else {
    if (tagChip) {
      tagChip.textContent = "Bespoke Cut";
      tagChip.style.borderColor = "var(--brass)";
      tagChip.style.color = "var(--brass)";
      tagChip.style.background = "transparent";
    }
    if (addCartBtn) {
      addCartBtn.disabled = false;
      addCartBtn.textContent = "Add to Cart";
      addCartBtn.style.opacity = "1";
      addCartBtn.style.cursor = "pointer";
    }
    if (buyNowBtn) {
      buyNowBtn.disabled = false;
      buyNowBtn.textContent = "⚡ Buy Now";
      buyNowBtn.style.opacity = "1";
      buyNowBtn.style.cursor = "pointer";
    }
  }

  // Multi-image gallery thumbnails (supports >3 images per product)
  const thumbsContainer = document.getElementById("qvThumbnails");
  if (thumbsContainer) {
    thumbsContainer.innerHTML = "";
    let galleryList = [];
    if (Array.isArray(prodData.gallery) && prodData.gallery.length > 0) {
      galleryList = prodData.gallery.map(p => p.startsWith("/") ? p : `/static/images/${p}`);
    } else {
      galleryList = [prodData.image];
    }

    const labels = ["Front View", "Collar & Lapel", "Tailored Fit", "Fabric Detail"];
    galleryList.forEach((thumbSrc, idx) => {
      const thumb = document.createElement("button");
      thumb.type = "button";
      thumb.className = `qv-thumb-btn ${idx === 0 ? "active" : ""}`;
      thumb.title = labels[idx] || `View ${idx+1}`;
      thumb.innerHTML = `<img src="${thumbSrc}" alt="${prodData.name} ${labels[idx] || idx+1}" loading="lazy">`;
      thumb.addEventListener("click", () => {
        document.getElementById("qvImage").src = thumbSrc;
        thumbsContainer.querySelectorAll(".qv-thumb-btn").forEach(t => t.classList.remove("active"));
        thumb.classList.add("active");
      });
      thumbsContainer.appendChild(thumb);
    });
  }

  // Sync Wishlist button state
  const qvWishlistBtn = document.getElementById("qvWishlistBtn");
  const qvWishlistText = document.getElementById("qvWishlistText");
  if (qvWishlistBtn) {
    const isSaved = getLocalWishlist().map(Number).includes(parseInt(prodData.id, 10));
    if (isSaved) {
      qvWishlistBtn.classList.add("active");
      if (qvWishlistText) qvWishlistText.textContent = "Saved in Wishlist";
    } else {
      qvWishlistBtn.classList.remove("active");
      if (qvWishlistText) qvWishlistText.textContent = "Add to Wishlist";
    }
  }

  // Populate size pills
  const pillsContainer = document.getElementById("qvSizePills");
  pillsContainer.innerHTML = "";
  const sizes = (prodData.sizes || "").split(",").map(s => s.trim()).filter(Boolean);

  let selectedSize = sizes[0] || "";
  currentQuickViewProduct.selectedSize = selectedSize;

  sizes.forEach((s, idx) => {
    const pill = document.createElement("button");
    pill.className = `qv-size-pill ${idx === 0 ? "selected" : ""}`;
    pill.textContent = s;
    pill.addEventListener("click", () => {
      pillsContainer.querySelectorAll(".qv-size-pill").forEach(p => p.classList.remove("selected"));
      pill.classList.add("selected");
      currentQuickViewProduct.selectedSize = s;
    });
    pillsContainer.appendChild(pill);
  });

  // Setup WhatsApp button in Quick View
  const brandLine = "Hi " + (SIZZLING_SETTINGS.brand_name || "there") + ", ";
  const waBtn = document.getElementById("qvWaBtn");
  if (waBtn) {
    waBtn.onclick = (e) => {
      e.preventDefault();
      const msg = brandLine + `I'm interested in:\n\nItem: ${prodData.name}\nSize: ${currentQuickViewProduct.selectedSize}\nPrice: ₹${prodData.price}\n\nPlease confirm availability!`;
      window.open(waLink(msg), "_blank");
    };
  }

  overlay.classList.add("open");
}

function closeQuickView() {
  document.getElementById("quickViewOverlay")?.classList.remove("open");
}

function openSizeGuide(initialTab = "upper") {
  const overlay = document.getElementById("sizeGuideOverlay");
  if (!overlay) return;
  switchSizeTab(initialTab);
  overlay.classList.add("open");
}

function closeSizeGuide() {
  document.getElementById("sizeGuideOverlay")?.classList.remove("open");
}

function switchSizeTab(tabName) {
  const tabBtnUpper = document.getElementById("tabBtnUpper");
  const tabBtnLower = document.getElementById("tabBtnLower");
  const panelUpper = document.getElementById("panelUpper");
  const panelLower = document.getElementById("panelLower");

  if (tabName === "lower") {
    tabBtnLower?.classList.add("active");
    tabBtnUpper?.classList.remove("active");
    if (panelLower) panelLower.style.display = "block";
    if (panelUpper) panelUpper.style.display = "none";
  } else {
    tabBtnUpper?.classList.add("active");
    tabBtnLower?.classList.remove("active");
    if (panelUpper) panelUpper.style.display = "block";
    if (panelLower) panelLower.style.display = "none";
  }
}

// ======================================================================
// PAGE WIRING
// ======================================================================
document.addEventListener("DOMContentLoaded", () => {

  const year = document.getElementById("year");
  if (year) year.textContent = new Date().getFullYear();

  updateCartBadge();

  const brandLine = "Hi " + (SIZZLING_SETTINGS.brand_name || "there") + ", ";

  const waHeaderBtn = document.getElementById("waHeaderBtn");
  const waFooterBtn = document.getElementById("waFooterBtn");
  const waFloatBtn = document.getElementById("waFloatBtn");
  const callFooterBtn = document.getElementById("callFooterBtn");
  const sizeGuideWaBtn = document.getElementById("sizeGuideWaBtn");

  if (waHeaderBtn) waHeaderBtn.href = waLink(brandLine + "I'd like to know more about your collection.");
  if (waFooterBtn) waFooterBtn.href = waLink(brandLine + "I'd like to visit the shop / place an order.");
  if (waFloatBtn) waFloatBtn.href = waLink(brandLine + "I'd like to know more about your collection.");
  if (sizeGuideWaBtn) sizeGuideWaBtn.href = waLink(brandLine + "I have a question about sizing and custom measurements.");
  if (callFooterBtn) callFooterBtn.href = `tel:+${SIZZLING_SETTINGS.shop_phone}`;

  // ------------------------------------------------------------
  // Mobile menu toggle
  // ------------------------------------------------------------
  const menuToggle = document.getElementById("menuToggle");
  const navLinks = document.getElementById("navLinks");
  if (menuToggle && navLinks) {
    menuToggle.addEventListener("click", () => {
      const isOpen = navLinks.style.display === "flex";
      navLinks.style.display = isOpen ? "none" : "flex";
      navLinks.style.flexDirection = "column";
      navLinks.style.position = "absolute";
      navLinks.style.top = "76px";
      navLinks.style.left = "0";
      navLinks.style.right = "0";
      navLinks.style.background = "#14171c";
      navLinks.style.padding = "18px 28px";
      navLinks.style.gap = "16px";
    });
  }

  // ------------------------------------------------------------
  // Cart drawer open/close
  // ------------------------------------------------------------
  document.getElementById("cartBtn")?.addEventListener("click", openCartDrawer);
  document.getElementById("cartCloseBtn")?.addEventListener("click", closeCartDrawer);
  document.getElementById("cartOverlay")?.addEventListener("click", closeCartDrawer);

  // ------------------------------------------------------------
  // Add to Cart / Buy Now buttons on product cards
  // ------------------------------------------------------------
  function readProductButton(btn){
    const selectEl = document.getElementById(btn.dataset.select);
    const card = btn.closest(".card");
    return {
      id: parseInt(btn.dataset.id, 10),
      name: btn.dataset.name,
      category: btn.dataset.category,
      price: btn.dataset.price,
      image: btn.dataset.image,
      size: selectEl ? selectEl.value : "",
      stock: card ? (card.dataset.stock !== undefined ? card.dataset.stock : "1") : "1"
    };
  }

  document.querySelectorAll(".add-cart-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      addToCart(readProductButton(btn));
      openCartDrawer();
    });
  });

  document.querySelectorAll(".buy-now-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const prod = readProductButton(btn);
      if (prod.stock === "0" || prod.stock === 0) {
        showToast(`"${prod.name}" is currently out of stock.`, "🚫");
        return;
      }
      addToCart(prod);
      window.location.href = "/checkout";
    });
  });

  // ------------------------------------------------------------
  // Quick View triggers and actions
  // ------------------------------------------------------------
  document.querySelectorAll(".quick-view-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      let gallery = [];
      try {
        if (btn.dataset.gallery) gallery = JSON.parse(btn.dataset.gallery);
      } catch (err) {}
      openQuickView({
        id: parseInt(btn.dataset.id, 10),
        name: btn.dataset.name,
        category: btn.dataset.category,
        price: parseFloat(btn.dataset.price),
        desc: btn.dataset.desc,
        image: btn.dataset.image,
        gallery: gallery,
        sizes: btn.dataset.sizes,
        stock: btn.dataset.stock,
        bestseller: btn.dataset.bestseller
      });
    });
  });

  // Clicking product card image opens Quick View
  document.querySelectorAll(".card-art").forEach(cardArt => {
    cardArt.addEventListener("click", (e) => {
      if (e.target.closest(".quick-view-btn")) return;
      const qvBtn = cardArt.querySelector(".quick-view-btn");
      if (qvBtn) qvBtn.click();
    });
  });

  document.getElementById("quickViewCloseBtn")?.addEventListener("click", closeQuickView);
  document.getElementById("quickViewOverlay")?.addEventListener("click", (e) => {
    if (e.target === e.currentTarget) closeQuickView();
  });

  document.getElementById("qvAddCartBtn")?.addEventListener("click", () => {
    if (!currentQuickViewProduct) return;
    if (currentQuickViewProduct.stock === 0 || currentQuickViewProduct.stock === "0") {
      showToast(`"${currentQuickViewProduct.name}" is currently out of stock.`, "🚫");
      return;
    }
    addToCart({
      id: currentQuickViewProduct.id,
      name: currentQuickViewProduct.name,
      category: currentQuickViewProduct.category,
      price: currentQuickViewProduct.price,
      image: currentQuickViewProduct.image,
      size: currentQuickViewProduct.selectedSize,
      stock: currentQuickViewProduct.stock
    });
    closeQuickView();
    openCartDrawer();
  });

  document.getElementById("qvBuyNowBtn")?.addEventListener("click", () => {
    if (!currentQuickViewProduct) return;
    if (currentQuickViewProduct.stock === 0 || currentQuickViewProduct.stock === "0") {
      showToast(`"${currentQuickViewProduct.name}" is currently out of stock.`, "🚫");
      return;
    }
    addToCart({
      id: currentQuickViewProduct.id,
      name: currentQuickViewProduct.name,
      category: currentQuickViewProduct.category,
      price: currentQuickViewProduct.price,
      image: currentQuickViewProduct.image,
      size: currentQuickViewProduct.selectedSize,
      stock: currentQuickViewProduct.stock
    });
    closeQuickView();
    window.location.href = "/checkout";
  });

  // Quick View Wishlist button handler
  document.getElementById("qvWishlistBtn")?.addEventListener("click", () => {
    if (!currentQuickViewProduct) return;
    const pid = parseInt(currentQuickViewProduct.id, 10);
    toggleWishlist(pid);
    const isSaved = getLocalWishlist().map(Number).includes(pid);
    const qvWishlistBtn = document.getElementById("qvWishlistBtn");
    const qvWishlistText = document.getElementById("qvWishlistText");
    if (isSaved) {
      qvWishlistBtn?.classList.add("active");
      if (qvWishlistText) qvWishlistText.textContent = "Saved in Wishlist";
    } else {
      qvWishlistBtn?.classList.remove("active");
      if (qvWishlistText) qvWishlistText.textContent = "Add to Wishlist";
    }
    highlightWishlistButtons();
  });

  // ------------------------------------------------------------
  // Size Guide Modals & Tabs
  // ------------------------------------------------------------
  document.getElementById("openSizeGuideBtn")?.addEventListener("click", () => openSizeGuide("upper"));
  document.getElementById("heroSizeBtn")?.addEventListener("click", () => openSizeGuide("upper"));
  document.getElementById("navSizeGuideLink")?.addEventListener("click", (e) => {
    e.preventDefault();
    openSizeGuide("upper");
  });
  document.getElementById("qvSizeGuideLink")?.addEventListener("click", () => {
    const isLower = currentQuickViewProduct && currentQuickViewProduct.category === "pants";
    openSizeGuide(isLower ? "lower" : "upper");
  });

  document.querySelectorAll(".card-size-guide-link").forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      openSizeGuide(link.dataset.type === "lower" ? "lower" : "upper");
    });
  });

  document.getElementById("sizeGuideCloseBtn")?.addEventListener("click", closeSizeGuide);
  document.getElementById("sizeGuideOverlay")?.addEventListener("click", (e) => {
    if (e.target === e.currentTarget) closeSizeGuide();
  });

  document.getElementById("tabBtnUpper")?.addEventListener("click", () => switchSizeTab("upper"));
  document.getElementById("tabBtnLower")?.addEventListener("click", () => switchSizeTab("lower"));

  // Global ESC key to close any modal
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeQuickView();
      closeSizeGuide();
      closeCartDrawer();
    }
  });

  // ------------------------------------------------------------
  // Live Instant Catalog Search
  // ------------------------------------------------------------
  const searchInput = document.getElementById("catalogSearch");
  const searchClearBtn = document.getElementById("searchClearBtn");
  const searchResultsBar = document.getElementById("searchResultsBar");
  const searchResultsCount = document.getElementById("searchResultsCount");
  const clearSearchLink = document.getElementById("clearSearchLink");

  function filterCatalog(query) {
    const q = (query || "").trim().toLowerCase();
    const cards = document.querySelectorAll(".card");
    let matchCount = 0;

    if (searchClearBtn) {
      searchClearBtn.style.display = q ? "block" : "none";
    }

    if (!q) {
      cards.forEach(card => card.style.display = "");
      document.querySelectorAll(".category").forEach(sec => sec.style.display = "");
      if (searchResultsBar) searchResultsBar.style.display = "none";
      return;
    }

    cards.forEach(card => {
      const name = (card.dataset.name || "").toLowerCase();
      const desc = (card.dataset.desc || "").toLowerCase();
      const category = (card.dataset.category || "").toLowerCase();
      const price = (card.dataset.price || "").toString();

      const matches = name.includes(q) || desc.includes(q) || category.includes(q) || price.includes(q);
      if (matches) {
        card.style.display = "";
        matchCount++;
      } else {
        card.style.display = "none";
      }
    });

    // Check category sections visibility
    document.querySelectorAll(".category").forEach(sec => {
      const visibleCards = sec.querySelectorAll(".card:not([style*='display: none'])");
      sec.style.display = visibleCards.length > 0 ? "" : "none";
    });

    if (searchResultsBar && searchResultsCount) {
      searchResultsBar.style.display = "flex";
      searchResultsCount.textContent = `Found ${matchCount} piece${matchCount === 1 ? "" : "s"} matching "${q}"`;
    }
  }

  searchInput?.addEventListener("input", (e) => filterCatalog(e.target.value));

  function resetSearch() {
    if (searchInput) searchInput.value = "";
    filterCatalog("");
  }

  searchClearBtn?.addEventListener("click", resetSearch);
  clearSearchLink?.addEventListener("click", resetSearch);

  // ------------------------------------------------------------
  // ScrollSpy for Category Navigation Pills
  // ------------------------------------------------------------
  const catPills = document.querySelectorAll(".cat-pill");
  const sections = document.querySelectorAll("section.category");

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const cat = entry.target.dataset.sectionCat;
          catPills.forEach(pill => {
            if (pill.dataset.cat === cat) {
              pill.classList.add("active");
            } else {
              pill.classList.remove("active");
            }
          });
        }
      });
    }, { threshold: 0.35 });

    sections.forEach(sec => observer.observe(sec));
  }

  // ------------------------------------------------------------
  // "Order on WhatsApp" / quick-link buttons
  // ------------------------------------------------------------
  document.querySelectorAll(".order-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const name = btn.dataset.name;
      const category = btn.dataset.category;
      const selectEl = document.getElementById(btn.dataset.select);
      const size = selectEl ? selectEl.value : "";

      const msg = brandLine + `I'd like to order:\n\nItem: ${name}\nSize: ${size}\n\nPlease share availability and delivery estimate.`;
      window.open(waLink(msg), "_blank");

      fetch("/api/log_click", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_name: name, category: category, size: size })
      }).catch(() => {});
    });
  });

  // ------------------------------------------------------------
  // Enquiry form -> save lead + open WhatsApp
  // ------------------------------------------------------------
  const enquiryForm = document.getElementById("enquiryForm");
  if (enquiryForm) {
    enquiryForm.addEventListener("submit", (e) => {
      e.preventDefault();

      const name = document.getElementById("fname").value.trim();
      const phone = document.getElementById("fphone").value.trim();
      const item = document.getElementById("fitem").value;
      const size = document.getElementById("fsize").value;
      const notes = document.getElementById("fmsg").value.trim();
      const statusEl = document.getElementById("formStatus");

      if (!name || !phone) {
        if (statusEl) {
          statusEl.textContent = "Please enter your name and phone number.";
          statusEl.className = "form-status error";
        }
        return;
      }

      fetch("/api/enquiry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, phone, item, size, notes, source: "enquiry_form" })
      })
      .then(r => r.json())
      .then(() => {
        if (statusEl) {
          statusEl.textContent = "Saved! Opening WhatsApp...";
          statusEl.className = "form-status success";
        }
        const msg = brandLine + `I'd like to place an order.\n\n` +
          `Name: ${name}\nPhone: ${phone}\nItem: ${item}\nSize: ${size}\n` +
          (notes ? `Notes: ${notes}\n` : "");
        window.open(waLink(msg), "_blank");
        enquiryForm.reset();
      })
      .catch(() => {
        if (statusEl) {
          statusEl.textContent = "Could not save your enquiry. Please try WhatsApp directly.";
          statusEl.className = "form-status error";
        }
      });
    });
  }

  // ------------------------------------------------------------
  // Wishlist Handling
  // ------------------------------------------------------------
  syncWishlistFromServer();

  document.querySelectorAll(".wishlist-card-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      const pid = btn.dataset.id;
      toggleWishlist(pid, btn);
    });
  });

});

// ======================================================================
// WISHLIST MANAGEMENT (localStorage + Server Sync)
// ======================================================================
const WISHLIST_KEY = "sizzling_wishlist";

function getLocalWishlist() {
  try {
    const raw = localStorage.getItem(WISHLIST_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function saveLocalWishlist(list) {
  localStorage.setItem(WISHLIST_KEY, JSON.stringify(list));
  updateWishlistBadge();
}

function updateWishlistBadge() {
  const badge = document.getElementById("wishlistCount");
  if (!badge) return;
  const list = getLocalWishlist();
  badge.textContent = list.length;
}

function syncWishlistFromServer() {
  fetch("/api/wishlist/ids")
    .then(r => r.json())
    .then(data => {
      if (data && Array.isArray(data.ids)) {
        if (data.ids.length > 0) {
          const combined = Array.from(new Set([...getLocalWishlist(), ...data.ids]));
          saveLocalWishlist(combined);
        }
        highlightWishlistButtons();
      }
    })
    .catch(() => {
      highlightWishlistButtons();
    });
}

function highlightWishlistButtons() {
  const wishlistedIds = new Set(getLocalWishlist().map(Number));
  document.querySelectorAll(".wishlist-card-btn").forEach(btn => {
    const pid = parseInt(btn.dataset.id, 10);
    if (wishlistedIds.has(pid)) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
  updateWishlistBadge();
}

function toggleWishlist(productId, btnEl) {
  productId = parseInt(productId, 10);
  let localList = getLocalWishlist().map(Number);
  const isCurrentlySaved = localList.includes(productId);

  if (isCurrentlySaved) {
    localList = localList.filter(id => id !== productId);
    saveLocalWishlist(localList);
    btnEl?.classList.remove("active");
    showToast("Removed item from wishlist", "♡");
  } else {
    localList.push(productId);
    saveLocalWishlist(localList);
    btnEl?.classList.add("active");
    showToast("Saved to your wishlist", "❤️");
  }

  fetch("/api/wishlist/toggle", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_id: productId })
  }).catch(() => {});
}

// ======================================================================
// SCROLL REVEAL — Premium entrance animations (IntersectionObserver)
// ======================================================================
(function initScrollReveal() {
  if (!("IntersectionObserver" in window)) return;

  // Mark all product cards as hidden initially
  document.querySelectorAll(".card").forEach(card => {
    card.classList.add("reveal-hidden");
  });

  // Reveal cards as they enter viewport
  const cardObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.remove("reveal-hidden");
        entry.target.classList.add("reveal-visible");
        cardObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.08, rootMargin: "0px 0px -40px 0px" });

  document.querySelectorAll(".card").forEach(card => cardObserver.observe(card));

  // Animate section headings as they enter
  const headObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("cat-animate");
        headObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.2 });

  document.querySelectorAll(".cat-head").forEach(el => headObserver.observe(el));

  // Header shrink effect on scroll
  const header = document.querySelector("header");
  if (header) {
    window.addEventListener("scroll", () => {
      if (window.scrollY > 60) {
        header.classList.add("scrolled");
      } else {
        header.classList.remove("scrolled");
      }
    }, { passive: true });
  }
})();

