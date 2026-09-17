import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify, redirect, url_for,
    session, flash, send_from_directory, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import qrcode

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "sizzling.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "images", "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}
MAX_UPLOAD_MB = 8

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deploying")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

CATEGORIES = [
    ("suits", "Suits", "upper"),
    ("blazers", "Blazers", "upper"),
    ("jackets", "Jackets", "upper"),
    ("shirts", "Formal Shirts", "upper"),
    ("pants", "Formal Pants", "lower"),
    ("sherwanis", "Wedding Sherwanis", "upper"),
]
CATEGORY_KEYS = [c[0] for c in CATEGORIES]
CATEGORY_LABELS = {c[0]: c[1] for c in CATEGORIES}
CATEGORY_SIZE_TYPE = {c[0]: c[2] for c in CATEGORIES}

UPPER_SIZES = [36, 38, 40, 42, 44]
LOWER_SIZES = [30, 32, 34, 36, 38]

DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "sizzling@2026")
QR_DIR = os.path.join(BASE_DIR, "static", "images", "qr")
os.makedirs(QR_DIR, exist_ok=True)


# =====================================================================
# DATABASE
# =====================================================================
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        price REAL,
        image_path TEXT,
        active INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS enquiries(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        item TEXT,
        size TEXT,
        notes TEXT,
        source TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_clicks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT,
        category TEXT,
        size TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT,
        phone TEXT,
        address TEXT,
        notes TEXT,
        total REAL,
        status TEXT DEFAULT 'pending_payment',
        payment_ref TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER,
        product_name TEXT,
        category TEXT,
        size TEXT,
        price REAL,
        qty INTEGER,
        line_total REAL,
        FOREIGN KEY(order_id) REFERENCES orders(id)
    )
    """)

    conn.commit()

    # Seed default settings if not present.
    defaults = {
        "whatsapp_number": "919811551935",
        "shop_phone": "919811551935",
        "brand_name": "SIZZLING by KBA Pvt Ltd",
        "owner_name": "Vinod Kumar Nathoo",
        "address": "Gali No. 5, Dev Nagar, Karol Bagh, New Delhi",
        "hours": "Open daily &middot; 11:00 AM &ndash; 8:30 PM<br>Closed Sundays",
        "admin_password_hash": generate_password_hash(DEFAULT_ADMIN_PASSWORD),
        "upi_id": "8595511923@ptaxis",
        "upi_payee_name": "SIZZLING by KBA",
    }
    for key, value in defaults.items():
        cur.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES (?,?)", (key, value)
        )

    conn.commit()

    # Seed sample products only if the products table is completely empty,
    # so re-running the app never overwrites an owner's real catalog/images.
    count = cur.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        seed_products(cur)
        conn.commit()

    conn.close()


def seed_products(cur):
    seed = {
        "suits": [
            ("Midnight Two-Piece Suit", "Deep navy, notch lapel, a first-suit that also works for the tenth interview.", 8999),
            ("Charcoal Windowpane Suit", "Subtle check, cut for the boardroom, built to travel well between meetings.", 9999),
            ("Ivory Tuxedo Suit", "Satin lapel, evening-only — for the dinner where the invite says black tie.", 12999),
        ],
        "blazers": [
            ("Bottle Green Velvet Blazer", "Textured velvet, single button — the piece that carries a festive evening.", 5499),
            ("Navy Textured Blazer", "Everyday blazer, pairs cleanly with formal or semi-formal trousers.", 4999),
            ("Rust Tweed Blazer", "Heavier weave for cooler months, worn open over a plain shirt.", 5999),
        ],
        "jackets": [
            ("Quilted Bomber Jacket", "Structured quilting, zip front — smart enough to wear over a shirt.", 6499),
            ("Wool Overcoat", "Full-length layer for Delhi winters, worn straight over a suit.", 8999),
            ("Textured Field Jacket", "Four-pocket utility cut, sits between casual and smart-casual.", 5999),
        ],
        "shirts": [
            ("Crisp White Dress Shirt", "The one every formal wardrobe is built around. Spread collar.", 1299),
            ("Sky Blue Formal Shirt", "Slightly softer than white, easy to wear with or without a tie.", 1199),
            ("Fine Striped Business Shirt", "Subtle stripe, holds its shape through a full working day.", 1399),
        ],
        "pants": [
            ("Classic Charcoal Trouser", "Flat-front, straight leg — the trouser that goes under any jacket.", 1799),
            ("Slim-Fit Navy Trouser", "Tapered through the leg, worn on its own or with a blazer.", 1699),
            ("Pleated Grey Trouser", "Traditional pleat for a roomier fit, favoured for longer days.", 1899),
        ],
        "sherwanis": [
            ("Royal Gold Zari Sherwani", "Hand-worked zari embroidery, the outfit built for the pheras.", 15999),
            ("Ivory Silk Sherwani", "Raw silk base, understated embroidery for the sangeet or reception.", 13999),
            ("Maroon Velvet Sherwani", "Deep velvet body, gold detailing at collar and placket.", 17999),
            ("Pastel Peach Sherwani", "Lighter tone for a daytime function, subtle thread work throughout.", 11999),
        ],
    }

    seed_images = {
        "Midnight Two-Piece Suit": "products/suit_midnight_navy.jpg",
        "Charcoal Windowpane Suit": "products/suit_charcoal_windowpane.jpg",
        "Ivory Tuxedo Suit": "products/suit_ivory_tuxedo.jpg",
        "Bottle Green Velvet Blazer": "products/blazer_bottle_green.jpg",
        "Navy Textured Blazer": "products/blazer_navy_textured.jpg",
        "Rust Tweed Blazer": "products/blazer_rust_tweed.jpg",
        "Quilted Bomber Jacket": "products/jacket_quilted_bomber.jpg",
        "Wool Overcoat": "products/jacket_wool_overcoat.jpg",
        "Textured Field Jacket": "products/jacket_textured_field.jpg",
        "Crisp White Dress Shirt": "products/shirt_crisp_white.jpg",
        "Sky Blue Formal Shirt": "products/shirt_sky_blue.jpg",
        "Fine Striped Business Shirt": "products/shirt_fine_striped.jpg",
        "Classic Charcoal Trouser": "products/pants_classic_charcoal.jpg",
        "Slim-Fit Navy Trouser": "products/pants_slim_navy.jpg",
        "Pleated Grey Trouser": "products/pants_pleated_grey.jpg",
        "Royal Gold Zari Sherwani": "products/sherwani_royal_gold.jpg",
        "Ivory Silk Sherwani": "products/sherwani_ivory_silk.jpg",
        "Maroon Velvet Sherwani": "products/sherwani_maroon_velvet.jpg",
        "Pastel Peach Sherwani": "products/sherwani_pastel_peach.jpg",
    }

    for category, items in seed.items():
        for i, (name, desc, price) in enumerate(items):
            prod_image = seed_images.get(name, f"products/{category}.jpg")
            cur.execute("""
                INSERT INTO products(category, name, description, price, image_path, sort_order)
                VALUES (?,?,?,?,?,?)
            """, (category, name, desc, price, prod_image, i))


init_db()


# =====================================================================
# HELPERS
# =====================================================================
def get_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def set_setting(key, value):
    conn = get_db()
    conn.execute(
        "INSERT INTO settings(key, value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def sizes_for(category):
    return UPPER_SIZES if CATEGORY_SIZE_TYPE.get(category, "upper") == "upper" else LOWER_SIZES


# =====================================================================
# PUBLIC SITE
# =====================================================================
@app.route("/")
def home():
    conn = get_db()
    products_by_cat = {}
    for key, label, size_type in CATEGORIES:
        rows = conn.execute(
            "SELECT * FROM products WHERE category=? AND active=1 ORDER BY sort_order, id",
            (key,),
        ).fetchall()
        products_by_cat[key] = [dict(r) for r in rows]
    conn.close()

    settings = get_settings()

    return render_template(
        "index.html",
        categories=CATEGORIES,
        products_by_cat=products_by_cat,
        upper_sizes=UPPER_SIZES,
        lower_sizes=LOWER_SIZES,
        category_size_type=CATEGORY_SIZE_TYPE,
        settings=settings,
    )


@app.route("/api/enquiry", methods=["POST"])
def api_enquiry():
    data = request.json or {}
    conn = get_db()
    conn.execute("""
        INSERT INTO enquiries(name, phone, item, size, notes, source)
        VALUES (?,?,?,?,?,?)
    """, (
        data.get("name", ""), data.get("phone", ""), data.get("item", ""),
        data.get("size", ""), data.get("notes", ""), data.get("source", "enquiry_form"),
    ))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/log_click", methods=["POST"])
def api_log_click():
    data = request.json or {}
    conn = get_db()
    conn.execute("""
        INSERT INTO order_clicks(product_name, category, size)
        VALUES (?,?,?)
    """, (data.get("product_name", ""), data.get("category", ""), data.get("size", "")))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# =====================================================================
# CART -> CHECKOUT -> UPI PAYMENT (manual verification, no gateway)
# =====================================================================
@app.route("/checkout")
def checkout():
    return render_template("checkout.html", settings=get_settings())


@app.route("/api/create_order", methods=["POST"])
def api_create_order():
    data = request.json or {}
    items = data.get("items", [])
    customer = data.get("customer", {})

    if not items:
        return jsonify({"success": False, "error": "Your cart is empty."}), 400

    name = (customer.get("name") or "").strip()
    phone = (customer.get("phone") or "").strip()
    address = (customer.get("address") or "").strip()
    notes = (customer.get("notes") or "").strip()

    if not name or not phone or not address:
        return jsonify({"success": False, "error": "Name, phone and address are required."}), 400

    conn = get_db()
    cur = conn.cursor()

    order_items = []
    total = 0.0

    for item in items:
        product_id = item.get("product_id")
        size = str(item.get("size", ""))
        qty = max(1, int(item.get("qty", 1)))

        product = cur.execute(
            "SELECT * FROM products WHERE id=? AND active=1", (product_id,)
        ).fetchone()
        if product is None or product["price"] is None:
            continue  # skip items with no fixed price or that no longer exist

        line_total = product["price"] * qty
        total += line_total
        order_items.append({
            "product_id": product["id"],
            "product_name": product["name"],
            "category": product["category"],
            "size": size,
            "price": product["price"],
            "qty": qty,
            "line_total": line_total,
        })

    if not order_items:
        conn.close()
        return jsonify({"success": False, "error": "None of the items in your cart could be ordered."}), 400

    cur.execute("""
        INSERT INTO orders(customer_name, phone, address, notes, total, status)
        VALUES (?,?,?,?,?, 'pending_payment')
    """, (name, phone, address, notes, total))
    order_id = cur.lastrowid

    for oi in order_items:
        cur.execute("""
            INSERT INTO order_items(order_id, product_id, product_name, category, size, price, qty, line_total)
            VALUES (?,?,?,?,?,?,?,?)
        """, (order_id, oi["product_id"], oi["product_name"], oi["category"],
              oi["size"], oi["price"], oi["qty"], oi["line_total"]))

    conn.commit()
    conn.close()

    _generate_upi_qr(order_id, total)

    return jsonify({
        "success": True,
        "order_id": order_id,
        "total": round(total, 2),
        "pay_url": url_for("order_pay", order_id=order_id),
    })


def _generate_upi_qr(order_id, amount):
    settings = get_settings()
    upi_id = settings.get("upi_id", "")
    payee = settings.get("upi_payee_name", settings.get("brand_name", "Shop"))
    upi_uri = (
        f"upi://pay?pa={upi_id}&pn={payee.replace(' ', '%20')}"
        f"&am={amount:.2f}&cu=INR&tn=Order%20{order_id}"
    )
    img = qrcode.make(upi_uri)
    img.save(os.path.join(QR_DIR, f"order_{order_id}.png"))
    return upi_uri


@app.route("/order/<int:order_id>/pay")
def order_pay(order_id):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if order is None:
        conn.close()
        abort(404)
    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id=?", (order_id,)
    ).fetchall()
    conn.close()

    settings = get_settings()
    upi_uri = _generate_upi_qr(order_id, order["total"])  # regenerate in case settings changed

    return render_template(
        "payment.html", order=order, items=items, settings=settings, upi_uri=upi_uri
    )


@app.route("/api/order/<int:order_id>/submit_payment_ref", methods=["POST"])
def api_submit_payment_ref(order_id):
    data = request.json or {}
    ref = (data.get("payment_ref") or "").strip()
    if not ref:
        return jsonify({"success": False, "error": "Please enter your UPI transaction reference."}), 400

    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if order is None:
        conn.close()
        return jsonify({"success": False, "error": "Order not found."}), 404

    conn.execute(
        "UPDATE orders SET payment_ref=?, status='payment_reported' WHERE id=?",
        (ref, order_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/order/<int:order_id>/confirmation")
def order_confirmation(order_id):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if order is None:
        conn.close()
        abort(404)
    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id=?", (order_id,)
    ).fetchall()
    conn.close()
    return render_template(
        "order_confirmation.html", order=order, items=items, settings=get_settings()
    )


# =====================================================================
# ADMIN AUTH
# =====================================================================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        settings = get_settings()
        stored_hash = settings.get("admin_password_hash", "")
        if stored_hash and check_password_hash(stored_hash, password):
            session["is_admin"] = True
            next_url = request.args.get("next") or url_for("admin_dashboard")
            return redirect(next_url)
        flash("Incorrect password. Please try again.", "error")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


# =====================================================================
# ADMIN DASHBOARD
# =====================================================================
@app.route("/admin")
@login_required
def admin_dashboard():
    conn = get_db()
    product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    enquiry_count = conn.execute("SELECT COUNT(*) FROM enquiries").fetchone()[0]
    click_count = conn.execute("SELECT COUNT(*) FROM order_clicks").fetchone()[0]
    order_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    pending_payment_count = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE status IN ('pending_payment','payment_reported')"
    ).fetchone()[0]
    paid_total = conn.execute(
        "SELECT COALESCE(SUM(total),0) FROM orders WHERE status IN ('paid','fulfilled')"
    ).fetchone()[0]
    recent_enquiries = conn.execute(
        "SELECT * FROM enquiries ORDER BY id DESC LIMIT 5"
    ).fetchall()
    recent_clicks = conn.execute(
        "SELECT * FROM order_clicks ORDER BY id DESC LIMIT 5"
    ).fetchall()
    recent_orders = conn.execute(
        "SELECT * FROM orders ORDER BY id DESC LIMIT 5"
    ).fetchall()
    conn.close()
    return render_template(
        "admin/dashboard.html",
        product_count=product_count,
        enquiry_count=enquiry_count,
        click_count=click_count,
        order_count=order_count,
        pending_payment_count=pending_payment_count,
        paid_total=paid_total,
        recent_enquiries=recent_enquiries,
        recent_clicks=recent_clicks,
        recent_orders=recent_orders,
    )


# ---------------------------------------------------------------
# Products CRUD
# ---------------------------------------------------------------
@app.route("/admin/products")
@login_required
def admin_products():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM products ORDER BY category, sort_order, id"
    ).fetchall()
    conn.close()
    return render_template(
        "admin/products.html", products=rows, category_labels=CATEGORY_LABELS
    )


@app.route("/admin/products/new", methods=["GET", "POST"])
@login_required
def admin_product_new():
    if request.method == "POST":
        return _save_product(None)
    return render_template(
        "admin/product_form.html", product=None, categories=CATEGORIES
    )


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def admin_product_edit(product_id):
    conn = get_db()
    product = conn.execute(
        "SELECT * FROM products WHERE id=?", (product_id,)
    ).fetchone()
    conn.close()
    if product is None:
        abort(404)

    if request.method == "POST":
        return _save_product(product_id)

    return render_template(
        "admin/product_form.html", product=product, categories=CATEGORIES
    )


def _save_product(product_id):
    name = request.form.get("name", "").strip()
    category = request.form.get("category", CATEGORY_KEYS[0])
    description = request.form.get("description", "").strip()
    price_raw = request.form.get("price", "").strip()
    price = float(price_raw) if price_raw else None
    active = 1 if request.form.get("active") == "on" else 0

    if not name:
        flash("Product name is required.", "error")
        return redirect(request.referrer or url_for("admin_products"))

    image_path = None
    file = request.files.get("image")
    if file and file.filename:
        if not allowed_file(file.filename):
            flash("Image must be PNG, JPG, JPEG or WEBP.", "error")
            return redirect(request.referrer or url_for("admin_products"))
        filename = secure_filename(file.filename)
        unique_name = f"{int(datetime.utcnow().timestamp())}_{filename}"
        file.save(os.path.join(UPLOAD_DIR, unique_name))
        image_path = f"uploads/{unique_name}"

    conn = get_db()
    if product_id is None:
        if image_path is None:
            image_path = f"defaults/{category}.svg"
        conn.execute("""
            INSERT INTO products(category, name, description, price, image_path, active)
            VALUES (?,?,?,?,?,?)
        """, (category, name, description, price, image_path, active))
        flash(f'"{name}" added.', "success")
    else:
        if image_path:
            conn.execute("""
                UPDATE products SET category=?, name=?, description=?, price=?,
                image_path=?, active=? WHERE id=?
            """, (category, name, description, price, image_path, active, product_id))
        else:
            conn.execute("""
                UPDATE products SET category=?, name=?, description=?, price=?,
                active=? WHERE id=?
            """, (category, name, description, price, active, product_id))
        flash(f'"{name}" updated.', "success")
    conn.commit()
    conn.close()
    return redirect(url_for("admin_products"))


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@login_required
def admin_product_delete(product_id):
    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    conn.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()
    if product:
        flash(f'"{product["name"]}" deleted.', "success")
    return redirect(url_for("admin_products"))


# ---------------------------------------------------------------
# Orders (UPI payments — manual verification)
# ---------------------------------------------------------------
ORDER_STATUSES = [
    ("pending_payment", "Pending Payment"),
    ("payment_reported", "Payment Reported by Customer"),
    ("paid", "Paid — Confirmed"),
    ("fulfilled", "Fulfilled / Delivered"),
    ("cancelled", "Cancelled"),
]


@app.route("/admin/orders")
@login_required
def admin_orders():
    conn = get_db()
    orders = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    conn.close()
    status_labels = dict(ORDER_STATUSES)
    return render_template(
        "admin/orders.html", orders=orders, status_labels=status_labels
    )


@app.route("/admin/orders/<int:order_id>", methods=["GET", "POST"])
@login_required
def admin_order_detail(order_id):
    conn = get_db()

    if request.method == "POST":
        new_status = request.form.get("status")
        if new_status in dict(ORDER_STATUSES):
            conn.execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
            conn.commit()
            flash("Order status updated.", "success")

    order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if order is None:
        conn.close()
        abort(404)
    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id=?", (order_id,)
    ).fetchall()
    conn.close()

    return render_template(
        "admin/order_detail.html", order=order, items=items, statuses=ORDER_STATUSES
    )


# ---------------------------------------------------------------
# Enquiries & order-click log
# ---------------------------------------------------------------
@app.route("/admin/enquiries")
@login_required
def admin_enquiries():
    conn = get_db()
    enquiries = conn.execute(
        "SELECT * FROM enquiries ORDER BY id DESC"
    ).fetchall()
    clicks = conn.execute(
        "SELECT * FROM order_clicks ORDER BY id DESC LIMIT 100"
    ).fetchall()
    conn.close()
    return render_template(
        "admin/enquiries.html", enquiries=enquiries, clicks=clicks
    )


# ---------------------------------------------------------------
# Settings (WhatsApp number, address, etc.)
# ---------------------------------------------------------------
@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def admin_settings():
    if request.method == "POST":
        for key in ["whatsapp_number", "shop_phone", "brand_name", "owner_name",
                    "address", "hours", "upi_id", "upi_payee_name"]:
            value = request.form.get(key, "").strip()
            if value:
                set_setting(key, value)

        new_password = request.form.get("new_password", "").strip()
        if new_password:
            set_setting("admin_password_hash", generate_password_hash(new_password))
            flash("Settings saved, including a new admin password.", "success")
        else:
            flash("Settings saved.", "success")

        return redirect(url_for("admin_settings"))

    settings = get_settings()
    return render_template("admin/settings.html", settings=settings)


if __name__ == "__main__":
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    print("=" * 62)
    print(" SIZZLING by KBA — website & admin panel is running!")
    print("=" * 62)
    print(f" Website:            http://127.0.0.1:5000")
    print(f" Admin panel:        http://127.0.0.1:5000/admin")
    print(f" On your phone:      http://{local_ip}:5000")
    print("=" * 62)

    app.run(host="0.0.0.0", port=5000, debug=False)
