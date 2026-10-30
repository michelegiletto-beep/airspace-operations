function comparisonText(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

export function CompanionTaskDescription({ title, description }: { title: string; description: string }) {
  // Compare complete values only. Keep distinct descriptions exactly as recorded.
  const content = comparisonText(description);
  return content && content !== comparisonText(title) ? <p>{description}</p> : null;
}
