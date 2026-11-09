
import unittest
from datetime import datetime, timedelta, timezone

from model import Issue, Event, State
import issue_metrics as metrics


class TestIssueMetrics(unittest.TestCase):

    def make_issue(
        self,
        state="closed",
        creator="alice",
        labels=None,
        events=None,
        created="2026-01-01T00:00:00Z",
        text="Example issue"
    ):
        return Issue({
            "state": state,
            "creator": creator,
            "labels": labels if labels is not None else [],
            "events": events if events is not None else [],
            "created_date": created,
            "text": text,
            "number": 100
        })

    def make_event(self, kind, author, date=None):
        return {
            "event_type": kind,
            "author": author,
            "event_date": date
        }

    # Text processing

    def test_text_of_string(self):
        self.assertEqual(metrics._text_of("hello"), "hello")

    def test_text_of_none(self):
        self.assertIsNone(metrics._text_of(None))

    def test_text_of_issue(self):
        issue = self.make_issue(text="Issue description")
        self.assertEqual(
            metrics._text_of(issue), "Issue description"
        )

    def test_code_share_empty(self):
        self.assertEqual(metrics.code_share(""), 0.0)
        self.assertEqual(metrics.code_share(None), 0.0)

    def test_code_share_without_code(self):
        self.assertEqual(
            metrics.code_share("Plain text only"), 0.0
        )

    def test_code_share_fenced_code(self):
        text = "Before\n```\nprint(1)\n```\nAfter"
        expected = len("print(1)\n") / len(text)
        self.assertAlmostEqual(
            metrics.code_share(text), expected
        )

    def test_code_share_unclosed_fence(self):
        text = "```\nabc\n"
        self.assertAlmostEqual(
            metrics.code_share(text),
            len("abc\n") / len(text)
        )

    def test_code_share_indented_block(self):
        self.assertEqual(
            metrics.code_share("    print(1)\n"), 0.0
        )

    def test_code_share_issue_object(self):
        issue = self.make_issue(text="```\nabc\n```")
        self.assertGreater(metrics.code_share(issue), 0.0)

    def test_remove_code_none(self):
        self.assertIsNone(metrics.remove_code(None))

    def test_remove_code_plain_text(self):
        self.assertIn(
            "Hello world",
            metrics.remove_code("Hello world")
        )

    def test_remove_code_fenced(self):
        result = metrics.remove_code(
            "Before\n\n```python\nsecret_code()\n```\n\nAfter"
        )
        self.assertIn("Before", result)
        self.assertIn("After", result)
        self.assertNotIn("secret_code()", result)

    def test_remove_code_inline(self):
        result = metrics.remove_code(
            "Use `print(1)` here."
        )
        self.assertIn("Use", result)
        self.assertNotIn("print(1)", result)

    def test_remove_code_markdown_link(self):
        result = metrics.remove_code(
            "[Issue](https://example.com/issue/1)"
        )
        self.assertIn("Issue", result)
        self.assertIn(
            "https://example.com/issue/1", result
        )

    def test_remove_code_html(self):
        result = metrics.remove_code(
            "<pre>hidden()</pre>\n\n<p>Visible</p>"
        )
        self.assertNotIn("hidden()", result)
        self.assertIn("Visible", result)

    def test_remove_code_line_break(self):
        result = metrics.remove_code("First\nSecond")
        self.assertIn("First", result)
        self.assertIn("Second", result)

    # Issue form sections

    def test_extract_section_found(self):
        text = (
            "### Description\n"
            "A bug occurs\n"
            "### Workarounds\n"
            "Restart"
        )
        self.assertEqual(
            metrics.extract_section(text, "Description"),
            "A bug occurs"
        )

    def test_extract_section_last(self):
        text = "### Description\nFirst\n### Workarounds\nRestart"
        self.assertEqual(
            metrics.extract_section(text, "Workarounds"),
            "Restart"
        )

    def test_extract_section_missing(self):
        self.assertIsNone(
            metrics.extract_section("No headings", "Description")
        )

    def test_extract_section_empty(self):
        self.assertEqual(
            metrics.extract_section(
                "### Description\n### Workarounds\nFix",
                "Description"
            ),
            ""
        )

    def test_extract_section_none(self):
        self.assertIsNone(
            metrics.extract_section(None, "Description")
        )

    def test_form_sections_both(self):
        text = (
            "### Description\nBug details\n"
            "### Workarounds\nRestart"
        )
        self.assertEqual(
            metrics.form_sections_text(text),
            "Bug details\n\nRestart"
        )

    def test_form_sections_one(self):
        self.assertEqual(
            metrics.form_sections_text(
                "### Description\nOnly description"
            ),
            "Only description"
        )

    def test_form_sections_missing(self):
        self.assertIsNone(
            metrics.form_sections_text("Old template")
        )

    # Closing events and dates

    def test_last_close_event_open_issue(self):
        issue = self.make_issue(
            state="open",
            events=[self.make_event(
                "closed", "bob", "2026-01-03T00:00:00Z"
            )]
        )
        self.assertIsNone(metrics._last_close_event(issue))

    def test_last_close_event_missing(self):
        issue = self.make_issue(events=[])
        self.assertIsNone(metrics._last_close_event(issue))

    def test_last_close_event_ignores_undated(self):
        issue = self.make_issue(events=[
            self.make_event("closed", "bob", None)
        ])
        self.assertIsNone(metrics.close_date(issue))

    def test_last_close_event_latest_date(self):
        issue = self.make_issue(events=[
            self.make_event(
                "closed", "bob", "2026-01-02T00:00:00Z"
            ),
            self.make_event(
                "closed", "carol", "2026-01-05T00:00:00Z"
            )
        ])
        event = metrics._last_close_event(issue)
        self.assertEqual(event.author, "carol")
        self.assertEqual(metrics.close_date(issue).day, 5)

    def test_last_close_event_tie(self):
        date = "2026-01-05T00:00:00Z"
        issue = self.make_issue(events=[
            self.make_event("closed", "bob", date),
            self.make_event("closed", "carol", date)
        ])
        self.assertEqual(
            metrics._last_close_event(issue).author,
            "carol"
        )

    def test_time_to_close(self):
        issue = self.make_issue(events=[
            self.make_event(
                "closed", "bob", "2026-01-04T00:00:00Z"
            )
        ])
        self.assertEqual(
            metrics.time_to_close(issue),
            timedelta(days=3)
        )

    def test_time_to_close_no_close(self):
        issue = self.make_issue(events=[])
        self.assertIsNone(metrics.time_to_close(issue))

    def test_time_to_close_no_created_date(self):
        issue = self.make_issue(
            created=None,
            events=[self.make_event(
                "closed", "bob", "2026-01-04T00:00:00Z"
            )]
        )
        self.assertIsNone(metrics.time_to_close(issue))

    # Labels and comments

    def test_has_label_true(self):
        issue = self.make_issue(labels=["kind/bug"])
        self.assertTrue(
            metrics.has_label(issue, "kind/bug")
        )

    def test_has_label_false(self):
        issue = self.make_issue(labels=[])
        self.assertFalse(
            metrics.has_label(issue, "kind/bug")
        )

    def test_has_label_none(self):
        issue = self.make_issue()
        issue.labels = None
        self.assertFalse(
            metrics.has_label(issue, "kind/bug")
        )

    def test_is_duplicate(self):
        issue = self.make_issue(
            labels=["status/duplicate"]
        )
        self.assertTrue(metrics.is_duplicate(issue))

    def test_is_not_duplicate(self):
        issue = self.make_issue(labels=["kind/bug"])
        self.assertFalse(metrics.is_duplicate(issue))

    def test_needs_reproduction(self):
        issue = self.make_issue(
            labels=["status/needs-reproduction"]
        )
        self.assertTrue(metrics.needs_reproduction(issue))

    def test_no_reproduction_label(self):
        issue = self.make_issue(labels=[])
        self.assertFalse(metrics.needs_reproduction(issue))

    def test_comment_count(self):
        issue = self.make_issue(events=[
            self.make_event("commented", "alice"),
            self.make_event("commented", "bob"),
            self.make_event("labeled", "carol")
        ])
        self.assertEqual(metrics.comment_count(issue), 2)

    def test_comment_count_empty(self):
        issue = self.make_issue(events=[])
        self.assertEqual(metrics.comment_count(issue), 0)

    # Maintainer identification

    def test_find_maintainers(self):
        issue = self.make_issue(
            creator="alice",
            events=[
                self.make_event("labeled", "bob"),
                self.make_event("closed", "carol"),
                self.make_event("commented", "dave"),
                self.make_event("labeled", "alice")
            ]
        )
        self.assertEqual(
            metrics.find_maintainers([issue]),
            {"bob", "carol"}
        )

    def test_find_maintainers_empty(self):
        self.assertEqual(
            metrics.find_maintainers([]), set()
        )

    def test_find_maintainers_missing_author(self):
        issue = self.make_issue(events=[
            self.make_event("labeled", None)
        ])
        self.assertEqual(
            metrics.find_maintainers([issue]), set()
        )

    def test_closer_type_reporter(self):
        issue = self.make_issue(events=[
            self.make_event(
                "closed", "alice", "2026-01-03T00:00:00Z"
            )
        ])
        self.assertEqual(
            metrics.closer_type(issue, {"alice"}),
            "reporter"
        )

    def test_closer_type_maintainer(self):
        issue = self.make_issue(events=[
            self.make_event(
                "closed", "bob", "2026-01-03T00:00:00Z"
            )
        ])
        self.assertEqual(
            metrics.closer_type(issue, {"bob"}),
            "maintainer"
        )

    def test_closer_type_other(self):
        issue = self.make_issue(events=[
            self.make_event(
                "closed", "dave", "2026-01-03T00:00:00Z"
            )
        ])
        self.assertEqual(
            metrics.closer_type(issue, {"bob"}),
            "other"
        )

    def test_closer_type_no_close(self):
        issue = self.make_issue(events=[])
        self.assertIsNone(
            metrics.closer_type(issue, set())
        )

    # Statistical helpers

    def test_days(self):
        self.assertEqual(
            metrics.days(timedelta(hours=36)), 1.5
        )

    def test_days_none(self):
        self.assertIsNone(metrics.days(None))

    def test_median_days_odd(self):
        values = [
            timedelta(days=1),
            timedelta(days=3),
            timedelta(days=5)
        ]
        self.assertEqual(metrics.median_days(values), 3.0)

    def test_median_days_even(self):
        values = [
            timedelta(days=1),
            timedelta(days=3)
        ]
        self.assertEqual(metrics.median_days(values), 2.0)

    def test_median_days_skips_none(self):
        self.assertEqual(
            metrics.median_days(
                [None, timedelta(days=4)]
            ),
            4.0
        )

    def test_median_days_empty(self):
        self.assertIsNone(metrics.median_days([]))

    def test_rate_mixed(self):
        self.assertEqual(
            metrics.rate([True, False, True]), 2 / 3
        )

    def test_rate_all_true(self):
        self.assertEqual(metrics.rate([True, True]), 1.0)

    def test_rate_all_false(self):
        self.assertEqual(metrics.rate([False, False]), 0.0)

    def test_rate_skips_none(self):
        self.assertEqual(
            metrics.rate([True, None, False]), 0.5
        )

    def test_rate_empty(self):
        self.assertIsNone(metrics.rate([]))

    def test_rate_only_none(self):
        self.assertIsNone(metrics.rate([None, None]))


if __name__ == "__main__":
    unittest.main()
