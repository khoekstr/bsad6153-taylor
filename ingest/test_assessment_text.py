"""Compatibility checks for saved legacy assessments and the simplified format."""
import unittest
from ingest.load import assessment_text

class AssessmentTextTests(unittest.TestCase):
    def test_legacy_notes_survive(self):
        summary, context = assessment_text({'summary':'Finding.', 'evidence_assessment':'Small sample.',
            'assessment_context':'Abstract.', 'novelty_reason':'Reading history unknown.'})
        self.assertEqual(summary, 'Finding.\n\nQualifications: Small sample.')
        self.assertIn('Reading history unknown.', context)

    def test_current_format_needs_no_retired_fields(self):
        self.assertEqual(assessment_text({'summary':'Finding.'}), ('Finding.', None))

    def test_notes_are_not_duplicated(self):
        self.assertEqual(assessment_text({'summary':'Qualifications: Small sample.',
            'evidence_assessment':'Small sample.'})[0], 'Qualifications: Small sample.')
