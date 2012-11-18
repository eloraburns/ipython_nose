from cStringIO import StringIO
import cgi
import os
import types
import unittest

from nose import core as nose_core
from nose import loader as nose_loader
from nose.config import Config, all_config_files
from nose.plugins.base import Plugin
from nose.plugins.manager import DefaultPluginManager


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

    def __init__(self):
        super(IPythonDisplay, self).__init__()
        self.html = []

    def addSuccess(self, test):
        self.html.append("<b style='color:green'>pass</b>")

    def addError(self, test, err):
        self.html.append("<b style='color:blue'>error</b>")

    def addFailure(self, test, err):
        self.html.append("<b style='color:red'>failure</b>")

    def addSkip(self, test):
        self.html.append("<b style='color:darkyellow'>skip</b>")

    def begin(self):
        self.html.append('<div><h1>Start plugin</h1>')

    def finalize(self, result):
        self.html.append('<!-- end plugin --></div>')

    def setOutputStream(self, stream):
        # grab for own use
        self.stream = stream
        return DummyUnittestStream()

    def startContext(self, ctx):
        pass

    def stopContext(self, ctx):
        pass

    def startTest(self, test):
        self.html.append('<div><h2>Starting %s</h2>' % cgi.escape(repr(test)))

    def stopTest(self, test):
        self.html.append('</div>')

    def _repr_html_(self):
        return '\n'.join(self.html)


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


def nose(line, test_module_getter=get_ipython_user_ns_as_a_module):
    test_module = test_module_getter()
    config = makeNoseConfig(os.environ)
    loader = nose_loader.TestLoader(config=config)
    tests = loader.loadTestsFromModule(test_module)
    plug = IPythonDisplay()

    tester = nose_core.TestProgram(
        argv=['ipython-nose', '--with-ipython-html'], suite=tests,
        addplugins=[plug], exit=False, config=config)

    return plug


def load_ipython_extension(ipython):
    from IPython.core.magic import register_line_magic
    register_line_magic(nose)
