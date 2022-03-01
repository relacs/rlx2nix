from setuptools import find_packages, setup

from rlx2nix.info import infodict

NAME = infodict["NAME"]
VERSION = infodict["VERSION"]
AUTHOR = infodict["AUTHOR"]
CONTACT = infodict["CONTACT"]
DESCRIPTION =  infodict["BRIEF"]

classifiers = [
    'Development Status :: 3 - Alpha',
    'License :: OSI Approved :: BSD License',
    'Programming Language :: Python :: 3',
    'Topic :: Scientific/Engineering'
]

README = "README.md"
with open(README) as f:
    description_text = f.read()

install_req = ["nixio>=1.5", "python-odml", "numpy"]

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    author=AUTHOR,
    author_email=CONTACT,
    classifiers=classifiers,
    packages=find_packages(),
    install_requires=install_req,
    package_data = {'rlx2nix':['info.json']},
    include_package_data=True,
    long_description=description_text,
    long_description_content_type="text/markdown",
    license="BSD"
)
