
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd

import template_switch_analysis as feature
from model import Issue


class TestTemplateSwitchAnalysis(unittest.TestCase):

    def setUp(self):
        self.analysis = feature.TemplateSwitchAnalysis()
        self.base = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def issue(
        self,
        number,
        day,
        form=False,
        state="open",
        labels=None,
        events=None,
        created=True
    ):
        data = {
            "number": number,
            "state": state,
            "creator": "alice",
            "text": (
                "### Description\nA problem occurred"
                if form else "Old checkbox template"
            ),
            "labels": labels or [],
            "events": events or [],
        }
        if created:
            data["created_date"] = (
                self.base + timedelta(days=day)
            ).isoformat()
        return Issue(data)

    # Form detection

    def test_uses_form_true(self):
        self.assertTrue(
            feature.uses_form(self.issue(1, 0, form=True))
        )

    def test_uses_form_false(self):
        self.assertFalse(
            feature.uses_form(self.issue(1, 0, form=False))
        )

    def test_uses_form_empty_text(self):
        issue = self.issue(1, 0)
        issue.text = None
        self.assertFalse(feature.uses_form(issue))

    # Switch date detection

    def test_detect_switch_empty(self):
        self.assertIsNone(feature.detect_switch_date([]))

    def test_detect_switch_no_form(self):
        issues = [
            self.issue(1, 0),
            self.issue(2, 1)
        ]
        self.assertIsNone(feature.detect_switch_date(issues))

    def test_detect_switch_all_form(self):
        issues = [
            self.issue(1, 0, form=True),
            self.issue(2, 1, form=True)
        ]
        self.assertEqual(
            feature.detect_switch_date(issues),
            self.base
        )

    def test_detect_switch_ignores_undated(self):
        issues = [
            self.issue(1, 0, form=True, created=False),
            self.issue(2, 5, form=True)
        ]
        self.assertEqual(
            feature.detect_switch_date(issues),
            self.base + timedelta(days=5)
        )

    def test_detect_switch_skips_early_outlier(self):
        issues = [
            self.issue(1, 0, form=True),
            self.issue(2, 1, form=False),
            self.issue(3, 2, form=False),
            self.issue(4, 3, form=True),
            self.issue(5, 4, form=True)
        ]
        self.assertEqual(
            feature.detect_switch_date(issues),
            self.base + timedelta(days=3)
        )

    def test_detect_switch_unsorted_input(self):
        issues = [
            self.issue(3, 3, form=True),
            self.issue(1, 0, form=False),
            self.issue(2, 2, form=True)
        ]
        self.assertEqual(
            feature.detect_switch_date(issues),
            self.base + timedelta(days=2)
        )

    def test_detect_switch_same_date(self):
        issues = [
            self.issue(2, 0, form=True),
            self.issue(1, 0, form=True)
        ]
        self.assertEqual(
            feature.detect_switch_date(issues),
            self.base
        )

    # Period statistics

    def test_period_stats_empty(self):
        stats = self.analysis._period_stats([])
        self.assertEqual(stats["n"], 0)
        self.assertEqual(stats["closed"], 0)
        self.assertIsNone(stats["median_days"])
        self.assertIsNone(stats["duplicate"])
        self.assertIsNone(stats["needs_repro"])

    def test_period_stats_open_issues(self):
        issues = [
            self.issue(1, 0, labels=["status/duplicate"]),
            self.issue(2, 1, labels=["status/needs-reproduction"])
        ]
        stats = self.analysis._period_stats(issues)

        self.assertEqual(stats["n"], 2)
        self.assertEqual(stats["closed"], 0)
        self.assertIsNone(stats["median_days"])
        self.assertEqual(stats["duplicate"], 0.5)
        self.assertEqual(stats["needs_repro"], 0.5)

    def test_period_stats_closed_issue(self):
        close_date = self.base + timedelta(days=4)
        issue = self.issue(
            1, 0, state="closed",
            events=[{
                "event_type": "closed",
                "author": "bob",
                "event_date": close_date.isoformat()
            }]
        )
        stats = self.analysis._period_stats([issue])

        self.assertEqual(stats["closed"], 1)
        self.assertEqual(stats["median_days"], 4.0)

    # Finding text

    def stats(self, median, duplicate, reproduction):
        return {
            "n": 10,
            "closed": 5,
            "median_days": median,
            "duplicate": duplicate,
            "needs_repro": reproduction
        }

    def test_finding_values_rise(self):
        before = self.stats(2, 0.1, 0.2)
        after = self.stats(4, 0.3, 0.4)
        result = self.analysis._finding(before, after)

        self.assertIn("rose from 2.0 to 4.0", result)
        self.assertIn("rose from 10.0% to 30.0%", result)

    def test_finding_values_fall(self):
        before = self.stats(4, 0.5, 0.6)
        after = self.stats(2, 0.2, 0.3)
        result = self.analysis._finding(before, after)

        self.assertIn("fell from 4.0 to 2.0", result)
        self.assertIn("fell from 50.0% to 20.0%", result)

    def test_finding_values_stay(self):
        before = self.stats(2, 0.1, 0.2)
        result = self.analysis._finding(before, before)
        self.assertIn("stayed from 2.0 to 2.0", result)

    def test_finding_missing_values(self):
        before = self.stats(None, None, None)
        after = self.stats(2, 0.1, 0.2)
        result = self.analysis._finding(before, after)
        self.assertIn("could not be compared", result)

    # Quarterly calculations

    def test_quarterly_stats_sufficient_issues(self):
        dates = pd.date_range("2026-01-01", periods=20)
        df = pd.DataFrame({
            "date": dates,
            "quarter": dates.to_period("Q"),
            "after": [False] * 20,
            "share": [0.5] * 20
        })

        result = self.analysis._quarterly_stats(df, "share")

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["n"], 20)
        self.assertAlmostEqual(
            result.iloc[0]["median"], 0.5
        )

    def test_quarterly_stats_too_few_issues(self):
        dates = pd.date_range("2026-01-01", periods=3)
        df = pd.DataFrame({
            "date": dates,
            "quarter": dates.to_period("Q"),
            "after": [False] * 3,
            "share": [0.1, 0.2, 0.3]
        })

        result = self.analysis._quarterly_stats(df, "share")
        self.assertTrue(result.empty)

    def test_quarterly_stats_separate_periods(self):
        dates = pd.date_range("2026-01-01", periods=40)
        df = pd.DataFrame({
            "date": dates,
            "quarter": dates.to_period("Q"),
            "after": [False] * 20 + [True] * 20,
            "share": [0.2] * 20 + [0.8] * 20
        })

        result = self.analysis._quarterly_stats(df, "share")
        self.assertEqual(len(result), 2)
        self.assertEqual(
            sorted(result["median"].tolist()),
            [0.2, 0.8]
        )

    # Application workflow

    def test_run_without_switch(self):
        issues = [
            self.issue(1, 0),
            self.issue(2, 1)
        ]

        with patch.object(
            feature.DataLoader, "get_issues",
            return_value=issues
        ):
            with patch("builtins.print") as mock_print:
                with patch.object(
                    self.analysis, "plot_quarterly_code_share"
                ) as mock_plot:
                    self.analysis.run()

        output = " ".join(
            str(call) for call in mock_print.call_args_list
        )
        self.assertIn("No issue form switch found", output)
        mock_plot.assert_not_called()

    def test_run_with_switch(self):
        issues = [
            self.issue(1, 0, form=False),
            self.issue(2, 1, form=True),
            self.issue(3, 2, form=True)
        ]

        with patch.object(
            feature.DataLoader, "get_issues",
            return_value=issues
        ):
            with patch.object(feature, "print_intro") as intro:
                with patch.object(feature, "print_table") as table:
                    with patch.object(feature, "print_finding") as finding:
                        with patch.object(
                            self.analysis, "plot_quarterly_code_share"
                        ) as plot:
                            self.analysis.run()

        intro.assert_called_once()
        table.assert_called_once()
        finding.assert_called_once()
        plot.assert_called_once_with(
            issues, self.base + timedelta(days=1)
        )

    # Chart generation with mocked file saving

    def test_plot_quarterly_code_share(self):
        issues = [
            self.issue(i, i, form=False)
            for i in range(1, 21)
        ] + [
            self.issue(i, i, form=True)
            for i in range(21, 41)
        ]

        switch_date = self.base + timedelta(days=21)

        with patch.object(feature, "save_chart") as save:
            try:
                self.analysis.plot_quarterly_code_share(
                    issues, switch_date
                )
                save.assert_called_once()
                self.assertEqual(
                    save.call_args.args[1],
                    feature.CHART_PATH
                )
            finally:
                feature.plt.close("all")


if __name__ == "__main__":
    unittest.main()
