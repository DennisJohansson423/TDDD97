import sqlite3
from flask import g
import uuid

DATABASE_URI = "database.db"


def get_db():
    db = getattr(g, "db", None)
    if db is None:
        db = g.db = sqlite3.connect(DATABASE_URI)
    return db


def disconnect_db():
    db = getattr(g, "db", None)
    if db is not None:
        db.close()
        g.db = None


def init_db(app):
    with app.app_context():
        db = get_db()
        with app.open_resource("schema.sql", mode="r") as f:
            db.cursor().executescript(f.read())
        db.commit()


# User functions

def create_user(email, password, firstname, familyname, gender, city, country):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)",
            (email, password, firstname, familyname, gender, city, country),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def get_user_by_email(email):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email=?", (email,))
    return cursor.fetchone()


def get_user_by_token(token):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT users.* FROM users 
        JOIN loggedin_users ON users.email = loggedin_users.email 
        WHERE loggedin_users.token = ?
    """,
        (token,),
    )

    row = cursor.fetchone()
    if row:
        return {
            "email": row[0],
            "firstname": row[2],
            "familyname": row[3],
            "gender": row[4],
            "city": row[5],
            "country": row[6],
        }
    return None


def update_password(email, new_password):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET password = ? WHERE email = ?", (new_password, email)
        )
        conn.commit()
        return True
    except:
        return False


# Token functions

def create_token(email):
    conn = get_db()
    cursor = conn.cursor()
    token = str(uuid.uuid4())
    try:
        # Tillåt bara en aktiv session per användare
        cursor.execute("DELETE FROM loggedin_users WHERE email=?", (email,))
        cursor.execute("INSERT INTO loggedin_users VALUES (?, ?)", (token, email))
        conn.commit()
        return token
    except:
        return None


def delete_token(token):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM loggedin_users WHERE token=?", (token,))
    conn.commit()
    return cursor.rowcount > 0


# Tar bort alla tokens för en viss användare (för att bara tillåta en aktiv session)
def delete_tokens_for_email(email):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM loggedin_users WHERE email=?", (email,))
    conn.commit()
    return cursor.rowcount >= 0


# Message functions

def create_message(sender_email, receiver_email, content):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO messages (sender_email, receiver_email, content) VALUES (?, ?, ?)",
            (sender_email, receiver_email, content),
        )
        conn.commit()
        return True
    except:
        return False


def get_messages(email):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sender_email, content FROM messages WHERE receiver_email=?", (email,)
    )
    rows = cursor.fetchall()

    messages = []
    for row in rows:
        messages.append({"writer": row[0], "content": row[1]})
    return messages
