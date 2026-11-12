# Team 3 — Milestone 3 Defect Report

## Application Under Test

Poetry GitHub Issue Analyzer (assigned team implementation).

Testing branch: https://github.com/bgovinda2003/enpm611-milestone3-testing/tree/testing

Testing pull request: https://github.com/bgovinda2003/enpm611-milestone3-testing/pull/1

## Testing Summary

Team 3 performed independent white-box unit testing with Python's `unittest` framework and measured statement coverage with `coverage.py`.

The suite covers configuration, data loading, the issue model, shared issue metrics, reporting, the command-line entry point, the example analysis, and all three analysis features.

Tests were executed together with:

```
python -m unittest discover
coverage run -m unittest discover
coverage report
```

Test modules are excluded from the coverage total by `.coveragerc`.

## Test Results

- Total tests executed: **258**
- Passed: **256**
- Failed: **2**
- Errors: **0**
- Total executable statements: **825**
- Statements covered: **818**
- Statements missed: **7**
- Total statement coverage: **99%**
- Required coverage: **90%**

Full command output is in `team_3_test_failures.txt`. The coverage table is in `team_3_test_coverage.txt`.

## Defect Findings

### DEF-001 — `get_parameter()` discards a falsy default

| Field | Value |
| --- | --- |
| Severity | Major |
| Status | Open |
| Location | `config.py`, `get_parameter()` |

**Description.** When a requested key is absent from both the environment and `config.json`, the function is documented to return the caller-supplied default. The guard is `if default:`, so a default of `0`, `""`, `False`, or `[]` is treated as missing and the function returns `None`.

**Steps to reproduce.**

1. From the repository root, with the virtual environment active:
   ```
   python -c "import config; print(repr(config.get_parameter('ENPM611_MISSING_TEST_KEY', 0)))"
   ```
2. Or run:
   ```
   python -m unittest test_config.TestConfig.test_get_falsy_numeric_default
   ```

**Expected.** `0`

**Actual.** `None`

**Evidence.** `FAIL: test_get_falsy_numeric_default` in `team_3_test_failures.txt`.

### DEF-002 — `print_table()` raises `IndexError` for an empty row list

| Field | Value |
| --- | --- |
| Severity | Major |
| Status | Open |
| Location | `report.py`, `print_table()` |

**Description.** Printing a table with headers but no data rows raises `IndexError: list index out of range` inside `tabulate` (version 0.9.0, the current unpinned install of `tabulate`). The function still builds column alignments and `maxcolwidths` and then passes an empty cell list to `tabulate`.

**Steps to reproduce.**

1. From the repository root, with the virtual environment active:
   ```
   python -c "from report import print_table; print_table(['name', 'count'], [])"
   ```
2. Or run:
   ```
   python -m unittest test_report.TestReport.test_print_table_empty_rows
   ```

**Expected.** A grid table that shows the header row and no data rows.

**Actual.** `IndexError: list index out of range`

**Evidence.** `FAIL: test_print_table_empty_rows` in `team_3_test_failures.txt`. The test catches the `IndexError` and fails the assertion, so unittest reports this as a failure rather than an error.

## Untested Statements

The 7 uncovered statements are unused `__main__` entry points and a Python 2 compatibility branch. They are coverage gaps, not confirmed defects.

| File | Missed lines | Reason untested |
| --- | --- | --- |
| `config.py` | 113–114 | Python 2 `vars(args).iteritems()` path; it always fails on Python 3 and is swallowed by `except:` |
| `data_loader.py` | 50 | `if __name__ == '__main__'` |
| `example_analysis.py` | 63 | `if __name__ == '__main__'` |
| `first_reporter_code_share_analysis.py` | 286 | `if __name__ == '__main__'` |
| `related_issues_analysis.py` | 406 | `if __name__ == '__main__'` |
| `template_switch_analysis.py` | 235 | `if __name__ == '__main__'` |

## Conclusion

The suite exceeds the 90% statement-coverage requirement at **99%**. Two reproducible production defects were confirmed: falsy defaults in `get_parameter()` and a crash in `print_table()` when the row list is empty. Passing tests show that the covered behavior matched the assertions; they do not guarantee the absence of other defects.

## Supporting Evidence

- `team_3_test_failures.txt`
- `team_3_test_coverage.txt`
- `team_3_testing_pr.txt`
- `team_3_test_repo.txt`
