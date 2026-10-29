import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { CompanionNextSteps } from './CompanionNextSteps';

afterEach(cleanup);

describe('additional companion instructions', () => {
  it('keeps unique structured and legacy instructions while removing exact repeated entries', () => {
    render(<CompanionNextSteps text={'Inspect the saved configuration.\n\nReview record AU_CFG_7.'} steps={[
      { id: 'covered', text: 'Review record AU_CFG_7.' },
      'Confirm permission LU_SITE_02.',
      { id: 'same-text', text: 'Confirm permission LU_SITE_02.' },
      { id: 'different-record', text: 'Review record AU_CFG_8.' },
    ]}/>);
    const items = within(screen.getByRole('list', { name: 'Next steps' })).getAllByRole('listitem');
    expect(items.map(item => item.textContent)).toEqual(['Confirm permission LU_SITE_02.', 'Review record AU_CFG_8.']);
  });

  it('does not treat quoted substrings, different vertical references or different punctuation as duplicates', () => {
    const instructions = ['Review permission EU_LU_01.', 'Use the reviewed altitude of 120 m AGL.', 'Use the reviewed altitude of 120 m AMSL'];
    render(<CompanionNextSteps text={'The saved note says: Review permission EU_LU_01.\n\nUse the reviewed altitude of 120 m AMSL.'} steps={instructions}/>);
    expect(screen.getAllByRole('listitem').map(item => item.textContent)).toEqual(instructions);
  });

  it('compares line endings and outer whitespace without rewriting displayed instructions', () => {
    const view = render(<CompanionNextSteps text={'Read the evidence.\r\n\r\nRecord evidence version 3.'} steps={['\tRecord evidence version 3.\t']}/>);
    expect(screen.queryByRole('list')).toBeNull();
    const original = '  Record LU_SITE_02 / v3 with 120 m AMSL.  ';
    view.rerender(<CompanionNextSteps text="Read the evidence." steps={[original]}/>);
    expect(screen.getByRole('listitem').textContent).toBe(original);
  });
});
