from setuptools import setup, find_packages

setup(
    name="snippet-runner",  # Distribution name can have hyphens
    version="0.1.0",
    packages=["snippet_runner"],  # Package name must use underscores
    install_requires=[
        "requests>=2.25.0",
        "graphql-core>=3.2.0",
        "jsonschema>=3.2.0",
        "rich>=10.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.10.0",
            "black>=20.8b1",
        ],
    },
    entry_points={
        'console_scripts': [
            'snippet-runner=snippet_runner.cli:main',  # Use underscore in import path
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
