"""Schema generation utilities for GraphQL types."""
from typing import Any, Dict, List, Tuple, Set
from graphql import DocumentNode, OperationDefinitionNode, NamedTypeNode, NonNullTypeNode, ListTypeNode, TypeNode, VariableDefinitionNode

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
        type_mapping = {
            "String": {"type": "string"},
            "Int": {"type": "integer"},
            "Float": {"type": "number"},
            "Boolean": {"type": "boolean"},
            "ID": {"type": "string"},
        }

        def convert_field_type(field_type) -> Tuple[List[str], dict]:
            unknown_types = []
            if field_type["name"] in type_mapping.keys():
                return [], type_mapping[field_type["name"]]

            kind = field_type.get("kind", None)

            if kind == "SCALAR":
                return unknown_types, type_mapping.get(
                    field_type["name"], {"type": "string"}
                )

            elif kind == "NON_NULL":
                # For NON_NULL, we process the ofType and pass along unknown types
                child_unknown_types, type_definition = convert_field_type(
                    field_type["ofType"]
                )
                unknown_types.extend(child_unknown_types)
                return unknown_types, type_definition

            elif kind == "LIST":
                ofType = field_type["ofType"]
                if ofType["name"] in type_mapping:
                    return unknown_types, {
                        "type": "array",
                        "items": type_mapping[ofType["name"]],
                    }
                unknown_types.append(ofType["name"])
                return unknown_types, {
                    "type": "array",
                    "items": {"$ref": f"#/definitions/{ofType['name']}"},
                }

            elif kind == "INPUT_OBJECT":
                unknown_types.append(field_type["name"])
                return unknown_types, {"$ref": f"#/definitions/{field_type['name']}"}
            elif kind is None:
                unknown_types.append(field_type["name"])
                return unknown_types, {"$ref": f"#/definitions/{field_type['name']}"}

            unknown_types.append(field_type["name"])
            return unknown_types, {"$ref": f"#/definitions/{field_type['name']}"}

        enums = introspection_data.get("data", {}).get("__type", {}).get("enumValues")

        if enums is not None:
            enum_values = [ev["name"] for ev in enums]
            return [], {"type": "string", "enum": enum_values}

        properties = {}
        required = []
        unknown_types = []

        for field in introspection_data["data"]["__type"]["inputFields"]:
            field_name = field["name"]
            field_type = field["type"]

            types, type_definition = convert_field_type(field_type)
            unknown_types.extend(types)
            properties[field_name] = type_definition

        definition = {"type": "object", "properties": properties}

        if required:
            definition["required"] = required

        # Remove duplicates from unknown_types
        unknown_types = list(set(unknown_types))

        return unknown_types, definition
