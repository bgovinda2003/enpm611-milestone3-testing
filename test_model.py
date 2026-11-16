
import unittest
from datetime import datetime

from model import State, Event, Issue


class TestState(unittest.TestCase):

    def test_open_state(self):
        self.assertEqual(State.open.value, "open")

    def test_closed_state(self):
        self.assertEqual(State.closed.value, "closed")

    def test_state_is_string(self):
        self.assertIsInstance(State.open, str)

    def test_invalid_state(self):
        with self.assertRaises(ValueError):
            State("pending")


class TestEvent(unittest.TestCase):

    def test_event_defaults(self):
        event = Event(None)
        self.assertIsNone(event.event_type)
        self.assertIsNone(event.author)
        self.assertIsNone(event.event_date)
        self.assertIsNone(event.label)
        self.assertIsNone(event.comment)

    def test_valid_event(self):
        event = Event({
            "event_type": "labeled",
            "author": "alice",
            "event_date": "2026-01-15T10:30:00Z",
            "label": "kind/bug",
            "comment": "Label added"
        })

        self.assertEqual(event.event_type, "labeled")
        self.assertEqual(event.author, "alice")
        self.assertIsInstance(event.event_date, datetime)
        self.assertEqual(event.label, "kind/bug")
        self.assertEqual(event.comment, "Label added")

    def test_invalid_event_date(self):
        event = Event({
            "event_type": "commented",
            "event_date": "not-a-date"
        })
        self.assertIsNone(event.event_date)

    def test_missing_event_date(self):
        event = Event({"event_type": "closed"})
        self.assertIsNone(event.event_date)

    def test_partial_event(self):
        event = Event({"author": "bob"})
        self.assertEqual(event.author, "bob")
        self.assertIsNone(event.event_type)
        self.assertIsNone(event.label)

    def test_event_from_json(self):
        event = Event(None)
        event.from_json({
            "event_type": "reopened",
            "author": "carol",
            "event_date": "2026-03-01"
        })
        self.assertEqual(event.event_type, "reopened")
        self.assertEqual(event.author, "carol")
        self.assertEqual(event.event_date.year, 2026)


class TestIssue(unittest.TestCase):

    def make_issue_data(self):
        return {
            "url": "https://github.com/python-poetry/poetry/issues/100",
            "creator": "alice",
            "labels": ["kind/bug", "status/triage"],
            "state": "open",
            "assignees": ["bob"],
            "title": "Example issue",
            "text": "Example description",
            "number": 100,
            "created_date": "2026-01-01T12:00:00Z",
            "updated_date": "2026-01-02T12:00:00Z",
            "timeline_url": "https://example.com/timeline",
            "events": [{
                "event_type": "labeled",
                "author": "bob",
                "event_date": "2026-01-02",
                "label": "kind/bug",
                "comment": None
            }]
        }

    def test_issue_defaults(self):
        issue = Issue()
        self.assertIsNone(issue.url)
        self.assertIsNone(issue.creator)
        self.assertEqual(issue.labels, [])
        self.assertIsNone(issue.state)
        self.assertEqual(issue.assignees, [])
        self.assertEqual(issue.number, -1)
        self.assertIsNone(issue.created_date)
        self.assertIsNone(issue.updated_date)
        self.assertEqual(issue.events, [])

    def test_issue_none(self):
        issue = Issue(None)
        self.assertEqual(issue.number, -1)
        self.assertEqual(issue.events, [])

    def test_valid_issue(self):
        issue = Issue(self.make_issue_data())

        self.assertEqual(issue.creator, "alice")
        self.assertEqual(issue.title, "Example issue")
        self.assertEqual(issue.text, "Example description")
        self.assertEqual(issue.number, 100)
        self.assertEqual(issue.state, State.open)
        self.assertEqual(issue.labels, ["kind/bug", "status/triage"])
        self.assertEqual(issue.assignees, ["bob"])
        self.assertEqual(
            issue.url,
            "https://github.com/python-poetry/poetry/issues/100"
        )
        self.assertEqual(
            issue.timeline_url,
            "https://example.com/timeline"
        )

    def test_closed_issue(self):
        data = self.make_issue_data()
        data["state"] = "closed"
        issue = Issue(data)
        self.assertEqual(issue.state, State.closed)

    def test_issue_dates(self):
        issue = Issue(self.make_issue_data())
        self.assertIsInstance(issue.created_date, datetime)
        self.assertIsInstance(issue.updated_date, datetime)
        self.assertEqual(issue.created_date.year, 2026)
        self.assertEqual(issue.updated_date.day, 2)

    def test_invalid_issue_dates(self):
        data = self.make_issue_data()
        data["created_date"] = "invalid-date"
        data["updated_date"] = "invalid-date"

        issue = Issue(data)
        self.assertIsNone(issue.created_date)
        self.assertIsNone(issue.updated_date)

    def test_missing_issue_dates(self):
        data = self.make_issue_data()
        data.pop("created_date")
        data.pop("updated_date")

        issue = Issue(data)
        self.assertIsNone(issue.created_date)
        self.assertIsNone(issue.updated_date)

    def test_number_as_string(self):
        data = self.make_issue_data()
        data["number"] = "123"

        issue = Issue(data)
        self.assertEqual(issue.number, 123)

    def test_invalid_issue_number(self):
        data = self.make_issue_data()
        data["number"] = "invalid"

        issue = Issue(data)
        self.assertEqual(issue.number, -1)

    def test_missing_issue_number(self):
        data = self.make_issue_data()
        data.pop("number")

        issue = Issue(data)
        self.assertEqual(issue.number, -1)

    def test_missing_labels_and_assignees(self):
        data = self.make_issue_data()
        data.pop("labels")
        data.pop("assignees")

        issue = Issue(data)
        self.assertEqual(issue.labels, [])
        self.assertEqual(issue.assignees, [])

    def test_issue_events(self):
        issue = Issue(self.make_issue_data())

        self.assertEqual(len(issue.events), 1)
        self.assertIsInstance(issue.events[0], Event)
        self.assertEqual(issue.events[0].event_type, "labeled")
        self.assertEqual(issue.events[0].label, "kind/bug")

    def test_empty_events(self):
        data = self.make_issue_data()
        data["events"] = []

        issue = Issue(data)
        self.assertEqual(issue.events, [])

    def test_issue_from_json(self):
        issue = Issue()
        issue.from_json(self.make_issue_data())

        self.assertEqual(issue.number, 100)
        self.assertEqual(issue.state, State.open)

    def test_invalid_state_raises_key_error(self):
        data = self.make_issue_data()
        data["state"] = "pending"

        with self.assertRaises(KeyError):
            Issue(data)

    def test_missing_state_raises_key_error(self):
        data = self.make_issue_data()
        data.pop("state")

        with self.assertRaises(KeyError):
            Issue(data)


if __name__ == "__main__":
    unittest.main()
