/* Static evidence exploration only. No inference, uploads or operational API. */
(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  const node = (tag, text, className) => { const item = document.createElement(tag); if (text !== undefined) item.textContent = String(text); if (className) item.className = className; return item; };
  const number = value => new Intl.NumberFormat('en-GB', { maximumFractionDigits: 3 }).format(value);
  const percent = value => new Intl.NumberFormat('en-GB', { style: 'percent', maximumFractionDigits: 2 }).format(value);
  const modeName = mode => mode === 'local_causal' ? 'Local causal LLM' : mode === 'native' ? 'Native reference' : mode;
  function officialLink(url) {
    try { const parsed = new URL(url); if (parsed.protocol !== 'https:' || !['www.easa.europa.eu', 'eur-lex.europa.eu'].includes(parsed.hostname)) return null; const link = node('a', 'Original official source ↗'); link.href = parsed.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; return link; } catch { return null; }
  }
  const tabs = [...document.querySelectorAll('[data-view]')];
  function selectView(index, focus = false) {
    tabs.forEach((tab, i) => { tab.setAttribute('aria-selected', String(i === index)); tab.tabIndex = i === index ? 0 : -1; byId('view-' + tab.dataset.view).hidden = i !== index; });
    if (focus) tabs[index].focus();
  }
  tabs.forEach((tab, index) => { tab.addEventListener('click', () => selectView(index)); tab.addEventListener('keydown', event => { let next; if (event.key === 'ArrowRight') next = (index + 1) % tabs.length; if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length; if (event.key === 'Home') next = 0; if (event.key === 'End') next = tabs.length - 1; if (next !== undefined) { event.preventDefault(); selectView(next, true); } }); });

  function renderComparison(evidence) {
    const questions = [...new Set(evidence.comparison.trials.map(trial => trial.question))];
    for (const question of questions) { const option = node('option', question); option.value = question; byId('query-select').append(option); }
    function render() {
      byId('comparison-body').replaceChildren();
      for (const trial of evidence.comparison.trials.filter(item => item.question === byId('query-select').value)) {
        const row = node('tr'); const mode = node('td', modeName(trial.mode)); mode.append(node('small', 'Recorded run ' + trial.record_order)); row.append(mode);
        row.append(node('td', trial.state, 'gate'), node('td', trial.target_section_retrieved ? 'Yes / structural target' : 'No'), node('td', trial.citation_count), node('td', trial.model_calls_with_generation), node('td', number(trial.seconds) + ' s'));
        byId('comparison-body').append(row);
      }
    }
    byId('query-select').addEventListener('change', render); render();
    byId('first-summary').textContent = evidence.first_experiment.steps + ' steps · ' + number(evidence.first_experiment.elapsed_seconds) + ' s · ' + evidence.first_experiment.state;
    byId('ui-summary').textContent = evidence.ui_workflow.trace.length + ' steps · ' + evidence.ui_workflow.citation_count + ' cited passages · ' + evidence.ui_workflow.state;
    byId('ui-period').textContent = 'Preserved trace: ' + evidence.ui_workflow.trace_start + ' to ' + evidence.ui_workflow.trace_end + '. The ' + number(evidence.ui_workflow.trace_span_seconds) + '-second span is computed from these separate timestamps, including gaps between steps.';
  }

  function renderWorkflow(evidence) {
    const workflow = evidence.ui_workflow;
    byId('workflow-question').textContent = workflow.question;
    byId('review-state').textContent = workflow.state + ' / approval granted: ' + String(workflow.review_gate.approval_granted);
    const buttons = [];
    function show(index) {
      const step = workflow.trace[index]; buttons.forEach((button, i) => { if (i === index) button.setAttribute('aria-current', 'step'); else button.removeAttribute('aria-current'); });
      byId('step-tool').textContent = step.tool; byId('step-specialist').textContent = step.specialist;
      const facts = [['Stored state', step.state], ['Controller version', step.model?.version || 'Unavailable in record'], ['Generative model used', String(step.model?.generative_model_used === true)], ['Step start', step.started_at], ['Step end', step.finished_at], ['Complete step duration', number(step.step_seconds) + ' s'], ['Controller generation duration', typeof step.model?.seconds === 'number' ? number(step.model.seconds) + ' s' : 'Not recorded'], ['Input / output tokens', String(step.model?.input_tokens ?? 'Not recorded') + ' / ' + String(step.model?.output_tokens ?? 'Not recorded')], ['Input snapshot SHA-256', step.input_snapshot], ['Artifact identity', step.artifact_id]];
      byId('step-facts').replaceChildren(); for (const [name, value] of facts) { const cell = node('div'); cell.append(node('dt', name), node('dd', value)); byId('step-facts').append(cell); }
      byId('step-proposal').textContent = JSON.stringify(step.proposal, null, 2);
    }
    workflow.trace.forEach((step, index) => { const item = node('li'); const button = node('button'); button.type = 'button'; button.append(node('span', String(index + 1).padStart(2, '0') + ' / ' + step.tool), node('small', step.state)); button.addEventListener('click', () => show(index)); item.append(button); byId('step-list').append(item); buttons.push(button); });
    show(0);
  }

  function citationCard(source, heading) {
    const article = node('article', undefined, 'citation'); article.append(node('h3', heading || source.title || source.source_id));
    const meta = node('div', undefined, 'meta'); for (const text of [source.source_id, source.document_version, source.legal_status, source.methodology].filter(Boolean)) meta.append(node('span', text)); article.append(meta);
    article.append(node('blockquote', source.text), node('p', 'Preserved block: ' + source.anchor, 'anchor'));
    const link = officialLink(source.source_url); if (link) article.append(link);
    const details = node('details'); details.append(node('summary', 'Source integrity reference'), node('p', 'SHA-256: ' + source.source_checksum)); article.append(details); return article;
  }
  function renderSources(evidence) {
    const all = evidence.ui_workflow.citations;
    function show() { const term = byId('source-search').value.trim().toLowerCase(); const rows = all.filter(source => [source.title, source.text, source.source_id, source.anchor].join(' ').toLowerCase().includes(term)); byId('citation-list').replaceChildren(); for (const source of rows) byId('citation-list').append(citationCard(source)); byId('citation-count').textContent = rows.length + ' of ' + all.length + ' recorded passages'; if (!rows.length) byId('citation-list').append(node('p', 'No bundled passage matches this filter. No new source retrieval was performed.', 'qualification')); }
    byId('source-search').addEventListener('input', show); show();
  }

  function renderStudent(evidence) {
    const student = evidence.student;
    byId('student-status').textContent = student.promotion_status;
    byId('student-dataset').textContent = student.dataset.rows + ' real source passages; ' + student.dataset.quarantined_rows + ' quarantined annotations; ' + student.dataset.accepted_rows + ' accepted machine-generated annotations. Human-reviewed rows: ' + student.dataset.human_reviewed_rows + '.';
    const names = { student: 'Trained neural student', deterministic_modal: 'Deterministic literal-word baseline', lexical_trained_linear: 'Trained hashed lexical linear baseline', pretrained_prototype: 'Frozen pretrained prototype baseline', majority: 'Training-majority baseline' };
    for (const [name, label] of Object.entries(names)) { const result = student.evaluation[name]; const row = node('tr'); row.append(node('td', label), node('td', percent(result.accuracy)), node('td', result.samples), node('td', number(result.brier_score))); byId('student-body').append(row); }
    for (const [index, failure] of student.failure_cases.entries()) { const card = citationCard(failure, 'Recorded failure ' + (index + 1)); const labels = node('p', 'Machine label: ' + failure.machine_label + ' / Student output: ' + failure.student_label, 'failure-labels'); card.insertBefore(labels, card.querySelector('blockquote')); byId('failure-list').append(card); }
  }

  function renderScreens(evidence) {
    const select = byId('screen-select');
    function show() { if (!evidence.media.includes(select.value)) return; byId('screen-image').src = 'media/' + select.value; byId('screen-full').href = 'media/' + select.value; byId('screen-image').alt = 'Actual ' + select.options[select.selectedIndex].text + ' software workspace.'; byId('screen-caption').textContent = 'Actual ' + select.options[select.selectedIndex].text + ' workspace / Open for full resolution.'; }
    select.addEventListener('change', show); show();
  }

  async function start() {
    try {
      const response = await fetch('data/evidence.json', { cache: 'no-store' }); if (!response.ok) throw new Error('Bundled evidence is unavailable'); const evidence = await response.json();
      if (evidence.live_inference !== false || evidence.live_flights !== false || evidence.operational_acceptance !== false) throw new Error('Unsupported evidence mode');
      renderComparison(evidence); renderWorkflow(evidence); renderSources(evidence); renderStudent(evidence); renderScreens(evidence);
      byId('loading').textContent = 'Bundled records loaded. Static selections do not execute a model or operational action.';
    } catch (error) { byId('loading').textContent = 'The bundled evidence could not be loaded. Serve this directory over HTTP or inspect the original JSON files below. No substitute records or live inference were started.'; byId('loading').dataset.state = 'error'; }
  }
  start();
})();
