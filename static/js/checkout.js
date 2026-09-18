const CART_KEY = "sizzling_cart";

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

function renderSummary(){
  const container = document.getElementById("checkoutSummary");
  const cart = getCart();

  if (cart.length === 0) {
    container.innerHTML = `
      <p style="text-align:center; padding:20px 0;">
        Your cart is empty. <a href="/">Go back and add something you like →</a>
      </p>`;
    document.getElementById("checkoutSubmitBtn").disabled = true;
    return;
  }

  const lines = cart.map(item => `
    <div class="checkout-line">
      <span>${item.name} &middot; Size ${item.size} &times; ${item.qty}</span>
      <span>₹${(item.price * item.qty).toFixed(0)}</span>
    </div>
  `).join("");

  container.innerHTML = lines + `
    <div class="checkout-line checkout-total-line">
      <span>Total</span>
      <span>₹${cartTotal(cart).toFixed(0)}</span>
    </div>
  `;
}

renderSummary();

document.getElementById("checkoutForm").addEventListener("submit", (e) => {
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

    btn.disabled = true;
    btn.textContent = "Setting up payment...";

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
        customer: { name, phone, address, notes }
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
      // Clear cart immediately so consecutive orders can be placed without old cart collision
      try {
        localStorage.removeItem(CART_KEY);
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
