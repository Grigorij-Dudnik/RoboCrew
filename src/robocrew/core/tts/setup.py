# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name="polly",
    version="0.1.0",
    description="Polish TTS module using Piper voice synthesis (POLish + parrot = Polly!)",
    author="shinken",
    py_modules=["polly"],
    install_requires=[
        "piper-tts>=1.0.0",
    ],
    python_requires=">=3.6",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
    ],
)
