# Library Management System

A full-stack web app to add, search, issue, return and delete books.

**Stack:** HTML + CSS + JavaScript (Fetch API) · Python Flask (REST API) · SQLite · Node.js (optional tooling: Prettier/ESLint)

## Features
- Add books (Title, Author, ISBN, Category) with availability status
- Add members and issue a book to a member (14-day loan), return it, or delete it
- Validation: unique ISBN, valid ISBN-10/13, a book cannot be issued if already issued,
  cannot return a book that is not issued, cannot delete an issued book
- Live search by title / author / ISBN and filter by status, without page reload
- Edge cases handled: searching a non-existent book, returning a book not issued
- Works with no setup (browser mode) and switches to Flask + SQLite automatically when the server runs

## Run
```bash
pip install -r requirements.txt
python app.py
```
The browser opens at http://127.0.0.1:5000. On Windows you can double-click `run.bat`.
Opening `index.html` directly also works (browser mode, data stored in the browser).

## Database (SQLite)
- `books(id, title, author, isbn UNIQUE, category)`
- `members(id, name, email UNIQUE)`
- `loans(id, book_id -> books, member_id -> members, issued_on, due_on, returned_on)`
  with a unique index so a book can have only one open loan.

## API
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/books?q=&status=` | List / search books |
| POST | `/api/books` | Add a book |
| DELETE | `/api/books/<id>` | Delete a book |
| POST | `/api/books/<id>/issue` | Issue to a member `{member_id}` |
| POST | `/api/books/<id>/return` | Return a book |
| GET / POST | `/api/members` | List / add members |
| GET | `/api/stats` | Counts |

## Tests
```bash
pip install pytest
python -m pytest -q
```
