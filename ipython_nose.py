import cgi
import os
import random
import traceback
import types
import unittest

from nose import core as nose_core
from nose import loader as nose_loader
from nose.config import Config, all_config_files
from nose.plugins.base import Plugin
from nose.plugins.manager import DefaultPluginManager
import IPython


class DummyUnittestStream:
    def write(self, *arg):
        pass
    def writeln(self, *arg):
        pass
    def flush(self, *arg):
        pass

class IPythonDisplay(Plugin):
    """Do something nice in IPython."""

    name = 'ipython-html'
    enabled = True
    score = 2

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

    _summary_template = '''
    <div class="noseresults">
      <div class="nosefailbar" style="width: {failpercent}%">&nbsp;</div>
      <div class="nosepassbar" style="width: {passpercent}%">&nbsp;</div>
      {text}
    </div>
    '''

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

        return self._summary_template.format(**locals())

    _tracebacks_template = '''
    <div class="nosefailure">
        <div class="nosefailbanner">
          failed: <span class="nosefailedfunc">{name}</span>
            [<a class="nosefailtoggle" href="#">toggle traceback</a>]
        </div>
        <pre class="nosetraceback">{formatted_traceback}</pre>
    </div>
    '''

    def _tracebacks(self, failures):
        output = []
        for test, exc in failures:
            name = cgi.escape(test.shortDescription() or str(test))
            formatted_traceback = cgi.escape(
                ''.join(traceback.format_exception(*exc)))
            output.append(self._tracebacks_template.format(**locals()))
        return ''.join(output)


    def __init__(self):
        super(IPythonDisplay, self).__init__()
        self.html = []
        self.num_tests = 0
        self.failures = []
        self.html_id = 'ipython_nose_%d' % random.randint(1, 4*10**8)

    def pub_js(self, js):
        IPython.core.displaypub.publish_javascript(js)

    def pub_html(self, html):
        IPython.core.displaypub.publish_html(html)

    def append(self, html):
        self.pub_js('document.%s.append($("<strong>%s</strong>"));' % (self.html_id, html))

    def addSuccess(self, test):
        self.append('.')

    def addError(self, test, err):
        self.append('E')
        self.failures.append((test, err))

    def addFailure(self, test, err):
        self.append('F')
        self.failures.append((test, err))

    def addSkip(self, test):
        self.append('S')

    def begin(self):
        self.pub_html('<div id="%s"></div>' % self.html_id)
        self.pub_js('document.%s = $("#%s");' % (self.html_id, self.html_id))

    def finalize(self, result):
        self.result = result
        self.pub_js('delete document.%s;' % self.html_id)

    def setOutputStream(self, stream):
        # grab for own use
        self.stream = stream
        return DummyUnittestStream()

    def startContext(self, ctx):
        pass

    def stopContext(self, ctx):
        pass

    def startTest(self, test):
        self.num_tests += 1

    def stopTest(self, test):
        pass

    def _repr_html_(self):
        if self.num_tests <= 0:
            return 'No tests found.'

        output = [self._nose_css, self._show_hide_js]

        output.append(self._summary(self.num_tests, len(self.failures)))
        output.append(self._tracebacks(self.failures))
        return ''.join(output)

def get_ipython_user_ns_as_a_module():
    test_module = types.ModuleType('test_module')
    test_module.__dict__.update(get_ipython().user_ns)
    return test_module

def makeNoseConfig(env):
    """Load a Config, pre-filled with user config files if any are
    found.
    """
    cfg_files = all_config_files()
    manager = DefaultPluginManager()
    return Config(env=env, files=cfg_files, plugins=manager)

def nose(line, test_module=get_ipython_user_ns_as_a_module):
    if callable(test_module):
        test_module = test_module()
    config = makeNoseConfig(os.environ)
    loader = nose_loader.TestLoader(config=config)
    tests = loader.loadTestsFromModule(test_module)
    plug = IPythonDisplay()

    nose_core.TestProgram(
        argv=['ipython-nose', '--with-ipython-html'], suite=tests,
        addplugins=[plug], exit=False, config=config)

    return plug

def load_ipython_extension(ipython):
    from IPython.core.magic import register_line_magic
    register_line_magic(nose)
