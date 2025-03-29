"""GraphQL snippet_runner package."""

from .snippet_runner.client import Client
from .snippet_runner.snippet import Snippet
from .snippet_runner.schema_generator import SnippetInputSchemaGenerator
from .snippet_runner.utils import get_snippet_list, run_snippet, pretty_print

__version__ = "0.1.0"
__author__ = "Compass Team"

__all__ = [
    "Client",
    "Snippet",
    "SnippetInputSchemaGenerator",
    "get_snippet_list",
    "run_snippet",
    "pretty_print",
]
