from setuptools import setup, find_packages

# with open("README.md", "r") as fh:
#     long_description = fh.read()

setup(
    name='tcb',
    version="0.1",
    description=('A mass circuit simulator for the Tor network'),
    long_description="",
    author='Sebastian Rust',
    author_email='rustseba@informatik.hu-berlin.de',
    url='https://github.com/harlequix/tcb',
    license='MPL-2.0',
    packages=find_packages(),
    entry_points = {
        'console_scripts': ['tcb=tcb.main:main'],
    },
#   no dependencies in this example
#   install_requires=[
#       'dependency==1.2.3',
#   ],
#   no scripts in this example
#   scripts=['bin/a-script'],
    include_package_data=True,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Science/Research',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.6'],
    )
