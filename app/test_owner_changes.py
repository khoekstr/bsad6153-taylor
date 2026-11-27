"""Offline checks for owner persistence and explicit feedback ranking."""
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from app import library_access as access
from app.streamlit_app import rank_with_feedback

class OwnerChangesTests(unittest.TestCase):
    def test_feedback_can_promote_and_demote_without_mutating_ai_scores(self):
        papers=[{'title':'Budget operations','summary':'','value_rating':5},
                {'title':'Student motivation','summary':'','value_rating':4}]
        feedback=[{'title':'Student motivation','value_rating':5},
                  {'title':'Budget operations','value_rating':1}]
        self.assertEqual(rank_with_feedback(papers,feedback)[0]['title'],'Student motivation')
        self.assertEqual(papers[0]['value_rating'],5)
        self.assertEqual(rank_with_feedback(papers,[]),papers)

    def test_notes_contribute_only_to_explicit_feedback_snapshot(self):
        papers=[{'title':'Unrelated article','summary':''}, {'title':'Metacognition','summary':''}]
        self.assertEqual(rank_with_feedback(papers,[{'value_rating':5,'notes':'metacognition'}])[0]['title'],'Metacognition')

    def test_assessment_validation_before_database(self):
        with patch.object(access,'database_connection') as db:
            for rating in (0,6,True,'5'):
                with self.assertRaises(access.LibraryUnavailable):
                    access.save_assessment(1,rating,'',False,False,None)
            db.assert_not_called()

    def test_edit_conflict_preserves_newer_version(self):
        db=MagicMock()
        db.execute.return_value.fetchone.return_value=None
        @contextmanager
        def connection(**kwargs):
            self.assertTrue(kwargs['notebook'])
            yield db
        with patch.object(access,'database_connection',connection):
            with self.assertRaises(access.LibraryUnavailable):
                access.revise_note(4,'old timestamp','draft','','')
        statement,values=db.execute.call_args.args
        self.assertIn('last_updated_at=%s',statement)
        self.assertNotIn('draft',statement)
        self.assertEqual(values[0],'draft')

if __name__=='__main__': unittest.main()
