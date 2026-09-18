const CART_KEY = "sizzling_cart";
const COUPON_KEY = "sizzling_coupon";

function getCart(){
  try {
    const raw = localStorage.getItem(CART_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function cartTotal(cart){
  return cart.reduce((sum, item) => sum + item.price * item.qty, 0);
}

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

function renderSummary(){
  const container = document.getElementById("checkoutSummary");
  const cart = getCart();

  if (cart.length === 0) {
    container.innerHTML = `
      <p style="text-align:center; padding:20px 0;">
        Your cart is empty. <a href="/" onclick="window.location.href='/'; return true;" style="color:var(--brass); text-decoration:underline;">Go back and add something you like →</a>
      </p>`;
    const btn = document.getElementById("checkoutSubmitBtn");
    if (btn) btn.disabled = true;
    return;
  }

  const subtotal = cartTotal(cart);
  const appliedCode = getAppliedCoupon();
  const discount = calculateDiscount(subtotal);
  const finalTotal = Math.max(0, subtotal - discount);

  const lines = cart.map(item => `
    <div class="checkout-line">
      <span>${item.name} &middot; Size ${item.size} &times; ${item.qty}</span>
      <span>₹${(item.price * item.qty).toFixed(0)}</span>
    </div>
  `).join("");

  let couponHtml = "";
  if (appliedCode && discount > 0) {
    couponHtml = `
      <div class="checkout-line" style="color:#22c55e; font-weight:600;">
        <span>Coupon Discount (${appliedCode})</span>
        <div style="display:flex; align-items:center; gap:8px;">
          <span>-₹${discount.toFixed(0)}</span>
          <button type="button" id="removeCheckoutCouponBtn" style="background:none; border:none; color:#fca5a5; font-size:11.5px; text-decoration:underline; cursor:pointer;" title="Remove coupon">Remove</button>
        </div>
      </div>
    `;
  } else {
    couponHtml = `
      <div style="padding:12px 0; border-bottom:1px solid #232b3b;">
        <div style="display:flex; gap:8px;">
          <input type="text" id="checkoutCouponInput" placeholder="Coupon Code (e.g. KBA200)" maxlength="16" style="flex:1; background:#080b10; border:1px solid #283347; color:#f3efe6; padding:8px 12px; font-family:var(--mono); font-size:12.5px; text-transform:uppercase; border-radius:2px;">
          <button type="button" id="applyCheckoutCouponBtn" class="btn btn-outline" style="padding:8px 14px; font-size:12px;">Apply</button>
        </div>
        <div id="checkoutCouponMsg" style="font-size:11.5px; margin-top:5px; display:none;"></div>
      </div>
    `;
  }

  container.innerHTML = `
    ${lines}
    <div class="checkout-line" style="opacity:0.8; font-size:14px;">
      <span>Subtotal</span>
      <span>₹${subtotal.toFixed(0)}</span>
    </div>
    ${couponHtml}
    <div class="checkout-line checkout-total-line" style="font-size:18px; font-weight:700; color:var(--brass-light); padding-top:12px;">
      <span>Total to Pay</span>
      <span>₹${finalTotal.toFixed(0)}</span>
    </div>
  `;

  // Bind coupon actions in summary
  const applyBtn = document.getElementById("applyCheckoutCouponBtn");
  const inputEl = document.getElementById("checkoutCouponInput");
  const removeBtn = document.getElementById("removeCheckoutCouponBtn");
  const msgEl = document.getElementById("checkoutCouponMsg");

  if (applyBtn && inputEl) {
    applyBtn.onclick = () => {
      const code = inputEl.value.trim().toUpperCase();
      if (!code) return;
      if (code === "KBA200") {
        setAppliedCoupon("KBA200");
        renderSummary();
      } else {
        if (msgEl) {
          msgEl.style.display = "block";
          msgEl.style.color = "#ef4444";
          msgEl.textContent = "Invalid coupon code. Try KBA200.";
        }
      }
    };
    inputEl.onkeyup = (e) => {
      if (e.key === "Enter") applyBtn.click();
    };
  }

  if (removeBtn) {
    removeBtn.onclick = () => {
      setAppliedCoupon(null);
      renderSummary();
    };
  }
}

renderSummary();

// Client-side auto-fill from saved local storage if fields are empty
(function initAutoFill() {
  try {
    const raw = localStorage.getItem("sizzling_customer_info");
    if (raw) {
      const saved = JSON.parse(raw);
      const nameInput = document.getElementById("cname");
      const phoneInput = document.getElementById("cphone");
      const addressInput = document.getElementById("caddress");

      if (nameInput && !nameInput.value.trim() && saved.name) {
        nameInput.value = saved.name;
      }
      if (phoneInput && !phoneInput.value.trim() && saved.phone) {
        phoneInput.value = saved.phone;
      }
      if (addressInput && !addressInput.value.trim() && saved.address) {
        addressInput.value = saved.address;
      }
    }
  } catch (err) {}

  function saveDetails() {
    try {
      const name = document.getElementById("cname")?.value.trim() || "";
      const phone = document.getElementById("cphone")?.value.trim() || "";
      const address = document.getElementById("caddress")?.value.trim() || "";
      if (name || phone || address) {
        localStorage.setItem("sizzling_customer_info", JSON.stringify({ name, phone, address }));
      }
    } catch (e) {}
  }

  document.getElementById("cname")?.addEventListener("input", saveDetails);
  document.getElementById("cphone")?.addEventListener("input", saveDetails);
  document.getElementById("caddress")?.addEventListener("input", saveDetails);
})();

document.getElementById("checkoutForm")?.addEventListener("submit", (e) => {
  e.preventDefault();

  const cart = getCart();
  if (cart.length === 0) return;

  const name = document.getElementById("cname").value.trim();
  const phone = document.getElementById("cphone").value.trim();
  const address = document.getElementById("caddress").value.trim();
  const notes = document.getElementById("cnotes").value.trim();
  const statusEl = document.getElementById("checkoutStatus");
  const btn = document.getElementById("checkoutSubmitBtn");

  if (!name || !phone || !address) {
    statusEl.textContent = "Please fill in your name, phone and address.";
    statusEl.className = "form-status error";
    return;
  }

  // Save for future auto-fill
  try {
    localStorage.setItem("sizzling_customer_info", JSON.stringify({ name, phone, address }));
  } catch (e) {}

  btn.disabled = true;
  btn.textContent = "Setting up payment...";

  const appliedCode = getAppliedCoupon();

  fetch("/api/create_order", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      items: cart.map(item => ({
        product_id: item.id,
        name: item.name,
        price: item.price,
        size: item.size,
        qty: item.qty
      })),
      customer: { name, phone, address, notes },
      coupon_code: appliedCode
    })
  })
  .then(r => r.json())
  .then(res => {
    if (!res.success) {
      statusEl.textContent = res.error || "Something went wrong. Please try again.";
      statusEl.className = "form-status error";
      btn.disabled = false;
      btn.textContent = "Continue to Payment & Verification →";
      return;
    }
    // Clear cart and coupon immediately upon successful order creation
    try {
      localStorage.removeItem(CART_KEY);
      localStorage.removeItem(COUPON_KEY);
      window.dispatchEvent(new Event("cartUpdated"));
    } catch (e) {}

    window.location.href = res.pay_url;
  })
  .catch(() => {
    statusEl.textContent = "Could not reach the server. Please check your connection and try again.";
    statusEl.className = "form-status error";
    btn.disabled = false;
    btn.textContent = "Continue to Payment & Verification →";
  });
});
