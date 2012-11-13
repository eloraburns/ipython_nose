from distutils.core import setup


with open('README.rst') as f:
    long_description = f.read()


setup(
    name='ipython_nose',
    version='0.1.0',
    author='Taavi Burns <taavi at taaviburns dot ca>, Greg Ward <greg at gerg dot ca>',
    py_modules=['ipython_nose'],
    url='https://github.com/taavi/ipython_nose',
    license='README.rst',
    description='IPython extension to run nosetests against the current kernel.',
    long_description=long_description,
)
