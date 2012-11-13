from nose.tools import eq_

import ipython_nose


def assert_in(subject, container):
    if subject not in container:
        raise AssertionError("'%s' not in '%s'" % (subject, container))


def assert_not_in(subject, container):
    if subject in container:
        raise AssertionError("'%s' contains '%s'" % (container, subject))


class TestMyResult(object):
    def test_summary_with_0_failed_doesnt_say_failed(self):
        r = ipython_nose.MyResult()
        summary = r._summary(1, 0)
        assert_not_in('failed', summary)

    def test_summary_with_1_failed_does_say_failed(self):
        r = ipython_nose.MyResult()
        summary = r._summary(1, 1)
        assert_in('failed', summary)

    def test_repr_html_works_with_no_tests(self):
        r = ipython_nose.MyResult()
        r.testsRun = 0
        eq_('No tests found.', r._repr_html_())
