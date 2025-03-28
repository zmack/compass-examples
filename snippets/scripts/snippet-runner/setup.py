from setuptools import setup, find_packages

setup(
    name="snippet-runner",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
        "graphql-core>=3.2.0",
        "jsonschema>=3.2.0",
        "rich>=10.0.0",
    ],
    entry_points={
        "console_scripts": [
            "snippet-runner=snippet_runner.cli:main",
        ],
    },
    python_requires=">=3.8",
    author="Compass Team",
    description="A tool for running GraphQL snippets",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
