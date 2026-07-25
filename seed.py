import json, os
from db import get_db, init_db

def seed():
    init_db()
    conn = get_db()
    c = conn.cursor()
    existing = c.execute("SELECT COUNT(*) as n FROM products").fetchone()["n"]
    if existing > 0:
        print(f"Products already seeded ({existing}). Skipping.")
        conn.close()
        return
    with open(os.path.join(os.path.dirname(__file__), "products_data.json")) as f:
        products = json.load(f)
    for p in products:
        c.execute(
            """INSERT INTO products
            (name, description, category, price, mrp, image, color, fabric, is_featured, rating, rating_count, stock)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                p["name"], p.get("description", ""), p["category"], p["price"], p["mrp"],
                p["image"], p.get("color", ""), p.get("fabric", ""), p.get("featured", 0),
                round(3.9 + (hash(p["name"]) % 11) / 10, 1), 50 + (hash(p["name"]) % 900), 100,
            ),
        )
    conn.commit()
    conn.close()
    print(f"Seeded {len(products)} products.")

if __name__ == "__main__":
    seed()
