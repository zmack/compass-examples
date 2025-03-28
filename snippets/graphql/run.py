import argparse
import json
import os
import sys
from rich.console import Console
from rich.syntax import Syntax
from dataclasses import dataclass
from pprint import pp, pformat
from typing import Any, Dict, List, Optional, Tuple

import requests
from graphql import (
    ListTypeNode,
    NonNullTypeNode,
    OperationDefinitionNode,
    TypeNode,
    VariableDefinitionNode,
    parse,
)
from graphql.language.ast import DocumentNode, NamedTypeNode
from jsonschema import Draft4Validator
from requests.models import HTTPBasicAuth


class Client:
    def __init__(self, url: str, username: str, password: str) -> None:
        if not url:
            raise ValueError("URL is required")
        if not username:
            raise ValueError("Username is required")
        if not password:
            raise ValueError("Password is required")

        self.url = url
        self.username = username
        self.password = password

    def get_type_shape(self, type_name: str) -> dict:
        """
        Fetch GraphQL type information using introspection.

        Args:
            type_name: Name of the GraphQL type to introspect

        Returns:
            dict: The introspection response for the type
        """
        query = """
        query GetTypeInput($type: String!) {
            __type(name: $type) {
                __typename
                inputFields {
                    name
                    type {
                        kind
                        name
                        ofType {
                            name
                        }
                    }
                }
                fields {
                    name
                    type {
                        kind
                        name
                        ofType {
                            name
                        }
                    }
                }
                enumValues {
                    name
                    description
                }
            }
        }"""

        payload = {
            "query": query,
            "variables": {"type": type_name},
            "operationName": "GetTypeInput",
        }

        response = requests.post(
            url=self.url,
            json=payload,
            auth=HTTPBasicAuth(self.username, self.password),
        )
        response.raise_for_status()
        return response.json()


class SnippetInputSchemaGenerator:
    def __init__(self, snippet: "Snippet", document: DocumentNode, client: Client):
        self.snippet = snippet
        self.document = document
        self.type_definitions = {}
        self.undefined_types = set()
        self.client = client

    def generate_schema(self) -> dict:
        self.schema = self._operation_input_json_schema()
        return self.schema

    def get_type_shape(self, type: str):
        return self.client.get_type_shape(type)

    def build_definitions(self, input_type, introspection_data: dict) -> dict:
        types, definitions = self.introspection_to_jsonschema_definition(
            introspection_data
        )
        definitions_by_name = {input_type: definitions}
        builtins = ["String"]
        for type in types:
            if type is None:
                continue
            shape = self.get_type_shape(type)
            print(f"Getting definition for {type}")
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
        Convert GraphQL introspection data to a JSON Schema definition
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


@dataclass
class Snippet:
    name: str
    path: str
    client: Client
    arguments: Optional[List[str]] = None

    def parse(self) -> Optional[OperationDefinitionNode]:
        self.content = self._read_content()
        if self.content is None:
            return

        parsed = parse(self.content)
        a = self._unwrap(parsed)
        self.schema_generator = SnippetInputSchemaGenerator(self, parsed, self.client)
        self.operation_name = self._get_operation_name(parsed)
        self.params = a

    def generate_validation_schema(self) -> dict:
        return self.schema_generator.generate_schema()

    def validate(self, arguments: object) -> Optional[List[str]]:
        schema = self.generate_validation_schema()
        validator = Draft4Validator(schema)
        print(validator.validate(arguments))

    def run(self, arguments: Optional[object] = None):
        self.parse()

        if arguments is not None:
            self.validate(arguments)

    def _read_content(self) -> Optional[str]:
        path = self._find_graphql_file()
        if path is None:
            return
        full_path = os.path.join(self.path, path)
        with open(full_path, "r") as file:
            content = file.read()

        return content

    def _find_graphql_file(self) -> Optional[str]:
        graphql_file = next(
            (file for file in os.listdir(self.path) if file.endswith(".graphql")), None
        )
        return graphql_file

    def _get_operation_name(self, document: DocumentNode) -> Optional[str]:
        for definition in document.definitions:
            if not isinstance(definition, OperationDefinitionNode):
                continue

            if definition.name is not None:
                return definition.name.value

    def _unwrap(self, document: DocumentNode) -> Dict[str, str]:
        a: Dict[str, str] = dict()

        for definition in document.definitions:
            if not isinstance(definition, OperationDefinitionNode):
                continue

            for variable in definition.variable_definitions:
                if (tuple := self._parse_variable_definition(variable)) is not None:
                    name, kind = tuple
                    a[name] = kind
        return a

    def _parse_variable_definition(
        self, node: VariableDefinitionNode
    ) -> Optional[Tuple[str, str]]:
        if (type_name := self._type_to_schema(node.type)) is not None:
            return node.variable.name.value, type_name

    def _type_to_schema(self, node: TypeNode) -> Optional[str]:
        match node:
            case NamedTypeNode():
                return node.name.value
            case ListTypeNode():
                return f"[{self._type_to_schema(node.type)}]"
            case NonNullTypeNode():
                return f"{self._type_to_schema(node.type)}!"


def pnd(obj: object) -> None:
    print([method for method in obj.__dir__() if not method.startswith("__")])


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


def load_environment() -> Client:
    """
    Load environment variables and create client instance.

    Returns:
        Configured Client instance

    Raises:
        EnvironmentError: If required environment variables are missing
    """
    username = os.getenv("ATL_USERNAME")
    password = os.getenv("ATL_PASSWORD")
    url = os.getenv("ATL_URL")

    try:
        return Client(url, username, password)
    except ValueError as e:
        raise EnvironmentError(f"Environment configuration error: {str(e)}")


def run_specific_snippet(
    snippet_name: str, arguments_json: str, client: Client
) -> None:
    """
    Run a specific snippet with the provided arguments.

    Args:
        snippet_name: Name of snippet to run
        arguments_json: JSON string of variables
        client: GraphQL client instance
    """
    try:
        params = json.loads(arguments_json)
    except json.JSONDecodeError:
        print(f"Invalid JSON arguments: {arguments_json}")
        return

    snippet = next(
        (s for s in get_snippet_list(client) if s.name == snippet_name), None
    )
    if not snippet:
        print(f"Snippet '{snippet_name}' not found")
        return

    try:
        snippet.run(params)
        response = run_snippet(snippet, client, params)
        pretty_print(response.json())
    except requests.RequestException as e:
        print(f"Error executing snippet: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")


def pretty_print(data: dict):
    syntax = Syntax(
        json.dumps(data, indent=4),
        "json",
        theme="monokai",
        line_numbers=True,
    )
    console = Console()
    console.print(syntax)


def main() -> None:
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

    parser_peek = subparsers.add_parser(
        "peek", help="Display the validation schema for arguments passed to a snippet"
    )
    parser_peek.add_argument("snippet", help="The snippet to display")

    args = parser.parse_args()

    try:
        client = load_environment()
    except EnvironmentError as e:
        print(str(e))
        return 1

    if args.subcommand == "list":
        snippets = get_snippet_list(client)
        for s in snippets:
            print(s.name)
    elif args.subcommand == "run":
        run_specific_snippet(args.snippet, args.arguments[0], client)
    elif args.subcommand == "peek":
        snippets = get_snippet_list(client)
        snippet = next((s for s in snippets if s.name == args.snippet), None)
        if snippet:
            snippet.parse()
            pretty_print(snippet.generate_validation_schema())
        else:
            print(f"Snippet '{args.snippet}' not found")
    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
