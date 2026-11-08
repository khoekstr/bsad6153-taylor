"""Offline checks for provenance and repeatable connection identity."""
import hashlib
import json
import unittest
from unittest.mock import Mock

from ingest.load import prepare_connections


class ConnectionValidationTests(unittest.TestCase):
    def setUp(self):
        self.rows = []
        for identifier in ('https://openalex.org/W1', 'https://openalex.org/W2'):
            self.rows.append(((identifier, 'Title', None, None, None, 'article', 'en', identifier), {}, []))
        self.record = {
            'from_openalex_id': self.rows[0][0][0], 'to_openalex_id': self.rows[1][0][0],
            'from_abstract_sha256': hashlib.sha256(self.rows[0][0][7].encode()).hexdigest(),
            'to_abstract_sha256': hashlib.sha256(self.rows[1][0][7].encode()).hexdigest(),
            'connection_type': 'supports', 'explanation': 'A qualified inference.',
            'evidence': 'Evidence from both abstracts.', 'review_basis': 'abstract',
            'proposed_by': 'ai', 'review_status': 'suggested'}

    def prepare(self, records):
        path = Mock()
        path.read_text.return_value = json.dumps({'batch_id': 'test', 'records': records})
        return prepare_connections(path, self.rows)

    def reverse(self, record):
        other = dict(record)
        for suffix in ('openalex_id', 'abstract_sha256'):
            a, b = 'from_'+suffix, 'to_'+suffix
            other[a], other[b] = other[b], other[a]
        return other

    def test_directed_relationship_preserves_direction(self):
        first = self.prepare([self.record])[0][0]
        second = self.prepare([self.reverse(self.record)])[0][0]
        self.assertNotEqual(first, second)
        self.assertEqual(first, self.prepare([dict(self.record, explanation='Rephrased')])[0][0])

    def test_symmetric_reverse_is_same_identity(self):
        for kind in ('overlaps', 'related_topic'):
            record = dict(self.record, connection_type=kind)
            self.assertEqual(self.prepare([record])[0][0], self.prepare([self.reverse(record)])[0][0])
            with self.assertRaises(ValueError):
                self.prepare([record, self.reverse(record)])

    def test_changed_or_missing_source_rejected(self):
        for change in ({'from_abstract_sha256':'wrong'}, {'to_abstract_sha256':'wrong'},
                       {'from_openalex_id':'https://openalex.org/W3'}):
            with self.assertRaises(ValueError):
                self.prepare([dict(self.record, **change)])

    def test_self_link_and_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            self.prepare([dict(self.record, to_openalex_id=self.record['from_openalex_id'])])
        with self.assertRaises(ValueError):
            self.prepare([self.record, self.record])

    def test_evidence_and_ai_scope_required(self):
        for change in ({'evidence':' '}, {'explanation':''}, {'connection_type':'cites'},
                       {'review_basis':'full_text'}, {'proposed_by':'user'}, {'review_status':'accepted'}):
            with self.assertRaises(ValueError):
                self.prepare([dict(self.record, **change)])


if __name__ == '__main__':
    unittest.main()
