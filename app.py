import os
import io
import base64
import random
import string
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify, redirect, url_for,
    session, flash, send_from_directory, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import qrcode

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# On Vercel the filesystem is read-only except for /tmp.
# Detect Vercel / serverless environment reliably.
_ON_VERCEL = bool(
    os.environ.get("VERCEL")
    or os.environ.get("VERCEL_ENV")
    or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    or not os.access(BASE_DIR, os.W_OK)
)
if _ON_VERCEL:
    DB_NAME = "/tmp/sizzling.db"
    UPLOAD_DIR = "/tmp/uploads"
    QR_DIR_TMP = "/tmp/qr"
else:
    DB_NAME = os.path.join(BASE_DIR, "sizzling.db")
    UPLOAD_DIR = os.path.join(BASE_DIR, "static", "images", "uploads")
    QR_DIR_TMP = None

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
QR_DIR = QR_DIR_TMP if _ON_VERCEL else os.path.join(BASE_DIR, "static", "images", "qr")
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
        gallery_images TEXT,
        active INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    try:
        cur.execute("ALTER TABLE products ADD COLUMN gallery_images TEXT")
    except Exception:
        pass

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
        customer_id INTEGER,
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

    # Add customer_id column to existing orders table if it doesn't exist (migration)
    try:
        cur.execute("ALTER TABLE orders ADD COLUMN customer_id INTEGER")
    except Exception:
        pass  # Column already exists

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

    # Customer accounts (phone-based, OTP login)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT UNIQUE NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    # OTP codes for customer login
    cur.execute("""
    CREATE TABLE IF NOT EXISTS otp_codes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        code TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used INTEGER DEFAULT 0
    )
    """)

    # Wishlist items (per customer)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS wishlist(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(customer_id, product_id)
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
    import json
    seed = {
        "suits": [
            ("Midnight Two-Piece Suit", "Deep navy, notch lapel, a first-suit that also works for the tenth interview.", 8999, "suit_midnight_navy.jpg"),
            ("Charcoal Windowpane Suit", "Subtle check, cut for the boardroom, built to travel well between meetings.", 9999, "suit_charcoal_windowpane.jpg"),
            ("Ivory Tuxedo Suit", "Satin lapel, evening-only — for the dinner where the invite says black tie.", 12999, "suit_ivory_tuxedo.jpg"),
            ("Royal Prince Check Suit", "Three-piece slate blue windowpane check suit with tailored waistcoat and matching trousers.", 10999, "suit_prince_check.jpg"),
            ("Classic Wall Street Navy Suit", "Sharp dark navy worsted wool two-piece suit with striped silk tie and French cuffs.", 11999, "suit_black_tie.jpg"),
            ("Mayfair Executive Navy Suit", "Sharp single-breasted two-piece suit in fine worsted wool with structured shoulders and silk-lined interior.", 9499, "suit_olive_tweed.jpg"),
        ],
        "blazers": [
            ("Bottle Green Velvet Blazer", "Textured velvet, single button — the piece that carries a festive evening.", 5499, "blazer_bottle_green.jpg"),
            ("Navy Textured Blazer", "Everyday blazer, pairs cleanly with formal or semi-formal trousers.", 4999, "blazer_navy_textured.jpg"),
            ("Rust Tweed Blazer", "Heavier weave for cooler months, worn open over a plain shirt.", 5999, "blazer_rust_tweed.jpg"),
            ("Dove Grey Flannel Blazer", "Contemporary unstructured blazer in soft dove grey wool flannel with notch lapels.", 5799, "blazer_royal_wine.jpg"),
            ("Herringbone Camel Wool Blazer", "Warm camel tone in classic herringbone weave with natural horn buttons.", 5299, "blazer_camel_herringbone.jpg"),
            ("Cobalt Blue Tailored Blazer", "Vibrant cobalt blue tailored single-breasted blazer featuring notch lapels and silk pocket square.", 6499, "blazer_midnight_jacquard.jpg"),
        ],
        "jackets": [
            ("Quilted Bomber Jacket", "Structured quilting, zip front — smart enough to wear over a shirt.", 6499, "jacket_quilted_bomber.jpg"),
            ("Wool Overcoat", "Full-length layer for Delhi winters, worn straight over a suit.", 8999, "jacket_wool_overcoat.jpg"),
            ("Textured Field Jacket", "Four-pocket utility cut, sits between casual and smart-casual.", 5999, "jacket_textured_field.jpg"),
            ("Cognac Leather Moto Jacket", "Supple cognac tan leather moto jacket with asymmetrical zip closure and snap lapels.", 6999, "jacket_suede_harrington.jpg"),
            ("Double-Breasted Trench Overcoat", "Classic double-breasted trench overcoat with storm flap, horn buttons, and shoulder epaulets.", 9499, "jacket_trench_overcoat.jpg"),
            ("Minimalist Leather Biker Jacket", "Supple full-grain calfskin moto leather jacket with asymmetric silver zips and tailored fit.", 7999, "jacket_leather_biker.jpg"),
        ],
        "shirts": [
            ("Crisp White Dress Shirt", "The one every formal wardrobe is built around. Spread collar and French cuffs.", 1299, "shirt_crisp_white.jpg"),
            ("Sky Blue Formal Shirt", "Slightly softer than white, easy to wear with or without a tie.", 1199, "shirt_sky_blue.jpg"),
            ("Fine Striped Business Shirt", "Subtle stripe with contrast white spread collar and double French cuffs.", 1399, "shirt_fine_striped.jpg"),
            ("Royal Oxford Pink Shirt", "Pinpoint Oxford cotton in subtle blush rose with spread collar and tailored fit.", 1349, "shirt_royal_oxford_pink.jpg"),
            ("Midnight Charcoal Formal Shirt", "Deep midnight charcoal poplin dress shirt with crisp spread collar and tailored silhouette.", 1499, "shirt_midnight_charcoal.jpg"),
            ("French Blue Cutaway Shirt", "Pure Egyptian cotton in royal French blue with spread collar and tailored fit.", 1599, "shirt_french_cuff_blue.jpg"),
        ],
        "pants": [
            ("Classic Charcoal Trouser", "Flat-front, straight leg — the trouser that goes under any jacket.", 1799, "pants_classic_charcoal.jpg"),
            ("Slim-Fit Navy Trouser", "Tapered through the leg, worn on its own or with a blazer.", 1699, "pants_slim_navy.jpg"),
            ("Pleated Grey Trouser", "Traditional pleat for a roomier fit, favoured for longer days.", 1899, "pants_pleated_grey.jpg"),
            ("Tailored Khaki Chino Trouser", "Versatile tailored khaki trousers cut from breathable cotton-twill for modern smart-casual styling.", 1999, "pants_khaki_gurkha.jpg"),
            ("Jet Black Tailored Dress Trouser", "Straight formal cut tailored in rich jet-black fabric, ideal for evening affairs and black-tie events.", 1899, "pants_jet_black_tux.jpg"),
            ("Tailored Charcoal Wool Trouser", "Mid-rise tapered formal trouser in breathable wool blend with crisp crease and turn-up cuffs.", 1799, "pants_olive_wool.jpg"),
        ],
        "sherwanis": [
            ("Regal Charcoal Brocade Sherwani", "Intricate floral brocade long achkan with structured mandarin collar for festive evenings.", 14499, "sherwani_royal_gold.jpg"),
            ("Ivory Silk Heritage Sherwani", "Hand-tailored ivory raw silk achkan with ornate silver buttons and royal brooch.", 13999, "sherwani_ivory_silk.jpg"),
            ("Imperial Gold & Maroon Wedding Sherwani", "Intricate gold zardozi embroidery with rich maroon velvet stole and royal safa.", 17999, "sherwani_maroon_velvet.jpg"),
            ("Noir Embroidered Designer Sherwani", "Sleek tonal jacquard raw silk achkan with velvet mandarin collar and handcrafted antique gold buttons.", 15999, "sherwani_pastel_peach.jpg"),
            ("Royal Heritage Bandhgala Suit", "Tailored black royal bandhgala jacket with jeweled ruby brooch and silk pocket square.", 12999, "sherwani_emerald_embroidered.jpg"),
            ("Royal Midnight & Gold Brocade Sherwani", "Lavish midnight blue and gold brocade achkan with royal blue velvet stole.", 16999, "sherwani_midnight_blue.jpg"),
        ],
    }

    for category, items in seed.items():
        for i, (name, desc, price, img_file) in enumerate(items):
            prod_image = f"products/{img_file}"
            base_name = img_file.rsplit(".", 1)[0]
            gallery = json.dumps([
                prod_image,
                f"products/gallery/{base_name}_detail.jpg",
                f"products/gallery/{base_name}_angle.jpg",
                f"products/gallery/{base_name}_fabric.jpg"
            ])
            cur.execute("""
                INSERT INTO products(category, name, description, price, image_path, gallery_images, sort_order)
                VALUES (?,?,?,?,?,?,?)
            """, (category, name, desc, price, prod_image, gallery, i))


if _ON_VERCEL:
    src_db = os.path.join(BASE_DIR, "sizzling.db")
    if os.path.exists(src_db) and not os.path.exists("/tmp/sizzling.db"):
        try:
            import shutil
            shutil.copy2(src_db, "/tmp/sizzling.db")
        except Exception:
            pass

try:
    init_db()
except Exception as e:
    import traceback
    print("Database initialization warning:", e)
    traceback.print_exc()



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

    # Also link order to customer if they are logged in
    cust_id = session.get("customer_id")
    if cust_id:
        conn2 = get_db()
        conn2.execute("UPDATE orders SET customer_id=? WHERE id=?", (cust_id, order_id))
        conn2.commit()
        conn2.close()

    _generate_upi_qr(order_id, total)  # generate (side-effect: updates upi uri, ignore return)

    return jsonify({
        "success": True,
        "order_id": order_id,
        "total": round(total, 2),
        "pay_url": url_for("order_pay", order_id=order_id),
    })


def _generate_upi_qr(order_id, amount):
    """Generate UPI QR as base64 data URI — no filesystem writes needed."""
    settings = get_settings()
    upi_id = settings.get("upi_id", "8595511923@ptaxis")
    payee = settings.get("upi_payee_name", settings.get("brand_name", "SIZZLING by KBA"))
    formatted_amount = f"{float(amount):.2f}"
    upi_uri = (
        f"upi://pay?pa={upi_id}&pn={urllib.parse.quote(payee)}"
        f"&am={formatted_amount}&cu=INR&tn={urllib.parse.quote(f'Order #{order_id} Sizzling')}"
        f"&tr={order_id}&mode=02"
    )
    img = qrcode.make(upi_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return upi_uri, f"data:image/png;base64,{b64}"


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
    upi_uri, qr_data_uri = _generate_upi_qr(order_id, order["total"])

    return render_template(
        "payment.html", order=order, items=items, settings=settings,
        upi_uri=upi_uri, qr_data_uri=qr_data_uri
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
    ("confirmed", "Confirmed & Accepted"),
    ("dispatched", "Dispatched / In Transit"),
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


@app.route("/admin/orders/<int:order_id>/update_status", methods=["POST"])
@login_required
def admin_update_order_status(order_id):
    new_status = request.form.get("status")
    valid_statuses = [s[0] for s in ORDER_STATUSES]
    if new_status in valid_statuses:
        conn = get_db()
        conn.execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
        conn.commit()
        conn.close()
        flash(f"Order #{order_id} status updated to {new_status.replace('_', ' ').title()}.", "success")
    return redirect(url_for("admin_orders"))


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
                    "address", "hours", "upi_id", "upi_payee_name", "fast2sms_api_key"]:
            value = request.form.get(key, "").strip()
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


# =====================================================================
# CUSTOMER ACCOUNT — OTP LOGIN
# =====================================================================
FAST2SMS_API_KEY = os.environ.get("FAST2SMS_API_KEY", "")


def _send_otp_fast2sms(phone, otp):
    """Send OTP via Fast2SMS. Returns True on success."""
    api_key = os.environ.get("FAST2SMS_API_KEY", "") or get_settings().get("fast2sms_api_key", "")
    if not api_key:
        print(f"[OTP LOG] Generated OTP for {phone}: {otp} (Fast2SMS key not set)")
        return False
    try:
        url = "https://www.fast2sms.com/dev/bulkV2"
        payload = urllib.parse.urlencode({
            "authorization": api_key,
            "variables_values": otp,
            "route": "otp",
            "numbers": phone,
        }).encode("ascii")
        req = urllib.request.Request(
            url, data=payload,
            headers={
                "cache-control": "no-cache",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("return") is True
    except Exception as exc:
        print(f"[WARN] Fast2SMS error: {exc}")
        return False


def _generate_otp():
    return "".join(random.choices(string.digits, k=6))


def customer_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("customer_id"):
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "login_required": True, "error": "Login required"}), 401
            return redirect(url_for("customer_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def _normalize_phone(raw_phone):
    import re
    digits = re.sub(r"\D", "", str(raw_phone or ""))
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[-10:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def _login_or_register_customer(clean_phone, name=None):
    conn = get_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS customers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT UNIQUE NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)
    conn.commit()

    existing = conn.execute(
        "SELECT * FROM customers WHERE phone=?", (clean_phone,)
    ).fetchone()

    if existing:
        cust_id = existing["id"]
        if name and (not existing["name"] or existing["name"] == "Customer"):
            conn.execute("UPDATE customers SET name=? WHERE id=?", (name, cust_id))
    else:
        conn.execute(
            "INSERT INTO customers(name, phone) VALUES (?,?)",
            (name or "Customer", clean_phone),
        )
        cust_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Link past orders
    try:
        conn.execute(
            "UPDATE orders SET customer_id=? WHERE (phone=? OR phone=? OR phone=?) AND (customer_id IS NULL OR customer_id != ?)",
            (cust_id, clean_phone, f"91{clean_phone}", f"+91{clean_phone}", cust_id),
        )
    except Exception:
        pass

    conn.commit()
    conn.close()

    session["customer_id"] = cust_id
    session["customer_phone"] = clean_phone
    return cust_id


@app.route("/account/login", methods=["GET", "POST"])
def customer_login():
    next_url = request.args.get("next") or request.form.get("next") or url_for("my_orders")
    if session.get("customer_id"):
        return redirect(next_url)

    if request.method == "POST":
        raw_phone = request.form.get("phone", "")
        name = request.form.get("name", "")
        clean_phone = _normalize_phone(raw_phone)
        if len(clean_phone) == 10:
            try:
                _login_or_register_customer(clean_phone, name)
                return redirect(next_url)
            except Exception as e:
                flash("Login failed. Please try again.", "error")
        else:
            flash("Please enter a valid 10-digit mobile number.", "error")

    return render_template(
        "user/login.html", next_url=next_url, settings=get_settings()
    )


@app.route("/api/account/direct_login", methods=["POST"])
def api_direct_login():
    try:
        data = request.get_json(silent=True) or request.form or {}
        raw_phone = data.get("phone") or ""
        name = data.get("name") or ""
        clean_phone = _normalize_phone(raw_phone)

        if len(clean_phone) != 10:
            return jsonify({"success": False, "error": "Please enter a valid 10-digit mobile number."}), 400

        _login_or_register_customer(clean_phone, name)

        next_url = request.args.get("next") or request.form.get("next") or url_for("my_orders")
        return jsonify({"success": True, "redirect": next_url})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Login failed: {str(e)}"}), 500


@app.route("/api/account/send_otp", methods=["POST"])
def api_send_otp():
    data = request.json or {}
    phone = (data.get("phone") or "").strip().lstrip("+")
    if not phone.isdigit() or len(phone) < 10:
        return jsonify({"success": False, "error": "Enter a valid 10-digit phone number."}), 400

    otp = _generate_otp()
    expires = (datetime.utcnow() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    conn.execute(
        "INSERT INTO otp_codes(phone, code, expires_at) VALUES (?,?,?)",
        (phone, otp, expires),
    )
    conn.commit()
    conn.close()

    sent = _send_otp_fast2sms(phone, otp)

    return jsonify({
        "success": True,
        "sms_sent": sent,
        "message": f"OTP sent to {phone} via SMS.",
    })


@app.route("/api/account/verify_otp", methods=["POST"])
def api_verify_otp():
    data = request.json or {}
    phone = (data.get("phone") or "").strip().lstrip("+")
    otp = (data.get("otp") or "").strip()
    name = (data.get("name") or "").strip()

    conn = get_db()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    row = conn.execute(
        """SELECT * FROM otp_codes
           WHERE phone=? AND code=? AND used=0 AND expires_at > ?
           ORDER BY id DESC LIMIT 1""",
        (phone, otp, now),
    ).fetchone()

    if row is None:
        conn.close()
        return jsonify({"success": False, "error": "Invalid or expired OTP."}), 400

    # Mark OTP as used
    conn.execute("UPDATE otp_codes SET used=1 WHERE id=?", (row["id"],))

    # Upsert customer
    existing = conn.execute(
        "SELECT * FROM customers WHERE phone=?", (phone,)
    ).fetchone()
    if existing:
        cust_id = existing["id"]
        if name and not existing["name"]:
            conn.execute("UPDATE customers SET name=? WHERE id=?", (name, cust_id))
    else:
        conn.execute(
            "INSERT INTO customers(name, phone) VALUES (?,?)", (name or "Customer", phone)
        )
        cust_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Link any orders by this phone to the customer account
    conn.execute(
        "UPDATE orders SET customer_id=? WHERE phone=? AND customer_id IS NULL",
        (cust_id, phone),
    )
    conn.commit()
    conn.close()

    session["customer_id"] = cust_id
    session["customer_phone"] = phone
    return jsonify({"success": True, "redirect": url_for("my_orders")})


@app.route("/account/logout")
def customer_logout():
    session.pop("customer_id", None)
    session.pop("customer_phone", None)
    return redirect(url_for("home"))


@app.route("/account/orders")
@customer_login_required
def my_orders():
    cust_id = session.get("customer_id")
    phone = session.get("customer_phone", "")
    conn = get_db()
    orders = conn.execute(
        """SELECT * FROM orders 
           WHERE customer_id=? 
              OR (phone IS NOT NULL AND phone != '' AND (phone=? OR phone=? OR phone=?))
           ORDER BY id DESC""",
        (cust_id, phone, f"91{phone}" if phone else "", f"+91{phone}" if phone else ""),
    ).fetchall()
    conn.close()
    return render_template(
        "user/my_orders.html",
        orders=orders,
        settings=get_settings(),
        customer_phone=session.get("customer_phone"),
    )


@app.route("/account/order/<int:order_id>")
@customer_login_required
def my_order_detail(order_id):
    cust_id = session["customer_id"]
    conn = get_db()
    order = conn.execute(
        "SELECT * FROM orders WHERE id=? AND customer_id=?", (order_id, cust_id)
    ).fetchone()
    if order is None:
        conn.close()
        abort(404)
    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id=?", (order_id,)
    ).fetchall()
    conn.close()
    return render_template(
        "user/order_detail.html",
        order=order, items=items,
        settings=get_settings(),
    )


# =====================================================================
# WISHLIST (requires login)
# =====================================================================
@app.route("/api/wishlist", methods=["GET"])
@customer_login_required
def api_wishlist_get():
    cust_id = session["customer_id"]
    conn = get_db()
    rows = conn.execute(
        """SELECT w.product_id, p.name, p.category, p.price, p.image_path
           FROM wishlist w JOIN products p ON w.product_id=p.id
           WHERE w.customer_id=?""",
        (cust_id,),
    ).fetchall()
    conn.close()
    return jsonify({"success": True, "items": [dict(r) for r in rows]})


@app.route("/api/wishlist/toggle", methods=["POST"])
@customer_login_required
def api_wishlist_toggle():
    cust_id = session["customer_id"]
    product_id = (request.json or {}).get("product_id")
    if not product_id:
        return jsonify({"success": False, "error": "product_id required"}), 400
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM wishlist WHERE customer_id=? AND product_id=?",
        (cust_id, product_id),
    ).fetchone()
    if existing:
        conn.execute("DELETE FROM wishlist WHERE id=?", (existing["id"],))
        wishlisted = False
    else:
        conn.execute(
            "INSERT OR IGNORE INTO wishlist(customer_id, product_id) VALUES (?,?)",
            (cust_id, product_id),
        )
        wishlisted = True
    conn.commit()
    conn.close()
    return jsonify({"success": True, "wishlisted": wishlisted})


@app.route("/api/wishlist/ids", methods=["GET"])
def api_wishlist_ids():
    """Return list of wishlisted product IDs for the current customer (or empty)."""
    cust_id = session.get("customer_id")
    if not cust_id:
        return jsonify({"ids": []})
    conn = get_db()
    rows = conn.execute(
        "SELECT product_id FROM wishlist WHERE customer_id=?", (cust_id,)
    ).fetchall()
    conn.close()
    return jsonify({"ids": [r["product_id"] for r in rows]})


@app.route("/account/wishlist")
@customer_login_required
def my_wishlist():
    cust_id = session["customer_id"]
    conn = get_db()
    rows = conn.execute(
        """SELECT p.* FROM wishlist w JOIN products p ON w.product_id=p.id
           WHERE w.customer_id=? AND p.active=1 ORDER BY w.id DESC""",
        (cust_id,),
    ).fetchall()
    conn.close()
    return render_template(
        "user/wishlist.html",
        products=[dict(r) for r in rows],
        settings=get_settings(),
    )


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
