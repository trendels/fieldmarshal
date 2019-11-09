import os
import re

from setuptools import setup, find_packages

with open(os.path.join('src', 'fieldmarshal', '__init__.py')) as f:
    VERSION = re.search(
        r'^__version__\s*=\s*[\'"](.*)[\'"]', f.read(), re.M
    ).group(1)

with open('README.md') as f:
    README = f.read()

setup(
    name='fieldmarshal',
    version=VERSION,
    author='Stanis Trendelenburg',
    author_email='stanis.trendelenburg@gmail.com',
    url='https://github.com/trendels/fieldmarshal',
    license='MIT',
    description='Marshal/unmarshal attrs-based data classes to and from JSON',
    long_description=README,
    long_description_content_type='text/markdown',
    classifiers = [
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    packages=find_packages('src'),
    package_dir={'': 'src'},
    install_requires=['attrs>=17.4.0'],
    zip_safe=False,
)
