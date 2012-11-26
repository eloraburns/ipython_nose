import sys

from nose.tools import eq_

import ipython_nose


def assert_in(subject, container):
    if subject not in container:
        raise AssertionError("'%s' not in '%s'" % (subject, container))


def assert_not_in(subject, container):
    if subject in container:
        raise AssertionError("'%s' contains '%s'" % (container, subject))


def get_raised_exception_tuple_with_message(message):
    try:
        raise Exception(message)
    except Exception as e:
        return sys.exc_info()


class TestTemplate(object):
    def test_str(self):
        context = {'var': 'val<ue'}
        template = ipython_nose.Template('{var}')
        eq_('val<ue', template.format(context))

    def test_escaped_str(self):
        context = {'var': 'val<ue'}
        template = ipython_nose.Template('{var!e}')
        eq_('val&lt;ue', template.format(context))


class FakeTest(object):
    def shortDescription(self):
        return '<'


class TestIPythonDisplay(object):
    def setup(self):
        self.plugin = ipython_nose.IPythonDisplay()

    def test_summary_says_num_passed_and_total(self):
        summary = self.plugin._summary(
            numtests=5, numfailed=3, template=self.plugin._summary_template_text)
        assert_in('2/5 tests passed', summary)

    def test_summary_with_0_failed_doesnt_say_failed(self):
        summary = self.plugin._summary(
            numtests=1, numfailed=0, template=self.plugin._summary_template_text)
        assert_not_in('failed', summary)

    def test_summary_with_1_failed_does_say_failed(self):
        summary = self.plugin._summary(
            numtests=1, numfailed=1, template=self.plugin._summary_template_text)
        assert_in(' 1 failed', summary)

    def test_summary_with_0_failed_tests_has_0_and_100_bars(self):
        summary = self.plugin._summary(
            numtests=1, numfailed=0, template=self.plugin._summary_template_html)
        assert_in(' 0%', summary)
        assert_in(' 100%', summary)

    def test_summary_with_1_of_1000_passed_tests_has_5_and_95_bars(self):
        # numfailed goes from 0 to 5, so you can always see it clearly
        summary = self.plugin._summary(
            numtests=1000, numfailed=999, template=self.plugin._summary_template_html)
        assert_in(' 1%', summary)
        assert_in(' 99%', summary)

    def test_summary_with_999_of_1000_passed_tests_has_1_and_99_bars(self):
        # numfailed is truncated to 99 so you can always see a sliver of hope
        summary = self.plugin._summary(
            numtests=1000, numfailed=1, template=self.plugin._summary_template_html)
        assert_in(' 5%', summary)
        assert_in(' 95%', summary)

    def test_repr_html_works_with_no_tests(self):
        self.plugin.testsRun = 0
        eq_('No tests found.', self.plugin._repr_html_())

    def test_repr_pretty_works_with_no_tests(self):
        class MockPretty(object):
            def text(self, line):
                self.text_called_with = line
        p = MockPretty()
        self.plugin.testsRun = 0
        self.plugin._repr_pretty_(p=p, cycle=False)
        eq_('No tests found.', p.text_called_with)

    def test_tracebacks_in_html_escapes_test_name(self):
        exception_tuple = get_raised_exception_tuple_with_message('>')
        tracebacks = self.plugin._tracebacks(
            [
                (FakeTest(), exception_tuple),
            ],
            self.plugin._tracebacks_template_html
        )
        assert_in('&lt;', tracebacks)

    def test_tracebacks_in_html_escapes_traceback(self):
        exception_tuple = get_raised_exception_tuple_with_message('>')
        tracebacks = self.plugin._tracebacks(
            [
                (FakeTest(), exception_tuple),
            ],
            self.plugin._tracebacks_template_html

        )
        assert_in('&gt;', tracebacks)

    def test_tracebacks_in_text_does_not_escape_test_name(self):
        exception_tuple = get_raised_exception_tuple_with_message('>')
        tracebacks = self.plugin._tracebacks(
            [
                (FakeTest(), exception_tuple),
            ],
            self.plugin._tracebacks_template_text
        )
        assert_in('>', tracebacks)

    def test_tracebacks_in_text_does_not_escape_traceback(self):
        exception_tuple = get_raised_exception_tuple_with_message('>')
        tracebacks = self.plugin._tracebacks(
            [
                (FakeTest(), exception_tuple),
            ],
            self.plugin._tracebacks_template_text

        )
        assert_in('>', tracebacks)

    def test_linkify_html_traceback(self):
        frame_number = '1'
        frame_name = 'ipython-input-' + frame_number + '-0123456789ab'
        linkified = self.plugin.linkify_html_traceback(
            '&lt;' + frame_name + '&gt;')
        expected_link = (
            '&lt;<a href="#' +
            frame_name +
            '">' +
            frame_name +
            '</a>')
        assert expected_link in linkified, "\n%s\nnot in\n%s" % (
            expected_link, linkified)
        expected_selector = (
            '$("div.prompt.input_prompt:contains([' +
            frame_number +
            '])")')
        assert expected_selector in linkified, "\n%s\nnot in\n%s" % (
            expected_selector, linkified)
