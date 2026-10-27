import { describe, expect, it } from 'vitest';
import { canWriteRecord, formData, kinds } from './schema';

describe('record editor serialization', () => {
  it('does not offer administrator privilege as operational authorship or reviewer authority', () => {
    expect(canWriteRecord('case', 'administrator')).toBe(false);
    expect(canWriteRecord('mission', 'regulatory')).toBe(false);
    expect(canWriteRecord('case', 'reviewer')).toBe(true);
    expect(canWriteRecord('aircraft', 'fleet_manager')).toBe(true);
    for (const role of ['pilot', 'administrator', 'incident_coordinator', 'fleet_manager']) expect(canWriteRecord('alert', role)).toBe(false);
  });
  it('keeps missing inputs missing and serializes evidence references as IDs', () => {
    expect(formData(kinds.case, { jurisdiction: 'LU', evidence_ids: ' first, second , ', conops: '' }, { conops: 'older value', custom: 'retained' })).toEqual({ custom: 'retained', jurisdiction: 'LU', evidence_ids: ['first', 'second'] });
  });
  it('does not substitute a zero financial assumption for an empty field', () => {
    expect(formData(kinds.commercial, { cost_per_mission: '', missions: '0' }, {})).toEqual({ missions: 0 });
  });
  it('parses geometry as data and rejects malformed geometry before a save', () => {
    expect(formData(kinds.site, { geometry: '{"type":"Point","coordinates":[6.1,49.6]}' }, {})).toEqual({ geometry: { type: 'Point', coordinates: [6.1,49.6] } });
    expect(() => formData(kinds.site, { geometry: '{"coordinates":[]}' }, {})).toThrow('GeoJSON type');
  });
});
