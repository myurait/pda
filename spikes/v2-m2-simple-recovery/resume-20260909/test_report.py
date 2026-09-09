"""Acceptance checks for the evidence-backed, explicitly incomplete report."""
import json
import unittest
from pathlib import Path
R = Path(__file__).resolve().parent

class ReportContract(unittest.TestCase):
    def test_original_scope_is_not_closed_by_partial_results(self):
        path = R / 'assessment.json'
        self.assertTrue(path.exists(), 'Evidence assessment has not been produced')
        d = json.loads(path.read_text())
        self.assertEqual(d['m2_status'], 'incomplete')
        self.assertEqual(d['admitted_candidates'], [])
        self.assertEqual(len(d['candidates']), 6)
        self.assertEqual(len({x['id'] for x in d['candidates']}), 6)
        self.assertEqual(d['thresholds'], {'state_s': 120, 'recovery_s': 300})
        self.assertEqual(len(d['criteria']), 8)
        self.assertTrue(d['unresolved'])
        for name in d['evidence_files']:
            self.assertTrue((R / 'evidence' / name).is_file(), name)
        self.assertIn('external_dependency_restore', d['corrections'])
        self.assertIn('stale_run_id', d['corrections'])
        html = (R / 'M2-RESUME-REPORT.html').read_text()
        self.assertIn('M2は未完了', html)
        self.assertIn('状態表示120秒', html)
        self.assertIn('正常版復帰300秒', html)
        self.assertNotIn('<script', html)
        self.assertEqual(html.count('<a href="https://'), 4, 'Source URLs must be clickable')

if __name__ == '__main__':
    unittest.main()
