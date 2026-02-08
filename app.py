from __future__ import annotations

import io
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, send_file
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database" / "billing.db"

app = Flask(__name__)


def get_db_connection() -> sqlite3.Connection:
    """Create a SQLite connection with row dictionaries enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize all required tables for the billing system."""
    with get_db_connection() as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL CHECK(price >= 0),
                stock INTEGER NOT NULL CHECK(stock >= 0),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                client_id INTEGER,
                payment_method TEXT NOT NULL,
                subtotal REAL NOT NULL,
                itbis REAL NOT NULL,
                total REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                price REAL NOT NULL,
                line_total REAL NOT NULL,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
            """
        )


def current_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def generate_invoice_number(conn: sqlite3.Connection) -> str:
    """Generate incremental invoice number in format FAC-000001."""
    row = conn.execute("SELECT COUNT(*) AS total FROM invoices").fetchone()
    next_number = (row["total"] or 0) + 1
    return f"FAC-{next_number:06d}"


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/api/clients", methods=["GET", "POST"])
def clients_collection():
    if request.method == "POST":
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "El nombre del cliente es obligatorio."}), 400

        with get_db_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO clients(name, email, phone, address, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    name,
                    data.get("email", "").strip(),
                    data.get("phone", "").strip(),
                    data.get("address", "").strip(),
                    current_timestamp(),
                ),
            )
            conn.commit()
            new_id = cursor.lastrowid
            row = conn.execute("SELECT * FROM clients WHERE id = ?", (new_id,)).fetchone()
            return jsonify(dict(row)), 201

    search = request.args.get("search", "").strip()
    query = "SELECT * FROM clients"
    params: list[Any] = []
    if search:
        query += " WHERE name LIKE ? OR email LIKE ? OR phone LIKE ?"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])

    query += " ORDER BY id DESC"
    with get_db_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/clients/<int:client_id>", methods=["PUT", "DELETE"])
def client_detail(client_id: int):
    with get_db_connection() as conn:
        existing = conn.execute("SELECT id FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not existing:
            return jsonify({"error": "Cliente no encontrado."}), 404

        if request.method == "DELETE":
            conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
            conn.commit()
            return jsonify({"message": "Cliente eliminado."})

        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "El nombre del cliente es obligatorio."}), 400

        conn.execute(
            """
            UPDATE clients
            SET name = ?, email = ?, phone = ?, address = ?
            WHERE id = ?
            """,
            (
                name,
                data.get("email", "").strip(),
                data.get("phone", "").strip(),
                data.get("address", "").strip(),
                client_id,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        return jsonify(dict(row))


@app.route("/api/products", methods=["GET", "POST"])
def products_collection():
    if request.method == "POST":
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "El nombre del producto es obligatorio."}), 400

        try:
            price = float(data.get("price", 0))
            stock = int(data.get("stock", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "Precio o stock inválido."}), 400

        if price < 0 or stock < 0:
            return jsonify({"error": "Precio y stock deben ser positivos."}), 400

        with get_db_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO products(name, price, stock, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (name, price, stock, current_timestamp()),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM products WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return jsonify(dict(row)), 201

    search = request.args.get("search", "").strip()
    query = "SELECT * FROM products"
    params: list[Any] = []
    if search:
        query += " WHERE name LIKE ?"
        params.append(f"%{search}%")
    query += " ORDER BY id DESC"

    with get_db_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/products/<int:product_id>", methods=["PUT", "DELETE"])
def product_detail(product_id: int):
    with get_db_connection() as conn:
        existing = conn.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
        if not existing:
            return jsonify({"error": "Producto no encontrado."}), 404

        if request.method == "DELETE":
            conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
            conn.commit()
            return jsonify({"message": "Producto eliminado."})

        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "El nombre del producto es obligatorio."}), 400

        try:
            price = float(data.get("price", 0))
            stock = int(data.get("stock", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "Precio o stock inválido."}), 400

        if price < 0 or stock < 0:
            return jsonify({"error": "Precio y stock deben ser positivos."}), 400

        conn.execute(
            "UPDATE products SET name = ?, price = ?, stock = ? WHERE id = ?",
            (name, price, stock, product_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return jsonify(dict(row))


@app.route("/api/invoices", methods=["GET", "POST"])
def invoices_collection():
    if request.method == "POST":
        payload = request.get_json() or {}
        client_id = payload.get("client_id")
        payment_method = payload.get("payment_method", "").strip()
        items = payload.get("items", [])

        if payment_method not in {"Efectivo", "Transferencia", "Tarjeta"}:
            return jsonify({"error": "Método de pago inválido."}), 400

        if not isinstance(items, list) or not items:
            return jsonify({"error": "Debe incluir al menos un producto."}), 400

        with get_db_connection() as conn:
            try:
                subtotal = 0.0
                normalized_items = []

                for item in items:
                    product_id = int(item.get("product_id"))
                    quantity = int(item.get("quantity"))
                    if quantity <= 0:
                        raise ValueError("Cantidad inválida")

                    product = conn.execute(
                        "SELECT id, name, price, stock FROM products WHERE id = ?", (product_id,)
                    ).fetchone()
                    if not product:
                        return jsonify({"error": f"Producto {product_id} no existe."}), 400
                    if product["stock"] < quantity:
                        return (
                            jsonify({"error": f"Stock insuficiente para {product['name']}."}),
                            400,
                        )

                    line_total = float(product["price"]) * quantity
                    subtotal += line_total
                    normalized_items.append(
                        {
                            "product_id": product_id,
                            "quantity": quantity,
                            "price": float(product["price"]),
                            "line_total": line_total,
                            "name": product["name"],
                        }
                    )

                itbis = round(subtotal * 0.18, 2)
                total = round(subtotal + itbis, 2)
                subtotal = round(subtotal, 2)
                invoice_number = generate_invoice_number(conn)

                cursor = conn.execute(
                    """
                    INSERT INTO invoices(invoice_number, client_id, payment_method, subtotal, itbis, total, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        invoice_number,
                        client_id if client_id else None,
                        payment_method,
                        subtotal,
                        itbis,
                        total,
                        current_timestamp(),
                    ),
                )
                invoice_id = cursor.lastrowid

                for item in normalized_items:
                    conn.execute(
                        """
                        INSERT INTO invoice_items(invoice_id, product_id, quantity, price, line_total)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            invoice_id,
                            item["product_id"],
                            item["quantity"],
                            item["price"],
                            item["line_total"],
                        ),
                    )
                    conn.execute(
                        "UPDATE products SET stock = stock - ? WHERE id = ?",
                        (item["quantity"], item["product_id"]),
                    )

                conn.commit()
                row = conn.execute(
                    """
                    SELECT invoices.*, clients.name AS client_name
                    FROM invoices
                    LEFT JOIN clients ON clients.id = invoices.client_id
                    WHERE invoices.id = ?
                    """,
                    (invoice_id,),
                ).fetchone()
                return jsonify(dict(row)), 201
            except ValueError:
                return jsonify({"error": "Items de factura inválidos."}), 400

    date_filter = request.args.get("date", "").strip()
    client_filter = request.args.get("client", "").strip()

    query = """
        SELECT invoices.*, clients.name AS client_name
        FROM invoices
        LEFT JOIN clients ON clients.id = invoices.client_id
    """
    conditions = []
    params: list[Any] = []
    if date_filter:
        conditions.append("DATE(invoices.created_at) = DATE(?)")
        params.append(date_filter)
    if client_filter:
        conditions.append("clients.name LIKE ?")
        params.append(f"%{client_filter}%")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY invoices.id DESC"

    with get_db_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/invoices/<int:invoice_id>", methods=["GET"])
def invoice_detail(invoice_id: int):
    with get_db_connection() as conn:
        invoice = conn.execute(
            """
            SELECT invoices.*, clients.name AS client_name, clients.email AS client_email,
                   clients.phone AS client_phone, clients.address AS client_address
            FROM invoices
            LEFT JOIN clients ON clients.id = invoices.client_id
            WHERE invoices.id = ?
            """,
            (invoice_id,),
        ).fetchone()

        if not invoice:
            return jsonify({"error": "Factura no encontrada."}), 404

        items = conn.execute(
            """
            SELECT invoice_items.*, products.name AS product_name
            FROM invoice_items
            JOIN products ON products.id = invoice_items.product_id
            WHERE invoice_items.invoice_id = ?
            """,
            (invoice_id,),
        ).fetchall()

    return jsonify({"invoice": dict(invoice), "items": [dict(i) for i in items]})


@app.route("/api/invoices/<int:invoice_id>/pdf", methods=["GET"])
def invoice_pdf(invoice_id: int):
    with get_db_connection() as conn:
        invoice = conn.execute(
            """
            SELECT invoices.*, clients.name AS client_name
            FROM invoices
            LEFT JOIN clients ON clients.id = invoices.client_id
            WHERE invoices.id = ?
            """,
            (invoice_id,),
        ).fetchone()

        if not invoice:
            return jsonify({"error": "Factura no encontrada."}), 404

        items = conn.execute(
            """
            SELECT invoice_items.*, products.name AS product_name
            FROM invoice_items
            JOIN products ON products.id = invoice_items.product_id
            WHERE invoice_items.invoice_id = ?
            """,
            (invoice_id,),
        ).fetchall()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle(f"Factura-{invoice['invoice_number']}")

    y = 760
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Comprobante de Factura")
    y -= 30

    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, y, f"Factura: {invoice['invoice_number']}")
    y -= 18
    pdf.drawString(50, y, f"Fecha: {invoice['created_at']}")
    y -= 18
    pdf.drawString(50, y, f"Cliente: {invoice['client_name'] or 'Consumidor final'}")
    y -= 18
    pdf.drawString(50, y, f"Método de pago: {invoice['payment_method']}")
    y -= 28

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Producto")
    pdf.drawString(280, y, "Cant.")
    pdf.drawString(350, y, "Precio")
    pdf.drawString(440, y, "Total")
    y -= 16
    pdf.line(50, y, 540, y)
    y -= 14

    pdf.setFont("Helvetica", 10)
    for item in items:
        pdf.drawString(50, y, item["product_name"][:35])
        pdf.drawRightString(310, y, str(item["quantity"]))
        pdf.drawRightString(410, y, f"RD$ {item['price']:.2f}")
        pdf.drawRightString(530, y, f"RD$ {item['line_total']:.2f}")
        y -= 16
        if y < 120:
            pdf.showPage()
            y = 760

    y -= 10
    pdf.line(330, y, 540, y)
    y -= 16
    pdf.drawRightString(480, y, "Subtotal:")
    pdf.drawRightString(540, y, f"RD$ {invoice['subtotal']:.2f}")
    y -= 16
    pdf.drawRightString(480, y, "ITBIS (18%):")
    pdf.drawRightString(540, y, f"RD$ {invoice['itbis']:.2f}")
    y -= 18
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(480, y, "Total:")
    pdf.drawRightString(540, y, f"RD$ {invoice['total']:.2f}")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"factura-{invoice['invoice_number']}.pdf",
    )


if __name__ == "__main__":
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
