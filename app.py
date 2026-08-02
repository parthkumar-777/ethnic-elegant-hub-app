import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from functools import wraps
from collections import defaultdict
from flask import (Flask, render_template, request, redirect, url_for,
                    session, flash, jsonify, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from db import get_db, init_db

app = Flask(__name__)
app.secret_key = "eeh-dev-secret-change-in-production-please"
UPLOAD_FOLDER = os.path.join(app.static_folder, "products")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()


def send_email(to_email, subject, html_body):
    """Best-effort email send. Silently does nothing if SMTP isn't configured,
    so local dev / missing credentials never break checkout."""
    if not SMTP_EMAIL or not SMTP_PASSWORD or not to_email:
        return False
    try:
        msg = MIMEText(html_body, "html")
        msg["Subject"] = subject
        msg["From"] = SMTP_EMAIL
        msg["To"] = to_email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        return False


def build_order_email_html(order_id, items, final_total, address, payment_method):
    rows = "".join(
        f"<tr><td style='padding:6px 10px;'>{it['product']['name']} (Size: {it['size']}) × {it['qty']}</td>"
        f"<td style='padding:6px 10px; text-align:right;'>₹{int(it['subtotal'])}</td></tr>"
        for it in items
    )
    return f"""
    <div style="font-family:Arial, sans-serif; max-width:520px; margin:0 auto;">
      <h2 style="color:#6b1626;">Thank you for your order!</h2>
      <p>Your order <b>#{order_id}</b> has been placed successfully.</p>
      <table style="width:100%; border-collapse:collapse; margin:16px 0;">{rows}</table>
      <p style="font-weight:bold; font-size:16px;">Total: ₹{int(final_total)}</p>
      <p><b>Payment Method:</b> {payment_method}</p>
      <p><b>Delivery Address:</b><br>{address}</p>
      <p style="color:#888; font-size:12px; margin-top:24px;">Ethnic Elegant Hub — Grace in every drape</p>
    </div>
    """


@app.template_filter("fmtdate")
def fmt_date(value):
    if not value:
        return ""
    from datetime import datetime
    if isinstance(value, str):
        try:
            dt = datetime.strptime(value.split(".")[0], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return value
    else:
        dt = value
    return dt.strftime("%d %b %Y, %I:%M %p")


CATEGORIES = ["Sarees", "Kurta Sets", "Lehenga Choli", "Salwar Suits",
              "Gowns", "Dupattas", "Ethnic Jackets"]


# ---------- helpers ----------
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return user


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("user_id"):
            flash("Please login to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        u = current_user()
        if not u or not u["is_admin"]:
            flash("Admin access required.", "danger")
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return wrapper


def get_cart():
    return session.setdefault("cart", {})  # {product_id_str: {"qty": n, "size": s}}


def cart_count():
    return sum(item["qty"] for item in get_cart().values())


@app.context_processor
def inject_globals():
    return dict(current_user=current_user(), categories=CATEGORIES,
                cart_count=cart_count())


# ---------- storefront ----------
@app.route("/")
def index():
    conn = get_db()
    featured = conn.execute("SELECT * FROM products WHERE is_featured=1").fetchall()
    all_products = conn.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("index.html", featured=featured, products=all_products)


@app.route("/category/<name>")
def category(name):
    conn = get_db()
    sort = request.args.get("sort", "")
    query = "SELECT * FROM products WHERE category=?"
    if sort == "price_low":
        query += " ORDER BY price ASC"
    elif sort == "price_high":
        query += " ORDER BY price DESC"
    elif sort == "rating":
        query += " ORDER BY rating DESC"
    else:
        query += " ORDER BY created_at DESC"
    products = conn.execute(query, (name,)).fetchall()
    conn.close()
    return render_template("category.html", products=products, category=name, sort=sort)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "")
    conn = get_db()
    query = "SELECT * FROM products WHERE LOWER(name) LIKE LOWER(?) OR LOWER(category) LIKE LOWER(?) OR LOWER(fabric) LIKE LOWER(?)"
    if sort == "price_low":
        query += " ORDER BY price ASC"
    elif sort == "price_high":
        query += " ORDER BY price DESC"
    elif sort == "rating":
        query += " ORDER BY rating DESC"
    else:
        query += " ORDER BY created_at DESC"
    like_q = f"%{q}%"
    products = conn.execute(query, (like_q, like_q, like_q)).fetchall()
    conn.close()
    return render_template("category.html", products=products, category=f'Results for "{q}"', sort=sort)


@app.route("/product/<int:pid>")
def product_detail(pid):
    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not product:
        conn.close()
        abort(404)
    related = conn.execute(
        "SELECT * FROM products WHERE category=? AND id<>? LIMIT 4",
        (product["category"], pid),
    ).fetchall()
    reviews = conn.execute(
        """SELECT reviews.*, users.name as reviewer_name FROM reviews
        JOIN users ON users.id = reviews.user_id
        WHERE product_id=? ORDER BY reviews.created_at DESC""",
        (pid,),
    ).fetchall()
    review_count = len(reviews)
    avg_rating = round(sum(r["rating"] for r in reviews) / review_count, 1) if review_count else None
    in_wishlist = False
    if session.get("user_id"):
        w = conn.execute(
            "SELECT id FROM wishlist WHERE user_id=? AND product_id=?", (session["user_id"], pid)
        ).fetchone()
        in_wishlist = bool(w)
    conn.close()
    return render_template("product.html", p=product, related=related, reviews=reviews,
                            review_count=review_count, avg_rating=avg_rating, in_wishlist=in_wishlist)


@app.route("/product/<int:pid>/review", methods=["POST"])
@login_required
def add_review(pid):
    rating = int(request.form["rating"])
    comment = request.form.get("comment", "").strip()
    conn = get_db()
    conn.execute(
        "INSERT INTO reviews (product_id, user_id, rating, comment) VALUES (?,?,?,?)",
        (pid, session["user_id"], rating, comment),
    )
    conn.commit()
    conn.close()
    flash("Thank you for your review!", "success")
    return redirect(url_for("product_detail", pid=pid))


# ---------- wishlist ----------
@app.route("/wishlist")
@login_required
def wishlist():
    conn = get_db()
    products = conn.execute(
        """SELECT products.* FROM wishlist JOIN products ON products.id = wishlist.product_id
        WHERE wishlist.user_id=? ORDER BY wishlist.created_at DESC""",
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return render_template("wishlist.html", products=products)


@app.route("/wishlist/add/<int:pid>", methods=["POST"])
@login_required
def wishlist_add(pid):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM wishlist WHERE user_id=? AND product_id=?", (session["user_id"], pid)
    ).fetchone()
    if not existing:
        conn.execute("INSERT INTO wishlist (user_id, product_id) VALUES (?,?)", (session["user_id"], pid))
        conn.commit()
    conn.close()
    flash("Added to wishlist.", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/wishlist/remove/<int:pid>", methods=["POST"])
@login_required
def wishlist_remove(pid):
    conn = get_db()
    conn.execute("DELETE FROM wishlist WHERE user_id=? AND product_id=?", (session["user_id"], pid))
    conn.commit()
    conn.close()
    flash("Removed from wishlist.", "info")
    return redirect(request.referrer or url_for("wishlist"))


@app.route("/categories")
def categories_page():
    return render_template("categories.html")


@app.route("/account")
@login_required
def account():
    return render_template("account.html")


@app.route("/account/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_pw = request.form["current_password"]
        new_pw = request.form["new_password"]
        confirm_pw = request.form["confirm_password"]
        user = current_user()
        if not check_password_hash(user["password_hash"], current_pw):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("change_password"))
        if len(new_pw) < 6:
            flash("New password must be at least 6 characters.", "danger")
            return redirect(url_for("change_password"))
        if new_pw != confirm_pw:
            flash("New password and confirm password do not match.", "danger")
            return redirect(url_for("change_password"))
        conn = get_db()
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (generate_password_hash(new_pw), user["id"]),
        )
        conn.commit()
        conn.close()
        flash("Password changed successfully.", "success")
        return redirect(url_for("account"))
    return render_template("change_password.html")


@app.route("/account/change-email", methods=["GET", "POST"])
@login_required
def change_email():
    if request.method == "POST":
        new_email = request.form["new_email"].strip().lower()
        current_pw = request.form["current_password"]
        user = current_user()
        if not check_password_hash(user["password_hash"], current_pw):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("change_email"))
        conn = get_db()
        existing = conn.execute("SELECT id FROM users WHERE email=? AND id<>?", (new_email, user["id"])).fetchone()
        if existing:
            flash("This email is already in use by another account.", "danger")
            conn.close()
            return redirect(url_for("change_email"))
        conn.execute("UPDATE users SET email=? WHERE id=?", (new_email, user["id"]))
        conn.commit()
        conn.close()
        flash("Email updated successfully. Please use your new email next time you log in.", "success")
        return redirect(url_for("account"))
    return render_template("change_email.html")


# ---------- auth ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form["password"]
        conn = get_db()
        existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            flash("An account with this email already exists. Please login.", "danger")
            conn.close()
            return redirect(url_for("signup"))
        conn.execute(
            "INSERT INTO users (name, email, phone, password_hash) VALUES (?,?,?,?)",
            (name, email, phone, generate_password_hash(password)),
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        session["user_id"] = user["id"]
        flash(f"Welcome to Ethnic Elegant Hub, {name}!", "success")
        return redirect(url_for("index"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['name']}!", "success")
            nxt = request.args.get("next")
            if user["is_admin"] and nxt is None:
                return redirect(url_for("admin_dashboard"))
            return redirect(nxt or url_for("index"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------- cart & checkout ----------
def get_applied_coupon():
    return session.get("coupon")


def compute_discount(total):
    coupon = get_applied_coupon()
    if not coupon:
        return 0, None
    if total < coupon.get("min_order_amount", 0):
        return 0, None
    discount = round(total * coupon["discount_percent"] / 100, 2)
    return discount, coupon


@app.route("/cart")
def view_cart():
    cart = get_cart()
    conn = get_db()
    items = []
    total = 0
    for pid, info in cart.items():
        p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if p:
            subtotal = p["price"] * info["qty"]
            total += subtotal
            items.append({"product": p, "qty": info["qty"], "size": info["size"], "subtotal": subtotal})
    conn.close()
    discount, coupon = compute_discount(total)
    return render_template("cart.html", items=items, total=total, discount=discount,
                            coupon=coupon, final_total=total - discount)


@app.route("/cart/apply-coupon", methods=["POST"])
def apply_coupon():
    code = request.form.get("coupon_code", "").strip().upper()
    conn = get_db()
    c = conn.execute("SELECT * FROM coupons WHERE code=? AND active=1", (code,)).fetchone()
    conn.close()
    if not c:
        flash("Invalid or inactive coupon code.", "danger")
        return redirect(url_for("view_cart"))
    session["coupon"] = {
        "code": c["code"],
        "discount_percent": c["discount_percent"],
        "min_order_amount": c["min_order_amount"],
    }
    session.modified = True
    flash(f"Coupon '{c['code']}' applied!", "success")
    return redirect(url_for("view_cart"))


@app.route("/cart/remove-coupon", methods=["POST"])
def remove_coupon():
    session.pop("coupon", None)
    session.modified = True
    flash("Coupon removed.", "info")
    return redirect(url_for("view_cart"))


@app.route("/cart/add/<int:pid>", methods=["POST"])
def add_to_cart(pid):
    size = request.form.get("size", "M")
    qty = int(request.form.get("qty", 1))
    action = request.form.get("action", "cart")

    conn = get_db()
    product = conn.execute("SELECT stock FROM products WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not product or product["stock"] <= 0:
        flash("Sorry, this product is out of stock.", "danger")
        return redirect(request.referrer or url_for("index"))

    cart = get_cart()
    key = str(pid)
    if key in cart:
        cart[key]["qty"] += qty
    else:
        cart[key] = {"qty": qty, "size": size}
    session.modified = True
    if action == "buy":
        return redirect(url_for("view_cart"))
    flash("Added to cart.", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/cart/update/<int:pid>", methods=["POST"])
def update_cart(pid):
    action = request.form.get("action")
    cart = get_cart()
    key = str(pid)
    if key in cart:
        if action == "increase":
            cart[key]["qty"] += 1
        elif action == "decrease":
            cart[key]["qty"] -= 1
            if cart[key]["qty"] <= 0:
                del cart[key]
        elif action == "remove":
            del cart[key]
    session.modified = True
    return redirect(url_for("view_cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart = get_cart()
    if not cart:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("index"))
    conn = get_db()
    items, total = [], 0
    for pid, info in cart.items():
        p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if p:
            subtotal = p["price"] * info["qty"]
            total += subtotal
            items.append({"product": p, "qty": info["qty"], "size": info["size"], "subtotal": subtotal})

    discount, coupon = compute_discount(total)
    final_total = total - discount

    if request.method == "POST":
        address = request.form["address"]
        payment_method = request.form.get("payment_method", "COD")
        cur = conn.execute(
            "INSERT INTO orders (user_id, total_amount, address, payment_method, coupon_code, discount_amount) VALUES (?,?,?,?,?,?)",
            (session["user_id"], final_total, address, payment_method,
             coupon["code"] if coupon else None, discount),
        )
        order_id = cur.lastrowid
        for it in items:
            conn.execute(
                """INSERT INTO order_items (order_id, product_id, product_name, size, quantity, price)
                VALUES (?,?,?,?,?,?)""",
                (order_id, it["product"]["id"], it["product"]["name"], it["size"], it["qty"], it["product"]["price"]),
            )
            conn.execute(
                "UPDATE products SET stock = CASE WHEN stock - ? < 0 THEN 0 ELSE stock - ? END WHERE id=?",
                (it["qty"], it["qty"], it["product"]["id"]),
            )
        conn.commit()
        conn.close()
        session["cart"] = {}
        session.pop("coupon", None)
        session.modified = True

        # best-effort order confirmation email (never blocks checkout on failure)
        try:
            user_for_email = current_user()
            if user_for_email and user_for_email["email"]:
                send_email(
                    user_for_email["email"],
                    f"Order Confirmed #{order_id} - Ethnic Elegant Hub",
                    build_order_email_html(order_id, items, final_total, address, payment_method),
                )
        except Exception as e:
            print(f"Order email skipped: {e}")

        return redirect(url_for("order_success", order_id=order_id))

    conn.close()
    user = current_user()
    return render_template("checkout.html", items=items, total=total, user=user,
                            discount=discount, coupon=coupon, final_total=final_total)


@app.route("/order-success/<int:order_id>")
@login_required
def order_success(order_id):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, session["user_id"])).fetchone()
    conn.close()
    if not order:
        abort(404)
    return render_template("order_success.html", order=order)


@app.route("/my-orders")
@login_required
def my_orders():
    conn = get_db()
    orders = conn.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC", (session["user_id"],)
    ).fetchall()
    orders_with_items = []
    for o in orders:
        items = conn.execute("SELECT * FROM order_items WHERE order_id=?", (o["id"],)).fetchall()
        return_req = conn.execute(
            "SELECT * FROM return_requests WHERE order_id=? ORDER BY id DESC LIMIT 1", (o["id"],)
        ).fetchone()
        orders_with_items.append({"order": o, "line_items": items, "return_request": return_req})
    conn.close()
    return render_template("orders.html", orders=orders_with_items)


@app.route("/orders/<int:order_id>/return-request", methods=["POST"])
@login_required
def request_return(order_id):
    reason = request.form.get("reason", "").strip()
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, session["user_id"])).fetchone()
    if not order:
        conn.close()
        abort(404)
    if order["status"] != "Delivered":
        flash("Return can only be requested for delivered orders.", "warning")
        conn.close()
        return redirect(url_for("my_orders"))
    existing = conn.execute("SELECT id FROM return_requests WHERE order_id=?", (order_id,)).fetchone()
    if existing:
        flash("A return request already exists for this order.", "warning")
        conn.close()
        return redirect(url_for("my_orders"))
    if not reason:
        flash("Please provide a reason for the return.", "warning")
        conn.close()
        return redirect(url_for("my_orders"))
    conn.execute(
        "INSERT INTO return_requests (order_id, user_id, reason) VALUES (?,?,?)",
        (order_id, session["user_id"], reason),
    )
    conn.commit()
    conn.close()
    flash("Return request submitted. Our team will review it shortly.", "success")
    return redirect(url_for("my_orders"))


# ---------- static pages ----------
@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()
        if name and email and message:
            conn = get_db()
            conn.execute(
                "INSERT INTO contact_messages (name, email, message) VALUES (?,?,?)",
                (name, email, message),
            )
            conn.commit()
            conn.close()
            flash("Thanks for reaching out! We'll get back to you soon.", "success")
            return redirect(url_for("contact"))
        flash("Please fill in all fields.", "warning")
    return render_template("contact.html")


# ---------- admin ----------
@app.route("/admin")
@admin_required
def admin_dashboard():
    from datetime import date, timedelta
    today_start = date.today().isoformat()
    tomorrow_start = (date.today() + timedelta(days=1)).isoformat()

    conn = get_db()
    n_products = conn.execute("SELECT COUNT(*) n FROM products").fetchone()["n"]
    n_orders = conn.execute("SELECT COUNT(*) n FROM orders").fetchone()["n"]
    n_users = conn.execute("SELECT COUNT(*) n FROM users WHERE is_admin=0").fetchone()["n"]
    revenue = conn.execute("SELECT COALESCE(SUM(total_amount),0) r FROM orders WHERE status='Delivered'").fetchone()["r"]
    today_revenue = conn.execute(
        "SELECT COALESCE(SUM(total_amount),0) r FROM orders WHERE status='Delivered' AND delivered_at >= ? AND delivered_at < ?",
        (today_start, tomorrow_start),
    ).fetchone()["r"]
    recent_orders = conn.execute(
        """SELECT orders.*, users.name as customer_name FROM orders
        JOIN users ON users.id = orders.user_id ORDER BY orders.created_at DESC LIMIT 8"""
    ).fetchall()
    conn.close()
    return render_template("admin/dashboard.html", n_products=n_products, n_orders=n_orders,
                            n_users=n_users, revenue=revenue, today_revenue=today_revenue,
                            recent_orders=recent_orders)


@app.route("/admin/analytics")
@admin_required
def admin_analytics():
    conn = get_db()
    best_sellers = conn.execute(
        """SELECT products.id, products.name, products.image, SUM(order_items.quantity) as total_qty
        FROM order_items
        JOIN orders ON orders.id = order_items.order_id
        JOIN products ON products.id = order_items.product_id
        WHERE orders.status <> 'Cancelled'
        GROUP BY products.id, products.name, products.image
        ORDER BY total_qty DESC
        LIMIT 5"""
    ).fetchall()

    delivered = conn.execute(
        "SELECT total_amount, delivered_at, created_at FROM orders WHERE status='Delivered'"
    ).fetchall()
    conn.close()

    monthly = defaultdict(float)
    for o in delivered:
        d = o["delivered_at"] or o["created_at"]
        if isinstance(d, str):
            try:
                d = datetime.strptime(d.split(".")[0], "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
        sort_key = d.strftime("%Y-%m")
        label = d.strftime("%b %Y")
        monthly[(sort_key, label)] += o["total_amount"]

    sorted_months = sorted(monthly.items(), key=lambda x: x[0][0])[-6:]
    month_labels = [m[0][1] for m in sorted_months]
    month_values = [round(m[1], 2) for m in sorted_months]

    return render_template("admin/analytics.html", best_sellers=best_sellers,
                            month_labels=month_labels, month_values=month_values)


@app.route("/admin/products")
@admin_required
def admin_products():
    conn = get_db()
    products = conn.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("admin/products.html", products=products)


@app.route("/admin/products/new", methods=["GET", "POST"])
@admin_required
def admin_product_new():
    if request.method == "POST":
        _save_product(None)
        return redirect(url_for("admin_products"))
    return render_template("admin/product_form.html", p=None, categories=CATEGORIES)


@app.route("/admin/products/<int:pid>/edit", methods=["GET", "POST"])
@admin_required
def admin_product_edit(pid):
    conn = get_db()
    p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not p:
        abort(404)
    if request.method == "POST":
        _save_product(pid)
        return redirect(url_for("admin_products"))
    return render_template("admin/product_form.html", p=p, categories=CATEGORIES)


def _save_product(pid):
    form = request.form
    image_name = form.get("existing_image", "")
    file = request.files.get("image_file")
    if file and file.filename:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        image_name = filename

    data = (
        form["name"], form.get("description", ""), form["category"],
        float(form["price"]), float(form["mrp"]), image_name,
        form.get("color", ""), form.get("fabric", ""),
        1 if form.get("is_featured") == "on" else 0,
        int(form.get("stock", 50)), form.get("sizes", "S,M,L,XL"),
    )
    conn = get_db()
    if pid:
        conn.execute(
            """UPDATE products SET name=?, description=?, category=?, price=?, mrp=?, image=?,
            color=?, fabric=?, is_featured=?, stock=?, sizes=? WHERE id=?""",
            data + (pid,),
        )
    else:
        conn.execute(
            """INSERT INTO products (name, description, category, price, mrp, image, color, fabric,
            is_featured, stock, sizes) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            data,
        )
    conn.commit()
    conn.close()


@app.route("/admin/products/<int:pid>/delete", methods=["POST"])
@admin_required
def admin_product_delete(pid):
    conn = get_db()
    conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash("Product deleted.", "info")
    return redirect(url_for("admin_products"))


@app.route("/admin/orders")
@admin_required
def admin_orders():
    conn = get_db()
    orders = conn.execute(
        """SELECT orders.*, users.name as customer_name, users.phone as customer_phone
        FROM orders JOIN users ON users.id = orders.user_id ORDER BY orders.created_at DESC"""
    ).fetchall()
    orders_with_items = []
    for o in orders:
        items = conn.execute("SELECT * FROM order_items WHERE order_id=?", (o["id"],)).fetchall()
        orders_with_items.append({"order": o, "line_items": items})
    conn.close()
    return render_template("admin/orders.html", orders=orders_with_items)


@app.route("/admin/orders/<int:oid>/status", methods=["POST"])
@admin_required
def admin_order_status(oid):
    status = request.form["status"]
    conn = get_db()
    if status == "Delivered":
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE orders SET status=?, delivered_at=? WHERE id=? AND delivered_at IS NULL",
            (status, now_str, oid),
        )
        conn.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    else:
        conn.execute("UPDATE orders SET status=?, delivered_at=NULL WHERE id=?", (status, oid))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_orders"))


@app.route("/admin/coupons")
@admin_required
def admin_coupons():
    conn = get_db()
    coupons = conn.execute("SELECT * FROM coupons ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("admin/coupons.html", coupons=coupons)


@app.route("/admin/coupons/new", methods=["POST"])
@admin_required
def admin_coupon_new():
    code = request.form["code"].strip().upper()
    discount = float(request.form["discount_percent"])
    min_amount = float(request.form.get("min_order_amount") or 0)
    conn = get_db()
    existing = conn.execute("SELECT id FROM coupons WHERE code=?", (code,)).fetchone()
    if existing:
        flash("A coupon with this code already exists.", "danger")
    else:
        conn.execute(
            "INSERT INTO coupons (code, discount_percent, min_order_amount) VALUES (?,?,?)",
            (code, discount, min_amount),
        )
        conn.commit()
        flash("Coupon created.", "success")
    conn.close()
    return redirect(url_for("admin_coupons"))


@app.route("/admin/coupons/<int:cid>/toggle", methods=["POST"])
@admin_required
def admin_coupon_toggle(cid):
    conn = get_db()
    c = conn.execute("SELECT active FROM coupons WHERE id=?", (cid,)).fetchone()
    if c:
        new_active = 0 if c["active"] else 1
        conn.execute("UPDATE coupons SET active=? WHERE id=?", (new_active, cid))
        conn.commit()
    conn.close()
    return redirect(url_for("admin_coupons"))


@app.route("/admin/coupons/<int:cid>/delete", methods=["POST"])
@admin_required
def admin_coupon_delete(cid):
    conn = get_db()
    conn.execute("DELETE FROM coupons WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    flash("Coupon deleted.", "info")
    return redirect(url_for("admin_coupons"))


@app.route("/admin/returns")
@admin_required
def admin_returns():
    conn = get_db()
    returns = conn.execute(
        """SELECT return_requests.*, users.name as customer_name, orders.total_amount
        FROM return_requests
        JOIN users ON users.id = return_requests.user_id
        JOIN orders ON orders.id = return_requests.order_id
        ORDER BY return_requests.created_at DESC"""
    ).fetchall()
    conn.close()
    return render_template("admin/returns.html", returns=returns)


@app.route("/admin/returns/<int:rid>/status", methods=["POST"])
@admin_required
def admin_return_status(rid):
    status = request.form["status"]
    conn = get_db()
    conn.execute("UPDATE return_requests SET status=? WHERE id=?", (status, rid))
    conn.commit()
    conn.close()
    flash("Return request updated.", "success")
    return redirect(url_for("admin_returns"))


@app.route("/admin/messages")
@admin_required
def admin_messages():
    conn = get_db()
    messages = conn.execute("SELECT * FROM contact_messages ORDER BY created_at DESC").fetchall()
    conn.execute("UPDATE contact_messages SET is_read=1")
    conn.commit()
    conn.close()
    return render_template("admin/messages.html", messages=messages)


@app.route("/sw.js")
def service_worker():
    resp = app.send_static_file("sw.js")
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)
