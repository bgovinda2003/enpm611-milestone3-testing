
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import first_reporter_code_share_analysis as feature
from model import Issue


class TestFirstReporterAnalysis(unittest.TestCase):

    def setUp(self):
        self.base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with patch.object(feature.config, "get_parameter", return_value=None):
            self.analysis = feature.FirstReporterAnalysis()

    def make_issue(
        self, number=1, creator="alice", day=0,
        label="kind/bug", text="### Description\nNo code",
        state="open", events=None
    ):
        return Issue({
            "number": number,
            "creator": creator,
            "created_date": (
                self.base + timedelta(days=day)
            ).isoformat(),
            "state": state,
            "labels": [label],
            "text": text,
            "events": events or []
        })

    def event(self, kind, author, day):
        return {
            "event_type": kind,
            "author": author,
            "event_date": (
                self.base + timedelta(days=day)
            ).isoformat()
        }

    # First activity detection

    def test_first_activity_empty(self):
        self.assertEqual(feature.first_activity_dates([]), {})

    def test_first_activity_creation(self):
        issue = self.make_issue()
        result = feature.first_activity_dates([issue])
        self.assertEqual(result["alice"], self.base)

    def test_first_activity_earlier_event(self):
        issue = self.make_issue(
            day=5,
            events=[self.event("commented", "bob", 1)]
        )
        result = feature.first_activity_dates([issue])
        self.assertEqual(
            result["bob"], self.base + timedelta(days=1)
        )

    def test_first_activity_earliest_date(self):
        issues = [
            self.make_issue(1, "alice", 5),
            self.make_issue(2, "alice", 1)
        ]
        result = feature.first_activity_dates(issues)
        self.assertEqual(
            result["alice"], self.base + timedelta(days=1)
        )

    def test_first_activity_ignores_passive_events(self):
        issue = self.make_issue(
            events=[self.event("subscribed", "bob", 1)]
        )
        result = feature.first_activity_dates([issue])
        self.assertNotIn("bob", result)

    def test_first_activity_ignores_missing_user(self):
        issue = self.make_issue(creator=None)
        self.assertEqual(feature.first_activity_dates([issue]), {})

    def test_first_activity_ignores_missing_date(self):
        issue = self.make_issue()
        issue.created_date = None
        self.assertEqual(feature.first_activity_dates([issue]), {})

    def test_first_activity_labeled_and_closed(self):
        issue = self.make_issue(events=[
            self.event("labeled", "bob", 2),
            self.event("closed", "carol", 3)
        ])
        result = feature.first_activity_dates([issue])
        self.assertIn("bob", result)
        self.assertIn("carol", result)

    # First-time reporter identification

    def test_is_first_time_reporter_true(self):
        issue = self.make_issue()
        self.assertTrue(
            feature.is_first_time_reporter(
                issue, {"alice": self.base}
            )
        )

    def test_is_first_time_reporter_false(self):
        issue = self.make_issue(day=5)
        self.assertFalse(
            feature.is_first_time_reporter(
                issue, {"alice": self.base}
            )
        )

    def test_is_first_time_reporter_unknown(self):
        self.assertFalse(
            feature.is_first_time_reporter(self.make_issue(), {})
        )

    def test_is_first_time_reporter_missing_creator(self):
        issue = self.make_issue(creator=None)
        self.assertFalse(
            feature.is_first_time_reporter(issue, {})
        )

    def test_is_first_time_reporter_missing_date(self):
        issue = self.make_issue()
        issue.created_date = None
        self.assertFalse(
            feature.is_first_time_reporter(issue, {})
        )

    # Code share thresholds and groups

    def test_top_cutoff_empty(self):
        self.assertIsNone(feature.top_cutoff([]))

    def test_top_cutoff_only_zero(self):
        self.assertIsNone(feature.top_cutoff([0, 0, 0]))

    def test_top_cutoff_single_nonzero(self):
        self.assertEqual(feature.top_cutoff([0, 0.5]), 0.5)

    def test_top_cutoff_percentile(self):
        self.assertAlmostEqual(
            feature.top_cutoff([0, 0.1, 0.5, 0.9]),
            0.82
        )

    def test_share_group_no_code(self):
        self.assertEqual(
            feature.share_group(0, 0.5), "no code"
        )

    def test_share_group_top(self):
        self.assertEqual(
            feature.share_group(0.8, 0.8), "top 10%"
        )

    def test_share_group_middle(self):
        self.assertEqual(
            feature.share_group(0.3, 0.8), "middle"
        )

    def test_share_group_without_cutoff(self):
        self.assertEqual(
            feature.share_group(0.3, None), "middle"
        )

    # Constructor and group statistics

    def test_constructor_reads_label(self):
        with patch.object(
            feature.config, "get_parameter",
            return_value="kind/feature"
        ) as parameter:
            analysis = feature.FirstReporterAnalysis()

        self.assertEqual(analysis.LABEL, "kind/feature")
        parameter.assert_called_once_with("label")

    def test_group_stats_empty(self):
        stats = self.analysis._group_stats([], set())
        self.assertEqual(stats["n"], 0)
        self.assertEqual(stats["closed"], 0)
        self.assertIsNone(stats["median_days"])
        self.assertIsNone(stats["median_comments"])
        self.assertIsNone(stats["duplicate"])
        self.assertEqual(
            stats["closers"],
            {"reporter": 0, "maintainer": 0, "other": 0}
        )

    def test_group_stats_open_issue(self):
        issue = self.make_issue(events=[
            self.event("commented", "bob", 1),
            self.event("commented", "alice", 2)
        ])
        stats = self.analysis._group_stats([issue], set())
        self.assertEqual(stats["n"], 1)
        self.assertEqual(stats["closed"], 0)
        self.assertEqual(stats["median_comments"], 2)
        self.assertIsNone(stats["median_days"])
        self.assertEqual(stats["duplicate"], 0.0)

    def test_group_stats_closed_issue(self):
        issue = self.make_issue(
            state="closed",
            events=[self.event("closed", "bob", 4)]
        )
        stats = self.analysis._group_stats([issue], {"bob"})
        self.assertEqual(stats["closed"], 1)
        self.assertEqual(stats["median_days"], 4.0)
        self.assertEqual(stats["closers"]["maintainer"], 1)

    # Closer formatting

    def test_closer_cell_without_closed_issues(self):
        stats = {"closed": 0, "closers": {"reporter": 0}}
        self.assertEqual(
            self.analysis._closer_cell(stats, "reporter"), "-"
        )

    def test_closer_cell_with_closed_issues(self):
        stats = {"closed": 4, "closers": {"reporter": 1}}
        self.assertEqual(
            self.analysis._closer_cell(stats, "reporter"),
            "1 (25%)"
        )

    # Finding generation

    def sample_stats(self, n, median, comments, duplicate, closed):
        return {
            "n": n,
            "closed": closed,
            "median_days": median,
            "median_comments": comments,
            "duplicate": duplicate,
            "needs_repro": 0.0,
            "closers": {
                "reporter": 1 if closed else 0,
                "maintainer": max(closed - 1, 0),
                "other": 0
            }
        }

    def test_finding_missing_group(self):
        stats = {
            "no code": self.sample_stats(0, None, None, None, 0),
            "top 10%": self.sample_stats(1, 2, 1, 0.0, 1)
        }
        self.assertIn(
            "Can't compare", self.analysis._finding(stats)
        )

    def test_finding_comparison(self):
        stats = {
            "no code": self.sample_stats(12, 5, 3, 0.2, 2),
            "top 10%": self.sample_stats(12, 2, 5, 0.4, 2)
        }
        result = self.analysis._finding(stats)
        self.assertIn("lower", result)
        self.assertIn("higher", result)

    def test_finding_small_groups(self):
        stats = {
            "no code": self.sample_stats(2, 5, 3, 0.2, 1),
            "top 10%": self.sample_stats(2, 5, 3, 0.2, 1)
        }
        result = self.analysis._finding(stats)
        self.assertIn("anecdotal", result)
        self.assertIn("the same", result)

    def test_finding_missing_metric(self):
        stats = {
            "no code": self.sample_stats(12, None, 3, 0.2, 0),
            "top 10%": self.sample_stats(12, 2, 5, 0.4, 0)
        }
        self.assertIn(
            "could not be compared",
            self.analysis._finding(stats)
        )

    # Main application workflow

    def test_run_invalid_label(self):
        issues = [self.make_issue()]
        self.analysis.LABEL = "nonexistent"

        with patch.object(
            feature.DataLoader, "get_issues", return_value=issues
        ), patch.object(feature, "print_intro") as intro:
            self.analysis.run()

        intro.assert_not_called()

    def test_run_default_label_no_chart(self):
        issues = [self.make_issue(text="Old template")]

        with patch.object(
            feature.DataLoader, "get_issues", return_value=issues
        ), patch.object(
            self.analysis, "plot_groups"
        ) as plot:
            self.analysis.run()

        plot.assert_not_called()

    def test_run_with_valid_group(self):
        issues = [
            self.make_issue(1, "alice", 0),
            self.make_issue(
                2, "bob", 1,
                text="### Description\n```\nprint(1)\n```"
            )
        ]

        with patch.object(
            feature.DataLoader, "get_issues", return_value=issues
        ), patch.object(
            feature, "print_intro"
        ), patch.object(
            feature, "print_table"
        ), patch.object(
            feature, "print_finding"
        ), patch.object(
            self.analysis, "plot_groups"
        ) as plot:
            self.analysis.run()

        plot.assert_called_once()

    # Chart generation

    def test_plot_groups(self):
        stats = {
            "no code": self.sample_stats(3, None, 0, 0.0, 0),
            "middle": self.sample_stats(3, 4, 2, 0.2, 2),
            "top 10%": self.sample_stats(3, 2, 1, 0.1, 1)
        }

        with patch.object(feature, "save_chart") as save:
            try:
                self.analysis.plot_groups("kind/bug", stats)
                save.assert_called_once()
                self.assertEqual(
                    save.call_args.args[1],
                    feature.CHART_PATH
                )
            finally:
                feature.plt.close("all")


if __name__ == "__main__":
    unittest.main()
