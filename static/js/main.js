const startBtn = document.getElementById('startBtn');
const statusEl = document.getElementById('status');
const summaryOutput = document.getElementById('summaryOutput');
const suggestionsContainer = document.getElementById('suggestionsContainer');
const toggleBtn = document.getElementById('toggle-suggestions-btn');

let recognition, recognizing = false, finalTranscript = '', pendingTranscript = '';
let autoRestart = true, suggestionsPaused = false, isRequesting = false;
const THROTTLE_INTERVAL = 30000; // 30秒

// 切換建議暫停/恢復
toggleBtn.addEventListener('click', () => {
  suggestionsPaused = !suggestionsPaused;
  toggleBtn.textContent = suggestionsPaused ? '恢復建議' : '暫停建議';
});

// 定時發送 pendingTranscript
setInterval(() => {
  if (pendingTranscript && !isRequesting) {
    isRequesting = true;
    const textToSend = pendingTranscript;
    pendingTranscript = '';

    fetch('/summarize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: textToSend, base_prompt: BASE_PROMPT, custom: CUSTOM })
    })
      .then(res => res.json())
      .then(data => {
        // 更新摘要
        let summaryText = '';
        for (const key in data.summary) {
          summaryText += `${key}：\n`;
          data.summary[key].forEach(pt => summaryText += `• ${pt}\n`);
          summaryText += '\n';
        }
        summaryOutput.value = summaryText.trim();
        summaryOutput.scrollTop = summaryOutput.scrollHeight;

        // 顯示建議
        if (!suggestionsPaused) {
          suggestionsContainer.textContent = data.suggestion;
          suggestionsContainer.scrollTop = suggestionsContainer.scrollHeight;
        }
      })
      .catch(err => console.error('摘要呼叫失敗：', err))
      .finally(() => { isRequesting = false; });
  }
}, THROTTLE_INTERVAL);

// 初始化語音辨識
if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.lang = 'zh-TW';
  recognition.continuous = true;
  recognition.interimResults = true;

  recognition.onstart = () => { 
    recognizing = true; 
    startBtn.textContent = '停止辨識'; 
    statusEl.textContent = '狀態：辨識中...'; 
  };

  recognition.onresult = (event) => {
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalTranscript += transcript + ' ';
        pendingTranscript = finalTranscript;
      }
    }
  };

  recognition.onerror = (e) => {
    console.error('語音辨識錯誤：', e.error);
    statusEl.textContent = '狀態：錯誤 - ' + e.error;

    // 避免每次錯誤都重啟，只在非no-speech錯誤時重啟
    if (autoRestart && e.error !== 'no-speech') {
      recognition.abort();
      setTimeout(() => {
        console.log('重新啟動語音辨識');
        recognition.start();
      }, 1000);
    }
  };

  recognition.onend = () => {
    // 防止在停止後無法重新開始
    if (!recognizing) {
      startBtn.textContent = '開始辨識';
      statusEl.textContent = '狀態：已停止';
    }
  };
} else {
  alert('此瀏覽器不支援語音辨識');
}

// 控制辨識啟停
startBtn.addEventListener('click', () => {
  if (!recognition) return;
  if (recognizing) { 
    recognition.stop(); 
    recognizing = false; 
    startBtn.textContent = '開始辨識';
    statusEl.textContent = '狀態：已停止';
  } else { 
    recognition.start(); 
    recognizing = true; 
    startBtn.textContent = '停止辨識'; 
    statusEl.textContent = '狀態：辨識中...'; 
  }
});
