// Samvaad — Realtime AI Voice Playground Frontend Application

let currentCustomerId = "CUST001";
let currentCustomerData = null;
let currentSessionId = `session_${Date.now()}`;
let lastAudioUrl = null;
let isAudioPlaying = false;
let isRecording = false;
let speechRecognitionInstance = null;
let isCallActive = false;
let isMuted = false;
let callTimerInterval = null;
let callDurationSeconds = 0;
let silenceTimer = null;
const SILENCE_TIMEOUT_MS = 1350; // 1.35 seconds silence triggers hands-free submission

// DOM Elements
const customerSelector = document.getElementById("customerSelector");
const customerName = document.getElementById("customerName");
const customerLoanInfo = document.getElementById("customerLoanInfo");
const customerEmi = document.getElementById("customerEmi");
const customerDueDate = document.getElementById("customerDueDate");
const customerStatusBadge = document.getElementById("customerStatusBadge");
const messagesScroll = document.getElementById("messagesScroll");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const startCallBtn = document.getElementById("startCallBtn");
const hangupBtn = document.getElementById("hangupBtn");
const micBtn = document.getElementById("micBtn");
const micBtnLabel = document.getElementById("micBtnLabel");
const tickBtn = document.getElementById("tickBtn");
const waveform = document.getElementById("waveform");
const callOrb = document.getElementById("callOrb");
const callStatusText = document.getElementById("callStatusText");
const callSubStatus = document.getElementById("callSubStatus");
const callTimerBadge = document.getElementById("callTimerBadge");
const callTimerText = document.getElementById("callTimerText");
const lastAgentText = document.getElementById("lastAgentText");
const callOrbContainer = document.querySelector(".call-orb-container");
const toggleTelemetryBtn = document.getElementById("toggleTelemetryBtn");
const toggleAudioBtn = document.getElementById("toggleAudioBtn");
const audioBtnIcon = document.getElementById("audioBtnIcon");
const audioBtnText = document.getElementById("audioBtnText");
const voiceTagBadge = document.getElementById("voiceTagBadge");
const voiceSelector = document.getElementById("voiceSelector");
const languageSelector = document.getElementById("languageSelector");
const pillLangEn = document.getElementById("pillLangEn");
const pillLangTe = document.getElementById("pillLangTe");
const pillLangHi = document.getElementById("pillLangHi");
const pillLangTa = document.getElementById("pillLangTa");
const pillLangMl = document.getElementById("pillLangMl");
const playbackSpeed = document.getElementById("playbackSpeed");
const handsFreeToggle = document.getElementById("handsFreeToggle");
const agentAudioPlayer = document.getElementById("agentAudioPlayer");
const turnLatencyDisplay = document.getElementById("turnLatencyDisplay");

// Telemetry DOM
const detectedIntent = document.getElementById("detectedIntent");
const outcomeBadge = document.getElementById("outcomeBadge");
const toolExecutionList = document.getElementById("toolExecutionList");
const complianceWarnings = document.getElementById("complianceWarnings");
const activeSopName = document.getElementById("activeSopName");
const citationsList = document.getElementById("citationsList");
const callHistoryList = document.getElementById("callHistoryList");
const rawCustomerJson = document.getElementById("rawCustomerJson");
const rawPaymentsJson = document.getElementById("rawPaymentsJson");

// Call Transcript & Regulatory Modals
const callTranscriptModal = document.getElementById("callTranscriptModal");
const closeTranscriptModal = document.getElementById("closeTranscriptModal");
const closeTranscriptFooterBtn = document.getElementById("closeTranscriptFooterBtn");
const transcriptCustomerName = document.getElementById("transcriptCustomerName");
const transcriptCallMeta = document.getElementById("transcriptCallMeta");
const transcriptMetaBar = document.getElementById("transcriptMetaBar");
const transcriptChatBody = document.getElementById("transcriptChatBody");

const rulesModal = document.getElementById("rulesModal");
const closeRulesModal = document.getElementById("closeRulesModal");
const navSopBtn = document.getElementById("navSopBtn");
const navPromptBtn = document.getElementById("navPromptBtn");
const navAuditBtn = document.getElementById("navAuditBtn");

const PLAY_ICON_SVG = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`;
const STOP_ICON_SVG = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"></rect></svg>`;

// Initialize Application
async function initApp() {
  setupTabs();
  setupQuickPrompts();
  setupModals();
  setupEventListeners();
  await loadCustomer(currentCustomerId);
}

// Tab Switching
function setupTabs() {
  const tabs = document.querySelectorAll(".tab-button, .tab-btn");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-content-area, .tab-pane").forEach(p => p.classList.remove("active"));

      tab.classList.add("active");
      const targetId = tab.dataset.tab;
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add("active");
    });
  });
}

// Modals Handling (Call Transcript Viewer & Rules/Regulations)
window.openRulesTab = function(tabName) {
  const modal = document.getElementById("rulesModal");
  if (!modal) return;
  modal.classList.add("open");
  modal.style.display = "flex";

  const ruleTabs = document.querySelectorAll(".rules-tab-btn");
  const rulePanes = document.querySelectorAll(".rules-pane");

  ruleTabs.forEach(t => {
    if (t.dataset.ruletab === tabName) t.classList.add("active");
    else t.classList.remove("active");
  });

  rulePanes.forEach(p => {
    if (p.id === tabName) p.classList.add("active");
    else p.classList.remove("active");
  });
};

window.closeRulesModalFunc = function() {
  const modal = document.getElementById("rulesModal");
  if (modal) {
    modal.classList.remove("open");
    modal.style.display = "none";
  }
};

function setupModals() {
  const closeTranscriptFunc = (e) => {
    if (e) e.preventDefault();
    if (callTranscriptModal) {
      callTranscriptModal.classList.remove("open");
      callTranscriptModal.style.display = "none";
    }
  };

  if (closeTranscriptModal) closeTranscriptModal.addEventListener("click", closeTranscriptFunc);
  if (closeTranscriptFooterBtn) closeTranscriptFooterBtn.addEventListener("click", closeTranscriptFunc);
  if (callTranscriptModal) {
    callTranscriptModal.addEventListener("click", (e) => {
      if (e.target === callTranscriptModal) closeTranscriptFunc(e);
    });
  }

  if (closeRulesModal && rulesModal) {
    closeRulesModal.addEventListener("click", (e) => {
      e.preventDefault();
      window.closeRulesModalFunc();
    });
    rulesModal.addEventListener("click", (e) => {
      if (e.target === rulesModal) window.closeRulesModalFunc();
    });
  }

  const navFlowBtn = document.getElementById("navFlowBtn");
  if (navFlowBtn) {
    navFlowBtn.addEventListener("click", (e) => {
      e.preventDefault();
      window.openRulesTab("sopTab");
    });
  }
  if (navSopBtn) {
    navSopBtn.addEventListener("click", (e) => {
      e.preventDefault();
      window.openRulesTab("sopTab");
    });
  }
  if (navPromptBtn) {
    navPromptBtn.addEventListener("click", (e) => {
      e.preventDefault();
      window.openRulesTab("promptTab");
    });
  }
  if (navAuditBtn) {
    navAuditBtn.addEventListener("click", (e) => {
      e.preventDefault();
      window.openRulesTab("rbiTab");
    });
  }

  // Rules tabs internal navigation
  document.querySelectorAll(".rules-tab-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      window.openRulesTab(btn.dataset.ruletab);
    });
  });
}

// Quick Prompt Chips
function setupQuickPrompts() {
  document.querySelectorAll(".quick-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      chatInput.value = chip.dataset.prompt;
      handleSendMessage();
    });
  });
}

// Toggle Audio Button State
function setAudioButtonToPlay() {
  isAudioPlaying = false;
  if (callOrbContainer) callOrbContainer.classList.remove("orb-active");
  if (audioBtnIcon) audioBtnIcon.innerHTML = PLAY_ICON_SVG;
  if (audioBtnText) audioBtnText.textContent = "Replay";
  if (toggleAudioBtn) toggleAudioBtn.classList.remove("btn-stop");
}

function setAudioButtonToStop() {
  isAudioPlaying = true;
  if (callOrbContainer) {
    callOrbContainer.classList.remove("orb-listening");
    callOrbContainer.classList.add("orb-active");
  }
  if (audioBtnIcon) audioBtnIcon.innerHTML = STOP_ICON_SVG;
  if (audioBtnText) audioBtnText.textContent = "Stop";
  if (toggleAudioBtn) toggleAudioBtn.classList.add("btn-stop");
}

// Call Duration Timer
function startCallTimer() {
  callDurationSeconds = 0;
  if (callTimerInterval) clearInterval(callTimerInterval);
  if (callTimerText) callTimerText.textContent = "00:00";
  if (callTimerBadge) callTimerBadge.style.display = "inline-flex";

  callTimerInterval = setInterval(() => {
    callDurationSeconds++;
    const mins = String(Math.floor(callDurationSeconds / 60)).padStart(2, "0");
    const secs = String(callDurationSeconds % 60).padStart(2, "0");
    if (callTimerText) callTimerText.textContent = `${mins}:${secs}`;
  }, 1000);
}

function stopCallTimer() {
  if (callTimerInterval) {
    clearInterval(callTimerInterval);
    callTimerInterval = null;
  }
}

// Real-Time Call Management (Start, End, Mute)
async function startRealtimeCall() {
  if (isCallActive) return;
  isCallActive = true;
  isMuted = false;

  // Generate unique session ID for this specific call so all turns belong to one call history
  currentSessionId = `session_${currentCustomerId}_${Date.now()}`;

  // UI button transition
  if (startCallBtn) startCallBtn.style.display = "none";
  if (toggleAudioBtn) toggleAudioBtn.style.display = "flex";
  if (micBtn) micBtn.style.display = "flex";
  if (tickBtn) tickBtn.style.display = "flex";
  if (hangupBtn) hangupBtn.style.display = "flex";
  if (micBtnLabel) micBtnLabel.textContent = "Mute";
  if (micBtn) micBtn.classList.remove("muted");

  startCallTimer();

  const cust = currentCustomerData && currentCustomerData.customer ? currentCustomerData.customer : null;
  const custName = cust ? cust.name : "Customer";
  const loanId = cust ? cust.loan_id : "";
  const product = cust ? cust.product_id : "Personal Loan";

  if (callStatusText) callStatusText.textContent = "Connecting to Samvaad Agent...";
  if (callSubStatus) callSubStatus.textContent = "Establishing live voice session...";

  const greeting = `Hello ${custName}, this is Samvaad regarding your ${product} loan (${loanId}). How may I assist you today?`;
  appendMessage("assistant", greeting, null);

  const chosenVoice = voiceSelector && voiceSelector.value !== "auto" ? voiceSelector.value : null;

  try {
    const ttsRes = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: greeting,
        customer_name: custName,
        voice: chosenVoice
      })
    });

    if (ttsRes.ok) {
      const audioData = await ttsRes.json();
      if (audioData.audio_url) {
        lastAudioUrl = audioData.audio_url;
        agentAudioPlayer.src = audioData.audio_url;
        applyPlaybackSpeed();
        if (voiceTagBadge && audioData.voice_gender) {
          voiceTagBadge.textContent = `Voice: ${audioData.voice_gender}`;
        }
        await agentAudioPlayer.play();
        return;
      }
    }
  } catch (err) {
    console.warn("Could not play initial greeting TTS, jumping to listening:", err);
  }

  // Fallback: direct listening if TTS unavailable
  if (callStatusText) callStatusText.textContent = "Call In Progress";
  if (callSubStatus) callSubStatus.textContent = "Listening to you... (Speak naturally)";
  startVoiceRecording();
}

function endRealtimeCall() {
  if (!isCallActive) return;
  isCallActive = false;
  isMuted = false;

  if (silenceTimer) clearTimeout(silenceTimer);
  stopCallTimer();

  if (agentAudioPlayer) {
    agentAudioPlayer.pause();
    agentAudioPlayer.currentTime = 0;
  }
  stopVoiceRecording();

  const mins = Math.floor(callDurationSeconds / 60);
  const secs = callDurationSeconds % 60;
  const durationStr = `${mins}m ${secs}s`;

  if (callStatusText) callStatusText.textContent = "Call Ended";
  if (callSubStatus) callSubStatus.textContent = `Call completed • Duration: ${durationStr} • Click "Start Call" to dial again`;
  if (callOrbContainer) {
    callOrbContainer.classList.remove("orb-listening");
    callOrbContainer.classList.remove("orb-active");
  }

  // Restore buttons
  if (startCallBtn) startCallBtn.style.display = "flex";
  if (toggleAudioBtn) toggleAudioBtn.style.display = "none";
  if (micBtn) micBtn.style.display = "none";
  if (tickBtn) tickBtn.style.display = "none";
  if (hangupBtn) hangupBtn.style.display = "none";
  if (callTimerBadge) callTimerBadge.style.display = "none";

  // Refresh customer profile to display the updated consolidated call history
  loadCustomer(currentCustomerId);
}

function toggleMute() {
  if (!isCallActive) return;

  if (isMuted) {
    isMuted = false;
    if (micBtn) micBtn.classList.remove("muted");
    if (micBtnLabel) micBtnLabel.textContent = "Mute";
    if (callSubStatus) callSubStatus.textContent = "Listening to you... (Speak naturally)";
    startVoiceRecording();
  } else {
    isMuted = true;
    if (micBtn) micBtn.classList.add("muted");
    if (micBtnLabel) micBtnLabel.textContent = "Unmute";
    stopVoiceRecording();
    if (callSubStatus) callSubStatus.textContent = "Microphone muted. Click Unmute to speak.";
  }
}

// Speech Recognition Normalizer for Banking & Transaction References
function normalizeSpokenBankingText(text) {
  if (!text) return "";
  let s = text;

  // 1. Spoken number phrases & zeros
  s = s.replace(/\btriple\s*(?:zero|zeros|0)\b/gi, "000");
  s = s.replace(/\bdouble\s*(?:zero|zeros|0)\b/gi, "00");
  s = s.replace(/\bseventy\s*thousand\s*(?:and\s*)?two\b/gi, "70002");
  s = s.replace(/\bseventy\s*thousand\s*(?:and\s*)?one\b/gi, "70001");
  s = s.replace(/\bseventy\s*thousand\s*(?:and\s*)?three\b/gi, "70003");
  s = s.replace(/\b70\s*thousand\s*(?:and\s*)?2\b/gi, "70002");
  s = s.replace(/\b70\s*thousand\s*(?:and\s*)?1\b/gi, "70001");
  s = s.replace(/\b70\s*thousand\s*(?:and\s*)?3\b/gi, "70003");
  s = s.replace(/\b70,002\b/g, "70002");
  s = s.replace(/\b70,001\b/g, "70001");
  s = s.replace(/\b70,003\b/g, "70003");

  // 2. Split digits (e.g. "7 0 0 0 2" -> "70002", "7 0 0 2" -> "70002")
  s = s.replace(/\b7\s+0\s+0\s+0\s+2\b/gi, "70002");
  s = s.replace(/\b7\s+0\s+0\s+2\b/gi, "70002");
  s = s.replace(/\b7000\s+2\b/gi, "70002");
  s = s.replace(/\b70\s+002\b/gi, "70002");

  // 3. Spoken "TXN" phonetic misrecognitions: "tx and", "t x n", "text and", "tax and"
  s = s.replace(/\b(?:tx\s+and|text\s+and|tax\s+and|t\s+x\s+n)\b/gi, "TXN");

  // 4. "TXN" or "transaction" followed by 7002 or 70002
  // Acoustic zero-drop: "txn 7002" -> "TXN-70002"
  s = s.replace(/\b(?:TXN|TRANSACTION|REF|REFERENCE|UTR)[-\s:]*(?:70002|7002)\b/gi, "TXN-70002");
  s = s.replace(/\b(?:TXN|TRANSACTION|REF|REFERENCE|UTR)[-\s:]*(?:70001|7001)\b/gi, "TXN-70001");
  s = s.replace(/\b(?:TXN|TRANSACTION|REF|REFERENCE|UTR)[-\s:]*(?:70003|7003)\b/gi, "TXN-70003");

  // Any general "txn <digits>" -> "TXN-<digits>"
  s = s.replace(/\bTXN[-\s:]*(\d{4,6})\b/gi, "TXN-$1");

  // 5. Standalone 7002 acoustic zero-drop correction (speech recognizer hearing 7002 instead of 70002)
  s = s.replace(/\b7002\b/g, "70002");
  s = s.replace(/\b7001\b/g, "70001");
  s = s.replace(/\b7003\b/g, "70003");

  // 6. Phonetic English misrecognitions of Telugu speech
  s = s.replace(/\b(?:name|menu|nemo|nanu)\s*(?:cartoon|cotton|cat\s*nu|katana)\b/gi, "నేను కట్టను");
  s = s.replace(/\bnenu\s*(?:cartoon|cotton|cat\s*nu|katana)\b/gi, "నేను కట్టను");
  s = s.replace(/\b(?:the\s*blue\s*ladder|double\s*a\s*do|dabbu\s*ladder|the\s*blue\s*letter)\b/gi, "డబ్బులు లేవు");
  s = s.replace(/\b(?:say\s*on\s*who|chey\s*on\s*who)\b/gi, "చెయ్యను");
  s = s.replace(/\b(?:if\s*one\s*who|if\s*on\s*who)\b/gi, "ఇవ్వను");

  // Spoken Telugu balance queries (Romanized / English speech recognition phonetic captures)
  s = s.replace(/\b(?:naa?|my)\s*emi\s*(?:enter|entha|enta)?\s*(?:pending\s*on\s*the|pending\s*und[hi]{1,2}|pending|und[hi]{1,2})\b/gi, "naa emi entha pending undhi");
  s = s.replace(/\bemi\s*ent[ha]{1,2}\s*und[hi]{1,2}\b/gi, "emi entha undhi");

  // 7. Pan-Indian Spoken Numerals and Banking Terms (Telugu, Hindi, Tamil, Malayalam)
  const indicDigits = {
    // Telugu
    "జీరో": "0", "సున్నా": "0", "వన్": "1", "ఒకటి": "1", "టు": "2", "రెండు": "2",
    "త్రీ": "3", "మూడు": "3", "ఫోర్": "4", "నాలుగు": "4", "ఫైవ్": "5", "ఐదు": "5",
    "సిక్స్": "6", "ఆరు": "6", "సెవెన్": "7", "ఏడు": "7", "ఎయిట్": "8", "ఎనిమిది": "8",
    "నైన్": "9", "తొమ్మిది": "9",
    // Hindi
    "शून्य": "0", "ज़ीरो": "0", "जीरो": "0", "एक": "1", "दो": "2", "तीन": "3", "चार": "4",
    "पाँच": "5", "पांच": "5", "छह": "6", "सात": "7", "आठ": "8", "नौ": "9",
    // Tamil
    "பூஜ்ஜியம்": "0", "ஜீரோ": "0", "ஒன்று": "1", "இரண்டு": "2", "மூன்று": "3",
    "நான்கு": "4", "ஐந்து": "5", "ஆறு": "6", "ஏழு": "7", "எட்டு": "8", "ஒன்பது": "9",
    // Malayalam
    "പൂജ്യം": "0", "സീറോ": "0", "ഒന്ന്": "1", "രണ്ട്": "2", "മൂന്ന്": "3",
    "നാല്": "4", "അഞ്ച്": "5", "ആറ്": "6", "ഏഴ്": "7", "എട്ട്": "8", "ഒൻപത്": "9", "ഒമ്പത്": "9"
  };

  for (const [w, d] of Object.entries(indicDigits)) {
    s = s.replaceAll(w, ` ${d} `);
  }

  // Banking keywords across Indic scripts -> canonical TXN / NUMBER
  s = s.replace(/ట్రాన్సాక్షన్|ట్రాన్స్ఫర్|ట్రాన్సఫర్|ट्रांजैक्शन|ट्रांसफर|பரிவர்த்தனை|டிரான்ஸாக்ஷன்|ഇടപാട്|ട്രാൻസാക്ഷൻ/gi, "TXN");
  s = s.replace(/నెంబర్|నంబర్|नंबर|எண்|நம்பர்|നമ്പർ/gi, "NUMBER");
  s = s.replace(/\b([0-9])\s+([0-9])\s+([0-9])\s+([0-9])\s+([0-9])\b/g, "$1$2$3$4$5");
  s = s.replace(/\b([0-9])\s+([0-9])\s+([0-9])\s+([0-9])\b/g, "$1$2$3$4");

  // Re-run TXN resolution with normalized digits
  s = s.replace(/\b(?:TXN|NUMBER)[-\s:]*(?:70002|7002)\b/gi, "TXN-70002");
  s = s.replace(/\b(?:TXN|NUMBER)[-\s:]*(?:70001|7001)\b/gi, "TXN-70001");
  s = s.replace(/\b(?:TXN|NUMBER)[-\s:]*(?:70003|7003)\b/gi, "TXN-70003");

  return s;
}

// Pan-Indian Languages Configuration
const PAN_INDIAN_LANGS = {
  "en-IN": {
    name: "English",
    label: "Voice: English (Neerja/Prabhat)",
    femaleVoice: "en-IN-NeerjaNeural",
    maleVoice: "en-IN-PrabhatNeural",
    listening: "🎤 Listening in English... Speak naturally."
  },
  "te-IN": {
    name: "Telugu",
    label: "Voice: Telugu (Shruti/Mohan)",
    femaleVoice: "te-IN-ShrutiNeural",
    maleVoice: "te-IN-MohanNeural",
    listening: "🎤 Listening in Telugu (తెలుగు)... మీరు మాట్లాడండి"
  },
  "hi-IN": {
    name: "Hindi",
    label: "Voice: Hindi (Swara/Madhur)",
    femaleVoice: "hi-IN-SwaraNeural",
    maleVoice: "hi-IN-MadhurNeural",
    listening: "🎤 Listening in Hindi (हिन्दी)... आप बोल सकते हैं"
  },
  "ta-IN": {
    name: "Tamil",
    label: "Voice: Tamil (Pallavi/Valluvar)",
    femaleVoice: "ta-IN-PallaviNeural",
    maleVoice: "ta-IN-ValluvarNeural",
    listening: "🎤 Listening in Tamil (தமிழ்)... நீங்கள் பேசலாம்"
  },
  "ml-IN": {
    name: "Malayalam",
    label: "Voice: Malayalam (Sobhana/Midhun)",
    femaleVoice: "ml-IN-SobhanaNeural",
    maleVoice: "ml-IN-MidhunNeural",
    listening: "🎤 Listening in Malayalam (മലയാളം)... സംസാരിക്കാം"
  }
};

const LANG_PILLS = {
  "en-IN": pillLangEn,
  "te-IN": pillLangTe,
  "hi-IN": pillLangHi,
  "ta-IN": pillLangTa,
  "ml-IN": pillLangMl
};

// Interactive Speaking Language Controller
function setSpeakingLanguage(langCode, triggerRestart = true) {
  const conf = PAN_INDIAN_LANGS[langCode] || PAN_INDIAN_LANGS["en-IN"];
  const targetCode = conf ? langCode : "en-IN";

  // 1. Update UI Language Pills
  Object.entries(LANG_PILLS).forEach(([code, el]) => {
    if (el) {
      if (code === targetCode) {
        el.classList.add("active");
      } else {
        el.classList.remove("active");
      }
    }
  });

  // 2. Sync Language Selector Dropdown
  if (languageSelector) {
    languageSelector.value = targetCode;
  }

  // 3. Sync Dynamic Gender-Inverted Voice
  if (voiceSelector) {
    const isFemale = currentCustomerId === "CUST002" || currentCustomerId === "CUST004";
    voiceSelector.value = isFemale ? conf.maleVoice : conf.femaleVoice;
  }

  // 4. Update Voice Tag & Listening Status
  if (voiceTagBadge) {
    voiceTagBadge.textContent = conf.label;
  }
  if (isCallActive && callSubStatus) {
    callSubStatus.textContent = conf.listening;
  }

  // 5. Restart STT Engine for new Locale
  if (triggerRestart && isCallActive && !isMuted) {
    restartVoiceRecordingWithLanguage(targetCode);
  }
}


function restartVoiceRecordingWithLanguage(langCode) {
  if (speechRecognitionInstance) {
    isRecording = false; // prevents onend loop
    try { speechRecognitionInstance.abort(); } catch (e) {}
    speechRecognitionInstance = null;
  }
  if (isCallActive && !isMuted) {
    setTimeout(() => {
      startVoiceRecording(langCode);
    }, 120);
  }
}

// Speech Recognition Management with Hands-Free VAD (Voice Activity Detection)
function startVoiceRecording(overrideLang) {
  if (isMuted) return;

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    if (callStatusText) callStatusText.textContent = "Speech recognition not supported in this browser. Please type.";
    return;
  }

  try {
    if (speechRecognitionInstance) {
      isRecording = false;
      try { speechRecognitionInstance.abort(); } catch(e) {}
      speechRecognitionInstance = null;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;

    // Determine active speech recognition language
    let chosenLang = overrideLang;
    if (!chosenLang) {
      for (const [code, pill] of Object.entries(LANG_PILLS)) {
        if (pill && pill.classList.contains("active")) {
          chosenLang = code;
          break;
        }
      }
      if (!chosenLang && languageSelector && languageSelector.value !== "auto") {
        chosenLang = languageSelector.value;
      }
      if (!chosenLang && voiceSelector) {
        for (const code of ["te-IN", "hi-IN", "ta-IN", "ml-IN", "en-IN"]) {
          if (voiceSelector.value.startsWith(code)) {
            chosenLang = code;
            break;
          }
        }
      }
      if (!chosenLang) chosenLang = "en-IN";
    }
    recognition.lang = chosenLang;

    let preText = chatInput.value ? chatInput.value.trim() + " " : "";

    recognition.onstart = () => {
      isRecording = true;
      if (callOrbContainer) {
        callOrbContainer.classList.remove("orb-active");
        callOrbContainer.classList.add("orb-listening");
      }
      if (micBtn) micBtn.classList.add("active");
      if (tickBtn) tickBtn.classList.add("highlight");
      if (callStatusText) callStatusText.textContent = "Listening to your voice...";
      if (callSubStatus) callSubStatus.textContent = "Speak naturally. Pausing auto-sends to agent.";
    };

    recognition.onresult = (event) => {
      let speechText = "";
      for (let i = 0; i < event.results.length; i++) {
        speechText += event.results[i][0].transcript;
      }
      const rawText = (preText + speechText).trim();
      const fullText = normalizeSpokenBankingText(rawText);
      chatInput.value = fullText;

      // Real-time Script & Phonetic Pan-Indian Language Detection
      let detectedPanIndian = null;
      if (/[\u0C00-\u0C7F]|\b(naa|na|entha|enta|undhi|undi|nenu|kattanu|katta|kattalenu|cheyyanu|ivvanu|dabbu|dabbulu|paisalu|ippudu|kudaradu|avvadu|vaddu|enduku|chesanu|matladu|telugulo|telugu|kattesanu|naaku|meeru|cheppandi|eppudu|oddu|lekapothe|kattali)\b/i.test(fullText)) {
        detectedPanIndian = "te-IN";
      } else if (/[\u0900-\u097F]|\b(mera|meri|mere|kitna|kitni|baki|nhi|nahi|dunga|dungi|paisa|paise|kya|shukriya|mujhe|aap|boliye|diya|de\s*diya|karunga|karungi|karega|karenge|kripya|namaste)\b/i.test(fullText)) {
        detectedPanIndian = "hi-IN";
      } else if (/[\u0B80-\u0BFF]|\b(en|enna|evvalavu|illai|kattamaaten|panam|ippo|mudiyathu|eppadi|solunga|katti\s*aachu|vanakkam|nandri|kadan|thavanai)\b/i.test(fullText)) {
        detectedPanIndian = "ta-IN";
      } else if (/[\u0D00-\u0D7F]|\b(ente|ethra|illa|adakkilla|panam|kazhiyilla|engane|nanni|parayu|koduthu|namaskaram|ippol|tharam|kadam)\b/i.test(fullText)) {
        detectedPanIndian = "ml-IN";
      }

      if (detectedPanIndian) {
        const activePill = LANG_PILLS[detectedPanIndian];
        if (activePill && !activePill.classList.contains("active")) {
          setSpeakingLanguage(detectedPanIndian, false);
        }
      }


      if (callSubStatus && fullText) {
        callSubStatus.textContent = `You: "${fullText.length > 55 ? '...' + fullText.slice(-55) : fullText}"`;
      }

      // Hands-Free VAD: silence detection (auto-send on natural pause)
      if (silenceTimer) clearTimeout(silenceTimer);
      if (isCallActive && !isMuted && fullText.length > 0) {
        silenceTimer = setTimeout(() => {
          if (isCallActive && !isAudioPlaying && chatInput.value.trim().length > 0) {
            if (callSubStatus) callSubStatus.textContent = "Processing speech...";
            handleSendMessage();
          }
        }, SILENCE_TIMEOUT_MS);
      }
    };

    recognition.onerror = (e) => {
      console.warn("Speech recognition notice:", e.error);
      if (e.error === "no-speech") return;
      stopVoiceRecording();
      if (callStatusText) {
        if (e.error === "not-allowed") {
          callStatusText.textContent = "Microphone access blocked. Please allow mic in browser settings.";
          if (callSubStatus) callSubStatus.textContent = "Grant microphone permissions in address bar to talk live.";
        } else {
          callStatusText.textContent = `Mic notice: ${e.error}. Click Send when ready.`;
        }
      }
    };

    recognition.onend = () => {
      if (isRecording) {
        setTimeout(() => {
          if (isRecording && !isMuted) {
            try { recognition.start(); } catch (err) {}
          }
        }, 150);
      } else {
        stopVoiceRecording();
      }
    };

    speechRecognitionInstance = recognition;
    recognition.start();

  } catch (err) {
    console.error("Speech Recognition start error:", err);
    stopVoiceRecording();
    if (callStatusText) callStatusText.textContent = "Could not activate microphone.";
    if (callSubStatus) callSubStatus.textContent = "Please check microphone permissions or click mic again.";
  }
}

function stopVoiceRecording() {
  isRecording = false;
  if (silenceTimer) clearTimeout(silenceTimer);
  if (speechRecognitionInstance) {
    try { speechRecognitionInstance.stop(); } catch (e) {}
  }
  if (callOrbContainer) callOrbContainer.classList.remove("orb-listening");
  if (micBtn) micBtn.classList.remove("active");
  if (tickBtn) tickBtn.classList.remove("highlight");
}

// Event Listeners
function setupEventListeners() {
  if (customerSelector) {
    customerSelector.addEventListener("change", (e) => {
      currentCustomerId = e.target.value;
      currentSessionId = `session_${currentCustomerId}_${Date.now()}`;
      if (messagesScroll) messagesScroll.innerHTML = "";
      if (isCallActive) {
        endRealtimeCall();
      }
      loadCustomer(currentCustomerId);
    });
  }

  // Language & Voice Synchronization
  const langPillsList = [
    { el: pillLangEn, code: "en-IN" },
    { el: pillLangTe, code: "te-IN" },
    { el: pillLangHi, code: "hi-IN" },
    { el: pillLangTa, code: "ta-IN" },
    { el: pillLangMl, code: "ml-IN" }
  ];

  langPillsList.forEach(({ el, code }) => {
    if (el) {
      el.addEventListener("click", () => {
        setSpeakingLanguage(code, true);
      });
    }
  });

  if (languageSelector) {
    languageSelector.addEventListener("change", () => {
      if (languageSelector.value !== "auto") {
        setSpeakingLanguage(languageSelector.value, true);
      }
    });
  }

  if (voiceSelector) {
    voiceSelector.addEventListener("change", () => {
      for (const code of ["te-IN", "hi-IN", "ta-IN", "ml-IN", "en-IN"]) {
        if (voiceSelector.value.startsWith(code)) {
          setSpeakingLanguage(code, true);
          break;
        }
      }
    });
  }


  // Start Call Button
  if (startCallBtn) {
    startCallBtn.addEventListener("click", () => {
      startRealtimeCall();
    });
  }

  // End Call / Hang Up Button
  if (hangupBtn) {
    hangupBtn.addEventListener("click", () => {
      endRealtimeCall();
    });
  }

  // Central Orb Click — interactive call trigger & barge-in
  if (callOrb) {
    callOrb.addEventListener("click", () => {
      if (!isCallActive) {
        startRealtimeCall();
      } else if (isAudioPlaying) {
        // Barge-in: interrupt AI speech and listen immediately
        agentAudioPlayer.pause();
        agentAudioPlayer.currentTime = 0;
        setAudioButtonToPlay();
        startVoiceRecording();
      } else {
        toggleMute();
      }
    });
  }

  // Hidden send button / enter key support
  if (sendBtn) {
    sendBtn.addEventListener("click", () => {
      stopVoiceRecording();
      handleSendMessage();
    });
  }

  if (chatInput) {
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        stopVoiceRecording();
        handleSendMessage();
      }
    });
  }

  // Tick Button: Quick override to send immediately without waiting for silence
  if (tickBtn) {
    tickBtn.addEventListener("click", () => {
      if (silenceTimer) clearTimeout(silenceTimer);
      stopVoiceRecording();
      if (callStatusText) callStatusText.textContent = "Processing speech...";
      handleSendMessage();
    });
  }

  // Mic Button: In active call, acts as Mute / Barge-in
  if (micBtn) {
    micBtn.addEventListener("click", () => {
      if (isAudioPlaying) {
        // Barge-in: stop AI speaking and switch to user
        agentAudioPlayer.pause();
        agentAudioPlayer.currentTime = 0;
        setAudioButtonToPlay();
        startVoiceRecording();
      } else if (isCallActive) {
        toggleMute();
      } else {
        // Not in call yet: clicking mic starts call!
        startRealtimeCall();
      }
    });
  }

  // Toggle Audio: Play or Stop Replay
  if (toggleAudioBtn) {
    toggleAudioBtn.addEventListener("click", () => {
      if (isAudioPlaying) {
        agentAudioPlayer.pause();
        agentAudioPlayer.currentTime = 0;
        setAudioButtonToPlay();
        if (waveform) waveform.classList.remove("speaking");
        if (isCallActive && !isMuted) startVoiceRecording();
      } else {
        if (lastAudioUrl) {
          agentAudioPlayer.src = lastAudioUrl;
          applyPlaybackSpeed();
          agentAudioPlayer.play().catch(console.error);
        }
      }
    });
  }

  // Playback Speed control
  if (playbackSpeed) {
    playbackSpeed.addEventListener("change", applyPlaybackSpeed);
  }

  // Telemetry Panel Toggle
  if (toggleTelemetryBtn) {
    toggleTelemetryBtn.addEventListener("click", () => {
      const playground = document.querySelector(".voice-call-playground");
      if (playground) playground.classList.toggle("telemetry-hidden");
    });
  }

  // Audio Events for Waveform Animation & Realtime Call Flow
  if (agentAudioPlayer) {
    agentAudioPlayer.addEventListener("play", () => {
      if (callOrbContainer) {
        callOrbContainer.classList.remove("orb-listening");
        callOrbContainer.classList.add("orb-active");
      }
      if (waveform) waveform.classList.add("speaking");
      if (callStatusText) callStatusText.textContent = "AI Agent Speaking";
      if (callSubStatus) callSubStatus.textContent = "Streaming live voice audio...";
      setAudioButtonToStop();
    });

    agentAudioPlayer.addEventListener("ended", () => {
      if (callOrbContainer) callOrbContainer.classList.remove("orb-active");
      if (waveform) waveform.classList.remove("speaking");
      setAudioButtonToPlay();

      // Realtime Hands-Free Call Loop: Automatically start listening for customer's response!
      if (isCallActive && !isMuted) {
        if (callStatusText) callStatusText.textContent = "Call In Progress";
        if (callSubStatus) callSubStatus.textContent = "Listening to you... (Speak naturally)";
        setTimeout(() => {
          if (isCallActive && !isRecording && !isAudioPlaying && !isMuted) {
            startVoiceRecording();
          }
        }, 350);
      } else if (!isCallActive) {
        if (callStatusText) callStatusText.textContent = "Ready to Call";
        if (callSubStatus) callSubStatus.textContent = 'Click "Start Call" to talk live';
      }
    });

    agentAudioPlayer.addEventListener("pause", () => {
      if (callOrbContainer) callOrbContainer.classList.remove("orb-active");
      if (waveform) waveform.classList.remove("speaking");
      setAudioButtonToPlay();
    });
  }
}

function applyPlaybackSpeed() {
  if (agentAudioPlayer && playbackSpeed) {
    agentAudioPlayer.playbackRate = parseFloat(playbackSpeed.value) || 1.0;
  }
}

// Load Customer Data from API
async function loadCustomer(customerId) {
  try {
    const res = await fetch(`/api/customers/${customerId}`);
    if (!res.ok) throw new Error("Failed to load customer details");
    const data = await res.json();
    currentCustomerData = data;

    const cust = data.customer;
    if (customerName) customerName.textContent = cust.name;
    if (customerLoanInfo) {
      customerLoanInfo.textContent = `${cust.loan_id} • ${cust.product_id}`;
    }
    if (customerEmi) {
      customerEmi.textContent = `₹${cust.emi_amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
    }
    if (customerDueDate) {
      customerDueDate.textContent = cust.emi_due_date;
    }

    // Status Badge
    if (customerStatusBadge) {
      customerStatusBadge.textContent = cust.status;
      customerStatusBadge.className = `status-badge ${cust.status.toLowerCase()}`;
    }

    // Raw banking JSON tabs
    if (rawCustomerJson) rawCustomerJson.textContent = JSON.stringify(cust, null, 2);
    if (rawPaymentsJson) rawPaymentsJson.textContent = JSON.stringify(data.payments, null, 2);

    // Call History Tab
    renderCallHistory(data.call_history);

    // Setup initial greeting preview in transcript and status only when not in active call
    if (!isCallActive) {
      const greeting = `Hello ${cust.name}, this is Samvaad regarding your ${cust.product_id} loan (${cust.loan_id}). How may I assist you today?`;
      appendMessage("assistant", greeting, null);
      if (lastAgentText) lastAgentText.textContent = greeting;
      if (callStatusText) callStatusText.textContent = `Ready: ${cust.name}`;
      if (callSubStatus) callSubStatus.textContent = 'Click "Start Call" to begin realtime voice call';
    }

  } catch (err) {
    console.error("Error loading customer:", err);
  }
}

// Clean Date & Time Formatter (Indian Standard Time - Asia/Kolkata)
function formatDateTimeClean(ts) {
  if (!ts) return "Recent Call";
  try {
    let parseable = ts;
    if (typeof parseable === "string" && !parseable.includes("Z") && !parseable.includes("+") && parseable.length >= 19) {
      parseable = parseable.replace(" ", "T") + "+05:30";
    }
    const d = new Date(parseable);
    if (!isNaN(d.getTime())) {
      const datePart = d.toLocaleDateString("en-IN", {
        timeZone: "Asia/Kolkata",
        day: "numeric",
        month: "short",
        year: "numeric"
      });
      const timePart = d.toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true
      });
      return `${datePart}, ${timePart} IST`;
    }
  } catch (e) {}
  return String(ts).replace("T", " ").slice(0, 19) + " IST";
}

// Render Call History as Single Consolidated Records per Call
function renderCallHistory(calls) {
  if (!callHistoryList) return;
  callHistoryList.innerHTML = "";
  if (!calls || calls.length === 0) {
    callHistoryList.innerHTML = `<div class="placeholder-text">No previous calls on record.</div>`;
    return;
  }

  calls.forEach((c) => {
    const item = document.createElement("div");
    item.className = "call-log-item";

    const formattedTime = formatDateTimeClean(c.timestamp);
    const turnCount = c.total_turns || (c.turns ? (c.turns.length > 2 ? Math.floor(c.turns.length / 2) : 1) : 1);
    const turnCountLabel = turnCount === 1 ? "1 turn" : `${turnCount} conversation turns`;

    let cleanSummary = c.summary || "Official customer phone call on record.";
    if (typeof cleanSummary === "string" && (cleanSummary.startsWith("{") || cleanSummary.includes('"customer_message"'))) {
      try {
        const parsed = JSON.parse(cleanSummary);
        if (parsed.summary) {
          cleanSummary = parsed.summary;
        } else if (parsed.customer_message) {
          cleanSummary = `Customer: "${parsed.customer_message.slice(0, 65)}..."`;
        }
      } catch (e) {}
    }

    item.innerHTML = `
      <div class="call-log-meta">
        <span class="call-log-id-time">📞 <strong>${c.call_id}</strong> • ${formattedTime}</span>
        <span class="view-transcript-tag">📄 View Call Transcript</span>
      </div>
      <div class="call-log-pills">
        <span class="outcome-pill ${c.outcome}" style="font-size:0.72rem; padding: 2px 7px;">${c.outcome}</span>
        <span class="turns-pill">${turnCountLabel}</span>
        <span class="intent-pill">Intent: ${c.intent || "General"}</span>
      </div>
      <div class="call-log-summary">${cleanSummary}</div>
    `;

    item.addEventListener("click", () => {
      openCallTranscriptModal(c);
    });

    callHistoryList.appendChild(item);
  });
}

// Open Full Call Transcript & Audit Details Modal
function openCallTranscriptModal(call) {
  if (!callTranscriptModal) return;

  const custName = currentCustomerData && currentCustomerData.customer ? currentCustomerData.customer.name : "Customer";
  const loanId = currentCustomerData && currentCustomerData.customer ? currentCustomerData.customer.loan_id : "";
  const formattedTime = formatDateTimeClean(call.timestamp);

  if (transcriptCustomerName) {
    transcriptCustomerName.textContent = `${custName} (${loanId})`;
  }
  if (transcriptCallMeta) {
    transcriptCallMeta.textContent = `Call ID: ${call.call_id} • Date & Time: ${formattedTime}`;
  }

  const turnCount = call.total_turns || (call.turns ? (call.turns.length > 2 ? Math.floor(call.turns.length / 2) : 1) : 1);

  if (transcriptMetaBar) {
    transcriptMetaBar.innerHTML = `
      <span class="outcome-pill ${call.outcome}" style="font-size:0.72rem; padding: 2px 8px;">Outcome: ${call.outcome}</span>
      <span class="transcript-meta-chip">Intent: ${call.intent || "General"}</span>
      <span class="transcript-meta-chip">Sentiment: ${call.sentiment || "neutral"}</span>
      <span class="transcript-meta-chip">${turnCount} conversation turn${turnCount > 1 ? "s" : ""}</span>
      <span class="transcript-meta-chip">Direction: ${call.direction || "outbound"}</span>
    `;
  }

  if (transcriptChatBody) {
    transcriptChatBody.innerHTML = "";
    let turns = call.turns;

    // Fallback if turns array is not directly populated
    if (!turns || turns.length === 0) {
      if (call.summary && typeof call.summary === "string" && call.summary.startsWith("{")) {
        try {
          const pj = JSON.parse(call.summary);
          if (pj.turns) turns = pj.turns;
          else if (pj.customer_message || pj.agent_response) {
            turns = [
              { speaker: "Customer", message: pj.customer_message, timestamp: formattedTime },
              { speaker: "Samvaad Voice Agent", message: pj.agent_response, timestamp: formattedTime }
            ];
          }
        } catch (e) {}
      } else if (call.summary) {
        turns = [
          { speaker: "Official Call Summary", message: call.summary, timestamp: formattedTime }
        ];
      }
    }

    if (turns && turns.length > 0) {
      turns.forEach((t) => {
        const isCustomer = t.speaker === "Customer" || t.speaker === "user";
        const speakerClass = isCustomer ? "customer" : "agent";
        const speakerTag = isCustomer ? `👤 ${custName}` : `🎙️ Samvaad Voice Agent`;
        const turnTime = t.timestamp ? (t.timestamp.length > 12 ? formatDateTimeClean(t.timestamp) : t.timestamp) : formattedTime;

        const turnEl = document.createElement("div");
        turnEl.className = `transcript-turn ${speakerClass}`;
        turnEl.innerHTML = `
          <div class="transcript-speaker-tag">${speakerTag}</div>
          <div class="transcript-bubble">${t.message || t.text || ""}</div>
          <div class="transcript-turn-time">${turnTime}</div>
        `;
        transcriptChatBody.appendChild(turnEl);
      });
    } else {
      transcriptChatBody.innerHTML = `<div class="placeholder-text" style="color: #94a3b8; padding: 20px;">No dialogue turns recorded for this call.</div>`;
    }
  }

  callTranscriptModal.classList.add("open");
  callTranscriptModal.style.display = "flex";
}



// Handle User Message Submission
async function handleSendMessage() {
  stopVoiceRecording();

  const rawQuery = chatInput.value.trim();
  const query = normalizeSpokenBankingText(rawQuery);
  if (!query) {
    if (callStatusText) callStatusText.textContent = "Please speak or press mic first";
    if (callSubStatus) callSubStatus.textContent = "Click the microphone button to start speaking.";
    return;
  }

  chatInput.value = "";
  appendMessage("user", query, null);

  if (callOrbContainer) {
    callOrbContainer.classList.remove("orb-listening");
    callOrbContainer.classList.remove("orb-active");
  }
  if (callStatusText) callStatusText.textContent = "AI Agent Processing...";
  if (callSubStatus) callSubStatus.textContent = "Querying banking core and SOP policies...";
  if (waveform) waveform.classList.add("speaking");

  const chosenVoice = voiceSelector && voiceSelector.value !== "auto" ? voiceSelector.value : null;

  try {
    // Auto-grasp Indic language from query text if not manually set
    let chosenLang = languageSelector && languageSelector.value !== "auto" ? languageSelector.value : null;

    if (!chosenLang) {
      if (/[\u0C00-\u0C7F]|\b(naa|na|entha|enta|undhi|undi|nenu|kattanu|katta|kattalenu|cheyyanu|ivvanu|dabbu|dabbulu|paisalu|ippudu|kudaradu|avvadu|vaddu|enduku|chesanu|matladu|telugulo|telugu|kattesanu|naaku|meeru|cheppandi|eppudu|oddu|lekapothe|kattali)\b/i.test(query)) {
        chosenLang = "te-IN";
      } else if (/[\u0900-\u097F]|\b(mera|meri|mere|kitna|kitni|baki|nhi|nahi|dunga|dungi|paisa|paise|kya|shukriya|mujhe|aap|boliye|diya|de\s*diya|karunga|karungi|karega|karenge|kripya|namaste)\b/i.test(query)) {
        chosenLang = "hi-IN";
      } else if (/[\u0B80-\u0BFF]|\b(en|enna|evvalavu|illai|kattamaaten|panam|ippo|mudiyathu|eppadi|solunga|katti\s*aachu|vanakkam|nandri|kadan|thavanai)\b/i.test(query)) {
        chosenLang = "ta-IN";
      } else if (/[\u0D00-\u0D7F]|\b(ente|ethra|illa|adakkilla|panam|kazhiyilla|engane|nanni|parayu|koduthu|namaskaram|ippol|tharam|kadam)\b/i.test(query)) {
        chosenLang = "ml-IN";
      }
    }


    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        customer_id: currentCustomerId,
        message: query,
        session_id: currentSessionId,
        voice: chosenVoice,
        language: chosenLang
      })
    });

    if (!res.ok) throw new Error("Agent turn processing failed.");
    const result = await res.json();

    // Latency
    if (turnLatencyDisplay) {
      const lat = result.turn_latency_ms;
      turnLatencyDisplay.textContent = `${lat} ms`;
      turnLatencyDisplay.style.color = lat < 2500 ? "#059669" : "#d97706";
    }

    // Append Assistant response with audio
    const audioUrl = result.audio && result.audio.audio_url ? result.audio.audio_url : null;
    lastAudioUrl = audioUrl;
    appendMessage("assistant", result.response, audioUrl);

    // Update Voice Tag Badge
    if (voiceTagBadge && result.audio && result.audio.voice_gender) {
      voiceTagBadge.textContent = `Voice: ${result.audio.voice_gender}`;
    }

    // Play TTS audio automatically in playground
    if (audioUrl) {
      agentAudioPlayer.src = audioUrl;
      applyPlaybackSpeed();
      agentAudioPlayer.play().catch(e => console.log("Auto-play prevented by browser policy:", e));
    } else {
      if (callOrbContainer) callOrbContainer.classList.remove("orb-active");
      if (waveform) waveform.classList.remove("speaking");
      if (isCallActive && !isMuted) {
        if (callStatusText) callStatusText.textContent = "Call In Progress";
        if (callSubStatus) callSubStatus.textContent = "Listening to you... (Speak naturally)";
        setTimeout(() => {
          if (isCallActive && !isRecording && !isAudioPlaying && !isMuted) {
            startVoiceRecording();
          }
        }, 350);
      } else {
        if (callStatusText) callStatusText.textContent = "Call Connected • Ready";
        if (callSubStatus) callSubStatus.textContent = "Press mic to speak or select another account";
      }
    }

    // Update Telemetry Panel
    updateTelemetry(result);

    // Refresh historical list
    loadCustomer(currentCustomerId);

  } catch (err) {
    console.error("Error processing turn:", err);
    if (callOrbContainer) callOrbContainer.classList.remove("orb-active");
    if (waveform) waveform.classList.remove("speaking");
    if (callStatusText) callStatusText.textContent = "Connection Error";
    if (callSubStatus) callSubStatus.textContent = "Failed to reach server. Please try again.";
    appendMessage("assistant", "I apologize, there was an issue processing your request. Please try again.", null);
  }
}

// Append Message to Transcript UI
function appendMessage(role, text, audioUrl) {
  if (role === "assistant") {
    if (lastAgentText) lastAgentText.textContent = text;
  } else if (role === "user") {
    if (callSubStatus) callSubStatus.textContent = `You: "${text}"`;
  }

  if (!messagesScroll) return;
  const item = document.createElement("div");
  item.className = `message-item ${role}`;

  const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  let audioBtnHtml = "";
  if (role === "assistant" && audioUrl) {
    audioBtnHtml = `
      <button class="play-audio-btn" onclick="toggleInlineAudio(this, '${audioUrl}')">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
        <span>Play Voice</span>
      </button>
    `;
  }

  const senderName = role === "user" ? (currentCustomerData && currentCustomerData.customer ? currentCustomerData.customer.name : "Customer") : "Samvaad AI Agent";

  item.innerHTML = `
    <div class="message-bubble">${text}</div>
    <div class="message-meta">
      <span>${senderName} • ${now}</span>
      ${audioBtnHtml}
    </div>
  `;

  messagesScroll.appendChild(item);
  messagesScroll.scrollTop = messagesScroll.scrollHeight;
}

// Inline audio toggle per message (Play / Stop)
window.toggleInlineAudio = function(btn, url) {
  const labelSpan = btn.querySelector("span");
  
  if (isAudioPlaying && agentAudioPlayer.src.includes(url.split("/").pop())) {
    agentAudioPlayer.pause();
    agentAudioPlayer.currentTime = 0;
    labelSpan.textContent = "Play Voice";
    return;
  }
  
  agentAudioPlayer.src = url;
  lastAudioUrl = url;
  applyPlaybackSpeed();
  agentAudioPlayer.play().catch(console.error);
  labelSpan.textContent = "Stop Voice";

  agentAudioPlayer.addEventListener("ended", function handler() {
    labelSpan.textContent = "Play Voice";
    agentAudioPlayer.removeEventListener("ended", handler);
  });
};

// Update Telemetry Panel & Citations Tab
function updateTelemetry(result) {
  if (detectedIntent) detectedIntent.textContent = result.intent;
  if (outcomeBadge) {
    outcomeBadge.textContent = result.outcome;
    outcomeBadge.className = `outcome-pill ${result.outcome}`;
  }

  // Tools Executed
  if (toolExecutionList) {
    toolExecutionList.innerHTML = "";
    if (result.tool_executions && result.tool_executions.length > 0) {
      result.tool_executions.forEach(exec => {
        const div = document.createElement("div");
        div.className = "tool-log-item";
        div.innerHTML = `
          <div style="font-weight:600; color:var(--primary-blue);">${exec.tool}</div>
          <div style="color:var(--text-muted); font-size:0.72rem;">Params: ${JSON.stringify(exec.params)}</div>
          <div style="color:var(--status-green); font-size:0.72rem;">Result: ${JSON.stringify(exec.result)}</div>
        `;
        toolExecutionList.appendChild(div);
      });
    } else {
      toolExecutionList.innerHTML = `<div class="placeholder-text">No database tools executed in this turn.</div>`;
    }
  }

  // Compliance Warnings
  if (complianceWarnings) {
    if (result.compliance_warnings && result.compliance_warnings.length > 0) {
      complianceWarnings.innerHTML = result.compliance_warnings.map(w => `• ${w}`).join("<br>");
    } else {
      complianceWarnings.innerHTML = "";
    }
  }

  // Active SOP
  if (activeSopName) {
    if (result.intent === "ALREADY_PAID") activeSopName.textContent = "Already Paid SOP (sop/already_paid.md)";
    else if (result.intent === "HARDSHIP") activeSopName.textContent = "Financial Hardship SOP (sop/financial_hardship.md)";
    else if (result.intent === "DISPUTE") activeSopName.textContent = "Payment Dispute SOP (sop/dispute.md)";
    else if (result.intent === "REFUSAL_TO_PAY") activeSopName.textContent = "Refusal to Pay SOP (sop/refusal_to_pay.md)";
    else activeSopName.textContent = "Policy & General Guidance (data/policies)";
  }

  // Citations List
  if (citationsList) {
    citationsList.innerHTML = "";
    if (result.citations && result.citations.length > 0) {
      result.citations.forEach(c => {
        const card = document.createElement("div");
        card.className = "citation-card";
        card.innerHTML = `
          <div class="citation-header">
            <span>${c.title}</span>
            <span style="font-family:var(--font-mono); font-size:0.72rem; color:var(--text-muted);">Score: ${c.score}</span>
          </div>
          <div style="font-size: 0.72rem; color: var(--text-dim); margin-bottom: 4px;">
            Source: ${c.source} ${c.version ? "• Version: " + c.version : ""}
          </div>
          <div class="citation-snippet">${c.snippet}</div>
        `;
        citationsList.appendChild(card);
      });
    } else {
      citationsList.innerHTML = `<div class="placeholder-text">No policy citations required for this direct tool action.</div>`;
    }
  }
}

// Start application
window.addEventListener("DOMContentLoaded", initApp);
