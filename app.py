import os
from datetime import datetime
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                    session, flash, jsonify, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from db import get_db, init_db

app = Flask(__name__)
app.secret_key = "eeh-dev-secret-change-in-production-please"
UPLOAD_FOLDER = os.path.join(app.static_folder, "products")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

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
    conn = get_db()
    products = conn.execute(
        "SELECT * FROM products WHERE name LIKE ? OR category LIKE ? OR fabric LIKE ?",
        (f"%{q}%", f"%{q}%", f"%{q}%"),
    ).fetchall()
    conn.close()
    return render_template("category.html", products=products, category=f'Results for "{q}"', sort="")


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
    conn.close()
    return render_template("product.html", p=product, related=related)


@app.route("/categories")
def categories_page():
    return render_template("categories.html")


@app.route("/account")
@login_required
def account():
    return render_template("account.html")


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
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/add/<int:pid>", methods=["POST"])
def add_to_cart(pid):
    size = request.form.get("size", "M")
    qty = int(request.form.get("qty", 1))
    action = request.form.get("action", "cart")
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

    if request.method == "POST":
        address = request.form["address"]
        payment_method = request.form.get("payment_method", "COD")
        cur = conn.execute(
            "INSERT INTO orders (user_id, total_amount, address, payment_method) VALUES (?,?,?,?)",
            (session["user_id"], total, address, payment_method),
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
        session.modified = True
        return redirect(url_for("order_success", order_id=order_id))

    conn.close()
    user = current_user()
    return render_template("checkout.html", items=items, total=total, user=user)


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
        orders_with_items.append({"order": o, "line_items": items})
    conn.close()
    return render_template("orders.html", orders=orders_with_items)


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


@app.route("/sw.js")
def service_worker():
    resp = app.send_static_file("sw.js")
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)
