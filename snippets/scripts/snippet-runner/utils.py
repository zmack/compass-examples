"""Utility functions for snippet management."""

import os
from typing import List

import json
import requests
from requests.auth import HTTPBasicAuth
from rich.console import Console
from rich.syntax import Syntax

from .client import Client
from .snippet import Snippet


def list_files_in_directory(directory: str) -> List[str]:
    """
    Get a list of all directories in the specified directory.

    Args:
        directory: Path to directory to list

    Returns:
        List of directory names
    """
    all_items = os.listdir(directory)
    # Filter to keep only directories
    dirs = [f for f in all_items if os.path.isdir(os.path.join(directory, f))]
    return dirs


def get_snippet_list(
    client: Client, path: str = os.path.dirname(__file__)
) -> List[Snippet]:
    """
    Get list of available snippets in the specified directory.

    Args:
        client: GraphQL client instance
        path: Directory path containing snippets, defaults to current directory

    Returns:
        List of Snippet instances
    """
    return [
        Snippet(
            name=snippet_name,
            path=os.path.join(path, snippet_name),
            client=client,
        )
        for snippet_name in list_files_in_directory(path)
    ]


def run_snippet(snippet: Snippet, client: Client, args: dict) -> requests.Response:
    """
    Execute a GraphQL snippet.

    Args:
        snippet: Snippet instance to run
        client: GraphQL client instance
        args: Variables to pass to the query

    Returns:
        Response from the GraphQL server
    """
    if not snippet.content:
        raise ValueError(f"No content found for snippet {snippet.name}")

    payload = {
        "query": snippet.content,
        "variables": args,
        "operationName": snippet.operation_name,
    }

    response = requests.post(
        url=client.url,
        json=payload,
        headers={"X-ExperimentalApi": "compass-prototype"},
        auth=HTTPBasicAuth(client.username, client.password),
    )
    response.raise_for_status()
    return response


def pretty_print(data: dict) -> None:
    """Pretty print JSON data with syntax highlighting."""
    syntax = Syntax(
        json.dumps(data, indent=4),
        "json",
        theme="monokai",
        line_numbers=True,
    )
    console = Console()
    console.print(syntax)


def pretty_print_markdown(data: str) -> None:
    """Pretty print markdown data with syntax highlighting."""
    syntax = Syntax(data, "markdown", theme="monokai", line_numbers=False)
    console = Console()
    console.print(syntax)
