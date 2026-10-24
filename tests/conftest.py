"""Frozen v1 study regressions execute in their original source checkout.

They are not dropped: test_frozen_study_regression launches every listed file
against revision 121c755. Running them against changed v2 source correctly trips
their provenance locks. Current evaluator tests run normally in this checkout.
"""

from tests.frozen_suite import FILES

collect_ignore = list(FILES)
