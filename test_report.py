import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import report


class TestReport(unittest.TestCase):
    def capture(self, function, *args):
        stream = io.StringIO()
        with redirect_stdout(stream):
            function(*args)
        return stream.getvalue()

    def test_print_intro(self):
        output = self.capture(report.print_intro, 'Analysis', 'Why?', 'Compare')
        self.assertIn('Analysis', output)
        self.assertIn('Question: Why?', output)
        self.assertIn('Method:   Compare', output)
        self.assertEqual(output.count('=' * report.RULE_WIDTH), 2)

    def test_print_finding(self):
        output = self.capture(report.print_finding, 'Result')
        self.assertIn('Finding: Result', output)
        self.assertIn('=' * report.RULE_WIDTH, output)

    def test_fmt_none(self):
        self.assertEqual(report.fmt(None, '.1f'), '-')

    def test_fmt_float(self):
        self.assertEqual(report.fmt(2.345, '.1f'), '2.3')

    def test_fmt_percent(self):
        self.assertEqual(report.fmt(0.25, '.1%'), '25.0%')

    def test_fmt_integer(self):
        self.assertEqual(report.fmt(5, 'd'), '5')

    def test_print_table_basic(self):
        output = self.capture(report.print_table, ['name', 'count'], [['alpha', 2], ['beta', 10]])
        for item in ('name', 'count', 'alpha', 'beta', '10'):
            self.assertIn(item, output)

    def test_print_table_empty_rows(self):
        try:
            output = self.capture(report.print_table, ['name', 'count'], [])
        except IndexError as error:
            self.fail(
                "print_table() raises IndexError for an empty row list: "
                + str(error)
            )
        self.assertIn('name', output)
        self.assertIn('count', output)

    def test_print_table_numeric_and_text_columns(self):
        with patch.object(report, 'tabulate', return_value='GRID') as tab:
            self.capture(report.print_table, ['label', 'value'], [['alpha', '10'], ['beta', '-']])
        self.assertEqual(tab.call_args.kwargs['colalign'], ['left', 'right'])
        self.assertTrue(tab.call_args.kwargs['disable_numparse'])

    def test_print_table_narrow_terminal_wraps(self):
        terminal = type('TerminalSize', (), {'columns': 30})()
        with patch.object(report.shutil, 'get_terminal_size', return_value=terminal):
            with patch.object(report, 'tabulate', return_value='GRID') as tab:
                self.capture(report.print_table, ['name', 'description'], [['A', 'many short words in a long description']])
        widths = tab.call_args.kwargs['maxcolwidths']
        self.assertLess(widths[1], len('many short words in a long description'))

    def test_print_table_unbreakable_word(self):
        terminal = type('TerminalSize', (), {'columns': 10})()
        with patch.object(report.shutil, 'get_terminal_size', return_value=terminal):
            with patch.object(report, 'tabulate', return_value='GRID') as tab:
                self.capture(report.print_table, ['heading'], [['unbreakableword']])
        self.assertEqual(tab.call_args.kwargs['maxcolwidths'], [len('unbreakableword')])

    def make_figure(self, width=8, height=4, axes=1):
        fig = MagicMock()
        fig.get_size_inches.return_value = (width, height)
        fig.axes = [MagicMock() for _ in range(axes)]
        return fig

    def test_save_chart_enlarges_narrow_figure(self):
        fig = self.make_figure(width=8, height=4)
        with patch.object(report.os, 'makedirs') as mkdir, \
             patch.object(report.plt, 'get_backend', return_value='Agg'), \
             patch.object(report.plt, 'show') as show:
            output = self.capture(report.save_chart, fig, 'output/chart.png')
        fig.set_size_inches.assert_called_once_with(report.MIN_CHART_WIDTH, 4)
        fig.savefig.assert_called_once_with('output/chart.png', dpi=150, bbox_inches='tight')
        mkdir.assert_called_once_with('output', exist_ok=True)
        show.assert_not_called()
        self.assertIn('Chart saved to output/chart.png', output)

    def test_save_chart_keeps_wide_figure(self):
        fig = self.make_figure(width=14)
        with patch.object(report.os, 'makedirs'), \
             patch.object(report.plt, 'get_backend', return_value='Agg'):
            self.capture(report.save_chart, fig, 'output/chart.png')
        fig.set_size_inches.assert_not_called()

    def test_save_chart_applies_grids_to_each_axis(self):
        fig = self.make_figure(axes=2)
        with patch.object(report.os, 'makedirs'), \
             patch.object(report.plt, 'get_backend', return_value='Agg'):
            self.capture(report.save_chart, fig, 'output/chart.png')
        for ax in fig.axes:
            ax.set_axisbelow.assert_called_once_with(True)
            self.assertEqual(ax.grid.call_count, 2)
            self.assertEqual(ax.grid.call_args_list[0].kwargs['which'], 'major')
            self.assertEqual(ax.grid.call_args_list[1].kwargs['which'], 'minor')

    def test_save_chart_gui_backend_shows(self):
        fig = self.make_figure()
        with patch.object(report.os, 'makedirs'), \
             patch.object(report.plt, 'get_backend', return_value='TkAgg'), \
             patch.object(report.plt, 'show') as show:
            self.capture(report.save_chart, fig, 'output/chart.png')
        show.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
