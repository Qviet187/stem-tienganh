import http.server
import socketserver
import sqlite3
import urllib.parse
from datetime import date, datetime, timedelta
import random
import webbrowser
import os
import json

from sound_manager import SoundManager

PORT = 80

def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            streak INTEGER,
            last_active TEXT,
            safe_mode INTEGER DEFAULT 0,
            theme TEXT DEFAULT 'dark',
            xp INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_words (
            username TEXT,
            word TEXT,
            meaning TEXT,
            pronunciation TEXT,
            example TEXT,
            UNIQUE(username, word)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_vocab (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit TEXT,
            word TEXT,
            type TEXT,
            pronunciation TEXT,
            meaning TEXT,
            example TEXT
        )
    ''')
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN xp INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass 
    conn.commit()
    conn.close()

init_db()

def load_vocab_pool():
    vocab_list = []
    try:
        with open("word_2.json", "r", encoding="utf-8") as f:
            vocab_list = json.load(f)
    except Exception as e:
        print("❌ Lỗi đọc file word_2.json:", e)
        vocab_list = [
            {"id": 1, "unit": "Unit 1", "word": "antibiotic", "type": "n", "pronunciation": "/ˌæntibaɪˈɒtɪk/", "meaning": "thuốc kháng sinh", "example": "The doctor prescribed an antibiotic for her throat infection."}
        ]
    
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, unit, word, type, pronunciation, meaning, example FROM custom_vocab")
        rows = cursor.fetchall()
        conn.close()
        for r in rows:
            vocab_list.append({
                "id": r[0] + 1000,
                "unit": r[1],
                "word": r[2],
                "type": r[3],
                "pronunciation": r[4],
                "meaning": r[5],
                "example": r[6]
            })
    except Exception as e:
        print("Lỗi tải custom vocab:", e)

    return vocab_list

VOCAB_LIST = load_vocab_pool()

SENTENCE_LIST = []
for item in VOCAB_LIST:
    if item.get("example"):
        SENTENCE_LIST.append({
            "id": item.get("id"),
            "english": item.get("example"),
            "vietnamese": f"Ví dụ cho từ: {item.get('word')} ({item.get('meaning')})"
        })

print(f"✨ Đã tải tổng cộng {len(VOCAB_LIST)} từ vựng và {len(SENTENCE_LIST)} câu luyện tập với giao diện Glassmorphism mới!")

class EnglishAppHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/static/') or self.path.startswith('/assets/'):
            return super().do_GET()

        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        cookies = self.parse_cookies()
        username = cookies.get("session_user")

        if path == "/":
            if not username:
                self.send_html(self.get_login_page())
            else:
                self.send_html(self.get_dashboard_page(username))
        elif path == "/register":
            self.send_html(self.get_register_page())
        elif path == "/practice":
            if not username:
                self.redirect("/")
            else:
                global VOCAB_LIST
                VOCAB_LIST = load_vocab_pool()
                self.send_html(self.get_practice_page(username))
        elif path == "/flashcards":
            if not username:
                self.redirect("/")
            else:
                VOCAB_LIST = load_vocab_pool()
                self.send_html(self.get_flashcard_page(username))
        elif path == "/notebook":
            if not username:
                self.redirect("/")
            else:
                self.send_html(self.get_notebook_page(username))
        elif path == "/sentence_practice":
            if not username:
                self.redirect("/")
            else:
                global SENTENCE_LIST
                VOCAB_LIST = load_vocab_pool()
                SENTENCE_LIST = [{"id": i.get("id"), "english": i.get("example"), "vietnamese": f"Ví dụ cho từ: {i.get('word')} ({i.get('meaning')})"} for i in VOCAB_LIST if i.get("example")]
                self.send_html(self.get_sentence_practice_page(username))
        elif path == "/quiz":
            if not username:
                self.redirect("/")
            else:
                VOCAB_LIST = load_vocab_pool()
                self.send_html(self.get_quiz_page(username))
        elif path == "/admin_vocab":
            if not username:
                self.redirect("/")
            else:
                self.send_html(self.get_admin_vocab_page(username))
        elif path == "/leaderboard":
            if not username:
                self.redirect("/")
            else:
                self.send_html(self.get_leaderboard_page(username))
        elif path == "/logout":
            self.send_response(303)
            self.send_header("Set-Cookie", "session_user=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT")
            self.send_header("Location", "/")
            self.end_headers()
        elif path == "/toggle_theme":
            if username:
                self.toggle_user_theme(username)
            self.redirect("/")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = urllib.parse.parse_qs(post_data)
        
        path = urllib.parse.urlparse(self.path).path
        cookies = self.parse_cookies()
        username = cookies.get("session_user")

        if path == "/login":
            user = params.get("username", [""])[0]
            pwd = params.get("password", [""])[0]
            if self.verify_user(user, pwd):
                self.update_streak(user)
                expires = (datetime.utcnow() + timedelta(days=30)).strftime('%a, %d %b %Y %H:%M:%S GMT')
                self.send_response(303)
                self.send_header("Set-Cookie", f"session_user={user}; Path=/; Expires={expires}")
                self.send_header("Set-Cookie", f"remembered_user={user}; Path=/; Expires={expires}")
                self.send_header("Location", "/")
                self.end_headers()
            else:
                self.send_html(self.get_login_page("Sai tên đăng nhập hoặc mật khẩu!", saved_user=user))

        elif path == "/register":
            user = params.get("username", [""])[0]
            pwd = params.get("password", [""])[0]
            if not user or not pwd:
                self.send_html(self.get_register_page("Vui lòng điền đầy đủ thông tin!"))
                return
            
            try:
                conn = sqlite3.connect("users.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (username, password, streak, last_active, safe_mode, theme, xp) VALUES (?, ?, 1, ?, 0, 'dark', 0)", (user, pwd, str(date.today())))
                conn.commit()
                conn.close()
                self.send_html(self.get_login_page(msg="Đăng ký thành công! Hãy đăng nhập.", saved_user=user))
            except sqlite3.IntegrityError:
                self.send_html(self.get_register_page("Tên tài khoản đã tồn tại!"))

        elif path == "/toggle_safe":
            pwd = params.get("password", [""])[0]
            if username and self.verify_user(username, pwd):
                conn = sqlite3.connect("users.db")
                cursor = conn.cursor()
                cursor.execute("SELECT safe_mode FROM users WHERE username = ?", (username,))
                safe_mode = cursor.fetchone()[0]
                new_mode = 0 if safe_mode == 1 else 1
                cursor.execute("UPDATE users SET safe_mode = ? WHERE username = ?", (new_mode, username))
                conn.commit()
                conn.close()
            self.redirect("/")

        elif path == "/add_custom_word":
            if username:
                unit = params.get("unit", [""])[0]
                word = params.get("word", [""])[0]
                v_type = params.get("type", [""])[0]
                pronun = params.get("pronunciation", [""])[0]
                meaning = params.get("meaning", [""])[0]
                example = params.get("example", [""])[0]
                if word and meaning:
                    try:
                        conn = sqlite3.connect("users.db")
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO custom_vocab (unit, word, type, pronunciation, meaning, example) VALUES (?, ?, ?, ?, ?, ?)",
                                       (unit, word, v_type, pronun, meaning, example))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        print("Lỗi thêm từ:", e)
            self.redirect("/admin_vocab")

        elif path == "/delete_custom_word":
            if username:
                v_id = params.get("id", [""])[0]
                try:
                    conn = sqlite3.connect("users.db")
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM custom_vocab WHERE id = ?", (v_id,))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print("Lỗi xóa từ:", e)
            self.redirect("/admin_vocab")

        elif path == "/save_word":
            if username:
                word = params.get("word", [""])[0]
                meaning = params.get("meaning", [""])[0]
                pronunciation = params.get("pronunciation", [""])[0]
                example = params.get("example", [""])[0]
                try:
                    conn = sqlite3.connect("users.db")
                    cursor = conn.cursor()
                    cursor.execute("INSERT OR IGNORE INTO saved_words (username, word, meaning, pronunciation, example) VALUES (?, ?, ?, ?, ?)",
                                   (username, word, meaning, pronunciation, example))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print("Lỗi lưu từ:", e)
            self.redirect("/practice")

        elif path == "/remove_saved":
            if username:
                word = params.get("word", [""])[0]
                conn = sqlite3.connect("users.db")
                cursor = conn.cursor()
                cursor.execute("DELETE FROM saved_words WHERE username = ? AND word = ?", (username, word))
                conn.commit()
                conn.close()
            self.redirect("/notebook")

        elif path == "/check_answer":
            user_ans = params.get("answer", [""])[0].strip().lower()
            correct_ans_str = params.get("correct_ans", [""])[0].strip().lower()
            
            correct_options = [opt.strip().lower() for opt in correct_ans_str.replace("/", ",").split(",")]
            is_correct = user_ans in correct_options and user_ans != ""
            
            safe_mode = 0
            if username:
                u_data = self.get_user_data(username)
                safe_mode = u_data["safe_mode"]
                if is_correct:
                    self.add_user_xp(username, 10)
                
            self.send_html(self.get_result_page(is_correct, correct_ans_str, safe_mode, return_url="/practice"))

        elif path == "/check_sentence":
            user_ans = params.get("user_sentence", [""])[0].strip()
            correct_ans = params.get("correct_sentence", [""])[0].strip()
            
            is_correct = (user_ans.lower() == correct_ans.lower())
            
            safe_mode = 0
            if username:
                u_data = self.get_user_data(username)
                safe_mode = u_data["safe_mode"]
                if is_correct:
                    self.add_user_xp(username, 15)
                
            self.send_html(self.get_result_page(is_correct, correct_ans, safe_mode, return_url="/sentence_practice"))

        elif path == "/check_quiz":
            selected = params.get("choice", [""])[0].strip().lower()
            correct = params.get("correct", [""])[0].strip().lower()
            
            is_correct = (selected == correct)
            safe_mode = 0
            if username:
                u_data = self.get_user_data(username)
                safe_mode = u_data["safe_mode"]
                if is_correct:
                    self.add_user_xp(username, 10)

            self.send_html(self.get_result_page(is_correct, correct, safe_mode, return_url="/quiz"))

    def parse_cookies(self):
        cookie_header = self.headers.get("Cookie")
        cookies = {}
        if cookie_header:
            for cookie in cookie_header.split(";"):
                if "=" in cookie:
                    key, val = cookie.strip().split("=", 1)
                    cookies[key] = val
        return cookies

    def send_html(self, html_content):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_content.encode("utf-8"))

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def verify_user(self, username, password):
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        res = cursor.fetchone()
        conn.close()
        return res is not None

    def update_streak(self, username):
        today = str(date.today())
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT streak, last_active FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            streak, last_active = row
            if last_active != today:
                streak += 1
                cursor.execute("UPDATE users SET streak = ?, last_active = ? WHERE username = ?", (streak, today, username))
                conn.commit()
        conn.close()

    def add_user_xp(self, username, points):
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT xp FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        current_xp = row[0] if row and row[0] is not None else 0
        new_xp = current_xp + points
        cursor.execute("UPDATE users SET xp = ? WHERE username = ?", (new_xp, username))
        conn.commit()
        conn.close()

    def toggle_user_theme(self, username):
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT theme FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            theme = row[0]
            new_theme = "dark" if theme == "light" else "light"
            cursor.execute("UPDATE users SET theme = ? WHERE username = ?", (new_theme, username))
            conn.commit()
        conn.close()

    def get_user_data(self, username):
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT streak, safe_mode, theme, xp FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"streak": row[0], "safe_mode": row[1], "theme": row[2] if row[2] else "dark", "xp": row[3] if row[3] is not None else 0}
        return {"streak": 1, "safe_mode": 0, "theme": "dark", "xp": 0}

    def get_base_template(self, title, body_content, theme="dark"):
        if theme == "light":
            bg = "#f1f5f9"
            fg = "#0f172a"
            card_bg = "rgba(255, 255, 255, 0.85)"
            input_bg = "#ffffff"
            input_border = "#cbd5e1"
            input_text = "#0f172a"
            border_glow = "rgba(0, 0, 0, 0.08)"
            blob1 = "rgba(99, 102, 241, 0.15)"
            blob2 = "rgba(16, 185, 129, 0.15)"
        else:
            bg = "#030712"
            fg = "#f8fafc"
            card_bg = "rgba(17, 24, 39, 0.75)"
            input_bg = "rgba(31, 41, 55, 0.8)"
            input_border = "rgba(75, 85, 99, 0.5)"
            input_text = "#f8fafc"
            border_glow = "rgba(255, 255, 255, 0.08)"
            blob1 = "rgba(99, 102, 241, 0.25)"
            blob2 = "rgba(236, 72, 153, 0.2)"

        return f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
            <style>
                * {{ box-sizing: border-box; }}
                body {{
                    font-family: 'Plus Jakarta Sans', sans-serif;
                    background-color: {bg};
                    color: {fg};
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    padding: 20px;
                    position: relative;
                    overflow-x: hidden;
                    transition: background 0.4s ease, color 0.4s ease;
                }}
                /* Hiệu ứng nền bóng đèn Neon mờ ảo */
                .bg-blob-1 {{
                    position: fixed; top: -150px; left: -150px; width: 500px; height: 500px;
                    background: {blob1}; filter: blur(100px); border-radius: 50%; z-index: 0; pointer-events: none;
                    animation: floatBlob 10s ease-in-out infinite alternate;
                }}
                .bg-blob-2 {{
                    position: fixed; bottom: -150px; right: -150px; width: 500px; height: 500px;
                    background: {blob2}; filter: blur(100px); border-radius: 50%; z-index: 0; pointer-events: none;
                    animation: floatBlob 12s ease-in-out infinite alternate-reverse;
                }}
                @keyframes floatBlob {{
                    0% {{ transform: translate(0, 0) scale(1); }}
                    100% {{ transform: translate(30px, 40px) scale(1.1); }}
                }}
                .container {{
                    position: relative; z-index: 1; background-color: {card_bg};
                    backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
                    padding: 40px 35px; border-radius: 24px;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.35);
                    border: 1px solid {border_glow};
                    width: 100%; max-width: 580px; text-align: center;
                    animation: slideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1);
                }}
                @keyframes slideUp {{
                    0% {{ opacity: 0; transform: translateY(20px); }}
                    100% {{ opacity: 1; transform: translateY(0); }}
                }}
                h2 {{ margin-top: 0; font-weight: 800; font-size: 26px; margin-bottom: 20px; letter-spacing: -0.5px; }}
                p {{ font-size: 14px; opacity: 0.85; line-height: 1.6; }}
                input, select, textarea {{
                    width: 100%; padding: 14px 18px; margin: 8px 0 16px 0;
                    border: 1.5px solid {input_border}; border-radius: 14px;
                    background: {input_bg}; color: {input_text}; font-size: 14px; outline: none;
                    transition: all 0.25s ease;
                }}
                input:focus, select:focus, textarea:focus {{
                    border-color: #6366f1;
                    box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.15);
                }}
                .password-wrapper {{
                    position: relative;
                    width: 100%;
                    margin: 8px 0 16px 0;
                }}
                .password-wrapper input {{
                    margin: 0 !important;
                    padding-right: 48px;
                }}
                .toggle-pwd-btn {{
                    position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
                    background: none; border: none; cursor: pointer; font-size: 16px;
                    width: auto !important; padding: 0 !important; margin: 0 !important;
                    box-shadow: none !important; color: inherit; opacity: 0.7;
                }}
                .toggle-pwd-btn:hover {{ opacity: 1; transform: translateY(-50%) scale(1.1); }}
                
                /* Nút bấm hiệu ứng mượt, có bóng đổ gradient */
                button.main-btn, button[type="submit"], .btn-custom {{
                    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
                    color: #fff; border: none; padding: 14px 20px; margin: 8px 0;
                    border-radius: 14px; cursor: pointer; font-weight: 700; width: 100%; font-size: 14px;
                    box-shadow: 0 10px 20px -5px rgba(99, 102, 241, 0.4);
                    transition: all 0.25s ease; letter-spacing: 0.3px;
                }}
                button.main-btn:hover, button[type="submit"]:hover, .btn-custom:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 15px 25px -5px rgba(99, 102, 241, 0.5);
                    opacity: 0.98;
                }}
                button:active {{ transform: translateY(0) scale(0.98); }}
                
                a {{ color: #818cf8; text-decoration: none; font-weight: 600; font-size: 13px; transition: color 0.2s; }}
                a:hover {{ color: #6366f1; text-decoration: underline; }}
                
                .alert {{ background-color: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); padding: 12px; border-radius: 12px; font-weight: 600; margin-bottom: 18px; font-size: 13px; }}
                .success {{ background-color: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); padding: 12px; border-radius: 12px; font-weight: 600; margin-bottom: 18px; font-size: 13px; }}
                
                .speak-btn {{
                    background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3);
                    border-radius: 50%; width: 38px; height: 38px; display: inline-flex;
                    align-items: center; justify-content: center; cursor: pointer; font-size: 16px;
                    transition: all 0.2s ease; box-shadow: none !important; margin-left: 8px; vertical-align: middle;
                }}
                .speak-btn:hover {{ background: rgba(99, 102, 241, 0.3); transform: scale(1.1); }}

                /* Menu Grid Cards trên Dashboard */
                .menu-grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 12px;
                    margin: 20px 0;
                }}
                .menu-card {{
                    background: rgba(255, 255, 255, 0.04);
                    border: 1px solid {border_glow};
                    padding: 16px 12px;
                    border-radius: 16px;
                    text-align: center;
                    cursor: pointer;
                    transition: all 0.25s ease;
                    text-decoration: none;
                    color: inherit;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    gap: 6px;
                }}
                .menu-card:hover {{
                    transform: translateY(-3px);
                    background: rgba(99, 102, 241, 0.1);
                    border-color: rgba(99, 102, 241, 0.3);
                    box-shadow: 0 10px 20px rgba(0,0,0,0.15);
                }}
                .menu-card span.icon {{ font-size: 26px; }}
                .menu-card span.label {{ font-size: 13px; font-weight: 700; }}
            </style>
            <script>
                function togglePassword(fieldId, btnElement) {{
                    const field = document.getElementById(fieldId);
                    if (field.type === "password") {{
                        field.type = "text";
                        btnElement.innerText = "🙈";
                    }} else {{
                        field.type = "password";
                        btnElement.innerText = "👁️";
                    }}
                }}
                function speakWord(text) {{
                    if ('speechSynthesis' in window) {{
                        window.speechSynthesis.cancel();
                        const utterance = new SpeechSynthesisUtterance(text);
                        utterance.lang = 'en-US';
                        utterance.rate = 0.9;
                        window.speechSynthesis.speak(utterance);
                    }} else {{
                        alert("Trình duyệt không hỗ trợ phát âm!");
                    }}
                }}
            </script>
        </head>
        <body>
            <div class="bg-blob-1"></div>
            <div class="bg-blob-2"></div>
            <div class="container">{body_content}</div>
        </body>
        </html>
        """

    def get_login_page(self, error="", msg="", saved_user=""):
        cookies = self.parse_cookies()
        auto_user = saved_user or cookies.get("remembered_user", "")
        content = f"""
            <div style="font-size: 40px; margin-bottom: 10px;">🎓</div>
            <h2>Đăng Nhập Hệ Thống</h2>
            <p style="margin-top: -10px; margin-bottom: 20px; opacity: 0.7; font-size: 13px;">Học tiếng Anh thông minh cùng không gian Glassmorphism</p>
            {f'<div class="alert">{error}</div>' if error else ''}
            {f'<div class="success">{msg}</div>' if msg else ''}
            <form method="POST" action="/login">
                <div style="text-align: left; font-size: 12px; font-weight: 700; margin-bottom: -2px; opacity: 0.8;">Tên đăng nhập</div>
                <input type="text" name="username" value="{auto_user}" placeholder="Nhập tên tài khoản..." required>
                <div style="text-align: left; font-size: 12px; font-weight: 700; margin-bottom: -2px; opacity: 0.8;">Mật khẩu</div>
                <div class="password-wrapper">
                    <input type="password" name="password" id="login-pwd" placeholder="Nhập mật khẩu..." required>
                    <button type="button" class="toggle-pwd-btn" onclick="togglePassword('login-pwd', this)">👁️</button>
                </div>
                <button type="submit">Truy Cập Ngay 🚀</button>
            </form>
            <div style="margin-top: 20px;"><a href="/register">Chưa có tài khoản? Đăng ký ngay ✨</a></div>
        """
        return self.get_base_template("Đăng Nhập", content)

    def get_register_page(self, error=""):
        content = f"""
            <div style="font-size: 40px; margin-bottom: 10px;">✨</div>
            <h2>Đăng Ký Tài Khoản</h2>
            <p style="margin-top: -10px; margin-bottom: 20px; opacity: 0.7; font-size: 13px;">Tạo tài khoản mới để bắt đầu hành trình chinh phục từ vựng</p>
            {f'<div class="alert">{error}</div>' if error else ''}
            <form method="POST" action="/register">
                <div style="text-align: left; font-size: 12px; font-weight: 700; margin-bottom: -2px; opacity: 0.8;">Tên đăng nhập mới</div>
                <input type="text" name="username" placeholder="Chọn tên tài khoản..." required>
                <div style="text-align: left; font-size: 12px; font-weight: 700; margin-bottom: -2px; opacity: 0.8;">Mật khẩu mới</div>
                <div class="password-wrapper">
                    <input type="password" name="password" id="reg-pwd" placeholder="Tạo mật khẩu..." required>
                    <button type="button" class="toggle-pwd-btn" onclick="togglePassword('reg-pwd', this)">👁️</button>
                </div>
                <button type="submit" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); box-shadow: 0 10px 20px -5px rgba(16, 185, 129, 0.4);">Hoàn Tất Đăng Ký 🌱</button>
            </form>
            <div style="margin-top: 20px;"><a href="/">Đã có tài khoản? Quay về Đăng Nhập</a></div>
        """
        return self.get_base_template("Đăng Ký", content)

    def get_dashboard_page(self, username):
        u_data = self.get_user_data(username)
        safe_text = "Đang Bật (Tấu hài)" if u_data["safe_mode"] else "Đang Tắt"
        safe_color = "#f87171" if u_data["safe_mode"] else "#4ade80"

        content = f"""
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <a href="/toggle_theme"><button style="width: auto; padding: 8px 14px; font-size: 12px; background: rgba(100,116,139,0.3); border-radius: 10px; margin: 0; box-shadow: none;">☀️ / 🌙 Đổi Giao Diện</button></a>
                <a href="/logout"><button style="width: auto; padding: 8px 14px; font-size: 12px; background: rgba(239,68,68,0.2); color: #f87171; border-radius: 10px; margin: 0; box-shadow: none;">Đăng Xuất 🚪</button></a>
            </div>
            
            <div style="text-align: left; margin-bottom: 15px;">
                <h2 style="margin-bottom: 4px; font-size: 24px;">Xin chào, {username}! 👋</h2>
                <p style="margin: 0; font-size: 13px; opacity: 0.7;">Sẵn sàng bứt phá điểm số hôm nay chưa nào?</p>
            </div>

            <div style="background: rgba(99, 102, 241, 0.08); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 18px; padding: 16px; margin-bottom: 15px; display: flex; justify-content: space-around; align-items: center; text-align: center;">
                <div>
                    <div style="font-size: 11px; opacity: 0.7; font-weight: 600; text-transform: uppercase;">Điểm XP</div>
                    <div style="font-size: 20px; font-weight: 800; color: #818cf8; margin-top: 2px;">⚡ {u_data['xp']}</div>
                </div>
                <div style="width: 1px; height: 30px; background: rgba(255,255,255,0.1);"></div>
                <div>
                    <div style="font-size: 11px; opacity: 0.7; font-weight: 600; text-transform: uppercase;">Chuỗi Streak</div>
                    <div style="font-size: 20px; font-weight: 800; color: #fbbf24; margin-top: 2px;">🔥 {u_data['streak']} ngày</div>
                </div>
                <div style="width: 1px; height: 30px; background: rgba(255,255,255,0.1);"></div>
                <div>
                    <div style="font-size: 11px; opacity: 0.7; font-weight: 600; text-transform: uppercase;">Safe Mode</div>
                    <div style="font-size: 13px; font-weight: 700; color: {safe_color}; margin-top: 6px;">{safe_text}</div>
                </div>
            </div>

            <div class="menu-grid">
                <a href="/practice" class="menu-card" style="border-color: rgba(16, 185, 129, 0.3);">
                    <span class="icon">🚀</span>
                    <span class="label" style="color: #4ade80;">Luyện Từ Vựng</span>
                    <span style="font-size: 11px; opacity: 0.6;">({len(VOCAB_LIST)} từ)</span>
                </a>
                <a href="/flashcards" class="menu-card" style="border-color: rgba(139, 92, 246, 0.3);">
                    <span class="icon">🃏</span>
                    <span class="label" style="color: #a78bfa;">Lật Thẻ Flashcard</span>
                    <span style="font-size: 11px; opacity: 0.6;">Ghi nhớ nhanh</span>
                </a>
                <a href="/sentence_practice" class="menu-card" style="border-color: rgba(59, 130, 246, 0.3);">
                    <span class="icon">🧩</span>
                    <span class="label" style="color: #60a5fa;">Sắp Xếp Câu</span>
                    <span style="font-size: 11px; opacity: 0.6;">Luyện ngữ pháp</span>
                </a>
                <a href="/quiz" class="menu-card" style="border-color: rgba(236, 72, 153, 0.3);">
                    <span class="icon">🎯</span>
                    <span class="label" style="color: #f472b6;">Thi Trắc Nghiệm</span>
                    <span style="font-size: 11px; opacity: 0.6;">4 đáp án A/B/C/D</span>
                </a>
                <a href="/notebook" class="menu-card" style="border-color: rgba(245, 158, 11, 0.3);">
                    <span class="icon">🔖</span>
                    <span class="label" style="color: #fbbf24;">Sổ Tay Từ Khó</span>
                    <span style="font-size: 11px; opacity: 0.6;">Từ vựng cá nhân</span>
                </a>
                <a href="/admin_vocab" class="menu-card" style="border-color: rgba(6, 182, 212, 0.3);">
                    <span class="icon">🛠️</span>
                    <span class="label" style="color: #22d3ee;">Quản Trị Từ Vựng</span>
                    <span style="font-size: 11px; opacity: 0.6;">Thêm từ mới</span>
                </a>
            </div>

            <a href="/leaderboard"><button style="background: linear-gradient(135deg, #475569 0%, #334155 100%); margin-top: 4px;">🏆 Xem Bảng Xếp Hạng XP</button></a>

            <form action="/toggle_safe" method="POST" style="margin-top: 15px; background: rgba(255,255,255,0.03); padding: 12px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.05);">
                <div style="font-size: 11px; font-weight: 700; text-align: left; margin-bottom: 4px; opacity: 0.7;">Xác thực mật khẩu đổi Safe Mode:</div>
                <div class="password-wrapper" style="margin-bottom: 8px;">
                    <input type="password" name="password" id="safe-pwd" placeholder="Nhập mật khẩu..." required>
                    <button type="button" class="toggle-pwd-btn" onclick="togglePassword('safe-pwd', this)">👁️</button>
                </div>
                <button type="submit" style="background: rgba(100,116,139,0.3); border: 1px solid rgba(100,116,139,0.4); box-shadow: none;">{'🔓 Tắt Safe Mode' if u_data['safe_mode'] else '🔒 Bật Safe Mode'}</button>
            </form>
        """
        return self.get_base_template("Dashboard", content, u_data["theme"])

    def get_flashcard_page(self, username):
        u_data = self.get_user_data(username)
        vocab_json = json.dumps(VOCAB_LIST)

        content = f"""
            <h2 style="color: #a78bfa; margin-bottom: 4px;">🃏 Flashcard Ghi Nhớ Nhanh</h2>
            <p style="font-size: 13px; opacity: 0.7; margin-bottom: 20px;">Click vào thẻ để lật mặt trước và sau. Luyện phát âm chuẩn xác:</p>

            <div id="flashcard-container" style="perspective: 1000px; width: 100%; height: 250px; margin-bottom: 20px; cursor: pointer;" onclick="flipCard()">
                <div id="card-inner" style="position: relative; width: 100%; height: 100%; text-align: center; transition: transform 0.6s cubic-bezier(0.4, 0.2, 0.2, 1); transform-style: preserve-3d; border-radius: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.2); border: 1px solid rgba(167, 139, 250, 0.3);">
                    
                    <!-- Mặt trước -->
                    <div id="card-front" style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; background: rgba(139, 92, 246, 0.1); border-radius: 20px; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 20px;">
                        <div id="fc-unit" style="font-size: 11px; font-weight: 800; color: #a78bfa; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;"></div>
                        <div style="display: flex; align-items: center; justify-content: center; gap: 10px; margin-bottom: 6px;">
                            <span id="fc-word" style="font-size: 28px; font-weight: 800; color: #fbbf24;"></span>
                            <button type="button" class="speak-btn" onclick="event.stopPropagation(); speakWord(currentWord)">🔊</button>
                        </div>
                        <div id="fc-pronun" style="font-size: 13px; opacity: 0.7; font-style: italic;"></div>
                        <div style="position: absolute; bottom: 14px; font-size: 11px; opacity: 0.5;">👆 Click vào thẻ để lật xem nghĩa</div>
                    </div>

                    <!-- Mặt sau -->
                    <div id="card-back" style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; background: rgba(16, 185, 129, 0.1); border-radius: 20px; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 20px; transform: rotateY(180deg);">
                        <div style="font-size: 11px; font-weight: 800; color: #4ade80; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;">Nghĩa Tiếng Việt & Ví Dụ</div>
                        <div id="fc-meaning" style="font-size: 22px; font-weight: 800; color: #4ade80; margin-bottom: 10px;"></div>
                        <div id="fc-example" style="font-size: 13px; font-style: italic; opacity: 0.9; max-width: 90%;"></div>
                        <div style="position: absolute; bottom: 14px; font-size: 11px; opacity: 0.5;">👆 Click để lật lại từ vựng</div>
                    </div>

                </div>
            </div>

            <div style="display: flex; gap: 12px; justify-content: center;">
                <button type="button" onclick="prevCard()" style="background: rgba(100,116,139,0.3); border: 1px solid rgba(100,116,139,0.4); width: 48%; box-shadow: none;">⬅ Từ Trước</button>
                <button type="button" onclick="nextCard()" style="background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%); width: 48%;">Từ Tiếp Theo ➡</button>
            </div>

            <div style="margin-top: 20px;"><a href="/">⬅ Quay lại Menu chính</a></div>

            <script>
                const vocabList = {vocab_json};
                let currentIndex = 0;
                let isFlipped = false;
                let currentWord = "";

                function updateCard() {{
                    isFlipped = false;
                    document.getElementById("card-inner").style.transform = "rotateY(0deg)";
                    const item = vocabList[currentIndex];
                    currentWord = item.word;
                    document.getElementById("fc-unit").innerText = item.unit || "Từ vựng";
                    document.getElementById("fc-word").innerText = item.word;
                    document.getElementById("fc-pronun").innerText = item.pronunciation || "";
                    document.getElementById("fc-meaning").innerText = item.meaning;
                    document.getElementById("fc-example").innerText = item.example ? `"${{item.example}}"` : "";
                }}

                function flipCard() {{
                    isFlipped = !isFlipped;
                    const rot = isFlipped ? "180deg" : "0deg";
                    document.getElementById("card-inner").style.transform = `rotateY(${{rot}})`;
                }}

                function nextCard() {{
                    currentIndex = (currentIndex + 1) % vocabList.length;
                    updateCard();
                }}

                function prevCard() {{
                    currentIndex = (currentIndex - 1 + vocabList.length) % vocabList.length;
                    updateCard();
                }}

                updateCard();
            </script>
        """
        return self.get_base_template("Flashcard Lật Thẻ", content, u_data["theme"])

    def get_notebook_page(self, username):
        u_data = self.get_user_data(username)
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT word, meaning, pronunciation, example FROM saved_words WHERE username = ?", (username,))
        saved = cursor.fetchall()
        conn.close()

        items_html = ""
        if not saved:
            items_html = "<p style='opacity: 0.6; padding: 30px;'>Sổ tay của bạn đang trống. Hãy bấm lưu từ khó trong lúc làm bài tập nhé! 🔖</p>"
        else:
            for word, meaning, pronun, ex in saved:
                items_html += f"""
                    <div style="background: rgba(245, 158, 11, 0.06); border: 1px solid rgba(245, 158, 11, 0.2); border-radius: 14px; padding: 14px 16px; margin-bottom: 12px; text-align: left; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <b style="font-size: 16px; color: #fbbf24;">{word}</b>
                                <button type="button" class="speak-btn" style="width: 30px; height: 30px; font-size: 12px;" onclick="speakWord('{word}')">🔊</button>
                                <span style="font-size: 12px; opacity: 0.7; font-style: italic;">{pronun}</span>
                            </div>
                            <div style="font-size: 14px; font-weight: 700; color: #4ade80; margin-top: 4px;">{meaning}</div>
                            {f'<div style="font-size: 12px; opacity: 0.8; font-style: italic; margin-top: 2px;">"{ex}"</div>' if ex else ''}
                        </div>
                        <form action="/remove_saved" method="POST" style="margin: 0;">
                            <input type="hidden" name="word" value="{word}">
                            <button type="submit" style="background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid rgba(239,68,68,0.3); width: auto; padding: 6px 12px; font-size: 11px; margin: 0; box-shadow: none;">Xóa</button>
                        </form>
                    </div>
                """

        content = f"""
            <h2>🔖 Sổ Tay Từ Khó</h2>
            <p style="font-size: 13px; opacity: 0.7; margin-top: -10px; margin-bottom: 20px;">Danh sách các từ vựng bạn đã lưu lại để ôn tập riêng:</p>
            <div style="max-height: 380px; overflow-y: auto; padding-right: 4px;">{items_html}</div>
            <div style="margin-top: 20px;"><a href="/"><button style="background: rgba(100,116,139,0.3); border: 1px solid rgba(100,116,139,0.4); box-shadow: none;">Quay Lại Menu Chính</button></a></div>
        """
        return self.get_base_template("Sổ Tay Từ Khó", content, u_data["theme"])

    def get_admin_vocab_page(self, username):
        u_data = self.get_user_data(username)
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, unit, word, meaning FROM custom_vocab")
        custom_list = cursor.fetchall()
        conn.close()

        items_html = ""
        if not custom_list:
            items_html = "<p style='opacity: 0.6; font-size: 13px;'>Chưa có từ vựng nào được thêm thủ công.</p>"
        else:
            for v_id, unit, word, meaning in custom_list:
                items_html += f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(6, 182, 212, 0.06); border: 1px solid rgba(6, 182, 212, 0.2); padding: 10px 14px; border-radius: 10px; margin-bottom: 8px; text-align: left;">
                        <span style="font-size: 13px;"><b>{word}</b> ({meaning}) — <i style="opacity: 0.7;">{unit}</i></span>
                        <form action="/delete_custom_word" method="POST" style="margin: 0;">
                            <input type="hidden" name="id" value="{v_id}">
                            <button type="submit" style="background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid rgba(239,68,68,0.3); width: auto; padding: 4px 10px; font-size: 11px; margin: 0; box-shadow: none;">Xóa</button>
                        </form>
                    </div>
                """

        content = f"""
            <h2 style="color: #22d3ee; margin-bottom: 4px;">🛠️ Quản Trị / Thêm Từ Mới</h2>
            <p style="font-size: 13px; opacity: 0.7; margin-bottom: 15px;">Thêm từ vựng vào bộ dữ liệu để luyện tập ngay lập tức:</p>

            <form method="POST" action="/add_custom_word" style="text-align: left;">
                <div style="display: flex; gap: 12px;">
                    <div style="flex: 1;">
                        <div style="font-size: 11px; font-weight: 700; opacity: 0.8;">Unit / Bài:</div>
                        <input type="text" name="unit" placeholder="Ví dụ: Unit 5" required style="margin: 4px 0 12px 0;">
                    </div>
                    <div style="flex: 1;">
                        <div style="font-size: 11px; font-weight: 700; opacity: 0.8;">Từ tiếng Anh:</div>
                        <input type="text" name="word" placeholder="Ví dụ: brilliant" required style="margin: 4px 0 12px 0;">
                    </div>
                </div>
                <div style="display: flex; gap: 12px;">
                    <div style="flex: 1;">
                        <div style="font-size: 11px; font-weight: 700; opacity: 0.8;">Loại từ (n, v, adj...):</div>
                        <input type="text" name="type" placeholder="adj" style="margin: 4px 0 12px 0;">
                    </div>
                    <div style="flex: 1;">
                        <div style="font-size: 11px; font-weight: 700; opacity: 0.8;">Phiên âm:</div>
                        <input type="text" name="pronunciation" placeholder="/ˈbrɪliənt/" style="margin: 4px 0 12px 0;">
                    </div>
                </div>
                <div style="font-size: 11px; font-weight: 700; opacity: 0.8;">Nghĩa tiếng Việt:</div>
                <input type="text" name="meaning" placeholder="Xuất sắc, tuyệt vời" required style="margin: 4px 0 12px 0;">
                <div style="font-size: 11px; font-weight: 700; opacity: 0.8;">Câu ví dụ tiếng Anh:</div>
                <input type="text" name="example" placeholder="That is a brilliant idea!" style="margin: 4px 0 18px 0;">
                
                <button type="submit" style="background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%); box-shadow: 0 10px 20px -5px rgba(6, 182, 212, 0.4);">➕ Thêm Vào Hệ Thống</button>
            </form>

            <hr style="border: 0; border-top: 1px solid rgba(255,255,255,0.08); margin: 20px 0;">
            <div style="font-size: 13px; font-weight: 700; text-align: left; margin-bottom: 8px;">Danh sách từ tự thêm ({len(custom_list)}):</div>
            <div style="max-height: 150px; overflow-y: auto; padding-right: 4px;">{items_html}</div>

            <div style="margin-top: 15px;"><a href="/">⬅ Quay lại Menu chính</a></div>
        """
        return self.get_base_template("Quản Trị Từ Vựng", content, u_data["theme"])

    def get_quiz_page(self, username):
        u_data = self.get_user_data(username)
        correct_item = random.choice(VOCAB_LIST)
        wrong_pool = [w for w in VOCAB_LIST if w["word"] != correct_item["word"]]
        distractors = random.sample(wrong_pool, min(3, len(wrong_pool)))
        
        options = [correct_item["meaning"]] + [d["meaning"] for d in distractors]
        random.shuffle(options)

        options_html = ""
        for opt in options:
            options_html += f"""
                <button type="submit" name="choice" value="{opt}" style="background: rgba(236, 72, 153, 0.06); color: inherit; border: 1.5px solid rgba(236, 72, 153, 0.25); font-weight: 700; text-align: left; padding: 14px 18px; border-radius: 14px; margin-bottom: 10px; width: 100%; box-shadow: none; transition: all 0.2s;">
                    🎯 {opt}
                </button>
            """

        content = f"""
            <h2 style="color: #f472b6; margin-bottom: 4px;">🎯 Thi Trắc Nghiệm (Quiz)</h2>
            <p style="font-size: 13px; opacity: 0.7; margin-bottom: 20px;">Chọn đáp án nghĩa tiếng Việt chính xác nhất cho từ sau:</p>

            <div style="background: rgba(236, 72, 153, 0.08); border-radius: 18px; padding: 20px; margin-bottom: 20px; border: 1px dashed rgba(236, 72, 153, 0.4);">
                <div style="display: flex; align-items: center; justify-content: center; gap: 10px; margin-bottom: 4px;">
                    <div style="font-size: 26px; font-weight: 800; color: #f472b6;">{correct_item['word']}</div>
                    <button type="button" class="speak-btn" onclick="speakWord('{correct_item['word']}')">🔊</button>
                </div>
                <div style="font-size: 13px; opacity: 0.7; font-style: italic;">({correct_item.get('type', '')}) — {correct_item.get('pronunciation', '')}</div>
            </div>

            <form method="POST" action="/check_quiz">
                <input type="hidden" name="correct" value="{correct_item['meaning']}">
                {options_html}
            </form>

            <div style="margin-top: 15px;"><a href="/">⬅ Quay lại Menu chính</a></div>
        """
        return self.get_base_template("Thi Trắc Nghiệm", content, u_data["theme"])

    def get_practice_page(self, username):
        u_data = self.get_user_data(username)
        word_item = random.choice(VOCAB_LIST)

        mode_title = "BÀI TẬP (SAFE MODE ON)" if u_data["safe_mode"] else "LUYỆN TẬP TỪ VỰNG"
        title_color = "#f87171" if u_data["safe_mode"] else "#818cf8"
        example_text = f"\"{word_item.get('example', '')}\"" if word_item.get('example') else ""
        pronunciation = word_item.get('pronunciation', '')

        content = f"""
            <h2 style="color: {title_color}; margin-bottom: 4px;">{mode_title}</h2>
            
            <div style="background: rgba(255,255,255,0.06); border-radius: 10px; height: 8px; width: 100%; margin-bottom: 12px; overflow: hidden;">
                <div id="timer-bar" style="background: #4ade80; height: 100%; width: 100%; transition: width 1s linear; border-radius: 10px;"></div>
            </div>
            <div style="font-size: 13px; font-weight: 700; color: #fbbf24; margin-bottom: 15px;">⏳ Thời gian còn lại: <span id="time-left">15</span>s</div>

            <div style="background: rgba(99, 102, 241, 0.08); border-radius: 18px; padding: 20px; margin: 10px 0 20px 0; border: 1px dashed rgba(99, 102, 241, 0.4); position: relative;">
                <div style="display: flex; align-items: center; justify-content: center; gap: 10px; margin-bottom: 4px;">
                    <div style="font-size: 24px; font-weight: 800; color: #fbbf24;">{word_item['word']}</div>
                    <button type="button" class="speak-btn" onclick="speakWord('{word_item['word']}')">🔊</button>
                </div>
                <div style="font-size: 12px; opacity: 0.7; margin-bottom: 10px;">({word_item.get('type', '')}) — <i>{pronunciation}</i></div>
                {f'<div style="font-size: 14px; font-style: italic; color: #4ade80;">{example_text}</div>' if example_text else ''}
            </div>

            <form id="quiz-form" method="POST" action="/check_answer">
                <input type="hidden" name="correct_ans" value="{word_item['meaning']}">
                <input type="text" id="answer-input" name="answer" placeholder="Nhập nghĩa tiếng Việt chính xác..." autocomplete="off" autofocus required>
                <button type="submit">Nộp Bài Kiểm Tra 🎯</button>
            </form>

            <form method="POST" action="/save_word" style="margin-top: 10px;">
                <input type="hidden" name="word" value="{word_item['word']}">
                <input type="hidden" name="meaning" value="{word_item['meaning']}">
                <input type="hidden" name="pronunciation" value="{pronunciation}">
                <input type="hidden" name="example" value="{word_item.get('example', '')}">
                <button type="submit" style="background: rgba(245, 158, 11, 0.12); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); font-weight: 700; box-shadow: none;">🔖 Lưu từ này vào Sổ tay</button>
            </form>

            <div style="margin-top: 15px;"><a href="/">⬅ Quay lại Menu chính</a></div>

            <script>
                let timeLeft = 15;
                const timerBar = document.getElementById("timer-bar");
                const timeLeftSpan = document.getElementById("time-left");
                const quizForm = document.getElementById("quiz-form");

                const countdown = setInterval(() => {{
                    timeLeft--;
                    timeLeftSpan.innerText = timeLeft;
                    timerBar.style.width = (timeLeft / 15 * 100) + "%";
                    if (timeLeft <= 5) {{ timerBar.style.background = "#f87171"; }}
                    if (timeLeft <= 0) {{
                        clearInterval(countdown);
                        document.getElementById("answer-input").value = "__TIME_OUT__";
                        quizForm.submit();
                    }}
                }}, 1000);
            </script>
        """
        return self.get_base_template("Luyện Từ Vựng", content, u_data["theme"])

    def get_sentence_practice_page(self, username):
        u_data = self.get_user_data(username)
        sentence_item = random.choice(SENTENCE_LIST)
        
        full_sentence = sentence_item["english"]
        vietnamese_meaning = sentence_item["vietnamese"]

        clean_sentence = full_sentence.rstrip(".!?")
        words = clean_sentence.split()
        
        shuffled_words = words.copy()
        random.shuffle(shuffled_words)
        
        shuffled_json = json.dumps(shuffled_words)
        correct_json = json.dumps(full_sentence)

        content = f"""
            <h2 style="color: #60a5fa; margin-bottom: 4px;">🧩 Sắp Xếp Câu Tiếng Anh</h2>
            <p style="font-size: 13px; opacity: 0.7; margin-bottom: 20px;">Dựa vào gợi ý, click vào các từ bên dưới để sắp xếp lại thành câu hoàn chỉnh:</p>

            <div style="background: rgba(59, 130, 246, 0.08); border-radius: 16px; padding: 16px; margin-bottom: 18px; border: 1px solid rgba(59, 130, 246, 0.25); display: flex; align-items: center; justify-content: space-between;">
                <div style="text-align: left;">
                    <div style="font-size: 11px; font-weight: 700; color: #60a5fa; margin-bottom: 4px; text-transform: uppercase;">📌 Gợi ý ngữ cảnh:</div>
                    <div style="font-size: 14px; font-style: italic;">"{vietnamese_meaning}"</div>
                </div>
                <button type="button" class="speak-btn" onclick="speakWord(correctSentence)">🔊</button>
            </div>

            <div id="drop-zone" style="min-height: 60px; background: rgba(255,255,255,0.04); border: 2px dashed rgba(255,255,255,0.15); border-radius: 16px; padding: 12px; margin-bottom: 18px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: center;">
                <span id="placeholder-text" style="font-size: 13px; opacity: 0.5;">Chọn các từ bên dưới theo thứ tự đúng...</span>
            </div>

            <div id="word-bank" style="display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 20px;"></div>

            <form id="sentence-form" method="POST" action="/check_sentence">
                <input type="hidden" id="user-sentence-input" name="user_sentence" value="">
                <input type="hidden" name="correct_sentence" value="{full_sentence}">
                <button type="button" id="reset-btn" style="background: rgba(100,116,139,0.3); border: 1px solid rgba(100,116,139,0.4); margin-bottom: 8px; box-shadow: none;">🔄 Làm Lại Từ Đầu</button>
                <button type="submit" id="submit-btn" style="background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);" disabled>Nộp Bài Sắp Xếp</button>
            </form>

            <div style="margin-top: 15px;"><a href="/">⬅ Quay lại Menu chính</a></div>

            <script>
                const shuffledWords = {shuffled_json};
                const correctSentence = {correct_json};
                
                let selectedWords = [];
                let availableWords = [...shuffledWords];

                const dropZone = document.getElementById("drop-zone");
                const wordBank = document.getElementById("word-bank");
                const userSentenceInput = document.getElementById("user-sentence-input");
                const submitBtn = document.getElementById("submit-btn");
                const resetBtn = document.getElementById("reset-btn");

                function render() {{
                    wordBank.innerHTML = "";
                    availableWords.forEach((word, index) => {{
                        const btn = document.createElement("button");
                        btn.type = "button";
                        btn.innerText = word;
                        btn.style.cssText = "background: rgba(30, 41, 59, 0.8); color: #fff; border: 1px solid rgba(255,255,255,0.1); padding: 8px 14px; border-radius: 10px; cursor: pointer; font-size: 13px; font-weight: 700; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: auto; margin: 0; transition: transform 0.2s;";
                        btn.onclick = () => selectWord(index);
                        wordBank.appendChild(btn);
                    }});

                    dropZone.innerHTML = "";
                    if (selectedWords.length === 0) {{
                        const ph = document.createElement("span");
                        ph.id = "placeholder-text";
                        ph.style.cssText = "font-size: 13px; opacity: 0.5;";
                        ph.innerText = "Chọn các từ bên dưới theo thứ tự đúng...";
                        dropZone.appendChild(ph);
                        submitBtn.disabled = true;
                        submitBtn.style.opacity = "0.5";
                    }} else {{
                        selectedWords.forEach((item, index) => {{
                            const chip = document.createElement("button");
                            chip.type = "button";
                            chip.innerText = item.word;
                            chip.style.cssText = "background: #3b82f6; color: #fff; border: none; padding: 8px 14px; border-radius: 10px; cursor: pointer; font-size: 13px; font-weight: 700; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: auto; margin: 0;";
                            chip.onclick = () => unselectWord(index);
                            dropZone.appendChild(chip);
                        }});
                        submitBtn.disabled = false;
                        submitBtn.style.opacity = "1";
                    }}

                    let currentStr = selectedWords.map(i => i.word).join(" ");
                    if (correctSentence.endsWith(".") && currentStr.length > 0) {{
                        currentStr += ".";
                    }}
                    userSentenceInput.value = currentStr;
                }}

                function selectWord(index) {{
                    const wordObj = availableWords.splice(index, 1)[0];
                    selectedWords.push({{word: wordObj}});
                    render();
                }}

                function unselectWord(index) {{
                    const wordObj = selectedWords.splice(index, 1)[0];
                    availableWords.push(wordObj.word);
                    render();
                }}

                resetBtn.onclick = () => {{
                    availableWords = [...shuffledWords];
                    selectedWords = [];
                    render();
                }};

                render();
            </script>
        """
        return self.get_base_template("Luyện Sắp Xếp Câu", content, u_data["theme"])

    def get_leaderboard_page(self, username):
        u_data = self.get_user_data(username)
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT username, xp, streak FROM users ORDER BY xp DESC LIMIT 10")
        top_users = cursor.fetchall()
        conn.close()

        list_html = ""
        for idx, (u, xp, streak) in enumerate(top_users, 1):
            medal = "🥇" if idx == 1 else ("🥈" if idx == 2 else ("🥉" if idx == 3 else f"#{idx}"))
            safe_xp = xp if xp is not None else 0
            list_html += f"""
                <li style='padding: 12px 16px; margin-bottom: 8px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; display: flex; justify-content: space-between; align-items: center;'>
                    <span style="font-weight: 700;">{medal} &nbsp; {u} <i style="font-size: 11px; opacity: 0.6;">(Streak: {streak}d)</i></span> 
                    <span style='color: #818cf8; font-weight: 800;'>{safe_xp} XP ⚡</span>
                </li>
            """

        content = f"""
            <h2>🏆 Bảng Xếp Hạng XP</h2>
            <p style="font-size: 13px; opacity: 0.7; margin-top: -10px; margin-bottom: 20px;">Thành tích thi đua tích lũy điểm kinh nghiệm toàn hệ thống:</p>
            <ul style="list-style: none; padding: 0; margin: 0 0 20px 0; text-align: left;">{list_html}</ul>
            <a href="/"><button style="background: rgba(100,116,139,0.3); border: 1px solid rgba(100,116,139,0.4); box-shadow: none;">Quay Lại Menu Chính</button></a>
        """
        return self.get_base_template("Bảng Xếp Hạng", content, u_data["theme"])

    def get_result_page(self, is_correct, correct_ans, safe_mode=0, return_url="/practice"):
        if is_correct:
            sound_html = SoundManager.get_sound_tag("correct")
            return f"""
                <!DOCTYPE html><html>
                <body style="background: #030712; color: #fff; font-family: 'Plus Jakarta Sans', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0;">
                    {sound_html}
                    <div style="text-align: center;">
                        <h2 style="color: #4ade80; font-size: 28px; font-weight: 800;">🎉 Chính xác tuyệt vời! Thưởng XP.</h2>
                        <p style="opacity: 0.7; font-size: 14px;">Đang chuyển hướng về trang chủ...</p>
                    </div>
                    <script>setTimeout(() => {{ window.location.href = "/"; }}, 1000);</script>
                </body></html>
            """
        else:
            sound_key = "wrong_on" if safe_mode == 1 else "wrong_off"
            sound_html = SoundManager.get_sound_tag(sound_key)
            html = f"""
                <!DOCTYPE html><html>
                <body style="background: #030712; color: #fff; font-family: 'Plus Jakarta Sans', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0;">
                    {sound_html}
                    <div style="text-align: center; max-width: 500px; padding: 20px;">
                        <h2 style="color: #f87171; font-size: 28px; font-weight: 800;">❌ Chưa chính xác rồi!</h2>
                        <p style="font-size: 15px; margin: 10px 0; opacity: 0.8;">Đáp án đúng chuẩn là:</p>
                        <p style="font-size: 18px; font-weight: 800; color: #fbbf24; background: rgba(251, 191, 36, 0.1); border: 1px solid rgba(251, 191, 36, 0.3); padding: 12px; border-radius: 12px;">COR_ANS</p>
                        <p style="opacity: 0.7; font-size: 13px; margin-top: 20px;">Đang tải lại câu hỏi...</p>
                    </div>
                    <script>setTimeout(() => {{ window.location.href = "RET_URL"; }}, 2500);</script>
                </body></html>
            """
            return html.replace("COR_ANS", correct_ans).replace("RET_URL", return_url)

if __name__ == "__main__":
    webbrowser.open(f"http://stem-tienganh.local")
    with socketserver.TCPServer(("", PORT), EnglishAppHandler) as httpd:
        print("Server Glassmorphism đang chạy tại: http://stem-tienganh.local")
        print("Chrome đã tự động bật với diện mạo mới cực chất. Nhấn Ctrl+C để tắt server.")
        httpd.serve_forever()

