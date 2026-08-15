/**
 * Voice RAG — Main Application Logic
 * Adapted for Vaani Studio UI
 */

const API_BASE = window.location.hostname === 'localhost' ? '' : '';

// ── DOM Elements ────────────────────────────────────────────
const recordBtn = document.getElementById('recordBtn');
const recordState = document.getElementById('recordState');
const statusText = document.getElementById('statusText');
const answerStatus = document.getElementById('answerStatus');
const queryForm = document.getElementById('queryForm');
const queryInput = document.getElementById('queryInput');
const clearBtn = document.getElementById('clearBtn');
const transcriptBox = document.getElementById('transcript');
const answerBox = document.getElementById('answer');
const sourcesGrid = document.getElementById('sources');
const metricsContainer = document.getElementById('metrics');
const languageSelect = document.getElementById('language');
const wave = document.getElementById('wave');
const requestIdEl = document.getElementById('requestId');

// ── Setup Wave ──────────────────────────────────────────────
if (wave) {
  for (let i = 0; i < 34; i++) { 
    const bar = document.createElement('i'); 
    bar.className = 'bar'; 
    wave.appendChild(bar); 
  }
}

// ── State ───────────────────────────────────────────────────
let state = 'idle'; // idle | listening | processing | answer | declined
let mediaRecorder = null;
let audioChunks = [];

// ── Helpers ─────────────────────────────────────────────────
function setStatus(text, warn = false) {
  statusText.textContent = text.toUpperCase();
  recordState.textContent = state === 'listening' ? 'LISTENING' : (warn ? 'CHECK' : 'READY');
  answerStatus.textContent = text.toUpperCase();
}

function setTranscript(text) {
  transcriptBox.replaceChildren();
  const labelNode = document.createElement('span'); 
  labelNode.className = 'label'; 
  labelNode.textContent = 'TRANSCRIPT';
  transcriptBox.append(labelNode, document.createTextNode(text || 'No transcript returned.'));
}

function updateState(newState) {
  state = newState;
  
  if (state === 'listening') {
    recordBtn.classList.add('recording');
    recordBtn.innerHTML = '<span><span class="button-dot">■</span> STOP RECORDING</span><span>↗</span>';
    wave.classList.add('is-recording');
    setStatus('LISTENING…');
  } else {
    recordBtn.classList.remove('recording');
    recordBtn.innerHTML = '<span><span class="button-dot">●</span> START RECORDING</span><span>↗</span>';
    wave.classList.remove('is-recording');
  }
}

// ── Time & Interactivity ────────────────────────────────────
function tickClock() { 
  const now = new Date(); 
  const value = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); 
  if (document.getElementById('clock')) document.getElementById('clock').textContent = value; 
  if (document.getElementById('footerTime')) document.getElementById('footerTime').textContent = `LOCAL LAB · ${value}`; 
}
tickClock(); 
setInterval(tickClock, 1000);

window.addEventListener('pointermove', event => { 
  document.documentElement.style.setProperty('--mx', `${event.clientX}px`); 
  document.documentElement.style.setProperty('--my', `${event.clientY}px`); 
});

const art = document.querySelector('.hero-art'); 
if (art) {
  window.addEventListener('pointermove', event => { 
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return; 
    const x = (event.clientX / window.innerWidth - .5) * 8; 
    const y = (event.clientY / window.innerHeight - .5) * 8; 
    art.style.transform = `translate(${x}px, ${y}px)`; 
  });
}

// ── Mic Button ──────────────────────────────────────────────
if (recordBtn) {
  recordBtn.addEventListener('click', async () => {
    if (state === 'idle' || state === 'answer' || state === 'declined') {
      await startRecording();
    } else if (state === 'listening') {
      stopRecording();
    }
  });
}

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
    updateState('listening');
    
    // reset UI
    answerBox.textContent = '';
    sourcesGrid.innerHTML = '';
    renderMetrics(null);
  } catch (err) {
    console.error('Mic error:', err);
    setStatus('MICROPHONE UNAVAILABLE', true);
    answerBox.textContent = 'This browser does not expose MediaRecorder or access was denied. Use the typed question box.';
    answerBox.dataset.status = 'blocked';
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    updateState('processing');
    setStatus('UPLOADING AUDIO…');
  }
}

function getMimeType() {
  if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) return 'audio/webm;codecs=opus';
  if (MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm';
  if (MediaRecorder.isTypeSupported('audio/mp4')) return 'audio/mp4';
  return 'audio/wav';
}

// ── Text Input ──────────────────────────────────────────────
if (queryForm) {
  queryForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query) return;

    updateState('processing');
    queryInput.value = '';
    
    setStatus('SEARCHING…'); 
    answerBox.textContent = '';
    answerBox.dataset.status = 'waiting';
    sourcesGrid.innerHTML = '';
    renderMetrics(null);

    try {
      const res = await fetch(`${API_BASE}/api/query-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await handleStream(res);
    } catch (err) {
      console.error('Text query error:', err);
      setStatus('REQUEST FAILED', true);
      answerBox.textContent = `Request failed: ${err.message}. Please try again.`;
      answerBox.dataset.status = 'blocked';
      updateState('declined');
    }
  });
}

if (clearBtn) {
  clearBtn.addEventListener('click', () => { 
    queryInput.value = ''; 
    setTranscript('Waiting for a voice or a typed question.'); 
    answerBox.textContent = 'Your answer will land here. Ask about the indexed corpus and we’ll show you the receipts.'; 
    answerBox.dataset.status = 'waiting'; 
    requestIdEl.textContent = '—'; 
    renderMetrics(null); 
    sourcesGrid.innerHTML = '<div class="source-empty">No evidence yet · ask a question above to populate the board.</div>'; 
    setStatus('WAITING'); 
    updateState('idle');
  });
}

// ── Audio Processing ────────────────────────────────────────
async function processAudio(blob) {
  try {
    // Sarvam API strictly requires WAV/MP3 and does not support WebM.
    const wavBlob = await blobToWav(blob);

    const formData = new FormData();
    formData.append('audio', wavBlob, 'recording.wav');

    const res = await fetch(`${API_BASE}/api/query`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await handleStream(res);
  } catch (err) {
    console.error('Pipeline error:', err);
    setStatus('REQUEST FAILED', true);
    answerBox.textContent = `Request failed: ${err.message}. Please try again.`;
    answerBox.dataset.status = 'blocked';
    updateState('declined');
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

// ── SSE Stream Handler ────────────────────────────────────────
async function handleStream(res) {
  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let eventType = 'message';
  
  answerBox.textContent = '';
  answerBox.dataset.status = 'answered';
  sourcesGrid.innerHTML = '';
  renderMetrics(null);
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    
    // Parse SSE lines
    let lines = buffer.split('\n');
    buffer = lines.pop(); 
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (line.startsWith('event: ')) {
        eventType = line.substring(7).trim();
      } else if (line.startsWith('data: ')) {
        const dataStr = line.substring(6).trim();
        if (dataStr) {
          try {
            const data = JSON.parse(dataStr);
            processStreamEvent(eventType, data);
          } catch (e) {
            console.error('Failed to parse stream data:', dataStr, e);
          }
        }
        eventType = 'message'; // reset
      }
    }
  }
  
  updateState('answer');
}

function processStreamEvent(eventType, data) {
  if (eventType === 'metadata') {
    if (data.transcript) {
      setTranscript(data.transcript);
    }
    setStatus('GENERATING ANSWER…');
  } else if (eventType === 'chunk') {
    answerBox.textContent += data.text;
  } else if (eventType === 'end') {
    renderSources(data.citations);
    
    let latencyData = {
      total_latency_ms: data.latency?.total_ms || data.latency?.rag_ms || 0
    };
    renderMetrics(latencyData);
    setStatus('ANSWERED WITH EVIDENCE');
  } else if (eventType === 'error') {
    setStatus('ERROR', true);
    answerBox.textContent = data.error || 'An error occurred';
    answerBox.dataset.status = 'blocked';
    updateState('declined');
  }
}

function formatMs(value) { return `${Number(value || 0).toFixed(1)} ms`; }

function renderMetrics(result) {
  if (!result) {
    metricsContainer.innerHTML = '<div class="metric"><b>READY</b><span>total</span></div><div class="metric"><b>READY</b><span>retrieval</span></div><div class="metric"><b>READY</b><span>generation</span></div><div class="metric"><b>ON</b><span>guardrails</span></div>';
    return;
  }
  
  metricsContainer.replaceChildren();
  const entries = [
    ['total', result.total_latency_ms], 
    ['retrieval', null], // Backend doesn't send detailed breakdown in this stream yet, using placeholder
    ['generation', null], 
    ['guardrails', null]
  ];
  
  entries.forEach(([name, value]) => { 
    const card = document.createElement('div'); 
    card.className = 'metric'; 
    const b = document.createElement('b'); 
    b.textContent = value == null ? (name === 'guardrails' ? 'ON' : 'READY') : formatMs(value); 
    const span = document.createElement('span'); 
    span.textContent = name; 
    card.append(b, span); 
    metricsContainer.append(card); 
  });
}

function renderSources(citations) {
  sourcesGrid.replaceChildren();
  if (!citations || !citations.length) { 
    const empty = document.createElement('div'); 
    empty.className = 'source-empty'; 
    empty.textContent = 'No evidence cited · the guardrail chose not to answer.'; 
    sourcesGrid.append(empty); 
    return; 
  }
  
  citations.forEach((citation, index) => {
    const tile = document.createElement('article'); 
    tile.className = 'source-tile';
    const top = document.createElement('div'); 
    top.className = 'source-top';
    const id = document.createElement('span'); 
    id.className = 'source-id'; 
    id.textContent = `[S${index + 1}]`; // Simplification
    const score = document.createElement('span'); 
    score.className = 'source-score'; 
    score.textContent = Number(citation.score || 0).toFixed(4); // Add score if we had it, but standard citations from API might not have it. Will just show index.
    if (citation.passage_id) {
       id.textContent = citation.passage_id;
    }
    
    top.append(id, score);
    const strategy = document.createElement('div'); 
    strategy.className = 'source-strategy'; 
    strategy.textContent = citation.strategy || 'PASSAGE';
    const text = document.createElement('p'); 
    text.className = 'source-text'; 
    text.textContent = citation.chunk_text || citation.text || '';
    const foot = document.createElement('div'); 
    foot.className = 'source-foot'; 
    const parent = document.createElement('span'); 
    parent.textContent = `PARENT —`; 
    const meta = document.createElement('span'); 
    meta.textContent = 'INDEXED'; 
    foot.append(parent, meta);
    
    tile.append(top, strategy, text, foot); 
    sourcesGrid.append(tile);
  });
}

console.log('🎙️ Voice RAG Pipeline — HH Goa 2026 · #RAGInGoa');
