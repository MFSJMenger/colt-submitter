#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

requirements = ['colt>=0.2', 'jinja2>=3.0']

setup_requirements = ['pytest-runner', ]

test_requirements = ['pytest>=3', ]

setup(
    author="Maximilian F.S.J. Menger",
    author_email='m.f.s.j.menger@rug.nl',
    python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    description="Basic submit script generation tool",
    install_requires=requirements,
    license="Apache License v2.0",
    long_description=readme + '\n\n',
    entry_points = {
        'console_scripts': {
            'submit': submitter.Submitter.run,
            },
    },
    include_package_data=True,
    keywords='colt-submitter',
    name='colt-submitter',
    packages=find_packages(include=['submitter']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/mfsjmenger/colt-submitter',
    version='0.1.0',
    zip_safe=False,
)
