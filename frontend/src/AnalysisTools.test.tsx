import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { EconomicsWorkbench, SiteScreening } from './AnalysisTools';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe('analysis input boundaries', () => {
  it('keeps blank financial inputs absent and displays a missing result', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'Incomplete', missing_inputs: ['planned_missions'], values: { total_revenue: null }, currency: 'EUR', period: 'Isolated test period' }))); vi.stubGlobal('fetch', fetch);
    render(<EconomicsWorkbench token="isolated-test-token" />);
    fireEvent.click(screen.getByText('Deployment economics calculation'));
    fireEvent.change(screen.getByLabelText('Currency (ISO 4217)'), { target: { value: 'EUR' } });
    fireEvent.change(screen.getByLabelText('Calculation period and units'), { target: { value: 'Isolated test period' } });
    fireEvent.click(screen.getByRole('button', { name: 'Calculate documented scenario' }));
    await screen.findByText('Incomplete');
    expect(JSON.parse((fetch.mock.calls[0][1] as RequestInit).body as string)).toEqual({ currency: 'EUR', period: 'Isolated test period', regulatory_blockers: [] });
    expect(screen.getByText('Not calculated — missing inputs or undefined')).toBeTruthy();
  });
  it('preserves unknown vertical reference and missing zone coverage', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'Incomplete', findings: ['No authoritative zone geometries supplied'], zone_results: [] }))); vi.stubGlobal('fetch', fetch);
    render(<SiteScreening token="isolated-test-token" />);
    fireEvent.click(screen.getByText('Candidate-site screening'));
    fireEvent.change(screen.getByLabelText('Longitude (WGS 84 degrees)'), { target: { value: '6.1' } });
    fireEvent.change(screen.getByLabelText('Latitude (WGS 84 degrees)'), { target: { value: '49.6' } });
    fireEvent.change(screen.getByLabelText('Horizontal uncertainty (metres)'), { target: { value: '10' } });
    fireEvent.change(screen.getByLabelText('Assessment time (ISO 8601 with offset)'), { target: { value: '2026-01-01T00:00:00Z' } });
    fireEvent.click(screen.getByRole('button', { name: 'Screen supplied site evidence' }));
    await screen.findByText('Incomplete');
    const payload = JSON.parse((fetch.mock.calls[0][1] as RequestInit).body as string) as { point: Record<string, unknown>; zones: unknown[]; coverage: Record<string, unknown> };
    expect(payload.point.vertical_reference).toBe('Unknown'); expect(payload.point.altitude_m).toBeUndefined(); expect(payload.zones).toEqual([]); expect(payload.coverage).toEqual({});
  });
});
