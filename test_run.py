"""White-box tests for the application's command-line entry point."""
import contextlib
import io
import runpy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


RUN_PATH = Path(__file__).resolve().with_name('run.py')


class TestRun(unittest.TestCase):
    def execute(self, *arguments):
        """Execute run.py as a script without running the real analyses."""
        import config
        import example_analysis
        import template_switch_analysis
        import first_reporter_code_share_analysis
        import related_issues_analysis

        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(sys, 'argv', ['run.py', *arguments]))
            overwrite = stack.enter_context(
                patch.object(config, 'overwrite_from_args'))
            mocks = {
                '0': stack.enter_context(patch.object(example_analysis, 'ExampleAnalysis')),
                '1': stack.enter_context(patch.object(template_switch_analysis, 'TemplateSwitchAnalysis')),
                '2': stack.enter_context(patch.object(first_reporter_code_share_analysis, 'FirstReporterAnalysis')),
                '3': stack.enter_context(patch.object(related_issues_analysis, 'RelatedIssuesAnalysis')),
            }
            stdout = io.StringIO()
            stderr = io.StringIO()
            stack.enter_context(contextlib.redirect_stdout(stdout))
            stack.enter_context(contextlib.redirect_stderr(stderr))
            try:
                namespace = runpy.run_path(str(RUN_PATH), run_name='__main__')
                error = None
            except SystemExit as exc:
                namespace = None
                error = exc
            return namespace, error, stdout.getvalue(), stderr.getvalue(), overwrite, mocks

    def test_feature_zero_runs_example(self):
        _, error, _, _, overwrite, mocks = self.execute('--feature', '0')
        self.assertIsNone(error)
        mocks['0'].return_value.run.assert_called_once_with()
        overwrite.assert_called_once()
        for key in ('1', '2', '3'):
            mocks[key].assert_not_called()

    def test_feature_one_runs_template_switch(self):
        _, error, _, _, _, mocks = self.execute('--feature', '1')
        self.assertIsNone(error)
        mocks['1'].return_value.run.assert_called_once_with()
        for key in ('0', '2', '3'):
            mocks[key].assert_not_called()

    def test_feature_two_runs_first_reporter(self):
        _, error, _, _, _, mocks = self.execute('-f', '2')
        self.assertIsNone(error)
        mocks['2'].return_value.run.assert_called_once_with()
        for key in ('0', '1', '3'):
            mocks[key].assert_not_called()

    def test_feature_three_runs_related_issues(self):
        _, error, _, _, _, mocks = self.execute('-f', '3')
        self.assertIsNone(error)
        mocks['3'].return_value.run.assert_called_once_with()
        for key in ('0', '1', '2'):
            mocks[key].assert_not_called()

    def test_unknown_feature_reports_error_without_running_analysis(self):
        _, error, stdout, _, overwrite, mocks = self.execute('--feature', '99')
        self.assertIsNone(error)
        self.assertIn('Unknown feature 99', stdout)
        overwrite.assert_called_once()
        for mock_class in mocks.values():
            mock_class.assert_not_called()

    def test_negative_feature_reports_unknown(self):
        _, error, stdout, _, _, mocks = self.execute('--feature', '-1')
        self.assertIsNone(error)
        self.assertIn('Unknown feature -1', stdout)
        for mock_class in mocks.values():
            mock_class.assert_not_called()

    def test_missing_feature_exits_with_argparse_error(self):
        _, error, _, stderr, overwrite, mocks = self.execute()
        self.assertIsInstance(error, SystemExit)
        self.assertEqual(error.code, 2)
        self.assertIn('required', stderr)
        overwrite.assert_not_called()
        for mock_class in mocks.values():
            mock_class.assert_not_called()

    def test_non_integer_feature_exits_with_error(self):
        _, error, _, stderr, overwrite, _ = self.execute('--feature', 'abc')
        self.assertIsInstance(error, SystemExit)
        self.assertEqual(error.code, 2)
        self.assertIn('invalid int value', stderr)
        overwrite.assert_not_called()

    def test_missing_feature_value_exits_with_error(self):
        _, error, _, stderr, _, _ = self.execute('--feature')
        self.assertIsInstance(error, SystemExit)
        self.assertEqual(error.code, 2)
        self.assertIn('expected one argument', stderr)

    def test_non_integer_issue_exits_with_error(self):
        _, error, _, stderr, _, _ = self.execute('--feature', '3', '--issue', 'abc')
        self.assertIsInstance(error, SystemExit)
        self.assertEqual(error.code, 2)
        self.assertIn('invalid int value', stderr)

    def test_unrecognized_argument_exits_with_error(self):
        _, error, _, stderr, _, _ = self.execute('--feature', '1', '--unknown')
        self.assertIsInstance(error, SystemExit)
        self.assertEqual(error.code, 2)
        self.assertIn('unrecognized arguments', stderr)

    def test_optional_arguments_forwarded_to_config(self):
        namespace, error, _, _, overwrite, mocks = self.execute(
            '--feature', '3', '--user', 'alice', '--label', 'kind/bug', '--issue', '1234')
        self.assertIsNone(error)
        args = overwrite.call_args.args[0]
        self.assertEqual(args.feature, 3)
        self.assertEqual(args.user, 'alice')
        self.assertEqual(args.label, 'kind/bug')
        self.assertEqual(args.issue, 1234)
        self.assertEqual(namespace['args'].issue, 1234)
        mocks['3'].return_value.run.assert_called_once_with()

    def test_short_optional_flags(self):
        _, error, _, _, overwrite, _ = self.execute(
            '-f', '2', '-u', 'bob', '-l', 'kind/feature', '-i', '77')
        self.assertIsNone(error)
        args = overwrite.call_args.args[0]
        self.assertEqual((args.user, args.label, args.issue),
                         ('bob', 'kind/feature', 77))

    def test_optional_values_default_to_none(self):
        _, error, _, _, overwrite, _ = self.execute('--feature', '1')
        self.assertIsNone(error)
        args = overwrite.call_args.args[0]
        self.assertIsNone(args.user)
        self.assertIsNone(args.label)
        self.assertIsNone(args.issue)

    def test_help_exits_successfully(self):
        _, error, stdout, _, overwrite, _ = self.execute('--help')
        self.assertIsInstance(error, SystemExit)
        self.assertEqual(error.code, 0)
        self.assertIn('--feature', stdout)
        self.assertIn('--issue', stdout)
        overwrite.assert_not_called()


if __name__ == '__main__':
    unittest.main()
