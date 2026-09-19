import hmac
import hashlib
import json
import sqlite3
from app import app, get_db

def run_tests():
    print("==================================================")
    print(" RUNNING SIZZLING BY KBA PAYMENT SECURITY TESTS   ")
    print("==================================================")
    
    client = app.test_client()
    
    # 1. Create a dummy test order in the DB
    conn = sqlite3.connect("sizzling.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO orders (
            customer_name, phone, address, total, 
            status, payment_status, created_at, updated_at
        ) VALUES (
            'Security Test User', '9999999999', 'Karol Bagh, New Delhi',
            2499, 'pending_payment', 'unpaid', datetime('now'), datetime('now')
        )
    """)
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    
    # Save original razorpay credentials so we restore them after test
    from app import get_settings, set_setting
    orig_settings = get_settings()
    orig_key_id = orig_settings.get("razorpay_key_id", "")
    orig_key_secret = orig_settings.get("razorpay_key_secret", "")

    test_key_id = "rzp_test_SecTest123"
    test_key_secret = "SecretSuperKeyXYZ789"
    set_setting("razorpay_key_id", test_key_id)
    set_setting("razorpay_key_secret", test_key_secret)
    
    print(f"[*] Created test order #{order_id} with status='pending_payment' and payment_status='unpaid'")
    
    # TEST 1: Direct GET on /order/<id>/confirmation while unpaid
    print("\n--- TEST 1: Unpaid Order Confirmation Access ---")
    resp = client.get(f"/order/{order_id}/confirmation")
    print(f"Status Code: {resp.status_code}")
    print(f"Location: {resp.headers.get('Location')}")
    assert resp.status_code == 302, f"Expected 302 redirect, got {resp.status_code}"
    assert f"/order/{order_id}/pay" in resp.headers.get('Location', ''), "Did not redirect to pay page!"
    print("PASSED: Unpaid order was strictly redirected to payment page.")
    
    # TEST 2: Submit forged / dummy signature to verify_payment
    print("\n--- TEST 2: Forged / Fake Signature Verification ---")
    fake_payload = {
        "razorpay_payment_id": "pay_fake_test_12345",
        "razorpay_order_id": "order_fake_98765",
        "razorpay_signature": "sig_verified_ok" # Old fake bypass signature!
    }
    resp = client.post(f"/api/order/{order_id}/razorpay/verify_payment",
                       data=json.dumps(fake_payload),
                       content_type="application/json")
    print(f"Status Code: {resp.status_code}")
    data = resp.get_json()
    print(f"Response: {data}")
    assert resp.status_code == 400, f"Expected 400 Bad Request, got {resp.status_code}"
    assert data.get("success") is False, "Fake signature should not succeed!"
    
    # Verify in DB that order was NOT updated
    conn = sqlite3.connect("sizzling.db")
    conn.row_factory = sqlite3.Row
    order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    assert order["payment_status"] == "unpaid", f"Expected unpaid, got {order['payment_status']}"
    assert order["status"] == "pending_payment", f"Expected pending_payment, got {order['status']}"
    conn.close()
    print("PASSED: Forged/fake signature was rejected and order remained unpaid.")
    
    # TEST 3: Genuine cryptographic HMAC-SHA256 signature
    print("\n--- TEST 3: Valid Cryptographic HMAC-SHA256 Signature ---")
    real_payment_id = "pay_valid_sample_9999"
    real_rzp_order_id = "order_valid_sample_8888"
    msg = f"{real_rzp_order_id}|{real_payment_id}".encode("utf-8")
    valid_signature = hmac.new(test_key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    
    valid_payload = {
        "razorpay_payment_id": real_payment_id,
        "razorpay_order_id": real_rzp_order_id,
        "razorpay_signature": valid_signature
    }
    resp = client.post(f"/api/order/{order_id}/razorpay/verify_payment",
                       data=json.dumps(valid_payload),
                       content_type="application/json")
    print(f"Status Code: {resp.status_code}")
    data = resp.get_json()
    print(f"Response: {data}")
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}"
    assert data.get("success") is True, "Valid signature failed!"
    
    # Verify in DB that order is confirmed and payment_verified
    conn = sqlite3.connect("sizzling.db")
    conn.row_factory = sqlite3.Row
    order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    assert order["payment_status"] == "payment_verified", f"Expected payment_verified, got {order['payment_status']}"
    assert order["status"] == "confirmed", f"Expected confirmed, got {order['status']}"
    conn.close()
    print("PASSED: Valid signature verified and order marked confirmed!")
    
    # TEST 4: Confirmation page after verified payment
    print("\n--- TEST 4: Confirmation Page Access for Verified Order ---")
    resp = client.get(f"/order/{order_id}/confirmation")
    print(f"Status Code: {resp.status_code}")
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}"
    html_text = resp.get_data(as_text=True)
    assert "Payment Verified &amp; Order Confirmed!" in html_text or "Payment Verified & Order Confirmed!" in html_text, "Confirmation header missing!"
    print("PASSED: Confirmed order shows Payment Verified header.")
    
    # Cleanup test order
    conn = sqlite3.connect("sizzling.db")
    conn.execute("DELETE FROM orders WHERE id=?", (order_id,))
    conn.commit()
    conn.close()

    # Restore original credentials
    set_setting("razorpay_key_id", orig_key_id)
    set_setting("razorpay_key_secret", orig_key_secret)
    print(f"\n[*] Cleaned up test order #{order_id}")
    print("\n==================================================")
    print(" ALL PAYMENT SECURITY & VERIFICATION TESTS PASSED! ")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
