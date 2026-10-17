const open = require('open');
const express = require('express');
const cors = require('cors');
require('dotenv').config();
const pool = require('./db');

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// API Kiểm tra kết nối
app.get('/', async (req, res) => {
  res.json({ message: 'Welcome to Penguin English API (Node.js)!' });
});

// API Đăng nhập
app.post('/api/login', async (req, res) => {
  const { username, password } = req.body;
  try {
    const result = await pool.query('SELECT password FROM users WHERE username = $1', [username]);
    if (result.rows.length > 0 && result.rows[0].password === password) {
      const today = new Date().toISOString().split('T')[0];
      const userCheck = await pool.query('SELECT streak, last_active FROM users WHERE username = $1', [username]);
      let { streak, last_active } = userCheck.rows[0];

      if (last_active !== today) {
        const yesterday = new Date(Date.now() - 86400000).toISOString().split('T')[0];
        if (last_active === yesterday) {
          streak += 1;
        } else {
          streak = 1;
        }
        await pool.query('UPDATE users SET streak = $1, last_active = $2 WHERE username = $3', [streak, today, username]);
      }

      res.json({ success: true, message: 'Đăng nhập thành công!', username, streak });
    } else {
      res.status(401).json({ success: false, message: 'Sai tên đăng nhập hoặc mật khẩu!' });
    }
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// API Đăng ký
app.post('/api/register', async (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.status(400).json({ success: false, message: 'Vui lòng điền đầy đủ thông tin!' });
  }
  try {
    const today = new Date().toISOString().split('T')[0];
    await pool.query(
      'INSERT INTO users (username, password, streak, last_active, safe_mode, theme, xp) VALUES ($1, $2, 1, $3, 0, $4, 0)',
      [username, password, today, 'dark']
    );
    res.json({ success: true, message: 'Đăng ký thành công!' });
  } catch (err) {
    res.status(400).json({ success: false, message: 'Tên tài khoản đã tồn tại hoặc lỗi hệ thống!' });
  }
});

// API Lấy Bảng xếp hạng XP
app.get('/api/leaderboard', async (req, res) => {
  try {
    const result = await pool.query('SELECT username, xp, streak FROM users ORDER BY xp DESC LIMIT 10');
    res.json({ success: true, leaderboard: result.rows });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});
const fs = require('fs');
const path = require('path');

// Hàm đọc kho từ vựng
function getVocabList() {
  try {
    const filePath = path.join(__dirname, '../word_2.json');
    if (fs.existsSync(filePath)) {
      return JSON.parse(fs.readFileSync(filePath, 'utf8'));
    }
  } catch (err) {
    console.error("Lỗi đọc file word_2.json:", err);
  }
  return [
    { id: 1, unit: "Unit 1", word: "antibiotic", type: "n", pronunciation: "/ˌæntibaɪˈɒtɪk/", meaning: "thuốc kháng sinh", example: "The doctor prescribed an antibiotic for her throat infection.", level: 0, next_review: new Date().toISOString().split('T')[0] },
    { id: 2, unit: "Unit 1", word: "penguin", type: "n", pronunciation: "/ˈpeŋɡwɪn/", meaning: "chim cánh cụt", example: "Penguins live in cold climates.", level: 0, next_review: new Date().toISOString().split('T')[0] }
  ];
}

// API Lấy danh sách từ vựng ôn tập
app.get('/api/vocab', (req, res) => {
  const list = getVocabList();
  res.json({ success: true, vocab: list });
});

// API Phục vụ các file tĩnh trong thư mục frontend
app.use(express.static(path.join(__dirname, '../frontend')));
app.listen(PORT, async () => {
  console.log(`🚀 Server Penguin English đang chạy tại http://localhost:${PORT}`);
  // Tự động mở trình duyệt Chrome/Edge lên trang web ngay khi server chạy
  await open(`http://localhost:${PORT}`);
});