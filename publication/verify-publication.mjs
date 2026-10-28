/* Local authoring checks. Executes only the newly authored, trusted viewer scripts. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import vm from 'node:vm';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.dirname(here);
const require = createRequire(path.join(root, 'frontend', 'package.json'));
const { JSDOM } = require('jsdom');
const postcss = require('postcss');
const read = name => fs.readFileSync(path.join(here, name), 'utf8');
const evidence = JSON.parse(read('hf-space/data/evidence.json'));
const publication = JSON.parse(read('status.json'));
const releasePublished = publication.states_reached?.includes('Independently Retrieved');
const siteHtml = read('site-project.html');
const spaceHtml = read('hf-space/index.html');
const spaceJs = read('hf-space/app.js');
const commands = [];
for (const name of ['hf-space/app.js', 'verify-publication.mjs']) {
  const command = spawnSync(process.execPath, ['--check', path.join(here, name)], { encoding: 'utf8' });
  assert.equal(command.status, 0, command.stderr);
  commands.push({ command: 'node --check publication/' + name, exit_code: command.status });
}
for (const name of ['site-project.css', 'hf-space/styles.css']) postcss.parse(read(name), { from: name });
const site = new JSDOM(siteHtml, { url: 'http://127.0.0.1:8793/projects/airspace-operations', runScripts: 'outside-only' });
for (const script of site.window.document.querySelectorAll('script:not([src])')) {
  new vm.Script(script.textContent);
  site.window.eval(script.textContent);
}
const siteDoc = site.window.document;
const screenTabs = [...siteDoc.querySelectorAll('[data-screen]')];
assert.equal(screenTabs.length, 6);
for (const [index, tab] of screenTabs.entries()) {
  tab.click();
  assert.equal(tab.getAttribute('aria-selected'), 'true');
  assert.match(siteDoc.querySelector('#workspace-image').src, /\.jpg$/);
  assert.equal(siteDoc.querySelector('#workspace-view').getAttribute('aria-labelledby'), tab.id);
  assert.equal(screenTabs.filter(t => t.getAttribute('aria-selected') === 'true').length, 1);
}
screenTabs.at(-1).dispatchEvent(new site.window.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
assert.equal(screenTabs[0].getAttribute('aria-selected'), 'true');
const traceTabs = [...siteDoc.querySelectorAll('[data-trace]')];
assert.equal(traceTabs.length, 5);
for (const [index, tab] of traceTabs.entries()) {
  tab.click(); assert.equal(siteDoc.querySelector('.as-trace').dataset.recordedStep, String(index));
}
assert.equal(siteDoc.querySelector('#trace-state').textContent, 'Needs Review');
if (siteDoc.querySelector('[data-prepared-url]')) {
  assert.equal(siteDoc.querySelector('[data-prepared-url]').disabled, true);
} else {
  assert.equal(releasePublished, true);
  assert.ok([...siteDoc.querySelectorAll('a')].some(a=>a.href.endsWith('/System-Lab-Airspace-Operations-0.2.0-rc.1.zip')));
}
assert.match(read('site-project.css'), /prefers-reduced-motion/);
site.window.close();

async function viewer(payload = evidence, fail = false) {
  const dom = new JSDOM(spaceHtml, { url: 'http://127.0.0.1:8792/', runScripts: 'outside-only' });
  let calls = 0;
  dom.window.fetch = async (url, options) => {
    calls++;
    assert.equal(url, 'data/evidence.json'); assert.equal(options.cache, 'no-store');
    if (fail) return { ok: false };
    return { ok: true, json: async () => structuredClone(payload) };
  };
  dom.window.eval(spaceJs);
  for (let i = 0; i < 5; i++) await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls, 1, 'Viewer must request only its bundled index');
  return dom;
}
const dom = await viewer(); const doc = dom.window.document;
assert.equal(doc.querySelector('#loading').dataset.state, undefined);
assert.match(doc.querySelector('#loading').textContent, /Bundled records loaded/);
assert.doesNotMatch(doc.body.textContent, /undefined|NaN/);
const tabs = [...doc.querySelectorAll('[data-view]')];
assert.equal(tabs.length, 5);
for (const tab of tabs) {
  tab.click(); assert.equal(tab.getAttribute('aria-selected'), 'true');
  assert.equal(doc.querySelector('#view-' + tab.dataset.view).hidden, false);
  assert.equal([...doc.querySelectorAll('.panel')].filter(p => !p.hidden).length, 1);
}
tabs.at(-1).dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
assert.equal(tabs[0].getAttribute('aria-selected'), 'true');
const select = doc.querySelector('#query-select'); assert.equal(select.options.length, 2);
for (let i = 0; i < 2; i++) {
  select.selectedIndex = i; select.dispatchEvent(new dom.window.Event('change'));
  assert.equal(doc.querySelectorAll('#comparison-body tr').length, 2);
}
const stepButtons = [...doc.querySelectorAll('#step-list button')]; assert.equal(stepButtons.length, 5);
for (const [index, button] of stepButtons.entries()) {
  button.click();
  assert.equal(button.getAttribute('aria-current'), 'step');
  assert.equal(doc.querySelector('#step-tool').textContent, evidence.ui_workflow.trace[index].tool);
  assert.doesNotThrow(() => JSON.parse(doc.querySelector('#step-proposal').textContent));
}
assert.match(doc.querySelector('#review-state').textContent, /Needs Review \/ approval granted: false/);
assert.equal(doc.querySelectorAll('#citation-list .citation').length, 12);
const filter = doc.querySelector('#source-search'); filter.value = 'no-such-test-token-93817'; filter.dispatchEvent(new dom.window.Event('input'));
assert.equal(doc.querySelectorAll('#citation-list .citation').length, 0);
assert.match(doc.querySelector('#citation-list').textContent, /No new source retrieval/);
filter.value = ''; filter.dispatchEvent(new dom.window.Event('input'));
assert.equal(doc.querySelectorAll('#student-body tr').length, 5);
assert.equal(doc.querySelectorAll('#failure-list .citation').length, 14);
assert.match(doc.querySelector('#student-body').textContent, /81.82%/);
const screens = doc.querySelector('#screen-select'); assert.equal(screens.options.length, 7);
for (const option of screens.options) {
  screens.value = option.value; screens.dispatchEvent(new dom.window.Event('change'));
  assert.equal(doc.querySelector('#screen-image').getAttribute('src'), 'media/' + option.value);
}
if (releasePublished) {
  assert.equal(doc.querySelector('[data-release-download]').href, 'https://github.com/michelegiletto-beep/airspace-operations/releases/download/v0.2.0-rc.1/System-Lab-Airspace-Operations-0.2.0-rc.1.zip');
} else {
  assert.equal(doc.querySelector('button[disabled]').disabled, true);
}
dom.window.close();

const outage = await viewer(evidence, true);
assert.equal(outage.window.document.querySelector('#loading').dataset.state, 'error');
assert.equal(outage.window.document.querySelectorAll('#step-list button').length, 0);
outage.window.close();
const wrongMode = structuredClone(evidence); wrongMode.live_inference = true;
const rejected = await viewer(wrongMode);
assert.equal(rejected.window.document.querySelector('#loading').dataset.state, 'error');
rejected.window.close();
const hostile = structuredClone(evidence);
hostile.ui_workflow.citations[0].text = '<img src=x onerror="window.__sourceExecuted=true">';
hostile.ui_workflow.citations[0].source_url = 'javascript:window.__sourceExecuted=true';
const escaped = await viewer(hostile); const hostileDoc = escaped.window.document;
assert.equal(hostileDoc.querySelectorAll('#citation-list img').length, 0);
assert.match(hostileDoc.querySelector('#citation-list').textContent, /<img src=x/);
assert.equal(hostileDoc.querySelectorAll('a[href^="javascript:"]').length, 0);
assert.equal(escaped.window.__sourceExecuted, undefined);
escaped.window.close();

const result = { node_javascript_syntax: 'Passed', postcss_parse: 'Passed', site_workspace_tabs: 6,
  site_recorded_trace_steps: 5, space_views: 5, space_recorded_queries: 2, space_trace_steps: 5,
  space_source_passages: 12, space_failure_examples: 14, space_screenshot_choices: 7,
  keyboard_wrap: 'Passed', publication_download_gate_checked: true, application_release_independently_retrieved: releasePublished, missing_data_no_substitutes: 'Passed',
  wrong_mode_rejected: 'Passed', source_text_escaping: 'Passed', network_requests: 'One own bundled index; no external data or inference', commands };
const reportPath = path.join(here, 'authoring-qa-v2.json');
const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
report.checked_at = new Date().toISOString(); report.checks.dom_and_syntax = result;
fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
process.stdout.write(JSON.stringify({ passed: true, ...result }) + '\n');
