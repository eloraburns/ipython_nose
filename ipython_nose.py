from types import ModuleType
import cgi
import unittest

from IPython.core.magic import register_line_magic
from nose import core
from nose.loader import TestLoader


class MyProgram(core.TestProgram):
    # XXX yuck: copy superclass runTests() so we can instantiate our own runner class;
    # can't do it early because we don't have access to nose's config object.
    def runTests(self):
        self.testRunner = MyRunner(self.config)
        # the rest is mostly duplicate code ;-(
        plug_runner = self.config.plugins.prepareTestRunner(self.testRunner)
        if plug_runner is not None:
            self.testRunner = plug_runner
        self.result = self.testRunner.run(self.test)
        self.success = self.result.wasSuccessful()
        return self.success


class MyResult(unittest.TestResult):
    def make_bar(self, tests, failing):
        return '''<div style="clear:both;">
                <div style="color: white; background:red; width:%(failing)dpx; float:left;">FAIL</div>
                <div style="color: white; background:green; width:%(passing)dpx; float:left;">PASS</div>
                </div><div style="clear:both;"></div>''' % {
                        'failing': failing * 10,
                        'passing': (tests - failing) * 10}

    def make_table_of_tests(self, tests):
        table = '<table>'
        for test in tests:
            table += '<tr><td>%s</td><td><div>Show</div><pre>%s</pre></td>' % (
                str(test[0]), cgi.escape(test[1]))
        table += '</table>'
        return table

    def _repr_html_(self):
        if self.errors or self.failures:
            not_successes = len(self.errors) + len(self.failures)
            return self.make_bar(self.testsRun, not_successes) + \
                '''
                <h2 style="color:red">Errors</h2>%s
                <h2 style="color:red">Failures</h2>%s''' % (
                    self.make_table_of_tests(self.errors),
                    self.make_table_of_tests(self.failures))
        else:
            return self.make_bar(self.testsRun, 0) + '<div>%d/%d&nbsp;tests&nbsp;passed</div>' % (
                self.testsRun, self.testsRun)


class MyRunner(object):
    def __init__(self, config):
        self.config = config

    def run(self, test):
        result = MyResult()
        if hasattr(result, 'startTestRun'):   # python 2.7
            result.startTestRun()
        test(result)
        if hasattr(result, 'stopTestRun'):
            result.stopTestRun()
        self.config.plugins.finalize(result)
        self.result = result
        return result


def nose(line):
    test_module = ModuleType('test_module')
    test_module.__dict__.update(get_ipython().user_ns)

    loader = TestLoader()
    tests = loader.loadTestsFromModule(test_module)

    tprog = MyProgram(argv=['dummy'], suite=tests)
    return tprog.result

def load_ipython_extension(ipython):
    register_line_magic(nose)
