# Snippet Runner

A tool for running GraphQL snippets with schema validation.

## Installation

```bash
pip install -e .
```

## Usage

First, set up your environment variables:

```bash
# GraphQL API credentials
export ATL_USERNAME="your_username"
export ATL_PASSWORD="your_password"
export ATL_URL="your_graphql_endpoint"

# Path to your snippets directory
export ATL_SNIPPET_PATH="/path/to/your/snippets"
```

Then you can use the tool in several ways:

1. As a command-line tool:
```bash
# List available snippets
snippet-runner list

# View schema for a snippet
snippet-runner peek <snippet_name>

# View README for a snippet
snippet-runner help <snippet_name>

# Run a snippet with arguments
snippet-runner run <snippet_name> '{"arg1": "value1"}'
```

2. As a Python module:
```bash
# From the scripts directory
python -m snippet_runner list
python -m snippet_runner peek <snippet_name>
python -m snippet_runner help <snippet_name>
python -m snippet_runner run <snippet_name> '{"arg1": "value1"}'
```

3. As a Python library:
```python
from snippet_runner import Client, Snippet, run_snippet

client = Client(url="...", username="...", password="...")
snippet = Snippet(name="my_snippet", path="/path/to/snippet", client=client)
response = run_snippet(snippet, client, {"arg1": "value1"})
```

## Development

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```

2. Install in development mode:
```bash
pip install -e ".[dev]"
