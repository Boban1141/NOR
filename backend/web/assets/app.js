'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const pref = (key, fallback = '') => { try { return localStorage.getItem('nor.' + key) ?? fallback; } catch { return fallback; } };
  const save = (key, value) => { try { localStorage.setItem('nor.' + key, value); } catch {} };
  let language = pref('language', 'fr') === 'en' ? 'en' : 'fr';
  let authenticated = false, controller = null, generation = 0, autoActive = false, recognition = null, silence = null;
  let installPrompt = null;
  const t = (fr, en) => language === 'fr' ? fr : en;
  const node = (tag, cls, text) => { const value = document.createElement(tag); if (cls) value.className = cls; if (text != null) value.textContent = text; return value; };
  const notice = text => { $('notice').textContent = text; $('notice').hidden = !text; };
  const show = id => { if (!$(id).open) $(id).showModal(); };
  const close = id => { if ($(id).open) $(id).close(); };
  function connection(connected, label) {
    $('connection-dot').classList.toggle('offline', !connected);
    $('connection-label').textContent = label || (connected ? t('Espace privé connecté', 'Private space connected') : t('Connexion requise', 'Sign in required'));
  }
  function translate() {
    document.documentElement.lang = language;
    document.title = language === 'fr' ? 'NOR — Recherche privée' : 'NOR — Private research';
    document.querySelectorAll('[data-fr]').forEach(element => { element.textContent = element.dataset[language]; });
    $('question').placeholder = t('Que souhaitez-vous explorer ?', 'What would you like to explore?');
    $('settings-open').ariaLabel = t('Réglages', 'Settings');
    $('mic').ariaLabel = t('Dicter une question', 'Dictate a question');
    $('send').ariaLabel = t('Envoyer la question', 'Send question');
    $('language').value = language;
    connection(authenticated);
    populateVoices();
    updateVoiceSupport();
  }
  async function api(path, options = {}) {
    const response = await fetch(path, { ...options, credentials: 'same-origin', cache: 'no-store', redirect: 'error',
      headers: { 'X-NOR-Client': 'pwa', ...(options.body ? {'Content-Type': 'application/json'} : {}), ...options.headers } });
    if (!response.ok) {
      const error = new Error(response.status === 401 ? t('Code expiré ou connexion à renouveler.', 'Expired code or sign-in required.') :
        response.status === 429 ? t('NOR est occupé. Patientez avant de réessayer.', 'NOR is busy. Please wait before trying again.') :
        t('La demande n’a pas abouti. Vérifiez le serveur NOR.', 'The request failed. Check the NOR server.'));
      error.status = response.status;
      if (response.status === 401) { authenticated = false; connection(false); show('login-dialog'); }
      throw error;
    }
    return response.json();
  }
  async function checkConnection() {
    try {
      const result = await api('/capabilities');
      authenticated = true; connection(true); close('login-dialog');
      $('connection-result').textContent = t('Connexion réussie · ', 'Connection successful · ') + result.indexed_passages + t(' passages disponibles.', ' indexed passages.');
      return true;
    } catch (error) {
      connection(false, error.status === 401 ? undefined : t('PC ou réseau indisponible', 'PC or network unavailable'));
      $('connection-result').textContent = error.message;
      if (error.status !== 401) notice(t('Gardez NOR ouvert sur votre PC et Tailscale connecté sur les deux appareils.', 'Keep NOR running on your PC and Tailscale connected on both devices.'));
      return false;
    }
  }
  $('login-form').addEventListener('submit', async event => {
    event.preventDefault();
    const code = $('pair-code').value.replace(/\s/g, '');
    const token = $('access-token').value.trim();
    if (!token && !/^[0-9]{8}$/.test(code)) { $('login-error').textContent = t('Saisissez les 8 chiffres affichés sur le PC.', 'Enter the 8 digits shown on your PC.'); return; }
    $('login-submit').disabled = true; $('login-error').textContent = '';
    try {
      await api('/session', {method: 'POST', body: JSON.stringify(token ? {token} : {code})});
      $('pair-code').value = ''; $('access-token').value = '';
      authenticated = true; close('login-dialog'); notice(''); await checkConnection();
    } catch (error) { $('login-error').textContent = error.message; }
    finally { $('login-submit').disabled = false; }
  });
  $('login-dialog').addEventListener('cancel', event => { event.preventDefault(); close('login-dialog'); });
  $('settings-open').onclick = () => { $('connection-result').textContent = ''; show('settings-dialog'); };
  $('settings-close').onclick = () => close('settings-dialog');
  $('connection-test').onclick = async () => { $('connection-test').disabled = true; try { await checkConnection(); } finally { $('connection-test').disabled = false; } };
  $('language').onchange = () => { stopVoice(); language = $('language').value; save('language', language); translate(); };
  function cancelRequest() { generation++; if (controller) controller.abort(); controller = null; stopVoice(); }
  $('new-chat').onclick = () => { cancelRequest(); $('messages').replaceChildren(); $('welcome').hidden = false; $('research-status').hidden = true; $('send').disabled = false; $('question').value = ''; notice(''); };
  $('signout').onclick = async () => {
    try { await api('/session', {method:'DELETE'}); }
    catch (error) { notice(error.message); return; }
    cancelRequest(); authenticated = false; $('messages').replaceChildren(); $('welcome').hidden = false;
    $('question').value = ''; $('research-status').hidden = true; $('send').disabled = false;
    close('settings-dialog'); connection(false); show('login-dialog');
  };
  document.querySelectorAll('[data-question-fr]').forEach(button => { button.onclick = () => { $('question').value = button.dataset[language === 'fr' ? 'questionFr' : 'questionEn']; $('question').focus(); }; });
  function appendSources(parent, sources) {
    const list = node('div', 'sources-list');
    (sources || []).forEach(source => {
      const card = node('details', 'source-card');
      const summary = node('summary');
      summary.append(node('span', 'source-tag', (source.network || '').toUpperCase() + ' · ' + (source.source_id || '')));
      summary.append(document.createTextNode(source.title || t('Source', 'Source')));
      card.append(summary, node('p', '', source.excerpt || ''));
      if (source.declared_operator) card.append(node('p', 'small', source.declared_operator));
      const date = new Date(source.collected_at);
      if (!Number.isNaN(date.valueOf())) card.append(node('p', 'small', t('Collecté le ', 'Collected ') + date.toLocaleString(language)));
      card.append(node('div', 'source-url', source.url || ''));
      const copy = node('button', 'copy-source', t('Copier l’adresse', 'Copy address'));
      copy.type = 'button'; copy.onclick = async () => { try { await navigator.clipboard.writeText(source.url); copy.textContent = t('Adresse copiée', 'Address copied'); } catch { notice(t('Sélectionnez l’adresse pour la copier.', 'Select the address to copy it.')); } };
      card.append(copy); list.append(card);
    }); parent.append(list);
  }
  function renderAnswer(turn, result, responseLanguage) {
    const choose = (fr, en) => responseLanguage === 'fr' ? fr : en;
    const heading = node('div', 'answer-heading'); heading.append(node('span', 'mini-mark', 'N'), document.createTextNode('NOR'));
    turn.append(heading, node('div', 'answer-body', result.answer || choose('Aucune réponse reçue.', 'No answer received.')));
    const meta = node('div', 'answer-meta');
    meta.append(node('span', '', ((result.duration_ms || 0) / 1000).toFixed(1) + ' s'));
    meta.append(node('span', '', result.cache?.hit ? choose('Réponse récente réutilisée', 'Recent answer reused') : result.capabilities?.live_search_used ? choose('Sources actualisées', 'Sources refreshed') : choose('Sources déjà collectées', 'Previously collected sources')));
    meta.append(node('span', '', choose('Non vérifié indépendamment', 'Not independently verified'))); turn.append(meta);
    const gaps = result.research_gaps || [];
    if (gaps.length) { const box = node('div','gap-list'); const list = node('ul'); gaps.forEach(gap => list.append(node('li','',gap))); box.append(node('h3','',choose('Ce qui reste ouvert', 'Open questions')), list); turn.append(box); }
    if ((result.warnings || []).includes('single_operator_evidence')) turn.append(node('p', 'warning-note', choose('Les documents sélectionnés proviennent d’un seul groupe d’opérateurs.', 'Selected documents come from one operator group.')));
    if ((result.warnings || []).some(value => ['synthesis_unavailable','no_supported_synthesis','response_language_unavailable'].includes(value))) turn.append(node('p', 'warning-note', choose('La synthèse est limitée. Examinez les extraits ci-dessous.', 'Synthesis is limited. Review the excerpts below.')));
    appendSources(turn, result.sources);
    const read = node('button', 'answer-action', choose('Écouter', 'Listen'));
    read.onclick = () => {
      if (window.speechSynthesis?.speaking) { stopVoice(); read.textContent = choose('Écouter', 'Listen'); return; }
      stopVoice(); read.textContent = choose('Arrêter la voix', 'Stop voice');
      speak(result.answer, responseLanguage).catch(() => notice(choose('Lecture vocale locale indisponible.', 'Local voice playback unavailable.'))).finally(() => { read.textContent = choose('Écouter', 'Listen'); });
    };
    const copy = node('button','answer-action',choose('Copier la réponse','Copy answer'));
    copy.onclick = async () => { try { await navigator.clipboard.writeText(result.answer); copy.textContent = choose('Copié','Copied'); } catch {} };
    turn.append(read, copy);
  }
  async function submit() {
    const question = $('question').value.trim();
    if (controller || question.length < 2 || question.length > 2000) return;
    if (!authenticated) { show('login-dialog'); return; }
    const current = ++generation, responseLanguage = language;
    controller = new AbortController(); const signal = controller.signal;
    const payload = {question, language, network: $('network').value, refresh: $('refresh').checked, profile: $('deep').checked ? 'deep' : 'balanced'};
    const turn = node('article','turn'); turn.append(node('div','question-bubble',question)); $('messages').append(turn);
    $('welcome').hidden = true; $('question').value = ''; $('send').disabled = true; notice('');
    $('research-status').hidden = false; const started = Date.now();
    const status = () => { $('research-text').textContent = t('J’examine les sources… ', 'Examining the sources… ') + Math.floor((Date.now() - started) / 1000) + ' s'; };
    status(); const timer = setInterval(status, 1000);
    const timeout = setTimeout(() => { if (current === generation && controller) controller.abort(); }, 600000);
    turn.scrollIntoView({block:'start', behavior:'smooth'});
    if ($('read-aloud').checked || autoActive) speak(t('D’accord, laisse-moi un instant pour examiner les sources.', 'All right, give me a moment to examine the sources.'), language).catch(() => {});
    try {
      const result = await api('/research', {method:'POST', body: JSON.stringify(payload), signal});
      if (current !== generation) return;
      renderAnswer(turn, result, responseLanguage);
      if ($('read-aloud').checked || autoActive) {
        try { await speak((result.answer || '') + ' ' + (responseLanguage === 'fr' ? 'As-tu une autre question ?' : 'Do you have another question?'), responseLanguage); }
        catch { autoActive = false; $('automatic').checked = false; notice(t('La réponse est disponible. La lecture vocale locale n’a pas pu démarrer.', 'Your answer is ready. Local voice playback could not start.')); }
      }
    } catch (error) {
      if (current !== generation) return;
      turn.append(node('p','warning-note', error.name === 'AbortError' ? t('Attente interrompue sur cet appareil. La recherche peut continuer sur le PC.', 'Stopped waiting on this device. Research may continue on the PC.') : error.message));
      autoActive = false; $('automatic').checked = false;
    } finally {
      clearInterval(timer); clearTimeout(timeout);
      if (current === generation) { controller = null; $('send').disabled = false; $('research-status').hidden = true; if (autoActive) startListening(true); }
    }
  }
  $('ask-form').onsubmit = event => { event.preventDefault(); submit(); };
  $('question').onkeydown = event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && !/iPhone|iPad/.test(navigator.userAgent)) { event.preventDefault(); submit(); } };
  $('cancel').onclick = () => { if (controller) controller.abort(); stopVoice(); };

  function localVoices() { return window.speechSynthesis ? speechSynthesis.getVoices().filter(voice => voice.localService && voice.lang.toLowerCase().startsWith(language)) : []; }
  function populateVoices() {
    const selected = pref('voice.' + language); $('voice').replaceChildren();
    const voices = localVoices(); voices.forEach(voice => { const option = node('option','',voice.name + ' · ' + voice.lang); option.value = voice.voiceURI; $('voice').append(option); });
    if (voices.some(voice => voice.voiceURI === selected)) $('voice').value = selected;
    else { const preferred = voices.find(voice => /Thomas|Daniel|David|Paul|Jacques|Arthur|Oliver/i.test(voice.name)); if (preferred) $('voice').value = preferred.voiceURI; }
    if (!voices.length) $('voice').append(node('option','',t('Aucune voix locale chargée', 'No local voice loaded')));
  }
  function speak(text, selectedLanguage = language) {
    return new Promise((resolve, reject) => {
      if (!window.speechSynthesis) { reject(new Error('speech_unavailable')); return; }
      const voices = speechSynthesis.getVoices().filter(voice => voice.localService && voice.lang.toLowerCase().startsWith(selectedLanguage));
      const selected = voices.find(voice => voice.voiceURI === (selectedLanguage === language ? $('voice').value : pref('voice.' + selectedLanguage))) || voices[0];
      if (!selected) { reject(new Error('speech_unavailable')); return; }
      speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(String(text).replace(/\[S\d+\]/g,'').slice(0,8000));
      utterance.voice = selected; utterance.lang = selected.lang; utterance.rate = 0.95;
      const voiceTimeout = setTimeout(() => { speechSynthesis.cancel(); reject(new Error('speech_timeout')); }, Math.min(240000, Math.max(20000, String(text).length * 120)));
      utterance.onend = () => { clearTimeout(voiceTimeout); resolve(); }; utterance.onerror = error => { clearTimeout(voiceTimeout); reject(error); }; speechSynthesis.speak(utterance);
    });
  }
  $('voice').onchange = () => save('voice.' + language, $('voice').value);
  $('voice-preview').onclick = () => speak(t('Bonjour, je suis NOR. Prenons le temps d’examiner les sources.', 'Hello, I am NOR. Let us take a moment to examine the sources.')).catch(() => notice(t('Aucune voix locale disponible.', 'No local voice available.')));
  $('read-aloud').checked = pref('read-aloud') === 'true';
  $('read-aloud').onchange = () => { save('read-aloud', String($('read-aloud').checked)); if (!$('read-aloud').checked && window.speechSynthesis) speechSynthesis.cancel(); };
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const localRecognition = Boolean(Recognition && 'processLocally' in Recognition.prototype && typeof Recognition.available === 'function');
  function updateVoiceSupport() { $('automatic').disabled = !localRecognition; $('voice-note').textContent = localRecognition ? t('La dictée automatique utilise uniquement une reconnaissance locale disponible. Gardez NOR au premier plan.', 'Automatic dictation only uses available on-device recognition. Keep NOR in the foreground.') : t('La dictée automatique locale n’est pas disponible dans ce navigateur. Utilisez le micro du clavier de l’iPhone pour dicter votre question, puis envoyez-la.', 'Local automatic dictation is unavailable in this browser. Use the iPhone keyboard microphone to dictate your question, then send it.'); }
  function stopVoice() { autoActive = false; $('automatic').checked = false; clearTimeout(silence); if (recognition) { recognition.onend = null; recognition.abort(); recognition = null; } if (window.speechSynthesis) speechSynthesis.cancel(); $('mic').classList.remove('listening'); }
  async function startListening(sendAfter) {
    if (controller || recognition) return;
    if (!localRecognition) { notice($('voice-note').textContent); return; }
    try {
      const lang = language === 'fr' ? 'fr-FR' : 'en-US';
      if (await Recognition.available({langs:[lang], processLocally:true}) !== 'available') throw new Error('local_unavailable');
      if (sendAfter && !autoActive) return;
      const current = new Recognition(); recognition = current; current.processLocally = true; current.lang = lang; current.continuous = true; current.interimResults = true;
      current.onresult = event => { $('question').value = Array.from(event.results).map(result => result[0].transcript).join(' ').slice(0,2000); clearTimeout(silence); silence = setTimeout(() => current.stop(),3500); };
      current.onend = () => { clearTimeout(silence); recognition = null; $('mic').classList.remove('listening'); notice(''); if (sendAfter && autoActive && $('question').value.trim().length > 1) submit(); };
      current.onerror = () => { stopVoice(); notice(t('La dictée locale a été interrompue. Vous pouvez écrire votre question.', 'Local dictation stopped. You can type your question.')); };
      current.start(); $('mic').classList.add('listening'); notice(t('Je vous écoute…', 'Listening…'));
    } catch { stopVoice(); notice(t('Reconnaissance locale indisponible. Utilisez le micro du clavier ou écrivez votre question.', 'On-device recognition is unavailable. Use the keyboard microphone or type your question.')); }
  }
  $('mic').onclick = () => { if (recognition) { recognition.stop(); } else { startListening(false); } };
  $('automatic').onchange = () => { if ($('automatic').checked) { autoActive = true; $('read-aloud').checked = true; close('settings-dialog'); startListening(true); } else stopVoice(); };
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopVoice(); });
  if (window.speechSynthesis) speechSynthesis.addEventListener('voiceschanged', populateVoices);
  window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); installPrompt = event; });
  $('install').onclick = async () => { if (installPrompt) { await installPrompt.prompt(); installPrompt = null; } else show('install-dialog'); };
  $('install-close').onclick = () => close('install-dialog');
  if (window.matchMedia('(display-mode: standalone)').matches || navigator.standalone) $('install').hidden = true;
  window.addEventListener('online', checkConnection);
  window.addEventListener('offline', () => { connection(false,t('Hors connexion', 'Offline')); notice(t('Reconnectez le réseau et Tailscale pour interroger NOR.', 'Reconnect your network and Tailscale to ask NOR.')); });
  translate();
  if (location.protocol !== 'file:') {
    checkConnection();
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
  } else connection(false,t('Aperçu local · connexion requise', 'Local preview · sign-in required'));
})();
