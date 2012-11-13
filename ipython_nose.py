from types import ModuleType
import cgi
import unittest

from IPython.core.magic import register_line_magic
from nose import core
from nose.loader import TestLoader


_nose_css = '''\
<style type="text/css">
  span.nosefailedfunc {
    font-family: monospace;
    font-weight: bold;
  }
  div.noseresults {
    width: 100%;
  }
  div.nosefailbar {
    background: red;
    float: left;
    padding: 1ex 0px 1ex 0px;
  }
  div.nosepassbar {
    background: green;
    float: left;
    padding: 1ex 0px 1ex 0px;
  }
  div.nosefailbanner {
    width: 75%;
    background: red;
    padding: 0.5ex 0em 0.5ex 1em;
    margin-top: 1ex;
    margin-bottom: 0px;
  }
  pre.nosetraceback {
    background: pink;
    padding-left: 1em;
    margin-left: 0px;
    margin-top: 0px;
    /*display: none;*/
  }
</style>
'''

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

    def _repr_html_(self):
        numtests = self.testsRun
        if numtests == 0:
            return 'No tests found.'

        # merge errors and failures: the distinction is for pedants only
        failures = self.errors + self.failures
        result = [_nose_css]
        result.append(self._summary(numtests, len(failures)))
        if failures:
            result.extend(self._tracebacks(failures))
        return "".join(result)

    def _summary(self, numtests, numfailed):
        if numfailed > 0:
            text = "%d/%d tests passed; %d failed" % (
                numtests - numfailed, numtests, numfailed)
        else:
            text = "%d/%d tests passed" % (numtests, numtests)

        failpercent = int(float(numfailed) / numtests * 100)
        if numfailed > 0 and failpercent < 5:
            # ensure the red bar is visible
            failpercent = 5
        passpercent = 100 - failpercent

        return '''
<div class="noseresults">
  <div class="nosefailbar" style="width: %(failpercent)d%%">&nbsp;</div>
  <div class="nosepassbar" style="width: %(passpercent)d%%">&nbsp;</div>
  %(text)s
</div>
''' % locals()

    def _tracebacks(self, failures):
        result = []
        for (test, traceback) in failures:
            name = cgi.escape(str(test))
            traceback = cgi.escape(traceback)
            result.append('''\
<div class="nosefailbanner">
  failed: <span class="nosefailedfunc">%(name)s</span>
</div>
<pre class="nosetraceback">
%(traceback)s
</pre>
''' % locals())
        return result

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


@register_line_magic
def nose(line):
    test_module = ModuleType('test_module')
    test_module.__dict__.update(get_ipython().user_ns)

    loader = TestLoader()
    tests = loader.loadTestsFromModule(test_module)

    tprog = MyProgram(argv=['dummy'], suite=tests)
    return tprog.result
