
#APS7BM_utils
#Alan Kastengren, XSD, APS

from setuptools import setup

setup(
    # 
    name='APS7BM_utils',
    url='https://github.com/aps-7bm/PyEpics_Scripting_Library',
    author='Alan Kastengren',
    author_email='',
    # Needed to actually package something
    packages=['APS7BM_utils'],
    # Needed for dependencies
    install_requires=[], # dependencies are expected to be installed.
    # *strongly* suggested for sharing
    version='0.1',
    # The license can be anything you like
    license='none',
    description='Library of functions for PyEpics scripting at the APS 7-BM beamline.',
    # We will also need a readme eventually (there will be a warning)
    long_description=open('README.md').read(),
)
