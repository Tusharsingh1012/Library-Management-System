"""Library Management System - Flask backend with SQLite.

Run:  python app.py   ->  opens http://127.0.0.1:5000
Tables: books, members, loans (a loan links one book to one member).
"""
import os
import re
import sqlite3
from datetime import date, timedelta

from flask import Flask, g, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOAN_DAYS = 14
CATEGORIES = ["Fiction", "Non-fiction", "Science", "Technology", "History",
              "Biography", "Fantasy", "Children", "Other"]

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["DATABASE"] = os.path.join(BASE_DIR, "library.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS books (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    author     TEXT NOT NULL,
    isbn       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    category   TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS loans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    member_id   INTEGER NOT NULL REFERENCES members(id),
    issued_on   TEXT NOT NULL,
    due_on      TEXT NOT NULL,
    returned_on TEXT
);
-- A book can have only ONE open (not yet returned) loan at a time.
CREATE UNIQUE INDEX IF NOT EXISTS one_open_loan ON loans(book_id) WHERE returned_on IS NULL;
"""

BOOK_SELECT = """
SELECT b.id, b.title, b.author, b.isbn, b.category,
       l.member_id, l.issued_on, l.due_on, m.name AS issued_to
FROM books b
LEFT JOIN loans   l ON l.book_id = b.id AND l.returned_on IS NULL
LEFT JOIN members m ON m.id = l.member_id
"""


# ---------- database helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(app.config["DATABASE"]) as conn:
        conn.executescript(SCHEMA)


def book_dict(r):
    issued = r["member_id"] is not None
    return {
        "id": r["id"], "title": r["title"], "author": r["author"], "isbn": r["isbn"],
        "category": r["category"], "status": "Issued" if issued else "Available",
        "issued_to": r["issued_to"], "member_id": r["member_id"],
        "issued_on": r["issued_on"], "due_on": r["due_on"],
    }


def member_dict(r):
    return {"id": r["id"], "name": r["name"], "email": r["email"],
            "code": f"LIB-{r['id']:04d}", "borrowed": r["borrowed"]}


def error(message, status=400, fields=None):
    body = {"error": message}
    if fields:
        body["fields"] = fields
    return jsonify(body), status


# ---------- validation ----------
NAME_RE = re.compile(r"[^\W\d_](?:[^\W\d_]|[ .'\-])*")
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def norm_isbn(value):
    return re.sub(r"[\s-]", "", str(value)).upper()


def validate_book(data):
    if not isinstance(data, dict):
        return None, {"title": "Request body must be JSON."}
    e = {}
    title = str(data.get("title", "")).strip()
    author = str(data.get("author", "")).strip()
    isbn = norm_isbn(data.get("isbn", ""))
    category = str(data.get("category", "")).strip()
    if not title:
        e["title"] = "Enter the book title."
    elif len(title) > 120:
        e["title"] = "Title is too long (max 120 characters)."
    if len(author) < 2 or re.search(r"\d", author):
        e["author"] = "Author name must be at least 2 letters, with no digits."
    if not re.fullmatch(r"\d{9}[\dX]|\d{13}", isbn):
        e["isbn"] = "ISBN must be 10 or 13 digits (hyphens allowed)."
    if category not in CATEGORIES:
        e["category"] = "Choose a category."
    if e:
        return None, e
    return {"title": title, "author": author, "isbn": isbn, "category": category}, {}


def validate_member(data):
    if not isinstance(data, dict):
        return None, {"name": "Request body must be JSON."}
    e = {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip()
    if len(name) < 2 or not NAME_RE.fullmatch(name):
        e["name"] = "Enter the full name using letters, spaces and . ' - only."
    if not EMAIL_RE.fullmatch(email):
        e["email"] = "Enter a valid email address."
    if e:
        return None, e
    return {"name": name, "email": email}, {}


# ---------- pages ----------
@app.after_request
def add_cors_headers(resp):
    if request.path.startswith("/api/"):
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return resp


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


# ---------- books ----------
@app.route("/api/books", methods=["GET"])
def list_books():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip().lower()
    sql, params, where = BOOK_SELECT, [], []
    if q:
        where.append("(b.title LIKE ? OR b.author LIKE ? OR b.isbn LIKE ?)")
        like = f"%{q}%"
        params += [like, like, like.replace("-", "")]
    if status == "available":
        where.append("l.id IS NULL")
    elif status == "issued":
        where.append("l.id IS NOT NULL")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY b.id DESC"
    rows = get_db().execute(sql, params).fetchall()
    return jsonify([book_dict(r) for r in rows])


def fetch_book(db, book_id):
    return db.execute(BOOK_SELECT + " WHERE b.id = ?", (book_id,)).fetchone()


@app.route("/api/books", methods=["POST"])
def add_book():
    clean, errors = validate_book(request.get_json(silent=True))
    if errors:
        return error("Please fix the highlighted fields.", 400, errors)
    db = get_db()
    try:
        cur = db.execute("INSERT INTO books (title, author, isbn, category) VALUES (?,?,?,?)",
                         (clean["title"], clean["author"], clean["isbn"], clean["category"]))
        db.commit()
    except sqlite3.IntegrityError:
        return error("A book with this ISBN already exists.", 409,
                     {"isbn": "This ISBN is already in the library."})
    return jsonify(book_dict(fetch_book(db, cur.lastrowid))), 201


@app.route("/api/books/<int:book_id>", methods=["DELETE"])
def delete_book(book_id):
    db = get_db()
    book = fetch_book(db, book_id)
    if book is None:
        return error("Book not found.", 404)
    if book["member_id"] is not None:
        return error("This book is currently issued. Return it before deleting.", 409)
    db.execute("DELETE FROM loans WHERE book_id = ?", (book_id,))
    db.execute("DELETE FROM books WHERE id = ?", (book_id,))
    db.commit()
    return jsonify({"message": "Book deleted."})


@app.route("/api/books/<int:book_id>/issue", methods=["POST"])
def issue_book(book_id):
    data = request.get_json(silent=True) or {}
    try:
        member_id = int(data.get("member_id"))
    except (TypeError, ValueError):
        return error("Choose a member to issue the book to.", 400, {"member_id": "Choose a member."})
    db = get_db()
    book = fetch_book(db, book_id)
    if book is None:
        return error("Book not found.", 404)
    if db.execute("SELECT 1 FROM members WHERE id = ?", (member_id,)).fetchone() is None:
        return error("Member not found.", 404)
    if book["member_id"] is not None:
        return error(f"\u201c{book['title']}\u201d is already issued and not available.", 409)
    today = date.today()
    try:
        db.execute("INSERT INTO loans (book_id, member_id, issued_on, due_on) VALUES (?,?,?,?)",
                   (book_id, member_id, today.isoformat(), (today + timedelta(days=LOAN_DAYS)).isoformat()))
        db.commit()
    except sqlite3.IntegrityError:
        return error("This book is already issued and not available.", 409)
    return jsonify(book_dict(fetch_book(db, book_id)))


@app.route("/api/books/<int:book_id>/return", methods=["POST"])
def return_book(book_id):
    db = get_db()
    book = fetch_book(db, book_id)
    if book is None:
        return error("Book not found.", 404)
    if book["member_id"] is None:
        return error("This book is not currently issued, so it cannot be returned.", 409)
    db.execute("UPDATE loans SET returned_on = ? WHERE book_id = ? AND returned_on IS NULL",
               (date.today().isoformat(), book_id))
    db.commit()
    return jsonify(book_dict(fetch_book(db, book_id)))


# ---------- members ----------
MEMBER_SELECT = """
SELECT m.id, m.name, m.email,
       (SELECT COUNT(*) FROM loans l WHERE l.member_id = m.id AND l.returned_on IS NULL) AS borrowed
FROM members m
"""


@app.route("/api/members", methods=["GET"])
def list_members():
    rows = get_db().execute(MEMBER_SELECT + " ORDER BY m.name COLLATE NOCASE").fetchall()
    return jsonify([member_dict(r) for r in rows])


@app.route("/api/members", methods=["POST"])
def add_member():
    clean, errors = validate_member(request.get_json(silent=True))
    if errors:
        return error("Please fix the highlighted fields.", 400, errors)
    db = get_db()
    try:
        cur = db.execute("INSERT INTO members (name, email) VALUES (?,?)", (clean["name"], clean["email"]))
        db.commit()
    except sqlite3.IntegrityError:
        return error("A member with this email already exists.", 409,
                     {"email": "This email is already registered."})
    row = db.execute(MEMBER_SELECT + " WHERE m.id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(member_dict(row)), 201


# ---------- stats ----------
@app.route("/api/stats", methods=["GET"])
def stats():
    db = get_db()
    books = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    issued = db.execute("SELECT COUNT(*) FROM loans WHERE returned_on IS NULL").fetchone()[0]
    members = db.execute("SELECT COUNT(*) FROM members").fetchone()[0]
    return jsonify({"books": books, "issued": issued, "available": books - issued, "members": members})


init_db()


def find_free_port(start=5000, tries=20):
    import socket
    for port in range(start, start + tries):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


if __name__ == "__main__":
    import threading
    import webbrowser

    port = int(os.environ.get("PORT", find_free_port(5000)))
    url = f"http://127.0.0.1:{port}"
    print("\n" + "=" * 56)
    print("  Library Management System is running")
    print(f"  Open this address in your browser:  {url}")
    print("  Keep this window open. Press Ctrl+C to stop.")
    print("=" * 56 + "\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, debug=False)
