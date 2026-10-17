const API_URL = 'http://localhost:5000/api';
let currentUser = null;
let vocabList = [];
let currentWordIndex = 0;
let currentQuizWord = null;
let sentenceWords = [];
let selectedSentenceWords = [];
let correctFullSentence = "";

function showSection(id) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

// 1. ĐĂNG NHẬP & ĐĂNG KÝ
async function handleLogin() {
  const user = document.getElementById('login-user').value;
  const pwd = document.getElementById('login-pwd').value;
  if (!user || !pwd) return alert('Vui lòng nhập đầy đủ!');

  try {
    const res = await fetch(`${API_URL}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password: pwd })
    });
    const data = await res.json();
    if (data.success) {
      currentUser = { username: user, streak: data.streak || 1, xp: 0 };
      document.getElementById('user-display').innerText = `👋 Chào, ${user}!`;
      document.getElementById('user-streak').innerText = currentUser.streak;
      fetchVocab();
      showSection('sec-dashboard');
    } else {
      alert(data.message);
    }
  } catch (e) { alert('Lỗi kết nối Server!'); }
}

async function handleRegister() {
  const user = document.getElementById('reg-user').value;
  const pwd = document.getElementById('reg-pwd').value;
  try {
    const res = await fetch(`${API_URL}/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password: pwd })
    });
    const data = await res.json();
    alert(data.message);
    if (data.success) showSection('sec-login');
  } catch (e) { alert('Lỗi đăng ký!'); }
}

function logout() {
  currentUser = null;
  showSection('sec-login');
}

async function fetchVocab() {
  try {
    const res = await fetch(`${API_URL}/vocab`);
    const data = await res.json();
    if (data.success) vocabList = data.vocab;
  } catch (e) { console.error(e); }
}

// 2. FLASHCARD
function startPractice() {
  if (vocabList.length === 0) return alert('Chưa có từ vựng!');
  currentWordIndex = Math.floor(Math.random() * vocabList.length);
  renderFlashcard();
  showSection('sec-practice');
}

function renderFlashcard() {
  const item = vocabList[currentWordIndex];
  document.getElementById('fc-word').innerText = item.word;
  document.getElementById('fc-pronun').innerText = item.pronunciation;
  document.getElementById('fc-meaning').innerText = item.meaning;
  document.getElementById('fc-example').innerText = `"${item.example}"`;
}

function speakCurrentWord() {
  const word = vocabList[currentWordIndex].word;
  const ut = new SpeechSynthesisUtterance(word);
  ut.lang = 'en-US';
  window.speechSynthesis.speak(ut);
}

function nextFlashcard() {
  currentWordIndex = (currentWordIndex + 1) % vocabList.length;
  renderFlashcard();
}

async function saveCurrentWord() {
  const item = vocabList[currentWordIndex];
  await fetch(`${API_URL}/save-word`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: currentUser.username, ...item })
  });
  alert('Đã lưu vào sổ tay!');
}

// 3. TRẮC NGHIỆM
function startQuiz() {
  if (vocabList.length === 0) return alert('Chưa có từ vựng!');
  document.getElementById('quiz-msg').innerText = '';
  currentQuizWord = vocabList[Math.floor(Math.random() * vocabList.length)];
  document.getElementById('quiz-word').innerText = currentQuizWord.word;
  document.getElementById('quiz-pronun').innerText = currentQuizWord.pronunciation;

  const choicesContainer = document.getElementById('quiz-choices');
  choicesContainer.innerHTML = '';
  
  let wrong = vocabList.filter(w => w.meaning !== currentQuizWord.meaning).map(w => w.meaning);
  wrong = wrong.sort(() => 0.5 - Math.random()).slice(0, 3);
  let options = [...wrong, currentQuizWord.meaning].sort(() => 0.5 - Math.random());

  options.forEach(opt => {
    const btn = document.createElement('button');
    btn.className = 'btn-choice';
    btn.innerText = `🔹 ${opt}`;
    btn.onclick = () => checkQuiz(opt);
    choicesContainer.appendChild(btn);
  });
  showSection('sec-quiz');
}

async function checkQuiz(ans) {
  const isCorrect = ans === currentQuizWord.meaning;
  const msg = document.getElementById('quiz-msg');
  if (isCorrect) {
    msg.style.color = '#34d399';
    msg.innerText = '🎉 Chính xác! +10 XP';
    currentUser.xp += 10;
    document.getElementById('user-xp').innerText = currentUser.xp;
  } else {
    msg.style.color = '#f87171';
    msg.innerText = `❌ Sai rồi! Đáp án: ${currentQuizWord.meaning}`;
  }

  await fetch(`${API_URL}/check-quiz`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: currentUser.username, word_id: currentQuizWord.id, is_correct: isCorrect })
  });

  setTimeout(startQuiz, 1500);
}

// 4. SẮP XẾP CÂU
function startSentence() {
  const valid = vocabList.filter(v => v.example);
  if (valid.length === 0) return alert('Không có câu mẫu!');
  const item = valid[Math.floor(Math.random() * valid.length)];
  
  correctFullSentence = item.example;
  document.getElementById('st-hint').innerText = `Gợi ý: Từ "${item.word}" (${item.meaning})`;
  document.getElementById('st-msg').innerText = '';

  const clean = item.example.replace(/[.!?]/g, '');
  sentenceWords = clean.split(' ').sort(() => 0.5 - Math.random());
  selectedSentenceWords = [];
  renderSentence();
  showSection('sec-sentence');
}

function renderSentence() {
  const bank = document.getElementById('st-bank');
  const drop = document.getElementById('st-drop');
  bank.innerHTML = ''; drop.innerHTML = '';

  sentenceWords.forEach((w, idx) => {
    const btn = document.createElement('button');
    btn.className = 'chip btn-outline';
    btn.innerText = w;
    btn.onclick = () => {
      selectedSentenceWords.push(sentenceWords.splice(idx, 1)[0]);
      renderSentence();
    };
    bank.appendChild(btn);
  });

  selectedSentenceWords.forEach((w, idx) => {
    const btn = document.createElement('button');
    btn.className = 'chip';
    btn.style.background = '#8b5cf6';
    btn.innerText = w;
    btn.onclick = () => {
      sentenceWords.push(selectedSentenceWords.splice(idx, 1)[0]);
      renderSentence();
    };
    drop.appendChild(btn);
  });
}

function resetSentence() {
  sentenceWords = [...sentenceWords, ...selectedSentenceWords].sort(() => 0.5 - Math.random());
  selectedSentenceWords = [];
  renderSentence();
}

function checkSentence() {
  const userAns = selectedSentenceWords.join(' ');
  const cleanCorrect = correctFullSentence.replace(/[.!?]/g, '');
  const msg = document.getElementById('st-msg');

  if (userAns.toLowerCase() === cleanCorrect.toLowerCase()) {
    msg.style.color = '#34d399';
    msg.innerText = '🎉 Chính xác hoàn hảo!';
    setTimeout(startSentence, 1500);
  } else {
    msg.style.color = '#f87171';
    msg.innerText = '❌ Chưa đúng thứ tự, thử lại nhé!';
  }
}

// 5. BẢNG XẾP HẠNG
async function showLeaderboard() {
  try {
    const res = await fetch(`${API_URL}/leaderboard`);
    const data = await res.json();
    const list = document.getElementById('lb-list');
    list.innerHTML = '';
    data.leaderboard.forEach((u, i) => {
      const div = document.createElement('div');
      div.style.cssText = 'padding:10px; margin-bottom:6px; background:rgba(255,255,255,0.05); border-radius:8px; display:flex; justify-content:space-between;';
      div.innerHTML = `<span>#${i+1} <b>${u.username}</b></span> <span style="color:#818cf8;">${u.xp || 0} XP</span>`;
      list.appendChild(div);
    });
    showSection('sec-leaderboard');
  } catch (e) { alert('Lỗi tải Bảng xếp hạng!'); }
}

