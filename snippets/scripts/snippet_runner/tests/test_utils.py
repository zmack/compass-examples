"""Tests for the utils module."""

import unittest
from unittest.mock import MagicMock, patch
import os
import requests

from snippet_runner.client import Client
from snippet_runner.snippet import Snippet
from snippet_runner import utils


class TestUtils(unittest.TestCase):
    """Test the utility functions in the utils module."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock(spec=Client)
        self.mock_client.url = "https://example.com/graphql"
        self.mock_client.username = "test_user"
        self.mock_client.password = "test_password"

    @patch("os.listdir")
    @patch("os.path.isdir")
    def test_list_files_in_directory(self, mock_isdir, mock_listdir):
        """Test listing directories in a specified path."""
        # Setup mock return values
        mock_listdir.return_value = ["dir1", "file1.txt", "dir2", "file2.py"]

        # Configure isdir to return True for directories and False for files
        def is_dir_side_effect(path):
            return os.path.basename(path) in ["dir1", "dir2"]

        mock_isdir.side_effect = is_dir_side_effect

        # Call the function
        result = utils.list_files_in_directory("/test/path")

        # Verify the result
        self.assertEqual(result, ["dir1", "dir2"])
        mock_listdir.assert_called_once_with("/test/path")

    @patch("snippet_runner.utils.list_files_in_directory")
    def test_get_snippet_list(self, mock_list_dirs):
        """Test getting a list of Snippet instances."""
        # Setup mock return values
        mock_list_dirs.return_value = ["snippet1", "snippet2"]

        # Call the function
        result = utils.get_snippet_list(self.mock_client, "/test/path")

        # Verify the result
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], Snippet)
        self.assertEqual(result[0].name, "snippet1")
        self.assertEqual(result[0].path, "/test/path/snippet1")
        self.assertEqual(result[0].client, self.mock_client)

        self.assertIsInstance(result[1], Snippet)
        self.assertEqual(result[1].name, "snippet2")
        self.assertEqual(result[1].path, "/test/path/snippet2")
        self.assertEqual(result[1].client, self.mock_client)

        mock_list_dirs.assert_called_once_with("/test/path")

    @patch("requests.post")
    def test_run_snippet_success(self, mock_post):
        """Test executing a GraphQL snippet successfully."""
        # Setup mock snippet
        mock_snippet = MagicMock(spec=Snippet)
        mock_snippet.name = "test_snippet"
        mock_snippet.content = "query { test }"
        mock_snippet.operation_name = "TestQuery"

        # Setup mock response
        mock_response = MagicMock(spec=requests.Response)
        mock_post.return_value = mock_response

        # Call the function
        result = utils.run_snippet(mock_snippet, self.mock_client, {"var": "value"})

        # Verify the result
        self.assertEqual(result, mock_response)
        mock_post.assert_called_once_with(
            url=self.mock_client.url,
            json={
                "query": mock_snippet.content,
                "variables": {"var": "value"},
                "operationName": mock_snippet.operation_name,
            },
            headers={"X-ExperimentalApi": "compass-prototype"},
            auth=requests.auth.HTTPBasicAuth(
                self.mock_client.username, self.mock_client.password
            ),
        )
        mock_response.raise_for_status.assert_called_once()

    def test_run_snippet_no_content(self):
        """Test executing a GraphQL snippet with no content."""
        # Setup mock snippet with no content
        mock_snippet = MagicMock(spec=Snippet)
        mock_snippet.name = "test_snippet"
        mock_snippet.content = None

        # Call the function and verify it raises ValueError
        with self.assertRaises(ValueError) as context:
            utils.run_snippet(mock_snippet, self.mock_client, {})

        self.assertIn(
            "No content found for snippet test_snippet", str(context.exception)
        )

    @patch("rich.console.Console.print")
    def test_pretty_print(self, mock_print):
        """Test pretty printing JSON data."""
        # Call the function
        test_data = {"key": "value", "nested": {"inner": "data"}}
        utils.pretty_print(test_data)

        # Verify that Console.print was called (we can't easily verify the exact output)
        mock_print.assert_called_once()

    @patch("rich.console.Console.print")
    def test_pretty_print_markdown(self, mock_print):
        """Test pretty printing markdown data."""
        # Call the function
        test_markdown = "# Heading\n\nSome text"
        utils.pretty_print_markdown(test_markdown)

        # Verify that Console.print was called
        mock_print.assert_called_once()


if __name__ == "__main__":
    unittest.main()
