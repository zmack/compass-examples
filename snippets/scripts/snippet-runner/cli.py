"""Command-line interface for the snippet runner."""

import argparse
import json
import os
from typing import Tuple

from .client import Client
from .utils import get_snippet_list, run_snippet, pretty_print, pretty_print_markdown


def load_environment() -> Tuple[Client, str]:
    """
    Load environment variables and create client instance.

    Returns:
        Tuple[Client, str]: Configured Client instance and snippet path

    Raises:
        EnvironmentError: If required environment variables are missing
    """
    username = os.getenv("ATL_USERNAME")
    password = os.getenv("ATL_PASSWORD")
    url = os.getenv("ATL_URL")
    snippet_path = os.getenv("ATL_SNIPPET_PATH")

    if not snippet_path:
        raise EnvironmentError("ATL_SNIPPET_PATH environment variable is required")

    try:
        return Client(url, username, password), snippet_path
    except ValueError as e:
        raise EnvironmentError(f"Environment configuration error: {str(e)}")


def run_specific_snippet(
    snippet_name: str, arguments_json: str, client: Client, snippet_path: str
) -> None:
    """
    Run a specific snippet with the provided arguments.

    Args:
        snippet_name: Name of snippet to run
        arguments_json: JSON string of variables
        client: GraphQL client instance
        snippet_path: Path to directory containing snippets
    """
    try:
        params = json.loads(arguments_json)
    except json.JSONDecodeError:
        print(f"Invalid JSON arguments: {arguments_json}")
        return

    snippet = next(
        (s for s in get_snippet_list(client, snippet_path) if s.name == snippet_name),
        None,
    )
    if not snippet:
        print(f"Snippet '{snippet_name}' not found")
        return

    try:
        snippet.run(params)
        response = run_snippet(snippet, client, params)
        pretty_print(response.json())
    except Exception as e:
        print(f"Error running snippet: {str(e)}")


def main() -> int:
    """Main entry point for the snippet runner CLI."""
    parser = argparse.ArgumentParser(description="A Compass snippet runner")
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommands")

    # List subcommand
    subparsers.add_parser("list", help="List available snippets")

    # Run subcommand
    parser_run = subparsers.add_parser("run", help="Run a specific snippet")
    parser_run.add_argument("snippet", help="The snippet to run")
    parser_run.add_argument(
        "arguments", nargs=1, help="JSON-formatted arguments for the snippet"
    )

    # Peek subcommand
    parser_peek = subparsers.add_parser(
        "peek", help="Display the validation schema for arguments passed to a snippet"
    )
    parser_peek.add_argument("snippet", help="The snippet to display")

    # Help subcommand
    parser_help = subparsers.add_parser(
        "help", help="Display the README.md file for a snippet"
    )
    parser_help.add_argument("snippet", help="The snippet to show help for")

    args = parser.parse_args()

    try:
        client, snippet_path = load_environment()
    except EnvironmentError as e:
        print(str(e))
        return 1

    if args.subcommand == "list":
        snippets = get_snippet_list(client, snippet_path)
        for s in snippets:
            print(s.name)
    elif args.subcommand == "run":
        run_specific_snippet(args.snippet, args.arguments[0], client, snippet_path)
    elif args.subcommand == "peek":
        snippets = get_snippet_list(client, snippet_path)
        snippet = next((s for s in snippets if s.name == args.snippet), None)
        if snippet:
            snippet.parse()
            pretty_print(snippet.generate_validation_schema())
        else:
            print(f"Snippet '{args.snippet}' not found")
    elif args.subcommand == "help":
        snippets = get_snippet_list(client, snippet_path)
        snippet = next((s for s in snippets if s.name == args.snippet), None)
        if snippet:
            readme_content = snippet.get_readme_content()
            if readme_content:
                pretty_print_markdown(readme_content)
            else:
                print(f"No README.md found for snippet '{args.snippet}'")
        else:
            print(f"Snippet '{args.snippet}' not found")
    else:
        parser.print_help()
        return 1

    return 0
