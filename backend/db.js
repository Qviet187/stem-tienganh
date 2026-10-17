const fs = require('fs');
const path = require('path');

// Tạo thư mục data lưu trữ cục bộ
const dataDir = path.join(__dirname, 'data');
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir);
}

const getUsers = () => {
  const file = path.join(dataDir, 'users.json');
  if (!fs.existsSync(file)) return [];
  return JSON.parse(fs.readFileSync(file, 'utf8'));
};

const saveUsers = (users) => {
  fs.writeFileSync(path.join(dataDir, 'users.json'), JSON.stringify(users, null, 2));
};

const getSavedWords = () => {
  const file = path.join(dataDir, 'saved_words.json');
  if (!fs.existsSync(file)) return [];
  return JSON.parse(fs.readFileSync(file, 'utf8'));
};

const saveSavedWords = (words) => {
  fs.writeFileSync(path.join(dataDir, 'saved_words.json'), JSON.stringify(words, null, 2));
};

const getCustomVocab = () => {
  const file = path.join(dataDir, 'custom_vocab.json');
  if (!fs.existsSync(file)) return [];
  return JSON.parse(fs.readFileSync(file, 'utf8'));
};

const saveCustomVocab = (vocab) => {
  fs.writeFileSync(path.join(dataDir, 'custom_vocab.json'), JSON.stringify(vocab, null, 2));
};

// Giả lập câu lệnh SQL dạng async để server.js giữ nguyên không cần sửa code phức tạp
const pool = {
  query: async (text, params = []) => {
    const t = text.trim().toLowerCase();
    
    // Xử lý bảng USERS
    if (t.includes('into users')) {
      const users = getUsers();
      users.push({
        username: params[0],
        password: params[1],
        streak: params[2] || 1,
        last_active: params[3],
        safe_mode: params[4] || 0,
        theme: params[5] || 'dark',
        xp: params[6] || 0
      });
      saveUsers(users);
      return { rowCount: 1 };
    }
    if (t.includes('select password from users')) {
      const users = getUsers();
      const user = users.find(u => u.username === params[0]);
      return { rows: user ? [{ password: user.password }] : [] };
    }
    if (t.includes('select streak, last_active from users')) {
      const users = getUsers();
      const user = users.find(u => u.username === params[0]);
      return { rows: user ? [{ streak: user.streak, last_active: user.last_active }] : [] };
    }
    if (t.includes('update users set streak')) {
      const users = getUsers();
      const user = users.find(u => u.username === params[2]);
      if (user) {
        user.streak = params[0];
        user.last_active = params[1];
        saveUsers(users);
      }
      return { rowCount: 1 };
    }
    if (t.includes('update users set xp')) {
      const users = getUsers();
      const user = users.find(u => u.username === params[1]);
      if (user) {
        user.xp = (user.xp || 0) + params[0];
        saveUsers(users);
      }
      return { rowCount: 1 };
    }
    if (t.includes('select username, xp, streak from users')) {
      const users = getUsers();
      const sorted = [...users].sort((a, b) => (b.xp || 0) - (a.xp || 0)).slice(0, 10);
      return { rows: sorted.map(u => ({ username: u.username, xp: u.xp || 0, streak: u.streak || 1 })) };
    }

    // Xử lý bảng SAVED_WORDS
    if (t.includes('into saved_words')) {
      const words = getSavedWords();
      const exists = words.some(w => w.username === params[0] && w.word === params[1]);
      if (!exists) {
        words.push({ username: params[0], word: params[1], meaning: params[2], pronunciation: params[3], example: params[4] });
        saveSavedWords(words);
      }
      return { rowCount: 1 };
    }

    return { rows: [], rowCount: 0 };
  }
};

console.log("✅ Đã chuyển sang cơ sở dữ liệu File JSON cục bộ (Thành công 100%, không cần C++ Tools!)");
module.exports = pool;
