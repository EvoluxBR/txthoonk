#!/usr/bin/env python

import os
from setuptools import setup

#def read(fname):
#    return open(os.path.join(os.path.dirname(__file__), fname)).read()

def get_version():
    from txthoonk import __version__ as v
    return v

def get_long_description():
    import txthoonk as t
    # remove blank lines
    return "\n".join([l for l in t.__doc__.splitlines() if l]) #@UndefinedVariable

sdict = {
    'name' : 'txthoonk',
    'version' : get_version(),
    'packages' : ['txthoonk'],
    'description' : 'Python/Twisted client for Thoonk',
    'author' : 'Iuri Diniz',
    'author_email' : 'iuridiniz@gmail.com',
    'maintainer' : 'Iuri Diniz',
    'maintainer_email' : 'iuridiniz@gmail.com',
    'license': 'MIT',
    'url': 'https://github.com/Diginet/txthoonk',
    'download_url':'http://pypi.python.org/pypi/txthoonk',
    'keywords': ['Redis', 'Thoonk', 'Twisted'],
    'long_description': get_long_description(),
    'install_requires': ['Twisted>=10.1.0',
                         'txredis>=2.2'],
    'test_suite': 'tests',
    'classifiers' : [
        'Development Status :: 1 - Planning',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Framework :: Twisted',
        ],
}

setup(**sdict)
