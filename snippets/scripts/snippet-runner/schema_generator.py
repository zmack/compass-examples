"""Schema generation utilities for GraphQL types."""

from typing import Any, Dict, List, Tuple, Set
from graphql import (
    DocumentNode,
    OperationDefinitionNode,
    NamedTypeNode,
    NonNullTypeNode,
    ListTypeNode,
    TypeNode,
)

from .client import Client


class SnippetInputSchemaGenerator:
    def __init__(self, snippet: "Snippet", document: DocumentNode, client: Client):
        self.snippet = snippet
        self.document = document
        self.type_definitions: Dict[str, Any] = {}
        self.undefined_types: Set[str] = set()
        self.client = client

    def generate_schema(self) -> dict:
        self.schema = self._operation_input_json_schema()
        return self.schema

    def get_type_shape(self, type: str) -> Dict:
        return self.client.get_type_shape(type)

    def build_definitions(self, input_type: str, introspection_data: dict) -> dict:
        types, definitions = self.introspection_to_jsonschema_definition(
            introspection_data
        )
        definitions_by_name = {input_type: definitions}
        builtins = ["String"]
        for type in types:
            if type is None:
                continue
            shape = self.get_type_shape(type)
            more_types, definition = self.introspection_to_jsonschema_definition(shape)
            definitions_by_name[type] = definition
            types.extend(
                [t for t in more_types if t not in types and t not in builtins]
            )

        return definitions_by_name

    def _operation_input_json_schema(self) -> Dict[Any, Any]:
        properties: Dict[str, str] = dict()
        required: List[str] = []

        for definition in self.document.definitions:
            if not isinstance(definition, OperationDefinitionNode):
                continue

            for variable in definition.variable_definitions:
                variable_name = variable.variable.name.value
                type_schema = self._type_to_json_schema_object(variable.type)
                if type_schema.get("required") == True:
                    required.append(variable_name)
                    del type_schema["required"]
                properties[variable_name] = type_schema

        return {
            "$schema": "http://json-schema.org/draft-04/schema#",
            "type": "object",
            "properties": properties,
            "required": required,
            "definitions": self._get_type_definitions(),
        }

    def _get_type_definitions(self) -> dict:
        for undefined_type in self.undefined_types:
            shape = self.get_type_shape(undefined_type)
            self.type_definitions.update(self.build_definitions(undefined_type, shape))

        return self.type_definitions

    def _type_to_json_schema_object(self, node: TypeNode) -> dict:
        match node:
            case NamedTypeNode():
                return self._object_to_json_schema(node)
            case NonNullTypeNode():
                schema = self._type_to_json_schema_object(node.type)
                return {**schema, "required": True}
            case ListTypeNode():
                return {
                    "type": "array",
                    "items": self._type_to_json_schema_object(node.type),
                }

    def _object_to_json_schema(self, node: NamedTypeNode) -> dict:
        match node.name.value:
            case "ID":
                return {"type": "string"}
            case "String":
                return {"type": "string"}
            case "Boolean":
                return {"type": "boolean"}
            case "Integer":
                return {"type": "integer"}
            case _:
                self.undefined_types.add(node.name.value)
                return {"type": "object", "$ref": f"#/definitions/{node.name.value}"}

    def introspection_to_jsonschema_definition(
        self, introspection_data: dict
    ) -> Tuple[List[str], dict]:
        """
        Convert GraphQL introspection data to a JSON Schema definition.
        """
        # Check if this is an enum type first
        enums = introspection_data.get("data", {}).get("__type", {}).get("enumValues")
        if enums is not None:
            enum_values = [ev["name"] for ev in enums]
            return [], {"type": "string", "enum": enum_values}

        # Process as an object type
        properties = {}
        required = []
        unknown_types = []

        # Process each field in the input type
        input_fields = (
            introspection_data.get("data", {}).get("__type", {}).get("inputFields", [])
        )
        for field in input_fields:
            field_name = field["name"]
            field_type = field["type"]

            new_types, field_schema = self._convert_field_type(field_type)

            # Handle required fields
            if field_schema.get("required"):
                required.append(field_name)
                del field_schema["required"]

            # Add field to properties
            properties[field_name] = field_schema
            unknown_types.extend(new_types)

        # Build the final schema
        definition = {"type": "object", "properties": properties}
        if required:
            definition["required"] = required

        # Remove duplicates from unknown types
        unknown_types = list(set(unknown_types))

        return unknown_types, definition

    def _convert_field_type(self, field_type) -> Tuple[List[str], dict]:
        """
        Convert a GraphQL field type to JSON Schema.

        Args:
            field_type: GraphQL type information from introspection

        Returns:
            Tuple containing:
            - List of unknown types that need to be resolved
            - JSON Schema definition for this field
        """
        # Basic type mappings
        type_mapping = {
            "String": {"type": "string"},
            "Int": {"type": "integer"},
            "Float": {"type": "number"},
            "Boolean": {"type": "boolean"},
            "ID": {"type": "string"},
        }

        unknown_types = []

        # Handle basic scalar types
        if field_type["name"] in type_mapping:
            return [], type_mapping[field_type["name"]]

        kind = field_type.get("kind", None)

        # Handle different GraphQL types
        if kind == "SCALAR":
            # Default to string for unknown scalar types
            return [], type_mapping.get(field_type["name"], {"type": "string"})

        elif kind == "NON_NULL":
            # Process non-null types and mark as required
            child_types, schema = self._convert_field_type(field_type["ofType"])
            schema["required"] = True
            unknown_types.extend(child_types)
            return unknown_types, schema

        elif kind == "LIST":
            # Process list types
            of_type = field_type["ofType"]
            if of_type["name"] in type_mapping:
                # Known type in the list
                return [], {
                    "type": "array",
                    "items": type_mapping[of_type["name"]],
                }
            else:
                # Unknown type in the list, will need to be resolved
                unknown_types.append(of_type["name"])
                return unknown_types, {
                    "type": "array",
                    "items": {"$ref": f"#/definitions/{of_type['name']}"},
                }

        elif kind == "INPUT_OBJECT" or kind is None:
            # Reference to another object type
            unknown_types.append(field_type["name"])
            return unknown_types, {"$ref": f"#/definitions/{field_type['name']}"}

        # Default case for any other kind
        unknown_types.append(field_type["name"])
        return unknown_types, {"$ref": f"#/definitions/{field_type['name']}"}
