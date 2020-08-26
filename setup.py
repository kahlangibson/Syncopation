import setuptools

with open("README.md", 'r') as readme:
    long_description = readme.read()

setuptools.setup(
    name="syncopation",
    version="1.0.0",
    author="Kahlan Gibson",
    author_email="kahlangibson@ece.ubc.ca",
    description="Syncopation HLS command-line tool",
    long_description=long_description,
    url="https://github.com/kahlangibson/Syncopation",
    packages=setuptools.find_packages(),
    install_requires = ['docopt'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
    ],
    entry_points={
        'console_scripts': [
            'syncopation=src.syncopation:main'
        ]
    }
)