import types
import cgi
import unittest

import nose.core
from nose import loader as nose_loader

class TestProgram(nose.core.TestProgram):
    # XXX yuck: copy superclass runTests() so we can instantiate our own
    # runner class; can't do it early because we don't have access to
    # nose's config object.
    def runTests(self):
        self.testRunner = TestRunner(self.config)
        # the rest is mostly duplicate code ;-(
        plug_runner = self.config.plugins.prepareTestRunner(self.testRunner)
        if plug_runner is not None:
            self.testRunner = plug_runner
        self.result = self.testRunner.run(self.test)
        self.success = self.result.wasSuccessful()
        return self.success

class TestResult(unittest.TestResult):
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
            display: none;
        }
    </style>
    '''

    _show_hide_js = '''
    <script>
        setTimeout(function () {
            $('.nosefailtoggle').bind(
                'click',
                function () {
                    $(
                        $(this)
                            .parent()
                            .parent()
                            .children()
                            .filter('.nosetraceback')
                    ).toggle();
                }
            );},
            0);
    </script>
    '''

    def _repr_html_(self):
        numtests = self.testsRun
        if numtests == 0:
            return 'No tests found.'

        # merge errors and failures: the distinction is for pedants only
        failures = self.errors + self.failures
        result = [self._nose_css, self._show_hide_js]
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
            result.append('''
<div class="nosefailure">
    <div class="nosefailbanner">
      failed: <span class="nosefailedfunc">%(name)s</span>
        [<a class="nosefailtoggle" href="#">toggle traceback</a>]
    </div>
    <pre class="nosetraceback">%(traceback)s</pre>
</div>
''' % locals())
        return result

class TestRunner(object):
    def __init__(self, config):
        self.config = config

    def run(self, test):
        result = TestResult()
        if hasattr(result, 'startTestRun'):   # python 2.7
            result.startTestRun()
        test(result)
        if hasattr(result, 'stopTestRun'):
            result.stopTestRun()
        self.config.plugins.finalize(result)
        self.result = result
        return result

def nose(line):
    test_module = types.ModuleType('test_module')
    test_module.__dict__.update(get_ipython().user_ns)

    loader = nose_loader.TestLoader()
    tests = loader.loadTestsFromModule(test_module)

    tester = TestProgram(argv=['dummy'], suite=tests)
    return tester.result

def load_ipython_extension(ipython):
    from IPython.core.magic import register_line_magic
    register_line_magic(nose)
