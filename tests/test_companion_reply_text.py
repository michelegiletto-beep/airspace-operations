"""Text comparisons never substitute semantic or legal interpretation."""
from airspace.assistant import ADMINISTRATIVE_GUIDANCE, _reply_text


def test_registered_instruction_is_not_repeated_but_its_source_fact_is_preserved():
    guidance = ADMINISTRATIVE_GUIDANCE['review_task_preview']
    fact = {'text': guidance, 'source_ref': 'isolated-source-anchor'}
    steps = [{'id': 'step_0', 'text': guidance}, {'id': 'step_1', 'text': 'Inspect the saved personal task.'}]
    assert _reply_text(guidance, [fact], steps).split('\n\n') == [guidance, guidance, 'Inspect the saved personal task.']
    assert fact['source_ref'] == 'isolated-source-anchor' and len(steps) == 2


def test_quotes_units_punctuation_and_source_backed_steps_are_not_removed():
    guidance = ADMINISTRATIVE_GUIDANCE['review_task_preview']
    texts = [f'The note says: {guidance}', 'Use 120 m AGL.', 'Use 120 m AMSL.', guidance.rstrip('.'), '  '+guidance]
    steps = [{'text': text} for text in texts] + [{'text': guidance, 'source_ref': 'isolated-provision'}]
    assert _reply_text(guidance, [], steps).split('\n\n') == [guidance, *texts, guidance]


def test_unregistered_text_is_never_used_as_an_instruction_deduplication_rule():
    quotation = 'Review permission LU_SITE_02 / version 3.'
    assert _reply_text(quotation, [], [{'text': quotation}]) == quotation+'\n\n'+quotation
