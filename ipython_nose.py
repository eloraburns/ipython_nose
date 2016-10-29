import cgi
import os
import traceback
import re
import shlex
import string
import types
import uuid

from nose import core as nose_core
from nose import loader as nose_loader
from nose.config import Config, all_config_files
from nose.plugins.base import Plugin
from nose.plugins.skip import SkipTest
from nose.plugins.manager import DefaultPluginManager
from nose.selector import defaultSelector
from IPython.core import magic
from IPython.display import display


class Template(string.Formatter):
    def __init__(self, template):
        self._template = template

    def format(self, **context):
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
        display({'text/html': ('<div id="{self.output_id}"></div>'
                               .format(self=self))},
                raw=True)
        display({'application/javascript': ('document.{self.output_id} = '
                                            '$("#{self.output_id}");'
                                            .format(self=self))},
                raw=True)

    def finalize(self):
        display({'application/javascript': ('delete document.{self.output_id};'
                                            .format(self=self))},
                raw=True)

    def write_chars(self, chars):
        display({'application/javascript': ('document.{self.output_id}.append('
                                            '$("<span>{chars}</span>"));'
                                            .format(self=self,
                                                    chars=cgi.escape(chars)))},
                raw=True)

    def write_line(self, line):
        display({'application/javascript': ('document.{self.output_id}.append('
                                            '$("<div>{line}</div>"));')
                                            .format(self=self,
                                                    line=cgi.escape(line))},
                raw=True)


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

    def __init__(self, verbose=False, expand_tracebacks=False):
        super(IPythonDisplay, self).__init__()
        self.verbose = verbose
        self.expand_tracebacks = expand_tracebacks
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
            background: #ff3019; /* Old browsers */
            /* FF3.6+ */
            background: -moz-linear-gradient(top, #ff3019 0%, #cf0404 100%);
            /* Chrome,Safari4+ */
            background: -webkit-gradient(linear, left top, left bottom,
                                         color-stop(0%,#ff3019),
                                         color-stop(100%,#cf0404));
            /* Chrome10+,Safari5.1+ */
            background: -webkit-linear-gradient(top, #ff3019 0%,#cf0404 100%);
            /* Opera 11.10+ */
            background: -o-linear-gradient(top, #ff3019 0%,#cf0404 100%);
            /* IE10+ */
            background: -ms-linear-gradient(top, #ff3019 0%,#cf0404 100%);
            /* W3C */
            background: linear-gradient(to bottom, #ff3019 0%,#cf0404 100%);
        }
        div.nosebar.pass {
            background: #52b152;
            background: -moz-linear-gradient(top, #52b152 1%, #008a00 100%);
            background: -webkit-gradient(linear, left top, left bottom,
                                         color-stop(1%,#52b152),
                                         color-stop(100%,#008a00));
            background: -webkit-linear-gradient(top, #52b152 1%,#008a00 100%);
            background: -o-linear-gradient(top, #52b152 1%,#008a00 100%);
            background: -ms-linear-gradient(top, #52b152 1%,#008a00 100%);
            background: linear-gradient(to bottom, #52b152 1%,#008a00 100%);
        }
        div.nosebar.skip {
            background: #f1e767;
            background: -moz-linear-gradient(top, #f1e767 0%, #feb645 100%);
            background: -webkit-gradient(linear, left top, left bottom,
                                         color-stop(0%,#f1e767),
                                         color-stop(100%,#feb645));
            background: -webkit-linear-gradient(top, #f1e767 0%,#feb645 100%);
            background: -o-linear-gradient(top, #f1e767 0%,#feb645 100%);
            background: -ms-linear-gradient(top, #f1e767 0%,#feb645 100%);
            background: linear-gradient(to bottom, #f1e767 0%,#feb645 100%);
        }
        div.nosebar.leftmost {
            border-radius: 4px 0 0 4px;
        }
        div.nosebar.rightmost {
            border-radius: 0 4px 4px 0;
        }
        div.nosefailbanner {
            border-radius: 4px 0 0 4px;
            border-left: 10px solid #cf0404;
            padding: 0.5ex 0em 0.5ex 1em;
            margin-top: 1ex;
            margin-bottom: 0px;
        }
        div.nosefailbanner.expanded {
            border-radius: 4px 4px 0 0;
            border-top: 10px solid #cf0404;
        }
        pre.nosetraceback {
            border-radius: 0 4px 4px 4px;
            border-left: 10px solid #cf0404;
            padding: 1em;
            margin-left: 0px;
            margin-top: 0px;
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
                            .parent().toggleClass('expanded')
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
      <div class="nosebar fail leftmost" style="width: {failpercent:d}%">
          &nbsp;
      </div>
      <div class="nosebar skip" style="width: {skippercent:d}%">
          &nbsp;
      </div>
      <div class="nosebar pass rightmost" style="width: {passpercent:d}%">
          &nbsp;
      </div>
      {text!e}
    </div>
    ''')

    _summary_template_text = Template('''{text}\n''')

    def _summary(self, numtests, numfailed, numskipped, template):
        text = "%d/%d tests passed" % (numtests - numfailed, numtests)
        if numfailed > 0:
            text += "; %d failed" % numfailed
        if numskipped > 0:
            text += "; %d skipped" % numskipped

        failpercent = int(float(numfailed) / numtests * 100)
        if numfailed > 0 and failpercent < 5:
            # Ensure the red bar is visible
            failpercent = 5

        skippercent = int(float(numskipped) / numtests * 100)
        if numskipped > 0 and skippercent < 5:
            # Ditto for the yellow bar
            skippercent = 5

        passpercent = 100 - failpercent - skippercent

        return template.format(
            text=text, failpercent=failpercent, skippercent=skippercent,
            passpercent=passpercent)

    _tracebacks_template_html = Template('''
    <div class="nosefailure">
        <div class="nosefailbanner">
          failed: <span class="nosefailedfunc">{name!e}</span>
            [<a class="nosefailtoggle" href="#">toggle traceback</a>]
        </div>
        <pre class="nosetraceback" style="display:{hide_traceback_style}">{formatted_traceback!e}</pre>
    </div>
    ''')

    _tracebacks_template_text = Template(
        '''========\n{name}\n========\n{formatted_traceback}\n''')

    def _tracebacks(self, failures, template):
        output = []
        for test, exc in failures:
            name = test.shortDescription() or str(test)
            formatted_traceback = ''.join(traceback.format_exception(*exc))
            output.append(template.format(
                name=name, formatted_traceback=formatted_traceback,
                hide_traceback_style=('block' if self.expand_tracebacks
                                      else 'none')
            ))
        return ''.join(output)

    def _write_test_line(self, test, status):
        self.live_output.write_line(
            "{} ... {}".format(test.shortDescription() or str(test), status))

    def addSuccess(self, test):
        if self.verbose:
            self._write_test_line(test, 'pass')
        else:
            self.live_output.write_chars('.')

    def addError(self, test, err):
        if issubclass(err[0], SkipTest):
            return self.addSkip(test)
        if self.verbose:
            self._write_test_line(test, 'error')
        else:
            self.live_output.write_chars('E')
        self.failures.append((test, err))

    def addFailure(self, test, err):
        if self.verbose:
            self._write_test_line(test, 'fail')
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
        self.live_output = NotebookLiveOutput()

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


class ExcludingTestSelector(defaultSelector):
    def __init__(self, config, excluded_objects):
        super(ExcludingTestSelector, self).__init__(config)
        self.excluded_objects = list(excluded_objects)

    def wantClass(self, cls):
        if cls in self.excluded_objects:
            return False
        else:
            return super(ExcludingTestSelector, self).wantClass(cls)

    def wantFunction(self, function):
        if function in self.excluded_objects:
            return False
        else:
            return super(ExcludingTestSelector, self).wantFunction(function)

    def wantMethod(self, method):
        if type(method.__self__) in self.excluded_objects:
            return False
        else:
            return super(ExcludingTestSelector, self).wantMethod(method)


def nose(line, cell=None, test_module=get_ipython_user_ns_as_a_module):
    if callable(test_module):
        test_module = test_module()
    config = makeNoseConfig(os.environ)
    if cell is None:
        # Called as the %nose line magic.
        # All objects in the notebook namespace should be considered for the
        # test suite.
        selector = None
    else:
        # Called as the %%nose cell magic.
        # Classes and functions defined outside the cell should be excluded from
        # the test run.
        selector = ExcludingTestSelector(config, test_module.__dict__.values())
        # Evaluate the cell and add objects it defined into the test module.
        exec(cell, test_module.__dict__)
    loader = nose_loader.TestLoader(config=config, selector=selector)
    tests = loader.loadTestsFromModule(test_module)
    extra_args = shlex.split(str(line))
    expand_tracebacks = '--expand-tracebacks' in extra_args
    if expand_tracebacks:
        extra_args.remove('--expand-tracebacks')
    argv = ['ipython-nose', '--with-ipython-html', '--no-skip'] + extra_args
    verbose = '-v' in extra_args
    plug = IPythonDisplay(verbose=verbose, expand_tracebacks=expand_tracebacks)

    nose_core.TestProgram(
        argv=argv, suite=tests, addplugins=[plug], exit=False, config=config)

    return plug


def load_ipython_extension(ipython):
    magic.register_line_cell_magic(nose)
