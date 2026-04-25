from flask import Flask, render_template, request, redirect, session
import sqlite3, os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, join_room, emit

app = Flask(__name__)
app.secret_key = "secret"

socketio = SocketIO(app)

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ===== DB =====
def init_db():
    conn = sqlite3.connect("db.sqlite3")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        lat REAL,
        lng REAL,
        image TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad_id INTEGER,
        sender TEXT,
        text TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()


# ===== HOME =====
@app.route("/", methods=["GET","POST"])
def index():
    conn = sqlite3.connect("db.sqlite3")
    c = conn.cursor()

    if request.method == "POST":
        title = request.form["title"]
        desc = request.form["description"]

        file = request.files["image"]
        filename = ""

        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        c.execute("INSERT INTO ads (title, description, image) VALUES (?, ?, ?)",
                  (title, desc, filename))
        conn.commit()

    ads = c.execute("SELECT * FROM ads").fetchall()
    conn.close()

    return render_template("index.html", ads=ads)


# ===== AD PAGE =====
@app.route("/ad/<int:id>")
def ad_page(id):
    conn = sqlite3.connect("db.sqlite3")
    c = conn.cursor()
    ad = c.execute("SELECT * FROM ads WHERE id=?", (id,)).fetchone()
    conn.close()
    return render_template("ad.html", ad=ad)


# ===== AUTH =====
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        conn = sqlite3.connect("db.sqlite3")
        c = conn.cursor()
        c.execute("INSERT INTO users (username,password) VALUES (?,?)",(username,password))
        conn.commit()
        conn.close()

        return redirect("/login")
    return render_template("register.html")


@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("db.sqlite3")
        c = conn.cursor()
        user = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            return redirect("/")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ===== CHAT =====
@socketio.on("join")
def join(data):
    join_room(str(data["ad_id"]))

@socketio.on("send_message")
def send_msg(data):
    conn = sqlite3.connect("db.sqlite3")
    c = conn.cursor()

    c.execute("INSERT INTO messages (ad_id, sender, text) VALUES (?, ?, ?)",
              (data["ad_id"], data["sender"], data["text"]))

    conn.commit()
    conn.close()

    emit("receive_message", data, room=str(data["ad_id"]))


@app.route("/messages/<int:ad_id>")
def get_messages(ad_id):
    conn = sqlite3.connect("db.sqlite3")
    c = conn.cursor()
    msgs = c.execute("SELECT sender,text FROM messages WHERE ad_id=?", (ad_id,)).fetchall()
    conn.close()
    return {"messages": msgs}


# ===== RUN =====
if __name__ == "__main__":
    socketio.run(app, debug=True)
