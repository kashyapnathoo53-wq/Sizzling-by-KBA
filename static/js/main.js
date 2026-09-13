// SIZZLING_SETTINGS is injected inline by index.html before this file loads.

function waLink(message){
  return `https://wa.me/${SIZZLING_SETTINGS.whatsapp_number}?text=${encodeURIComponent(message)}`;
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

function addToCart({ id, name, category, price, image, size }){
  const cart = getCart();
  const existing = cart.find(item => item.id === id && item.size === size);
  if (existing) {
    existing.qty += 1;
  } else {
    cart.push({ id, name, category, price: parseFloat(price), image, size, qty: 1 });
  }
  saveCart(cart);
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
  cart.splice(index, 1);
  saveCart(cart);
  renderCartDrawer();
}

function cartTotal(cart){
  return cart.reduce((sum, item) => sum + item.price * item.qty, 0);
}

function cartCount(cart){
  return cart.reduce((sum, item) => sum + item.qty, 0);
}

function updateCartBadge(){
  const el = document.getElementById("cartCount");
  if (el) el.textContent = cartCount(getCart());
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
        <div class="cart-item-meta">Size ${item.size} &middot; ₹${item.price.toFixed(0)} each</div>
        <div class="cart-qty-row">
          <button class="qty-btn" data-action="dec" data-index="${index}">−</button>
          <span>${item.qty}</span>
          <button class="qty-btn" data-action="inc" data-index="${index}">+</button>
          <button class="cart-item-remove" data-action="remove" data-index="${index}">Remove</button>
        </div>
      </div>
      <div class="cart-item-price">₹${(item.price * item.qty).toFixed(0)}</div>
    </div>
  `).join("");

  if (foot) {
    foot.style.display = "block";
    document.getElementById("cartSubtotal").textContent = `₹${cartTotal(cart).toFixed(0)}`;
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

  if (waHeaderBtn) waHeaderBtn.href = waLink(brandLine + "I'd like to know more about your collection.");
  if (waFooterBtn) waFooterBtn.href = waLink(brandLine + "I'd like to visit the shop / place an order.");
  if (waFloatBtn) waFloatBtn.href = waLink(brandLine + "I'd like to know more about your collection.");
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
    return {
      id: parseInt(btn.dataset.id, 10),
      name: btn.dataset.name,
      category: btn.dataset.category,
      price: btn.dataset.price,
      image: btn.dataset.image,
      size: selectEl ? selectEl.value : ""
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
      addToCart(readProductButton(btn));
      window.location.href = "/checkout";
    });
  });

  // ------------------------------------------------------------
  // "Order on WhatsApp" / quick-link buttons (no fixed price items,
  // and the small text link on priced items)
  // ------------------------------------------------------------
  document.querySelectorAll(".order-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const name = btn.dataset.name;
      const category = btn.dataset.category;
      const selectEl = document.getElementById(btn.dataset.select);
      const size = selectEl ? selectEl.value : "";

      const msg = brandLine + `I'd like to order:\n\nItem: ${name}\nSize: ${size}\n\nPlease share availability and price.`;
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

});
