from nose.tools import eq_

import ipython_nose


def assert_in(subject, container):
    if subject not in container:
        raise AssertionError("'%s' not in '%s'" % (subject, container))


def assert_not_in(subject, container):
    if subject in container:
        raise AssertionError("'%s' contains '%s'" % (container, subject))


class TestMyResult(object):
    def setup(self):
        self.result = ipython_nose.MyResult()

    def test_summary_says_num_passed_and_total(self):
        summary = self.result._summary(numtests=5, numfailed=3)
        assert_in('2/5 tests passed', summary)

    def test_summary_with_0_failed_doesnt_say_failed(self):
        summary = self.result._summary(numtests=1, numfailed=0)
        assert_not_in('failed', summary)

    def test_summary_with_1_failed_does_say_failed(self):
        summary = self.result._summary(numtests=1, numfailed=1)
        assert_in(' 1 failed', summary)

    def test_summary_with_0_failed_tests_has_0_and_100_bars(self):
        summary = self.result._summary(numtests=1, numfailed=0)
        assert_in(' 0%', summary)
        assert_in(' 100%', summary)

    def test_summary_with_1_of_1000_passed_tests_has_5_and_95_bars(self):
        # numfailed goes from 0 to 5, so you can always see it clearly
        summary = self.result._summary(numtests=1000, numfailed=999)
        assert_in(' 1%', summary)
        assert_in(' 99%', summary)

    def test_summary_with_999_of_1000_passed_tests_has_1_and_99_bars(self):
        # numfailed is truncated to 99 so you can always see a sliver of hope
        summary = self.result._summary(numtests=1000, numfailed=1)
        assert_in(' 5%', summary)
        assert_in(' 95%', summary)

    def test_repr_html_works_with_no_tests(self):
        self.result.testsRun = 0
        eq_('No tests found.', self.result._repr_html_())

    def test_tracebacks_escapes_test_name(self):
        tracebacks = self.result._tracebacks([('<', '')])
        assert_in('&lt;', tracebacks[0])

    def test_tracebacks_escapes_traceback(self):
        tracebacks = self.result._tracebacks([('', '>')])
        assert_in('&gt;', tracebacks[0])
