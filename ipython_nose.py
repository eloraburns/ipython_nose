import cgi
import os
import traceback
import re
import shlex
import string
import sys
import types
import unittest
import uuid

from nose import core as nose_core
from nose import loader as nose_loader
from nose.config import Config, all_config_files
from nose.plugins.base import Plugin
from nose.plugins.skip import SkipTest
from nose.plugins.manager import DefaultPluginManager
from IPython.core import displaypub, magic
from IPython.zmq.displayhook import ZMQShellDisplayHook


class Template(string.Formatter):
    def __init__(self, template):
        self._template = template

    def format(self, context):
        return self.vformat(self._template, (), context)

    def convert_field(self, value, conversion):
        if conversion == 'e':
            return cgi.escape(value)
        else:
            return super(Template, self).convert_field(value, conversion)


class DummyUnittestStream:
    def write(self, *arg):
        pass
    def writeln(self, *arg):
        pass
    def flush(self, *arg):
        pass


class NotebookLiveOutput(object):
    def __init__(self):
        self.output_id = 'ipython_nose_%s' % uuid.uuid4().hex
        displaypub.publish_html(
            '<div id="%s"></div>' % self.output_id)
        displaypub.publish_javascript(
            'document.%s = $("#%s");' % (self.output_id, self.output_id))

    def finalize(self):
        displaypub.publish_javascript('delete document.%s;' % self.output_id)

    def write_chars(self, chars):
        displaypub.publish_javascript(
            'document.%s.append($("<span>%s</span>"));' % (
                self.output_id, cgi.escape(chars)))

    def write_line(self, line):
        displaypub.publish_javascript(
            'document.%s.append($("<div>%s</div>"));' % (
                self.output_id, cgi.escape(line)))


class ConsoleLiveOutput(object):
    def __init__(self, stream_obj):
        self.stream_obj = stream_obj

    def finalize(self):
        self.stream_obj.stream.write('\n')

    def write_chars(self, chars):
        self.stream_obj.stream.write(chars)

    def write_line(self, line):
        self.stream_obj.stream.write(line + '\n')


def html_escape(s):
    return cgi.escape(str(s))


class IPythonDisplay(Plugin):
    """Do something nice in IPython."""

    name = 'ipython-html'
    enabled = True
    score = 2

    def __init__(self, verbose=False):
        super(IPythonDisplay, self).__init__()
        self.verbose = verbose
        self.html = []
        self.num_tests = 0
        self.failures = []
        self.skipped = 0

    _nose_css = '''\
    <style type="text/css">
        span.nosefailedfunc {
            font-family: monospace;
            font-weight: bold;
        }
        div.noseresults {
            width: 100%;
        }
        div.nosebar {
            float: left;
            padding: 1ex 0px 1ex 0px;
        }
        div.nosebar.fail {
            background: red;
        }
        div.nosebar.pass {
            background: green;
        }
        div.nosebar.skip {
            background: yellow;
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

    _summary_template_html = Template('''
    <div class="noseresults">
      <div class="nosebar fail" style="width: {failpercent:d}%">&nbsp;</div>
      <div class="nosebar skip" style="width: {skippercent:d}%">&nbsp;</div>
      <div class="nosebar pass" style="width: {passpercent:d}%">&nbsp;</div>
      {text!e}
    </div>
    ''')

    _summary_template_text = Template('''{text}\n''')

    def _summary(self, numtests, numfailed, numskipped, template):
        if numfailed > 0:
            text = "%d/%d tests passed; %d failed; %d skipped" % (
                numtests - numfailed, numtests, numfailed, numskipped)
        else:
            text = "%d/%d tests passed" % (numtests, numtests)

        failpercent = int(float(numfailed) / numtests * 100)
        if numfailed > 0 and failpercent < 5:
            # ensure the red bar is visible
            failpercent = 5

        # Ditto for the yellow bar
        skippercent = int(float(numskipped) / numtests * 100)
        if numskipped > 0 and skippercent < 5:
            skippercent = 5

        passpercent = 100 - failpercent - skippercent

        return template.format(locals())

    _tracebacks_template_html = Template('''
    <div class="nosefailure">
        <div class="nosefailbanner">
          failed: <span class="nosefailedfunc">{name!e}</span>
            [<a class="nosefailtoggle" href="#">toggle traceback</a>]
        </div>
        <pre class="nosetraceback">{formatted_traceback!e}</pre>
    </div>
    ''')

    _tracebacks_template_text = Template(
        '''========\n{name}\n========\n{formatted_traceback}\n''')

    def _tracebacks(self, failures, template):
        output = []
        for test, exc in failures:
            name = test.shortDescription() or str(test)
            formatted_traceback = ''.join(traceback.format_exception(*exc))
            output.append(template.format(locals()))
        return ''.join(output)


    def addSuccess(self, test):
        if self.verbose:
            self.live_output.write_line(str(test) + " ... pass")
        else:
            self.live_output.write_chars('.')

    def addError(self, test, err):
        if issubclass(err[0], SkipTest):
            return self.addSkip(test)
        if self.verbose:
            self.live_output.write_line(str(test) + " ... error")
        else:
            self.live_output.write_chars('E')
        self.failures.append((test, err))

    def addFailure(self, test, err):
        if self.verbose:
            self.live_output.write_line(str(test) + " ... fail")
        else:
            self.live_output.write_chars('F')
        self.failures.append((test, err))

    # Deprecated in newer versions of nose; skipped tests are handled in
    # addError in newer versions
    def addSkip(self, test):
        if self.verbose:
            self.live_output.write_line(str(test) + " ... SKIP")
        else:
            self.live_output.write_chars('S')
        self.skipped += 1

    def begin(self):
        # This feels really hacky
        if isinstance(sys.displayhook, ZMQShellDisplayHook):
            self.live_output = NotebookLiveOutput()
        else:
            self.live_output = ConsoleLiveOutput(self)

    def finalize(self, result):
        self.result = result
        self.live_output.finalize()

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

    @staticmethod
    def make_link(matches):
        target = matches.group(0)
        input_id = matches.group(1)
        link = '<a href="#{target}">{target}</a>'.format(target=target)
        make_anchor_js = '''<script>
            $("div.prompt.input_prompt:contains([{input_id}])")
                .attr("id", "{target}");
            </script>'''.format(input_id=input_id, target=target)
        return link + make_anchor_js

    def linkify_html_traceback(self, html):
        return re.sub(
            r'ipython-input-(\d+)-[0-9a-f]{12}',
            self.make_link,
            html)

    def _repr_html_(self):
        if self.num_tests <= 0:
            return 'No tests found.'

        output = [self._nose_css, self._show_hide_js]

        output.append(self._summary(
            self.num_tests, len(self.failures), self.skipped,
            self._summary_template_html))
        output.append(self.linkify_html_traceback(self._tracebacks(
            self.failures, self._tracebacks_template_html)))
        return ''.join(output)

    def _repr_pretty_(self, p, cycle):
        if self.num_tests <= 0:
            p.text('No tests found.')
            return
        p.text(self._summary(
            self.num_tests, len(self.failures), self.skipped,
            self._summary_template_text))
        p.text(self._tracebacks(self.failures, self._tracebacks_template_text))


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
    extra_args = shlex.split(str(line))
    argv = ['ipython-nose', '--with-ipython-html', '--no-skip'] + extra_args
    verbose = '-v' in extra_args
    plug = IPythonDisplay(verbose=verbose)

    nose_core.TestProgram(
        argv=argv, suite=tests, addplugins=[plug], exit=False, config=config)

    return plug


def load_ipython_extension(ipython):
    magic.register_line_magic(nose)
