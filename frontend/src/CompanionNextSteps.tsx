import type { CompanionMessage } from './companionApi';

type NextSteps = NonNullable<CompanionMessage['data']['next_steps']>;

function comparisonText(text: string): string {
  return text.replace(/\r\n/g, '\n').trim();
}

export function CompanionNextSteps({ text, steps = [] }: { text: string; steps?: NextSteps }) {
  // The service includes its chosen steps as complete paragraphs in the reply.
  // Compare whole paragraphs only: a quoted or qualified substring is not the same instruction.
  // Keep the original reply and every displayed step unchanged.
  const displayed = new Set(comparisonText(text).split(/\n[\t ]*\n/).map(comparisonText));
  const additional = steps.filter(step => {
    const value = comparisonText(typeof step === 'string' ? step : step.text);
    if (!value || displayed.has(value)) return false;
    displayed.add(value);
    return true;
  });
  return additional.length ? <ul className="companion-next-steps" aria-label="Next steps">{additional.map((step, index) => <li key={index}>{typeof step === 'string' ? step : step.text}</li>)}</ul> : null;
}
