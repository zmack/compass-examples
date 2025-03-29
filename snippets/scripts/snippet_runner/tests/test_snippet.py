"""Tests for the Snippet class."""

import unittest
from unittest.mock import MagicMock, patch, mock_open
import os
from graphql import (
    DocumentNode,
    OperationDefinitionNode,
    NamedTypeNode,
    NonNullTypeNode,
    ListTypeNode,
)

from snippet_runner.snippet import Snippet
from snippet_runner.client import Client
from snippet_runner.schema_generator import SnippetInputSchemaGenerator


class TestSnippet(unittest.TestCase):
    """Test the Snippet class functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock(spec=Client)
        self.snippet = Snippet(
            name="test_snippet", path="/test/path", client=self.mock_client
        )

    @patch("os.listdir")
    @patch(
        "builtins.open", new_callable=mock_open, read_data="query TestQuery { test }"
    )
    def test_read_content(self, mock_file, mock_listdir):
        """Test reading content from a GraphQL file."""
        # Setup mock return values
        mock_listdir.return_value = ["test.graphql", "README.md"]

        # Call the method
        content = self.snippet._read_content()

        # Verify the result
        self.assertEqual(content, "query TestQuery { test }")
        mock_listdir.assert_called_once_with(self.snippet.path)
        mock_file.assert_called_once_with(
            os.path.join(self.snippet.path, "test.graphql"), "r"
        )

    @patch("os.listdir")
    def test_find_graphql_file(self, mock_listdir):
        """Test finding a GraphQL file in the snippet directory."""
        # Test with a GraphQL file present
        mock_listdir.return_value = ["test.graphql", "README.md"]
        result = self.snippet._find_graphql_file()
        self.assertEqual(result, "test.graphql")

        # Test with no GraphQL file
        mock_listdir.return_value = ["README.md", "config.json"]
        result = self.snippet._find_graphql_file()
        self.assertIsNone(result)

    def test_get_operation_name(self):
        """Test extracting operation name from a GraphQL document."""
        # Create mock document with a named operation
        mock_document = MagicMock(spec=DocumentNode)
        mock_operation = MagicMock(spec=OperationDefinitionNode)
        mock_operation.name.value = "TestQuery"
        mock_document.definitions = [mock_operation]

        result = self.snippet._get_operation_name(mock_document)
        self.assertEqual(result, "TestQuery")

        # Test with unnamed operation
        mock_operation.name = None
        result = self.snippet._get_operation_name(mock_document)
        self.assertIsNone(result)

        # Test with no operation definitions
        mock_document.definitions = []
        result = self.snippet._get_operation_name(mock_document)
        self.assertIsNone(result)

    def test_type_to_schema(self):
        """Test conversion of GraphQL type nodes to schema strings."""
        # Test NamedTypeNode
        named_node = MagicMock(spec=NamedTypeNode)
        named_node.name.value = "String"
        result = self.snippet._type_to_schema(named_node)
        self.assertEqual(result, "String")

        # Test NonNullTypeNode
        inner_node = MagicMock(spec=NamedTypeNode)
        inner_node.name.value = "String"
        non_null_node = MagicMock(spec=NonNullTypeNode)
        non_null_node.type = inner_node
        result = self.snippet._type_to_schema(non_null_node)
        self.assertEqual(result, "String!")

        # Test ListTypeNode
        list_node = MagicMock(spec=ListTypeNode)
        list_node.type = inner_node
        result = self.snippet._type_to_schema(list_node)
        self.assertEqual(result, "[String]")

        # Test nested types (NonNull List of NonNull String)
        non_null_inner = MagicMock(spec=NonNullTypeNode)
        non_null_inner.type = inner_node
        list_of_non_null = MagicMock(spec=ListTypeNode)
        list_of_non_null.type = non_null_inner
        non_null_list = MagicMock(spec=NonNullTypeNode)
        non_null_list.type = list_of_non_null

        result = self.snippet._type_to_schema(non_null_list)
        self.assertEqual(result, "[String!]!")

    @patch("snippet_runner.snippet.parse")
    @patch.object(Snippet, "_read_content")
    @patch.object(Snippet, "_unwrap")
    @patch.object(Snippet, "_get_operation_name")
    def test_parse(self, mock_get_name, mock_unwrap, mock_read, mock_parse):
        """Test parsing a GraphQL snippet."""
        # Setup mocks
        mock_read.return_value = "query TestQuery { test }"
        mock_document = MagicMock(spec=DocumentNode)
        mock_parse.return_value = mock_document
        mock_unwrap.return_value = {"var1": "String", "var2": "Int!"}
        mock_get_name.return_value = "TestQuery"

        # Call the method
        self.snippet.parse()

        # Verify results
        mock_read.assert_called_once()
        mock_parse.assert_called_once_with("query TestQuery { test }")
        mock_unwrap.assert_called_once_with(mock_document)
        mock_get_name.assert_called_once_with(mock_document)
        self.assertEqual(self.snippet.content, "query TestQuery { test }")
        self.assertEqual(self.snippet.params, {"var1": "String", "var2": "Int!"})
        self.assertEqual(self.snippet.operation_name, "TestQuery")

        # Test with no content
        mock_read.return_value = None
        result = self.snippet.parse()
        self.assertIsNone(result)

    @patch.object(Snippet, "parse")
    @patch.object(Snippet, "validate")
    def test_run(self, mock_validate, mock_parse):
        """Test running a snippet with arguments."""
        # Test with arguments
        args = {"var1": "test"}
        self.snippet.run(args)
        mock_parse.assert_called_once()
        mock_validate.assert_called_once_with(args)

        # Reset mocks
        mock_parse.reset_mock()
        mock_validate.reset_mock()

        # Test without arguments
        self.snippet.run()
        mock_parse.assert_called_once()
        mock_validate.assert_not_called()

    @patch.object(Snippet, "generate_validation_schema")
    @patch("snippet_runner.snippet.Draft4Validator")
    def test_validate(self, mock_validator_class, mock_generate_schema):
        """Test validating arguments against the schema."""
        # Setup mocks
        mock_schema = {"type": "object", "properties": {"var1": {"type": "string"}}}
        mock_generate_schema.return_value = mock_schema
        mock_validator = MagicMock()
        mock_validator_class.return_value = mock_validator

        # Call the method
        args = {"var1": "test"}
        self.snippet.validate(args)

        # Verify results
        mock_generate_schema.assert_called_once()
        mock_validator_class.assert_called_once_with(mock_schema)
        mock_validator.validate.assert_called_once_with(args)

    def test_generate_validation_schema(self):
        """Test generating a validation schema."""
        # Setup mock
        mock_schema = {"type": "object", "properties": {}}
        mock_schema_generator = MagicMock(spec=SnippetInputSchemaGenerator)
        mock_schema_generator.generate_schema.return_value = mock_schema

        # Set the attribute directly for testing
        self.snippet.schema_generator = mock_schema_generator

        # Call the method
        result = self.snippet.generate_validation_schema()

        # Verify results
        self.assertEqual(result, mock_schema)
        mock_schema_generator.generate_schema.assert_called_once()


if __name__ == "__main__":
    unittest.main()
