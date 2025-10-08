(() => {
  const state = {
    words: [],
    stats: null,
    filters: {
      segment: 'all',
      sort: 'recent',
      search: ''
    },
    lastLanguage: null,
    isLoading: false,
    listenersAttached: false
  };

  const filterRanges = {
    all: { min: 0, max: 4 },
    new: { min: 0, max: 0 },
    learning: { min: 1, max: 2 },
    confident: { min: 3, max: 4 }
  };

  let searchDebounce = null;

  const getEl = (id) => document.getElementById(id);
  const t = (key, fallback) => (typeof window.t === 'function' ? window.t(key, fallback) : fallback);

  const elements = () => ({
    grid: getEl('words-learning-grid'),
    loading: getEl('words-learning-loading'),
    auth: getEl('words-learning-auth'),
    empty: getEl('words-learning-empty'),
    language: getEl('words-learning-language'),
    error: getEl('words-learning-error'),
    errorMessage: getEl('words-error-message'),
    total: getEl('words-total-count'),
    inprogress: getEl('words-inprogress-count'),
    confident: getEl('words-confident-count'),
    filterButtons: document.querySelectorAll('#words-filter-group .words-filter-chip'),
    searchInput: getEl('words-search-input'),
    sortSelect: getEl('words-sort-select'),
    loginBtn: getEl('words-login-button'),
    languageSelect: getEl('target-lang')
  });

  const isAuthenticated = () => window.authManager && window.authManager.isAuthenticated();

  const getNativeLanguage = () => localStorage.getItem('siluma_native') || 'en';

  const getTargetLanguage = () => {
    const langSelect = elements().languageSelect;
    if (langSelect && langSelect.value) {
      return langSelect.value;
    }
    const stored = localStorage.getItem('siluma_target');
    return stored && stored !== 'undefined' ? stored : '';
  };

  const isWordsTabActive = () => {
    const tab = document.querySelector('[data-tab="words"]');
    return !!(tab && tab.classList.contains('active'));
  };

  const setLoading = (on) => {
    const { loading } = elements();
    if (!loading) return;
    loading.style.display = on ? 'flex' : 'none';
  };

  const hideAllMessages = () => {
    const { auth, empty, language, error, grid } = elements();
    [auth, empty, language, error].forEach((el) => {
      if (el) el.style.display = 'none';
    });
    if (grid) grid.style.display = 'grid';
  };

  const showMessage = (type) => {
    const { auth, empty, language, error, grid } = elements();
    if (grid) grid.style.display = 'none';
    if (auth) auth.style.display = type === 'auth' ? 'block' : 'none';
    if (empty) empty.style.display = type === 'empty' ? 'block' : 'none';
    if (language) language.style.display = type === 'language' ? 'block' : 'none';
    if (error) error.style.display = type === 'error' ? 'block' : 'none';
  };

  const escapeHtml = (value) => String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  const familiarityLabel = (value) => {
    switch (value) {
      case 0: return t('words.learning.stage.new', 'Neu');
      case 1: return t('words.learning.stage.seen', 'Gesehen');
      case 2: return t('words.learning.stage.learning', 'In Arbeit');
      case 3: return t('words.learning.stage.confident', 'Sicher');
      case 4: return t('words.learning.stage.almost', 'Fast geschafft');
      default: return t('words.learning.stage.mastered', 'Gemeistert');
    }
  };

  const relativeTimeFormatter = () => {
    try {
      return new Intl.RelativeTimeFormat(document.documentElement.lang || 'de', { numeric: 'auto' });
    } catch (_) {
      return null;
    }
  };

  const rtf = relativeTimeFormatter();

  const formatRelativeTime = (timestamp) => {
    if (!timestamp) return t('words.learning.last_reviewed.never', 'Noch nicht geübt');
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) return t('words.learning.last_reviewed.never', 'Noch nicht geübt');
    const diffMs = date.getTime() - Date.now();
    const units = [
      { unit: 'day', ms: 86400000 },
      { unit: 'hour', ms: 3600000 },
      { unit: 'minute', ms: 60000 }
    ];
    for (const { unit, ms } of units) {
      const value = Math.round(diffMs / ms);
      if (Math.abs(value) >= 1) {
        if (rtf) {
          return rtf.format(value, unit);
        }
        const fallback = {
          day: t('words.learning.relative.days', '{n} Tage'),
          hour: t('words.learning.relative.hours', '{n} Stunden'),
          minute: t('words.learning.relative.minutes', '{n} Minuten')
        };
        return fallback[unit].replace('{n}', Math.abs(value));
      }
    }
    return t('words.learning.relative.just_now', 'Gerade eben');
  };

  const computeStats = (words) => {
    const stats = { total: words.length, inProgress: 0, confident: 0 };
    words.forEach((w) => {
      if (w.familiarity >= 1 && w.familiarity <= 2) stats.inProgress += 1;
      if (w.familiarity >= 3) stats.confident += 1;
    });
    return stats;
  };

  const applyFilters = () => {
    const { segment, search } = state.filters;
    const filterRange = filterRanges[segment] || filterRanges.all;
    const query = search.trim().toLowerCase();

    return state.words
      .filter((word) => {
        if (word.familiarity < filterRange.min || word.familiarity > filterRange.max) {
          return false;
        }
        if (!query) return true;
        const haystack = `${word.word || ''} ${word.translation || ''} ${word.example || ''}`.toLowerCase();
        return haystack.includes(query);
      });
  };

  const sortWords = (words) => {
    const { sort } = state.filters;
    const sorted = [...words];
    if (sort === 'alphabetical') {
      sorted.sort((a, b) => (a.word || '').localeCompare(b.word || '', undefined, { sensitivity: 'base' }));
    } else if (sort === 'challenge') {
      sorted.sort((a, b) => {
        const seenA = a.seen_count || 0;
        const seenB = b.seen_count || 0;
        const incorrectA = seenA - (a.correct_count || 0);
        const incorrectB = seenB - (b.correct_count || 0);
        const rateA = seenA > 0 ? incorrectA / seenA : 1;
        const rateB = seenB > 0 ? incorrectB / seenB : 1;
        if (rateA !== rateB) return rateB - rateA;
        if ((a.familiarity || 0) !== (b.familiarity || 0)) {
          return (a.familiarity || 0) - (b.familiarity || 0);
        }
        return seenB - seenA;
      });
    } else {
      sorted.sort((a, b) => {
        const timeA = a.last_reviewed ? new Date(a.last_reviewed).getTime() : 0;
        const timeB = b.last_reviewed ? new Date(b.last_reviewed).getTime() : 0;
        return timeB - timeA;
      });
    }
    return sorted;
  };

  const renderGrid = (words) => {
    const { grid } = elements();
    if (!grid) return;
    if (!words.length) {
      grid.innerHTML = '';
      showMessage('empty');
      return;
    }
    hideAllMessages();

    const cards = words.map((word) => {
      const familiarity = word.familiarity ?? 0;
      const familiarityClass = `familiarity-${Math.min(4, Math.max(0, familiarity))}`;
      const seen = word.seen_count || 0;
      const correct = word.correct_count || 0;
      const accuracy = seen > 0 ? Math.round((correct / seen) * 100) : null;
      const lastReviewed = formatRelativeTime(word.last_reviewed);
      const accuracyLabel = seen > 0
        ? `${t('words.learning.accuracy_label', 'Trefferquote')}: ${accuracy}%`
        : t('words.learning.accuracy_pending', 'Noch keine Antworten');

      const chips = [];
      if (word.pos) chips.push(escapeHtml(word.pos));
      if (word.cefr) chips.push(escapeHtml(word.cefr));
      if (word.ipa) chips.push(escapeHtml(word.ipa));

      const example = word.example ? `<p class="word-card-example">“${escapeHtml(word.example)}”</p>` : '';
      const exampleNative = word.example_native
        ? `<p class="word-card-example-native">${escapeHtml(word.example_native)}</p>`
        : '';

      const lastReviewedLabel = t('words.learning.last_reviewed', 'Zuletzt {time}').replace('{time}', lastReviewed);

      return `
        <div class="word-learning-card" data-familiarity="${familiarity}">
          <div class="word-card-header">
            <div>
              <h3 class="word-card-title">${escapeHtml(word.word)}</h3>
              ${word.translation ? `<p class="word-card-translation">${escapeHtml(word.translation)}</p>` : ''}
            </div>
            <span class="familiarity-badge ${familiarityClass}">${escapeHtml(familiarityLabel(familiarity))}</span>
          </div>
          ${chips.length ? `<div class="word-card-meta">${chips.map((chip) => `<span class="word-card-chip">${chip}</span>`).join('')}</div>` : ''}
          ${example}
          ${exampleNative}
          <div class="word-card-footer">
            <div class="word-progress">
              <span class="progress-pill">${escapeHtml(accuracyLabel)}</span>
              ${seen > 0 ? `<span>${escapeHtml(`${correct} / ${seen} ${t('words.learning.correct_answers', 'richtig')}`)}</span>` : ''}
            </div>
            <div class="word-last-reviewed">
              <span>🕒</span>
              <span>${escapeHtml(lastReviewedLabel)}</span>
            </div>
          </div>
        </div>
      `;
    }).join('');

    grid.innerHTML = cards;
  };

  const refreshView = () => {
    const stats = computeStats(state.words);
    const { total, inprogress, confident } = elements();
    if (total) total.textContent = stats.total;
    if (inprogress) inprogress.textContent = stats.inProgress;
    if (confident) confident.textContent = stats.confident;
    const filtered = applyFilters();
    const sorted = sortWords(filtered);
    renderGrid(sorted);
  };

  const buildQuery = () => {
    const params = new URLSearchParams();
    const language = getTargetLanguage();
    params.set('language', language);
    params.set('limit', '300');
    params.set('min_familiarity', '0');
    params.set('max_familiarity', '4');
    const search = state.filters.search.trim();
    if (search) {
      params.set('q', search);
    }
    return params.toString();
  };

  const fetchWords = async () => {
    const language = getTargetLanguage();
    if (!language) {
      state.words = [];
      setLoading(false);
      showMessage('language');
      return false;
    }

    if (!isAuthenticated()) {
      state.words = [];
      setLoading(false);
      showMessage('auth');
      return false;
    }

    const headers = window.authManager ? window.authManager.getAuthHeaders() || {} : {};
    headers['X-Native-Language'] = getNativeLanguage();

    const query = buildQuery();
    const response = await fetch(`/api/words/learning?${query}`, { headers });
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }
    const data = await response.json();
    if (!data.success) {
      throw new Error(data.error || 'Unknown error');
    }
    state.words = Array.isArray(data.words) ? data.words : [];
    state.stats = data.stats || null;
    state.lastLanguage = language;
    return true;
  };

  const loadData = async (force = false) => {
    if (state.isLoading) return;
    if (!force && state.words.length && state.lastLanguage === getTargetLanguage()) {
      refreshView();
      return;
    }

    state.isLoading = true;
    hideAllMessages();
    setLoading(true);

    try {
      const loaded = await fetchWords();
      if (!loaded) {
        return;
      }
      refreshView();
      if (!state.words.length) {
        showMessage('empty');
      }
    } catch (error) {
      console.error('Failed to load learning words:', error);
      const { errorMessage } = elements();
      if (errorMessage) {
        errorMessage.textContent = t('words.learning.error_copy', 'Die Wörter konnten nicht geladen werden. Bitte versuche es später noch einmal.');
      }
      showMessage('error');
    } finally {
      setLoading(false);
      state.isLoading = false;
    }
  };

  const attachListeners = () => {
    if (state.listenersAttached) return;
    const { filterButtons, searchInput, sortSelect, loginBtn, languageSelect } = elements();

    if (filterButtons) {
      filterButtons.forEach((btn) => {
        btn.addEventListener('click', () => {
          if (btn.classList.contains('active')) return;
          filterButtons.forEach((b) => b.classList.remove('active'));
          btn.classList.add('active');
          state.filters.segment = btn.dataset.filter || 'all';
          refreshView();
        });
      });
    }

    if (searchInput) {
      searchInput.addEventListener('input', (event) => {
        const value = event.target.value || '';
        state.filters.search = value;
        if (searchDebounce) clearTimeout(searchDebounce);
        searchDebounce = setTimeout(() => loadData(true), 320);
      });
    }

    if (sortSelect) {
      sortSelect.addEventListener('change', (event) => {
        state.filters.sort = event.target.value;
        refreshView();
      });
    }

    if (loginBtn) {
      loginBtn.addEventListener('click', () => {
        if (window.authManager && typeof window.authManager.showLoginModal === 'function') {
          window.authManager.showLoginModal();
        }
      });
    }

    if (languageSelect) {
      languageSelect.addEventListener('change', () => {
        if (isWordsTabActive()) {
          loadData(true);
        } else {
          state.lastLanguage = null;
        }
      });
    }

    state.listenersAttached = true;
  };

  const activate = () => {
    attachListeners();
    loadData(true);
  };

  const refresh = () => {
    loadData(true);
  };

  window.wordsTabManager = {
    activate,
    refresh
  };

  document.addEventListener('DOMContentLoaded', () => {
    attachListeners();
  });
})();
