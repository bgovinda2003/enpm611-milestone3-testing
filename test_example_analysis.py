import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import example_analysis as example
from model import Issue


class TestExampleAnalysis(unittest.TestCase):
    def setUp(self):
        self.issues = [
            Issue({'number': 1, 'state': 'open', 'creator': 'alice', 'events': [
                {'event_type': 'commented', 'author': 'alice'},
                {'event_type': 'commented', 'author': 'bob'},
            ]}),
            Issue({'number': 2, 'state': 'closed', 'creator': 'bob', 'events': [
                {'event_type': 'labeled', 'author': 'alice'},
                {'event_type': 'closed', 'author': 'bob'},
            ]}),
            Issue({'number': 3, 'state': 'open', 'creator': 'alice', 'events': []}),
        ]

    def make_analysis(self, user=None):
        with patch.object(example.config, 'get_parameter', return_value=user) as get:
            analysis = example.ExampleAnalysis()
        get.assert_called_once_with('user')
        return analysis

    def run_analysis(self, user=None, issues=None):
        analysis = self.make_analysis(user)
        output = io.StringIO()
        with patch.object(example.DataLoader, 'get_issues', return_value=self.issues if issues is None else issues) as load, \
             patch.object(example.plt, 'show') as show, \
             redirect_stdout(output):
            analysis.run()
        load.assert_called_once_with()
        show.assert_called_once_with()
        return output.getvalue()

    def test_constructor_without_user(self):
        self.assertIsNone(self.make_analysis().USER)

    def test_constructor_with_user(self):
        self.assertEqual(self.make_analysis('alice').USER, 'alice')

    def test_all_events_counted_without_filter(self):
        output = self.run_analysis()
        self.assertIn('Found 4 events across 3 issues.', output)

    def test_events_filtered_for_alice(self):
        output = self.run_analysis('alice')
        self.assertIn('Found 2 events across 3 issues for alice.', output)

    def test_events_filtered_for_bob(self):
        output = self.run_analysis('bob')
        self.assertIn('Found 2 events across 3 issues for bob.', output)

    def test_unknown_user_has_zero_events(self):
        output = self.run_analysis('nobody')
        self.assertIn('Found 0 events across 3 issues for nobody.', output)

    def test_issues_without_events(self):
        output = self.run_analysis(issues=[self.issues[2]])
        self.assertIn('Found 0 events across 1 issues.', output)

    def test_chart_axis_labels(self):
        self.run_analysis()
        ax = plt.gca()
        self.assertEqual(ax.get_xlabel(), 'Creator Names')
        self.assertEqual(ax.get_ylabel(), '# of issues created')
        self.assertEqual(ax.get_title(), 'Top 50 issue creators')

    def test_chart_contains_creator_categories(self):
        self.run_analysis()
        ax = plt.gca()
        self.assertEqual(len(ax.patches), 2)

    def test_chart_limits_to_top_50_creators(self):
        issues = [Issue({'number': n, 'state': 'open', 'creator': f'user{n:02d}'})
                  for n in range(60)]
        self.run_analysis(issues=issues)
        self.assertEqual(len(plt.gca().patches), 50)

    def tearDown(self):
        plt.close('all')


if __name__ == '__main__':
    unittest.main()
