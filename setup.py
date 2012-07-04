#!/usr/bin/env python

import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

def get_version():
    from txthoonk import __version__ as v
    return v

sdict = {
    'name' : 'txthoonk',
    'version' : get_version(),
    'packages' : ['txthoonk', 'tests'],
    'description' : 'Python/Twisted client for Thoonk',
    'author' : 'Iuri Diniz',
    'author_email' : 'iuridiniz@gmail.com',
    'maintainer' : 'Iuri Diniz',
    'maintainer_email' : 'iuridiniz@gmail.com',
    'license': 'MIT',
    'url': 'http://pypi.python.org/pypi/txthoonk',
    'keywords': ['Redis', 'Thoonk', 'Twisted'],
    'long_description': read('README.rst'),
    'classifiers' : [
        'Classifier: Development Status :: 1 - Planning',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Classifier: License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Framework :: Twisted',
        'Platform: OS Independent',
        ],
}

setup(**sdict)
