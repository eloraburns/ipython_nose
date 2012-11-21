import types

import ipython_nose

test_module = types.ModuleType('test_module')
from nose.plugins.skip import SkipTest

def test_foo():
    assert True

def test_bar():
    assert False

def test_baz():
    raise Exception()

def test_quux():
    raise SkipTest()

test_module.test_foo = test_foo
test_module.test_bar = test_bar
test_module.test_baz = test_baz
test_module.test_quux = test_quux

plugin = ipython_nose.nose('', test_module)
print plugin._repr_html_()
