"""FileDrop - 轻量级自托管文件共享服务器"""

from setuptools import setup, find_packages

setup(
    name="filedrop",
    version="1.0.0",
    description="轻量级自托管文件共享服务器",
    long_description=open("README.md", encoding="utf-8").read() if __import__("os").path.exists("README.md") else "",
    author="FileDrop",
    license="MIT",
    python_requires=">=3.8",
    packages=find_packages(),
    package_data={
        "filedrop": ["templates/*.html"],
    },
    entry_points={
        "console_scripts": [
            "filedrop=filedrop.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Utilities",
    ],
)
