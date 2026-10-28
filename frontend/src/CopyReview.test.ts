import { describe, expect, it } from 'vitest';
import { workspaces } from './schema';
import { releaseVersion } from './release';
const sources = import.meta.glob('./*.tsx', { query: '?raw', import: 'default', eager: true }) as Record<string, string>;
const authored = Object.entries(sources).filter(([path]) => !path.includes('.test.'));

describe('plain task language and presentation boundaries', () => {
  it('removes known slogans, decorative workspace eyebrows and numbered form headings', () => {
    const obsolete = ['One operational context. Bounded specialist work.', 'Choose the work. Keep the evidence.', 'One intended mission, distinct national conditions', '01 · Operation', '02 · Intended resources', 'AIRSPACE OPERATIONS /', 'Your operating geography starts here'];
    for (const [path, text] of authored) {
      for (const phrase of obsolete) expect(text, path).not.toContain(phrase);
      expect(text, path).not.toContain('className="eyebrow"');
      expect(text, path).not.toMatch(/<img[^>]*mascots\//);
    }
    expect(workspaces.every(workspace => workspace.description.length > 25)).toBe(true);
  });
  it('preserves legal editions, vertical units, source links and technical record contracts', () => {
    const text = authored.map(([, source]) => source).join('\n');
    for (const required of ['SORA 2.5', 'WGS 84', 'evidence_version', 'expected_version', 'AMSL', 'AGL', 'flight_level']) expect(text).toContain(required);
    expect(text).toContain('https://giletto-systems-lab.michele-giletto.chatgpt.site/projects/multiagentic-systems');
    expect(releaseVersion).toBe('0.3.0-rc.1');
  });
});
