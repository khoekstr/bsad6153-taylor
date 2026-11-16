import unittest

from scripts.estimate_reading_time import estimate


class ReadingTimeTests(unittest.TestCase):
    def test_inclusive_page_range(self):
        self.assertEqual(estimate({'biblio': {'first_page': '389', 'last_page': '399'}})[0], 22)

    def test_unknown_and_ambiguous_lengths(self):
        for first, last in [(None, None), ('eadn5290', 'eadn5290'), ('5568', '5568'),
                            ('12', '10'), ('0', '10'), ('1', '9999'), ('S1', 'S12')]:
            with self.subTest(first=first, last=last):
                self.assertIsNone(estimate({'biblio': {'first_page': first, 'last_page': last}}))
        self.assertIsNone(estimate(None))
        self.assertIsNone(estimate({}))


if __name__ == '__main__':
    unittest.main()
