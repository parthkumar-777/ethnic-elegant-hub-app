import os

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg2
    import psycopg2.extras
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), "eeh.db")


class Cursor:
    """Wraps a DB-API cursor so the same app code works on SQLite and Postgres."""

    def __init__(self, raw_cursor):
        self._cur = raw_cursor
        self._pg_lastrowid = None

    def execute(self, query, params=()):
        if USE_PG:
            q = query.replace("?", "%s")
            stripped = q.strip().upper()
            if stripped.startswith("INSERT") and "RETURNING" not in stripped:
                q = q.rstrip().rstrip(";") + " RETURNING id"
            self._cur.execute(q, params)
            if stripped.startswith("INSERT"):
                try:
                    row = self._cur.fetchone()
                    self._pg_lastrowid = row["id"] if row else None
                except Exception:
                    self._pg_lastrowid = None
        else:
            self._cur.execute(query, params)
        return self

    def executescript(self, script):
        self._cur.execute(script)
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def lastrowid(self):
        if USE_PG:
            return self._pg_lastrowid
        return self._cur.lastrowid


class Conn:
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def _new_cursor(self):
        if USE_PG:
            return self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        return self._conn.cursor()

    def execute(self, query, params=()):
        return Cursor(self._new_cursor()).execute(query, params)

    def executescript(self, script):
        cur = self._new_cursor()
        if USE_PG:
            cur.execute(script)
        else:
            cur.executescript(script)

    def cursor(self):
        return Cursor(self._new_cursor())

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_db():
    if USE_PG:
        raw = psycopg2.connect(DATABASE_URL, sslmode="require")
        return Conn(raw)
    else:
        raw = sqlite3.connect(DB_PATH)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA foreign_keys = ON")
        return Conn(raw)


SCHEMA_SQLITE = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        password_hash TEXT NOT NULL,
        address TEXT,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        mrp REAL NOT NULL,
        rating REAL DEFAULT 4.5,
        rating_count INTEGER DEFAULT 100,
        image TEXT,
        stock INTEGER DEFAULT 50,
        sizes TEXT DEFAULT 'S,M,L,XL',
        color TEXT,
        fabric TEXT,
        is_featured INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        total_amount REAL NOT NULL,
        status TEXT DEFAULT 'Placed',
        address TEXT,
        payment_method TEXT DEFAULT 'COD',
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        size TEXT,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    );

    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        comment TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS wishlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id),
        UNIQUE(user_id, product_id)
    );

    CREATE TABLE IF NOT EXISTS coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        discount_percent REAL NOT NULL,
        min_order_amount REAL DEFAULT 0,
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    );
"""

SCHEMA_PG = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        password_hash TEXT NOT NULL,
        address TEXT,
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        mrp REAL NOT NULL,
        rating REAL DEFAULT 4.5,
        rating_count INTEGER DEFAULT 100,
        image TEXT,
        stock INTEGER DEFAULT 50,
        sizes TEXT DEFAULT 'S,M,L,XL',
        color TEXT,
        fabric TEXT,
        is_featured INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        total_amount REAL NOT NULL,
        status TEXT DEFAULT 'Placed',
        address TEXT,
        payment_method TEXT DEFAULT 'COD',
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES orders(id),
        product_id INTEGER NOT NULL REFERENCES products(id),
        product_name TEXT NOT NULL,
        size TEXT,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS reviews (
        id SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL REFERENCES products(id),
        user_id INTEGER NOT NULL REFERENCES users(id),
        rating INTEGER NOT NULL,
        comment TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS wishlist (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        product_id INTEGER NOT NULL REFERENCES products(id),
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(user_id, product_id)
    );

    CREATE TABLE IF NOT EXISTS coupons (
        id SERIAL PRIMARY KEY,
        code TEXT UNIQUE NOT NULL,
        discount_percent REAL NOT NULL,
        min_order_amount REAL DEFAULT 0,
        active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT NOW()
    );
"""


def _safe_add_column(conn, table, col_sqlite, col_pg):
    try:
        if USE_PG:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_pg}")
        else:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_sqlite}")
        conn.commit()
    except Exception:
        pass


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA_PG if USE_PG else SCHEMA_SQLITE)
    conn.commit()

    # migration: add delivered_at column if it doesn't already exist (tracks when an
    # order's status was actually set to Delivered, so "today's revenue" reflects the
    # delivery date rather than the order's original placement date)
    _safe_add_column(conn, "orders", "delivered_at TEXT", "delivered_at TIMESTAMP")
    # migration: coupon tracking on orders
    _safe_add_column(conn, "orders", "coupon_code TEXT", "coupon_code TEXT")
    _safe_add_column(conn, "orders", "discount_amount REAL DEFAULT 0", "discount_amount REAL DEFAULT 0")

    admin = conn.execute("SELECT * FROM users WHERE is_admin=1").fetchone()
    if not admin:
        from werkzeug.security import generate_password_hash
        conn.execute(
            "INSERT INTO users (name, email, phone, password_hash, is_admin) VALUES (?,?,?,?,1)",
            ("Admin", "admin@ethnicelegant.com", "9999999999",
             generate_password_hash("Admin@123")),
        )
        conn.commit()
    conn.close()
