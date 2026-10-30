import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { CompanionTaskDescription } from './CompanionTaskDescription';

afterEach(cleanup);

describe('saved task descriptions', () => {
  it.each(['Review the procedure.', ' \r\nReview\t the   procedure.\n'])('does not repeat a complete title with equivalent whitespace: %j', description => {
    const view = render(<article><h3>Review the procedure.</h3><CompanionTaskDescription title="Review the procedure." description={description}/></article>);
    expect(screen.getByRole('heading', { name: 'Review the procedure.' })).toBeTruthy();
    expect(view.container.querySelector('p')).toBeNull();
  });

  it.each([
    ['Review the procedure.', 'Review the procedure. Only an authorised reviewer can release internal dispatch.'],
    ['Use 120 m AGL.', 'Use 120 m AMSL.'],
    ['Review permission EU_LU_01.', 'Review permission EU_LU_02.'],
    ['Review the procedure.', 'review the procedure.'],
    ['Review the procedure.', 'Review the procedure'],
    ['Read https://authority.example/conditions/v1.', 'Read https://authority.example/conditions/v2.'],
    ['Review the procedure.', 'The saved note says: Review the procedure.'],
    ['Review the procedure.', '\\tReview the procedure.\\n'],
    ['Review the procedure.', 'Review the procedure.\n\nKeep the authority conditions with source version 3.'],
  ])('preserves distinct recorded text for %j', (title, description) => {
    const view = render(<CompanionTaskDescription title={title} description={description}/>);
    expect(view.container.querySelector('p')?.textContent).toBe(description);
  });

  it('does not add a blank paragraph for a missing description', () => {
    const view = render(<CompanionTaskDescription title="Review the procedure." description={' \t\r\n '}/>);
    expect(view.container.querySelector('p')).toBeNull();
  });

  it('renders untrusted distinct text without creating markup', () => {
    const description = '<img src=x onerror="window.stolen=true">';
    const view = render(<CompanionTaskDescription title="Review the procedure." description={description}/>);
    expect(screen.getByText(description).textContent).toBe(description);
    expect(view.container.querySelector('img')).toBeNull();
  });
});
