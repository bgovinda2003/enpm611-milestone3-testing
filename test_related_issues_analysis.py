import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import related_issues_analysis as feature
from model import Issue


BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_issue(number=1, title='Title', text='', state='open', creator='alice',
               day=0, events=None, dated=True):
    data = {'number': number, 'title': title, 'text': text, 'state': state,
            'creator': creator, 'labels': [], 'events': events or []}
    if dated:
        data['created_date'] = (BASE + timedelta(days=day)).isoformat()
    return Issue(data)


def event(kind='commented', author='bob', comment=None, day=1):
    return {'event_type': kind, 'author': author, 'comment': comment,
            'event_date': (BASE + timedelta(days=day)).isoformat() if day is not None else None}


class TestReferences(unittest.TestCase):
    def test_reference_texts_title_body_comments(self):
        issue = make_issue(title='See #2', text='And #3', events=[
            event(comment='Also #4'), event(kind='labeled', comment='#5')])
        self.assertEqual([text for _, text in feature.reference_texts(issue)],
                         ['See #2', 'And #3', 'Also #4'])

    def test_reference_texts_empty(self):
        self.assertEqual(list(feature.reference_texts(make_issue(title='', text=''))), [])

    def test_find_references_hash_and_url(self):
        text = 'See #12 and https://github.com/python-poetry/poetry/issues/34'
        self.assertEqual(feature.find_references(text), {12, 34})

    def test_find_references_ignores_code(self):
        self.assertEqual(feature.find_references('`#12` and #34'), {34})

    def test_find_references_ignores_other_repository(self):
        self.assertEqual(feature.find_references('other/repo#12 and #34'), {34})

    def test_find_references_none(self):
        self.assertEqual(feature.find_references(None), set())

    def test_extract_references_removes_self(self):
        issue = make_issue(12, title='See #12 and #34', events=[event(comment='#56')])
        self.assertEqual(feature.extract_references(issue), {34, 56})

    def test_reference_map_filters_unknown(self):
        issues = [make_issue(1, text='#2 #999'), make_issue(2)]
        self.assertEqual(feature.reference_map(issues), {1: {2}, 2: set()})

    def test_invert(self):
        self.assertEqual(feature.invert({1: {2}, 2: {1}, 3: {2}}),
                         {1: {2}, 2: {1, 3}, 3: set()})

    def test_invert_unknown_target(self):
        self.assertEqual(feature.invert({1: {99}}), {1: set(), 99: {1}})

    def test_related_issues_directions(self):
        outgoing = {1: {2, 3}}
        incoming = {1: {3, 4}}
        self.assertEqual(feature.related_issues(1, outgoing, incoming),
                         {2: feature.OUTGOING, 3: feature.BOTH, 4: feature.INCOMING})

    def test_related_issues_no_links(self):
        self.assertEqual(feature.related_issues(1, {}, {}), {})

    def test_reference_dates_one_per_text(self):
        issue = make_issue(text='#2 #3', events=[event(comment='See #2', day=4)])
        self.assertEqual(feature.reference_dates(issue, {2}),
                         [BASE, BASE + timedelta(days=4)])

    def test_reference_dates_missing(self):
        self.assertEqual(feature.reference_dates(make_issue(text='#2'), {99}), [])


class TestMetrics(unittest.TestCase):
    def test_participants_distinct_commenters(self):
        issue = make_issue(events=[event(author='bob'), event(author='bob'),
                                   event(author='alice'), event(kind='labeled', author='carol'),
                                   event(author=None)])
        self.assertEqual(feature.participants(issue), {'bob', 'alice'})

    def test_issue_stats_open(self):
        issue = make_issue(events=[event(author='alice'), event(author='bob')])
        result = feature.issue_stats(issue, [None, BASE], {'bob'})
        self.assertEqual(result['refs'], 2)
        self.assertEqual(result['first_ref'], BASE)
        self.assertIsNone(result['ref_to_close'])
        self.assertEqual(result['participants'], 2)
        self.assertEqual(result['insiders'], 2)

    def test_issue_stats_closed(self):
        issue = make_issue(state='closed', events=[event(kind='closed', day=5)])
        result = feature.issue_stats(issue, [BASE + timedelta(days=2)], set())
        self.assertEqual(result['time_to_close'], timedelta(days=5))
        self.assertEqual(result['ref_to_close'], timedelta(days=3))

    def test_issue_stats_no_dates(self):
        self.assertIsNone(feature.issue_stats(make_issue(), [None], set())['first_ref'])

    def test_format_days(self):
        issue = make_issue()
        self.assertEqual(feature.format_days(timedelta(hours=36), issue), '1.5')
        self.assertEqual(feature.format_days(None, issue), 'open')
        self.assertEqual(feature.format_days(None, make_issue(state='closed')), 'n/a')

    def test_close_status(self):
        self.assertEqual(feature.close_status(make_issue()), 'open')
        self.assertEqual(feature.close_status(make_issue(state='closed')), 'unknown')
        closed = make_issue(state='closed', events=[event(kind='closed', day=2)])
        self.assertEqual(feature.close_status(closed), 'closed')

    def test_format_time_to_close(self):
        self.assertEqual(feature.format_time_to_close(make_issue(), None), 'open')
        self.assertEqual(feature.format_time_to_close(make_issue(state='closed'), None),
                         'closed, date unknown')
        closed = make_issue(state='closed', events=[event(kind='closed', day=2)])
        self.assertEqual(feature.format_time_to_close(closed, timedelta(days=2)), '2.0')


class TestAnalysis(unittest.TestCase):
    def setUp(self):
        with patch.object(feature.config, 'get_parameter', return_value=1):
            self.analysis = feature.RelatedIssuesAnalysis()

    def test_constructor_reads_issue(self):
        with patch.object(feature.config, 'get_parameter', return_value=42) as getter:
            analysis = feature.RelatedIssuesAnalysis()
        self.assertEqual(analysis.ISSUE, 42)
        getter.assert_called_once_with('issue')

    def test_run_missing_issue_argument(self):
        self.analysis.ISSUE = None
        with patch.object(feature.DataLoader, 'get_issues') as loader, \
             patch('builtins.print') as output:
            self.analysis.run()
        loader.assert_not_called()
        self.assertIn('needs an issue number', str(output.call_args_list))

    def test_run_unknown_issue(self):
        self.analysis.ISSUE = 99
        with patch.object(feature.DataLoader, 'get_issues', return_value=[make_issue(1)]), \
             patch('builtins.print') as output:
            self.analysis.run()
        self.assertIn('not in the dataset', str(output.call_args_list))

    def test_run_without_related_issues(self):
        with patch.object(feature.DataLoader, 'get_issues', return_value=[make_issue(1)]), \
             patch.object(feature, 'print_intro'), \
             patch.object(feature, 'print_finding') as finding, \
             patch.object(self.analysis, 'plot') as plot:
            self.analysis.run()
        finding.assert_called_once()
        plot.assert_not_called()

    def test_run_with_related_issues(self):
        issues = [make_issue(1, text='See #2'), make_issue(2, text='See #1')]
        with patch.object(feature.DataLoader, 'get_issues', return_value=issues), \
             patch.object(feature, 'print_intro') as intro, \
             patch.object(feature, 'print_table') as table, \
             patch.object(feature, 'print_finding') as finding, \
             patch.object(self.analysis, 'plot') as plot:
            self.analysis.run()
        intro.assert_called_once()
        table.assert_called_once()
        finding.assert_called_once()
        plot.assert_called_once()
        self.assertEqual(plot.call_args.args[2], {2: feature.BOTH})

    def test_finding_open_target(self):
        target = make_issue(1)
        related = {2: feature.OUTGOING}
        by_number = {2: make_issue(2)}
        stats = {2: {'time_to_close': None, 'ref_to_close': None}}
        text = self.analysis.finding(target, {'time_to_close': None}, related, stats, by_number)
        self.assertIn('still open', text)
        self.assertIn('1 is open', text)

    def test_finding_unknown_target(self):
        target = make_issue(1, state='closed')
        text = self.analysis.finding(target, {'time_to_close': None}, {}, {}, {})
        self.assertIn('close date is unknown', text)

    def test_finding_closed_and_after_close_reference(self):
        target = make_issue(1, state='closed', events=[event(kind='closed', day=3)])
        related_issue = make_issue(2, state='closed', events=[event(kind='closed', day=4)])
        text = self.analysis.finding(
            target, {'time_to_close': timedelta(days=3)},
            {2: feature.INCOMING},
            {2: {'time_to_close': timedelta(days=4),
                 'ref_to_close': timedelta(days=-1)}},
            {2: related_issue})
        self.assertIn('closed after 3.0 days', text)
        self.assertIn('linked only after', text)

    def test_finding_closed_without_reference_date(self):
        target = make_issue(1)
        related_issue = make_issue(2, state='closed', events=[event(kind='closed', day=4)])
        text = self.analysis.finding(
            target, {'time_to_close': None}, {2: feature.INCOMING},
            {2: {'time_to_close': timedelta(days=4), 'ref_to_close': None}},
            {2: related_issue})
        self.assertIn('median time to close', text)

    def test_plot_no_dated_issues(self):
        target = make_issue(1, dated=False)
        with patch.object(feature, 'save_chart') as save:
            self.analysis.plot(target, {'first_ref': None}, {}, {}, {}, None)
        save.assert_not_called()

    def test_plot_open_and_closed_issues(self):
        target = make_issue(1)
        closed = make_issue(2, day=1, state='closed',
                            events=[event(kind='closed', day=4)])
        related = {2: feature.OUTGOING}
        stats = {2: {'first_ref': BASE + timedelta(days=2),
                     'time_to_close': timedelta(days=3)}}
        with patch.object(feature, 'save_chart') as save:
            try:
                self.analysis.plot(target, {'first_ref': BASE}, related,
                                   stats, {2: closed}, BASE + timedelta(days=5))
                save.assert_called_once()
                self.assertEqual(save.call_args.args[1], feature.CHART_PATH)
            finally:
                feature.plt.close('all')

    def test_plot_unknown_closed_date(self):
        target = make_issue(1, state='closed')
        with patch.object(feature, 'save_chart') as save:
            try:
                self.analysis.plot(target, {'first_ref': None}, {}, {}, {}, BASE)
                save.assert_called_once()
            finally:
                feature.plt.close('all')


if __name__ == '__main__':
    unittest.main()
