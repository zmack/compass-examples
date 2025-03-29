"""Tests for the schema_generator module.

This test file uses a simpler approach by recreating the key functions
we want to test rather than importing the actual module.
"""

import unittest
from unittest.mock import MagicMock, patch
from snippet_runner.schema_generator import SnippetInputSchemaGenerator
import graphql


class TestSchemaGenerator(unittest.TestCase):
    """Test the schema generator functionality by recreating the key methods."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock client
        self.mock_client = MagicMock()

        # Mock document with variable definitions
        self.mock_document = MagicMock(spec=graphql.DocumentNode)
        self.mock_operation = MagicMock(spec=graphql.OperationDefinitionNode)

        # Mock snippet
        self.mock_snippet = MagicMock()

        # Create schema generator instance
        self.schema_generator = SnippetInputSchemaGenerator(
            snippet=self.mock_snippet,
            document=self.mock_document,
            client=self.mock_client,
        )

    def test_type_mapping_scalar_types(self):
        """Test mapping of scalar GraphQL types to JSON Schema types."""
        # Test ID type
        id_node = MagicMock(spec=graphql.NamedTypeNode)
        id_node.name.value = "ID"
        result = self.schema_generator._object_to_json_schema(id_node)
        self.assertEqual(result, {"type": "string"})

        # Test String type
        string_node = MagicMock(spec=graphql.NamedTypeNode)
        string_node.name.value = "String"
        result = self.schema_generator._object_to_json_schema(string_node)
        self.assertEqual(result, {"type": "string"})

        # Test Boolean type
        bool_node = MagicMock(spec=graphql.NamedTypeNode)
        bool_node.name.value = "Boolean"
        result = self.schema_generator._object_to_json_schema(bool_node)
        self.assertEqual(result, {"type": "boolean"})

        # Test Integer type
        int_node = MagicMock(spec=graphql.NamedTypeNode)
        int_node.name.value = "Integer"
        result = self.schema_generator._object_to_json_schema(int_node)
        self.assertEqual(result, {"type": "integer"})

    def test_type_mapping_custom_types(self):
        """Test mapping of custom GraphQL types to JSON Schema references."""
        # Test custom type
        custom_node = MagicMock(spec=graphql.NamedTypeNode)
        custom_node.name.value = "CustomType"
        result = self.schema_generator._object_to_json_schema(custom_node)

        # Should add to undefined types and return a reference
        self.assertIn("CustomType", self.schema_generator.undefined_types)
        self.assertEqual(result, {"type": "object", "$ref": "#/definitions/CustomType"})

    def test_type_to_json_schema_object_named_type(self):
        """Test conversion of NamedTypeNode to JSON Schema."""
        node = MagicMock(spec=graphql.NamedTypeNode)
        node.name.value = "String"

        result = self.schema_generator._type_to_json_schema_object(node)
        self.assertEqual(result, {"type": "string"})

    def test_type_to_json_schema_object_non_null_type(self):
        """Test conversion of NonNullTypeNode to JSON Schema."""
        inner_node = MagicMock(spec=graphql.NamedTypeNode)
        inner_node.name.value = "String"

        node = MagicMock(spec=graphql.NonNullTypeNode)
        node.type = inner_node

        result = self.schema_generator._type_to_json_schema_object(node)
        self.assertEqual(result, {"type": "string", "required": True})

    def test_type_to_json_schema_object_list_type(self):
        """Test conversion of ListTypeNode to JSON Schema."""
        inner_node = MagicMock(spec=graphql.NamedTypeNode)
        inner_node.name.value = "String"

        node = MagicMock(spec=graphql.ListTypeNode)
        node.type = inner_node

        result = self.schema_generator._type_to_json_schema_object(node)
        self.assertEqual(result, {"type": "array", "items": {"type": "string"}})

    def test_convert_field_type_scalar(self):
        """Test conversion of scalar field types."""
        # Test String scalar
        field_type = {"name": "String", "kind": "SCALAR"}
        unknown_types, schema = self.schema_generator._convert_field_type(field_type)

        self.assertEqual(unknown_types, [])
        self.assertEqual(schema, {"type": "string"})

        # Test Int scalar
        field_type = {"name": "Int", "kind": "SCALAR"}
        unknown_types, schema = self.schema_generator._convert_field_type(field_type)

        self.assertEqual(unknown_types, [])
        self.assertEqual(schema, {"type": "integer"})

    def test_convert_field_type_non_null(self):
        """Test conversion of non-null field types."""
        field_type = {
            "kind": "NON_NULL",
            "name": None,
            "ofType": {"name": "String", "kind": "SCALAR"},
        }

        unknown_types, schema = self.schema_generator._convert_field_type(field_type)

        self.assertEqual(unknown_types, [])
        self.assertEqual(schema, {"type": "string", "required": True})

    def test_convert_field_type_list(self):
        """Test conversion of list field types."""
        field_type = {
            "kind": "LIST",
            "name": None,
            "ofType": {"name": "String", "kind": "SCALAR"},
        }

        unknown_types, schema = self.schema_generator._convert_field_type(field_type)

        self.assertEqual(unknown_types, [])
        self.assertEqual(schema, {"type": "array", "items": {"type": "string"}})

    def test_convert_field_type_list_with_custom_type(self):
        """Test conversion of list field types with custom types."""
        field_type = {
            "kind": "LIST",
            "name": None,
            "ofType": {"name": "CustomType", "kind": "INPUT_OBJECT"},
        }

        unknown_types, schema = self.schema_generator._convert_field_type(field_type)

        self.assertEqual(unknown_types, ["CustomType"])
        self.assertEqual(
            schema, {"type": "array", "items": {"$ref": "#/definitions/CustomType"}}
        )

    def test_convert_field_type_input_object(self):
        """Test conversion of input object field types."""
        field_type = {"kind": "INPUT_OBJECT", "name": "CustomInput"}

        unknown_types, schema = self.schema_generator._convert_field_type(field_type)

        self.assertEqual(unknown_types, ["CustomInput"])
        self.assertEqual(schema, {"$ref": "#/definitions/CustomInput"})

    def test_introspection_to_jsonschema_definition_enum(self):
        """Test conversion of enum types from introspection data."""
        introspection_data = {
            "data": {
                "__type": {
                    "enumValues": [
                        {"name": "OPTION1"},
                        {"name": "OPTION2"},
                        {"name": "OPTION3"},
                    ]
                }
            }
        }

        unknown_types, definition = (
            self.schema_generator.introspection_to_jsonschema_definition(
                introspection_data
            )
        )

        self.assertEqual(unknown_types, [])
        self.assertEqual(
            definition, {"type": "string", "enum": ["OPTION1", "OPTION2", "OPTION3"]}
        )

    def test_introspection_to_jsonschema_definition_input_object(self):
        """Test conversion of input object types from introspection data."""
        introspection_data = {
            "data": {
                "__type": {
                    "inputFields": [
                        {
                            "name": "field1",
                            "type": {"name": "String", "kind": "SCALAR"},
                        },
                        {
                            "name": "field2",
                            "type": {
                                "kind": "NON_NULL",
                                "name": None,
                                "ofType": {"name": "Int", "kind": "SCALAR"},
                            },
                        },
                    ]
                }
            }
        }

        unknown_types, definition = (
            self.schema_generator.introspection_to_jsonschema_definition(
                introspection_data
            )
        )

        self.assertEqual(unknown_types, [])
        self.assertEqual(
            definition,
            {
                "type": "object",
                "properties": {
                    "field1": {"type": "string"},
                    "field2": {"type": "integer"},
                },
                "required": ["field2"],
            },
        )

    @patch.object(SnippetInputSchemaGenerator, "_get_type_definitions")
    @patch.object(SnippetInputSchemaGenerator, "_type_to_json_schema_object")
    def test_operation_input_json_schema(self, mock_type_to_json, mock_get_type_defs):
        """Test generation of JSON Schema for operation inputs."""
        # Setup mocks
        mock_get_type_defs.return_value = {
            "CustomType": {"type": "object", "properties": {}}
        }

        # Mock variable definitions
        var1_type = MagicMock()
        var1 = MagicMock(spec=graphql.VariableDefinitionNode)
        var1.variable = MagicMock(spec=graphql.VariableNode)
        var1.variable.name = MagicMock(spec=graphql.NameNode)
        var1.variable.name.value = "var1"
        var1.type = var1_type

        var2_type = MagicMock()
        var2 = MagicMock(spec=graphql.VariableDefinitionNode)
        var2.variable = MagicMock(spec=graphql.VariableNode)
        var2.variable.name = MagicMock(spec=graphql.NameNode)
        var2.variable.name.value = "var2"
        var2.type = var2_type

        # Setup return values for type conversion
        mock_type_to_json.side_effect = [
            {"type": "string"},
            {"type": "integer", "required": True},
        ]

        # Setup document
        operation = MagicMock(spec=graphql.OperationDefinitionNode)
        operation.variable_definitions = [var1, var2]
        self.mock_document.definitions = [operation]

        # Call the method
        result = self.schema_generator._operation_input_json_schema()

        # Verify the result
        self.assertEqual(result["type"], "object")
        self.assertEqual(result["properties"]["var1"], {"type": "string"})
        self.assertEqual(result["properties"]["var2"], {"type": "integer"})
        self.assertEqual(result["required"], ["var2"])
        self.assertEqual(result["$schema"], "http://json-schema.org/draft-04/schema#")


if __name__ == "__main__":
    unittest.main()
