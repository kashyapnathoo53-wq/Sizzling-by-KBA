SIZZLING BY KBA PVT LTD — WEBSITE + BACKEND + ADMIN PANEL
============================================================

WHAT THIS IS
------------
A full website for your menswear brand with:
- The public site (same design as before, now loading products from
  a real database instead of hardcoded text)
- An admin panel at /admin where you can add products, upload real
  photos, edit prices, and change the WhatsApp number, address, hours
  etc. WITHOUT touching any code
- Every enquiry form submission and every "Order on WhatsApp" click
  is saved to the database so you can see it later in /admin

Your WhatsApp number (9811551935) is already set as the default.

============================================================
HOW ORDERING WORKS (Cart + UPI Payment)
============================================================
Customers can now:
1. Tap "Add to Cart" or "Buy Now" on any priced item (size selected first)
2. Open the cart (top-right), adjust quantities, and hit "Proceed to Checkout"
3. Fill in name, phone and address
4. Get a UPI QR code + payment link for the exact total, to pay to
   8595511923@ptaxis
5. Optionally type in their UPI transaction reference number after paying,
   or send a payment screenshot on WhatsApp instead

IMPORTANT — READ THIS: There is no payment gateway involved (Razorpay,
PayU, etc. require a business bank account, PAN/GST verification, and
approval, which is a separate setup). This is a "manual verification"
UPI flow: the site shows the customer a QR code / payment link to your
UPI ID, but nothing here automatically confirms that money actually
arrived. YOU must check your own UPI app or bank SMS to confirm the
payment landed before marking an order "Paid — Confirmed" in
/admin → Orders, and before dispatching any item. The transaction
reference a customer types in is just what they claim — it is not
verified by any bank API.

If you'd like real-time automatic payment confirmation later (so
orders are marked "Paid" the instant money arrives, no manual
checking needed), that requires integrating a UPI-enabled payment
gateway with webhook support (e.g. Razorpay, Cashfree) — a separate,
well-scoped addition once you have a registered business account with
one of them. Happy to build that integration whenever you're ready.

Items without a price still show "Order on WhatsApp" only, since the
cart cannot check out an item with no set price — add a price in
/admin → Products to enable cart ordering for that item.

============================================================
WHERE ORDERS ARE STORED
============================================================
Every order (cart checkout) and every enquiry-form submission is saved
in the database. View them anytime at:
   /admin → Orders       (cart checkouts, with UPI payment status)
   /admin → Enquiries    (enquiry form + WhatsApp click log)

============================================================
PART 1 - ONE-TIME SETUP (on your computer)
============================================================
1. Install Python 3 if not already installed: https://python.org
   (On Windows, tick "Add Python to PATH" during install.)
2. Unzip this folder somewhere easy to find (e.g. Desktop).
3. Open a terminal / command prompt INSIDE this folder and run:
       pip install -r requirements.txt

============================================================
PART 2 - RUNNING IT ON YOUR COMPUTER (to test / use locally)
============================================================
EASIEST WAY:
   - Windows: double-click "start_windows.bat"
   - Mac / Linux: double-click "start_mac_linux.sh"
     (or run:  ./start_mac_linux.sh  from a terminal)

MANUAL WAY:
   python app.py

Then open:
   Website:      http://127.0.0.1:5000
   Admin panel:  http://127.0.0.1:5000/admin

DEFAULT ADMIN PASSWORD: sizzling@2026
CHANGE THIS IMMEDIATELY — log in, go to Settings, and set a new
password under "Change Admin Password".

============================================================
PART 3 - ADDING YOUR REAL PRODUCT PHOTOS
============================================================
Right now every product uses a simple illustrated placeholder image
(there were no real product photos to work with). To add real photos:

1. Go to http://127.0.0.1:5000/admin (or your live domain + /admin)
2. Log in
3. Click "Products"
4. Click "Edit" next to any item, or "+ Add Product" for a new one
5. Choose a photo (JPG, PNG or WEBP, up to 8MB) and click Save

The photo appears on the live site immediately — no restart needed.
Good product photos matter a lot for a clothing brand; a plain,
well-lit photo of the actual garment (even taken on a phone against
a clean background) will sell far better than the placeholder art.

A NOTE ON "MODEL WEARING THE PRODUCT" PHOTOS: the placeholder
illustrations are drawn as a figure wearing each garment to give a
sense of fit, but they're original sketches, not real photography —
I'm not able to source or generate real photos of a person wearing
your specific products, since that would either require a licensed
stock photo (which isn't yours to use commercially) or a real photo
shoot. If you get product photography done — even simple photos of
a model or staff member wearing each item — upload those the same
way above and they'll replace the sketches immediately.

============================================================
PART 4 - CHANGING THE WHATSAPP NUMBER OR SHOP DETAILS
============================================================
Go to /admin → Settings. You can change:
- WhatsApp number (currently 919811551935)
- "Call Shop" number
- Brand name, owner name, address, opening hours
- Admin password

No code editing needed — everything updates on the live site instantly.

============================================================
PART 5 - DEPLOYING TO A REAL DOMAIN
============================================================
This app is ready to deploy to any Python-friendly host. A few
common, beginner-friendly options:

OPTION A — Render.com / Railway.app (easiest, has free/cheap tiers)
1. Create a free account and a new "Web Service" from this folder
   (push it to a GitHub repo first, then connect that repo).
2. Build command:   pip install -r requirements.txt
3. Start command:   gunicorn wsgi:app
4. Add environment variables (Settings → Environment):
       SECRET_KEY = (any long random string)
       ADMIN_PASSWORD = (a real password — only used the very first
                          time the site starts; after that, change
                          it from /admin → Settings instead)
5. Once deployed, point your domain's DNS to the host as instructed
   by Render/Railway, and your site is live on your own domain.

OPTION B — A VPS (e.g. DigitalOcean, Hostinger VPS)
1. Upload this folder to the server.
2. Install Python, then: pip install -r requirements.txt
3. Run with gunicorn behind Nginx:
       gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app
4. Point Nginx (or your domain) to that address, add an SSL
   certificate (e.g. via Certbot / Let's Encrypt, free).

OPTION C — PythonAnywhere (good for less technical setup)
Upload the folder, set the WSGI file to import from wsgi.py, and
follow their "Web" tab instructions to map your domain.

IMPORTANT BEFORE GOING LIVE:
- Copy .env.example to .env (or set the same variables on your host)
  and set a real SECRET_KEY and ADMIN_PASSWORD.
- The included database (sizzling.db) is a SQLite file. This is
  fine for a single-shop site with normal traffic. If you ever need
  multiple admins editing at once at high volume, a developer can
  move it to PostgreSQL later — the code is structured so that's a
  small change, not a rewrite.
- Make sure the "static/images/uploads" and "static/images/qr" folders
  are writable and backed up regularly (product photos and payment QR
  codes live there).
