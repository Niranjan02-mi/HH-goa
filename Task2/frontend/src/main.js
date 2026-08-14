/**
 * Voice RAG — Main Application Logic
 *
 * State machine: idle → listening → processing → answer | declined
 * Handles: mic capture (MediaRecorder API), API calls, UI state rendering
 */

// ── API base URL ────────────────────────────────────────────
const API_BASE = window.location.hostname === 'localhost'
  ? ''  // Vite proxy handles /api → :8000
  : '';  // Same-origin in production

// ── DOM Elements ────────────────────────────────────────────
const micBtn = document.getElementById('mic-btn');
const micStatus = document.getElementById('mic-status');
const textInput = document.getElementById('text-input');
const textSendBtn = document.getElementById('text-send-btn');
const transcriptSection = document.getElementById('transcript-section');
const transcriptText = document.getElementById('transcript-text');
const answerCard = document.getElementById('answer-card');
const answerText = document.getElementById('answer-text');
const citationsEl = document.getElementById('citations');
const strategyStats = document.getElementById('strategy-stats');
const declineCard = document.getElementById('decline-card');
const declineReason = document.getElementById('decline-reason');
const declineMeta = document.getElementById('decline-meta');
const latP50 = document.getElementById('lat-p50');
const latP70 = document.getElementById('lat-p70');
const latP100 = document.getElementById('lat-p100');
const latThis = document.getElementById('lat-this');
const latCount = document.getElementById('lat-count');
const breakdown = document.getElementById('breakdown');
const breakdownGrid = document.getElementById('breakdown-grid');

// ── State ───────────────────────────────────────────────────
let state = 'idle';  // idle | listening | processing | answer | declined
let mediaRecorder = null;
let audioChunks = [];

// ── Mic Button ──────────────────────────────────────────────
micBtn.addEventListener('click', async () => {
  if (state === 'idle') {
    await startRecording();
  } else if (state === 'listening') {
    stopRecording();
  }
});

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream, { mimeType: getMimeType() });
    audioChunks = [];

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
      await processAudio(blob);
    };

    mediaRecorder.start();
    setState('listening');
  } catch (err) {
    console.error('Mic error:', err);
    micStatus.textContent = 'Microphone access denied';
    micStatus.className = 'mic-section__status';
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    setState('processing');
  }
}

function getMimeType() {
  if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) return 'audio/webm;codecs=opus';
  if (MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm';
  if (MediaRecorder.isTypeSupported('audio/mp4')) return 'audio/mp4';
  return 'audio/wav';
}

// ── Text Input ──────────────────────────────────────────────
textSendBtn.addEventListener('click', () => sendTextQuery());
textInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') sendTextQuery();
});

async function sendTextQuery() {
  const query = textInput.value.trim();
  if (!query) return;

  setState('processing');
  textInput.value = '';

  try {
    const res = await fetch(`${API_BASE}/api/query-text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    handleResponse(data);
  } catch (err) {
    console.error('Text query error:', err);
    showError(`Request failed: ${err.message}. Please try again.`);
  }
}

// ── Audio Processing ────────────────────────────────────────
async function processAudio(blob) {
  try {
    // Sarvam API strictly requires WAV/MP3 and does not support WebM.
    // We convert the browser's WebM recording to a 16-bit PCM WAV Blob in the frontend.
    const wavBlob = await blobToWav(blob);

    const formData = new FormData();
    formData.append('audio', wavBlob, 'recording.wav');

    const res = await fetch(`${API_BASE}/api/query`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    handleResponse(data);
  } catch (err) {
    console.error('Pipeline error:', err);
    showError(`Request failed: ${err.message}. Please try again.`);
  }
}

// ── Audio Format Conversion (WebM -> WAV) ───────────────────
async function blobToWav(blob) {
  const audioContext = new (window.AudioContext || window.webkitAudioContext)();
  const arrayBuffer = await blob.arrayBuffer();
  const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
  
  const numOfChan = audioBuffer.numberOfChannels;
  const length = audioBuffer.length * numOfChan * 2 + 44;
  const buffer = new ArrayBuffer(length);
  const view = new DataView(buffer);
  const channels = [];
  const sampleRate = audioBuffer.sampleRate;
  
  let offset = 0, pos = 0;

  function setUint16(data) { view.setUint16(offset, data, true); offset += 2; }
  function setUint32(data) { view.setUint32(offset, data, true); offset += 4; }

  setUint32(0x46464952); // "RIFF"
  setUint32(length - 8); // file length - 8
  setUint32(0x45564157); // "WAVE"
  setUint32(0x20746d66); // "fmt " chunk
  setUint32(16);         // length = 16
  setUint16(1);          // PCM (uncompressed)
  setUint16(numOfChan);
  setUint32(sampleRate);
  setUint32(sampleRate * 2 * numOfChan); // avg. bytes/sec
  setUint16(numOfChan * 2);              // block-align
  setUint16(16);         // 16-bit
  setUint32(0x61746164); // "data" - chunk
  setUint32(length - pos - 4); // chunk length

  for (let i = 0; i < audioBuffer.numberOfChannels; i++) {
    channels.push(audioBuffer.getChannelData(i));
  }

  while (pos < audioBuffer.length) {
    for (let i = 0; i < numOfChan; i++) {
      let sample = Math.max(-1, Math.min(1, channels[i][pos]));
      sample = (0.5 + sample < 0 ? sample * 32768 : sample * 32767) | 0;
      view.setInt16(offset, sample, true); 
      offset += 2;
    }
    pos++;
  }

  return new Blob([buffer], { type: 'audio/wav' });
}

// ── Response Handler ────────────────────────────────────────
function handleResponse(data) {
  // Show transcript
  if (data.transcript) {
    transcriptText.textContent = data.transcript;
    transcriptSection.classList.remove('hidden');
  }

  // Update latency for this query
  if (data.latency) {
    latThis.textContent = `${Math.round(data.latency.rag_ms)}ms`;
    showBreakdown(data.latency);
  }

  // Check guardrail
  if (data.guardrail && !data.guardrail.passed) {
    showDeclined(data);
    setState('declined');
  } else if (data.answer) {
    showAnswer(data);
    setState('answer');
  } else {
    showError('No answer generated.');
  }

  // Fetch live latency stats
  fetchLatencyStats();
}

// ── Show Answer ─────────────────────────────────────────────
function showAnswer(data) {
  answerText.textContent = data.answer;

  // Citations
  citationsEl.innerHTML = '';
  if (data.citations && data.citations.length > 0) {
    data.citations.forEach(c => {
      const chip = document.createElement('span');
      chip.className = 'citation-chip';
      chip.textContent = c.passage_id;
      chip.title = c.chunk_text || '';
      citationsEl.appendChild(chip);
    });
  }

  // Strategy stats
  strategyStats.innerHTML = '';
  if (data.strategy_stats && data.strategy_stats.length > 0) {
    data.strategy_stats.forEach(s => {
      const dotClass = s.strategy === 'semantic' ? 'strategy-dot--semantic'
        : s.strategy === 'sentence_window' ? 'strategy-dot--window'
        : s.strategy === 'metadata_aware' ? 'strategy-dot--meta'
        : '';
      const chip = document.createElement('span');
      chip.className = 'strategy-chip';
      chip.innerHTML = `<span class="strategy-dot ${dotClass}"></span>${s.strategy}: ${s.win_count} (avg ${s.avg_score.toFixed(3)})`;
      strategyStats.appendChild(chip);
    });
  }

  declineCard.classList.add('hidden');
  answerCard.classList.remove('hidden');
}

// ── Show Declined ───────────────────────────────────────────
function showDeclined(data) {
  const g = data.guardrail;
  declineReason.textContent = g.reason || 'Query was declined by guardrails.';

  declineMeta.innerHTML = '';
  if (g.score !== null && g.score !== undefined) {
    declineMeta.innerHTML += `<span class="decline-score">Score: ${g.score.toFixed(4)}</span>`;
  }
  if (g.threshold !== null && g.threshold !== undefined) {
    declineMeta.innerHTML += `<span class="decline-threshold">Threshold: ${g.threshold}</span>`;
  }
  if (g.status) {
    declineMeta.innerHTML += `<span>${g.status}</span>`;
  }

  answerCard.classList.add('hidden');
  declineCard.classList.remove('hidden');
}

// ── Show Breakdown ──────────────────────────────────────────
function showBreakdown(latency) {
  const items = [
    { label: 'STT', value: latency.stt_ms },
    { label: 'Embed', value: latency.embedding_ms },
    { label: 'Retrieve', value: latency.retrieval_ms },
    { label: 'Rerank', value: latency.rerank_ms },
    { label: 'Generate', value: latency.generation_ms },
    { label: 'Guard Pre', value: latency.guardrail_pre_ms },
    { label: 'Guard Post', value: latency.guardrail_post_retrieval_ms },
    { label: 'Ground Check', value: latency.guardrail_post_gen_ms },
    { label: 'RAG Total', value: latency.rag_ms },
    { label: 'Total', value: latency.total_ms },
  ];

  breakdownGrid.innerHTML = '';
  items.forEach(item => {
    if (item.value === undefined || item.value === null) return;
    const valueClass = item.value < 50 ? 'breakdown-item__value--fast'
      : item.value > 200 ? 'breakdown-item__value--slow'
      : '';
    const div = document.createElement('div');
    div.className = 'breakdown-item';
    div.innerHTML = `
      <span class="breakdown-item__label">${item.label}</span>
      <span class="breakdown-item__value ${valueClass}">${Math.round(item.value)}ms</span>
    `;
    breakdownGrid.appendChild(div);
  });

  breakdown.classList.remove('hidden');
}

// ── Show Error ──────────────────────────────────────────────
function showError(message) {
  declineReason.textContent = message;
  declineMeta.innerHTML = '';
  answerCard.classList.add('hidden');
  declineCard.classList.remove('hidden');
  setState('declined');
}

// ── State Machine ───────────────────────────────────────────
function setState(newState) {
  state = newState;

  micBtn.classList.remove('recording');

  switch (state) {
    case 'idle':
      micStatus.textContent = 'Tap to speak';
      micStatus.className = 'mic-section__status';
      break;

    case 'listening':
      micStatus.textContent = 'Listening... tap to stop';
      micStatus.className = 'mic-section__status listening';
      micBtn.classList.add('recording');
      // Hide previous results
      answerCard.classList.add('hidden');
      declineCard.classList.add('hidden');
      transcriptSection.classList.add('hidden');
      breakdown.classList.add('hidden');
      break;

    case 'processing':
      micStatus.textContent = 'Processing...';
      micStatus.className = 'mic-section__status processing';
      break;

    case 'answer':
    case 'declined':
      micStatus.textContent = 'Tap to speak again';
      micStatus.className = 'mic-section__status';
      state = 'idle';  // Reset for next query
      break;
  }
}

// ── Latency Stats Polling ───────────────────────────────────
async function fetchLatencyStats() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    if (!res.ok) return;
    const stats = await res.json();

    latP50.textContent = stats.p50_ms > 0 ? `${Math.round(stats.p50_ms)}ms` : '—';
    latP70.textContent = stats.p70_ms > 0 ? `${Math.round(stats.p70_ms)}ms` : '—';
    latP100.textContent = stats.p100_ms > 0 ? `${Math.round(stats.p100_ms)}ms` : '—';
    latCount.textContent = stats.query_count || '0';
  } catch {
    // Silent fail — stats are nice-to-have
  }
}

// Initial stats fetch
fetchLatencyStats();
// Refresh stats every 10 seconds
setInterval(fetchLatencyStats, 10000);

// ── Init ────────────────────────────────────────────────────
console.log('🎙️ Voice RAG Pipeline — HH Goa 2026 · #RAGInGoa');
