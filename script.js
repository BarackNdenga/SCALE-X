/* SCALE-X V0.1 frontend bridge.
   Après déploiement, définir window.SCALE_X_API_URL avant ce script,
   ou conserver la valeur de secours correspondant à l’API publique Render.
*/
const API_BASE_URL = (window.SCALE_X_API_URL || 'https://scale-x-bdlg.onrender.com').replace(/\/+$/, '');

const setText = (id, value) => {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
};

const formatScore = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(1) : '—';
};

const setStatus = (message, tone = '') => {
  const status = document.getElementById('upload-status');
  if (!status) return;
  status.textContent = message;
  status.className = `upload-status ${tone}`.trim();
};

const setEvaluationStatus = (message, tone = '') => {
  const status = document.getElementById('evaluation-status');
  if (!status) return;
  status.textContent = message;
  status.className = `upload-status ${tone}`.trim();
};

const refreshModelStatus = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/model-config`, { headers: { Accept: 'application/json' } });
    const config = await response.json();
    if (!response.ok) throw new Error('API indisponible');
    if (config.configured) {
      setEvaluationStatus(`V0.2 disponible · modèle configuré : ${config.model || 'modèle actif'}`, 'ready');
    } else {
      setEvaluationStatus('V0.2 disponible · modèle non configuré sur Render.', 'error');
    }
  } catch (_) {
    setEvaluationStatus('V0.2 disponible · API Render momentanément indisponible.', 'error');
  }
};

// Le statut initial reste volontairement neutre ; l’API signale une erreur uniquement lors d’une évaluation.

const renderReport = (report) => {
  const results = document.getElementById('dashboard-results');
  if (results) results.hidden = false;

  const score = Number(report?.dfs?.score || 0);
  const components = report?.dfs?.components || {};
  const dataset = report?.dataset || {};
  const quality = report?.quality || {};
  const diversity = report?.diversity || {};
  const bias = report?.bias || {};
  const rareCases = report?.rare_cases || {};
  const linguistics = report?.linguistics || {};
  const integrity = report?.integrity || {};

  setText('dfs-score', formatScore(score));
  setText('dfs-score-ring', formatScore(score));
  setText('dfs-label', report?.dfs?.label || 'ANALYSED');
  setText('report-headline', report?.summary?.headline || 'Voici la santé de votre dataset.');
  const provenance = report?.provenance;
  setText('provenance-note', provenance?.source === 'uploaded_file' && provenance?.simulated === false
    ? `Calculé à partir de ${provenance.rows_analysed || dataset.rows || 0} ligne(s) réelle(s) · aucune simulation`
    : 'Provenance du rapport indisponible.');

  Object.entries({
    quality: components.quality,
    coverage: components.coverage,
    diversity: components.diversity,
    'rare-cases': components.rare_cases,
    consistency: components.consistency,
    integrity: components.integrity,
  }).forEach(([key, value]) => setText(`metric-${key}`, formatScore(value)));

  const ring = document.querySelector('.score-ring');
  if (ring) {
    const degrees = Math.max(0, Math.min(360, score * 3.6));
    ring.style.background = `radial-gradient(circle at 50% 50%, rgba(24,217,255,.18) 0 36%, transparent 37%), conic-gradient(var(--cyan) 0deg ${degrees}deg, rgba(24,217,255,.15) ${degrees}deg 360deg)`;
  }

  setText('dataset-overview', `${dataset.rows || 0} lignes · ${dataset.columns || 0} colonnes`);
  setText('dataset-details', `${dataset.format || 'Fichier'} · ${dataset.filename || 'dataset'} · ${dataset.parse_errors || 0} erreur(s) de lecture`);
  setText('quality-overview', `${formatScore(components.quality)} / 100`);
  setText('quality-details', `${quality.missing_cells || 0} cellule(s) manquante(s) · ${quality.duplicate_rows || 0} doublon(s) · ${quality.outlier_values || 0} outlier(s)`);
  setText('diversity-overview', `${formatScore(diversity.average_unique_ratio)} % de valeurs uniques moyennes`);
  setText('diversity-details', `${diversity.columns?.length || 0} colonne(s) profilée(s) pour la diversité des valeurs.`);

  const distribution = bias.class_distribution;
  if (distribution) {
    const classes = distribution.classes || [];
    const preview = classes.slice(0, 3).map(item => `${item.label}: ${item.share}%`).join(' · ');
    setText('bias-overview', `${distribution.class_count} classe(s) · ${distribution.column}`);
    setText('bias-details', preview || 'Distribution indisponible.');
  } else {
    setText('bias-overview', 'Signal catégoriel limité');
    setText('bias-details', bias.imbalance_note || 'Aucune colonne de classe candidate détectée.');
  }

  setText('rare-overview', `${formatScore(rareCases.score)} / 100`);
  setText('rare-details', `${rareCases.outlier_values || 0} valeur(s) extrême(s) détectée(s) avec la méthode IQR.`);
  setText('linguistics-overview', linguistics.language_estimate || 'Indéterminée');
  setText('linguistics-details', `${linguistics.word_count || 0} mot(s) · ${linguistics.average_words_per_value || 0} mot(s) par valeur textuelle en moyenne.`);

  const list = document.getElementById('recommendations-list');
  if (list) {
    list.replaceChildren();
    (report?.summary?.recommendations || ['Valider les résultats avec le contexte métier.']).forEach(recommendation => {
      const item = document.createElement('li');
      item.textContent = recommendation;
      list.appendChild(item);
    });
  }

  if (integrity.suspicious_count) {
    setStatus(`Analyse terminée. ${integrity.suspicious_count} motif(s) suspect(s) à vérifier.`, 'success');
  } else {
    setStatus('Analyse terminée. Rapport DFS disponible ci-dessous.', 'success');
  }
};

const datasetForm = document.getElementById('dataset-form');
const datasetFile = document.getElementById('dataset-file');
const analyzeButton = document.getElementById('analyze-button');

if (datasetFile) {
  datasetFile.addEventListener('change', () => {
    const file = datasetFile.files?.[0];
    setText('file-name', file ? file.name : 'Choose a file');
    if (file) setStatus(`${file.name} prêt pour l’analyse.`);
  });
}

if (datasetForm) {
  datasetForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const file = datasetFile?.files?.[0];
    if (!file) {
      setStatus('Sélectionnez un fichier CSV, JSON, JSONL ou TXT.', 'error');
      return;
    }

    const payload = new FormData();
    payload.append('file', file);
    if (analyzeButton) {
      analyzeButton.disabled = true;
      analyzeButton.innerHTML = 'Analysing <span>…</span>';
    }
    setStatus('Analyse du dataset en cours…');

    try {
      const response = await fetch(`${API_BASE_URL}/analyze`, { method: 'POST', body: payload });
      let body = {};
      try { body = await response.json(); } catch (_) { /* réponse non JSON */ }
      if (!response.ok) throw new Error(body.detail || `Erreur API (${response.status}).`);
      renderReport(body);
    } catch (error) {
      const isLocal = API_BASE_URL.includes('localhost');
      const hint = isLocal ? ' Lancez l’API avec uvicorn dans le dossier backend.' : ' Vérifiez l’URL Render et la configuration CORS.';
      setStatus(`${error.message}${hint}`, 'error');
    } finally {
      if (analyzeButton) {
        analyzeButton.disabled = false;
        analyzeButton.innerHTML = 'Analyze dataset <span>→</span>';
      }
    }
  });
}

document.querySelectorAll('a[href^="#"]').forEach(link => {
  link.addEventListener('click', event => {
    const target = document.querySelector(link.getAttribute('href'));
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});

if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) entry.target.classList.add('in-view');
    });
  }, { threshold: 0.12 });
  document.querySelectorAll('.card, .timeline-item, .founder, .dashboard-shell').forEach(element => observer.observe(element));
}

const evaluationForm = document.getElementById('evaluation-form');
const evaluationFile = document.getElementById('evaluation-file');
const evaluateButton = document.getElementById('evaluate-button');

const renderMfs = (report) => {
  const results = document.getElementById('evaluation-results');
  if (results) results.hidden = false;
  const mfs = report?.mfs || {};
  const metrics = report?.metrics || {};
  const score = mfs.score;
  setText('mfs-score', formatScore(score));
  setText('mfs-score-ring', formatScore(score));
  setText('mfs-label', mfs.label || 'UNAVAILABLE');
  setText('mfs-model', `Modèle : ${report?.model?.name || 'non renseigné'} · ${report?.dataset?.cases_evaluated || 0} cas évalué(s)`);
  setText('mfs-provenance', report?.provenance?.simulated === false
    ? `Calculé à partir de ${report.dataset?.cases_evaluated || 0} sortie(s) réellement reçue(s) · aucune simulation`
    : 'Provenance du rapport indisponible.');
  const displayMetric = (key, id, suffix = '') => setText(id, metrics[key]?.score == null ? '—' : `${formatScore(metrics[key].score)}${suffix}`);
  displayMetric('accuracy', 'mfs-accuracy');
  displayMetric('robustness', 'mfs-robustness');
  displayMetric('consistency', 'mfs-consistency');
  displayMetric('hallucination', 'mfs-hallucination');
  displayMetric('refusal', 'mfs-refusal');
  displayMetric('bias', 'mfs-bias');
  const multi = metrics.multilingualism;
  setText('mfs-dataset', `${report.dataset?.cases_evaluated || 0} cas évalué(s)`);
  setText('mfs-dataset-details', `${report.dataset?.cases_prepared || 0} cas préparé(s) · ${report.errors?.length || 0} erreur(s)`);
  setText('mfs-multilingualism', multi?.score == null ? '—' : `${formatScore(multi.score)} / 100`);
  setText('mfs-multilingualism-details', multi?.by_language ? Object.entries(multi.by_language).map(([language, value]) => `${language}: ${formatScore(value)}`).join(' · ') : 'Deux langues annotées sont nécessaires.');
  setText('mfs-errors', `${report.errors?.length || 0}`);
  setText('mfs-errors-details', report.errors?.length ? report.errors.slice(0, 2).map(error => `Cas ${error.case}: ${error.error}`).join(' · ') : 'Aucune erreur de modèle signalée.');
  const ring = document.querySelector('#evaluation-results .score-ring');
  if (ring && Number.isFinite(Number(score))) {
    const degrees = Math.max(0, Math.min(360, Number(score) * 3.6));
    ring.style.background = `radial-gradient(circle at 50% 50%, rgba(24,217,255,.18) 0 36%, transparent 37%), conic-gradient(var(--cyan) 0deg ${degrees}deg, rgba(24,217,255,.15) ${degrees}deg 360deg)`;
  }
};

if (evaluationFile) {
  evaluationFile.addEventListener('change', () => {
    const file = evaluationFile.files?.[0];
    setText('evaluation-file-name', file ? file.name : 'Choisir un fichier annoté');
  });
}

if (evaluationForm) {
  evaluationForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const file = evaluationFile?.files?.[0];
    if (!file) {
      setStatus('Sélectionnez un dataset d’évaluation.', 'error');
      return;
    }
    const criteria = [...evaluationForm.querySelectorAll('input[name="criterion"]:checked')].map(input => input.value).join(',');
    const payload = new FormData();
    payload.append('file', file);
    payload.append('criteria', criteria);
    payload.append('model_name', document.getElementById('model-name')?.value || '');
    if (evaluateButton) {
      evaluateButton.disabled = true;
      evaluateButton.innerHTML = 'Évaluation en cours <span>…</span>';
    }
    setText('evaluation-status', 'Le modèle configuré est interrogé…');
    try {
      const response = await fetch(`${API_BASE_URL}/evaluate`, { method: 'POST', body: payload });
      let body = {};
      try { body = await response.json(); } catch (_) { /* réponse non JSON */ }
      if (!response.ok) throw new Error(body.detail || `Erreur API (${response.status}).`);
      renderMfs(body);
      setText('evaluation-status', 'Évaluation terminée. Rapport MFS disponible ci-dessous.');
    } catch (error) {
      setText('evaluation-status', `${error.message} Vérifiez la configuration du modèle côté serveur.`, 'error');
    } finally {
      if (evaluateButton) {
        evaluateButton.disabled = false;
        evaluateButton.innerHTML = 'Évaluer le modèle <span>→</span>';
      }
    }
  });
}

// Remove host-injected badge/HUD nodes if they appear after the page loads.
const badgeSelectors = '#nl-badge, #netlify-badge, .netlify-badge, [id^="netlify-badge"], [class*="netlify-badge"], [data-netlify-badge]';
const stripHostNodes = (root) => {
  root.querySelectorAll?.(badgeSelectors).forEach(node => node.remove());
  root.querySelectorAll?.('script[src*="/.netlify/scripts/"]').forEach(node => node.remove());
  root.querySelectorAll?.('*').forEach(node => {
    if (node.shadowRoot) stripHostNodes(node.shadowRoot);
  });
};
const removeInjectedBadge = () => stripHostNodes(document);
removeInjectedBadge();
if (document.documentElement) {
  new MutationObserver(removeInjectedBadge).observe(document.documentElement, { childList: true, subtree: true });
}
