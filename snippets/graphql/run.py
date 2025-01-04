import argparse
import json
import os
from dataclasses import dataclass
from pprint import pp
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
from jsonschema import validate, Draft4Validator
from requests.models import HTTPBasicAuth


def get_type_shape(
    type: str, username: str, password: str, url: str
) -> requests.Response:
    data = """query GetTypeInput($type: String!) {
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
        "query": data,
        "variables": {"type": type},
        "operationName": "GetTypeInput",
    }

    response = requests.post(
        url=url,
        json=payload,
        auth=HTTPBasicAuth(username, password),
    )

    return response


@dataclass
class Snippet:
    name: str
    path: str
    arguments: Optional[List[str]] = None

    def parse(self) -> Optional[OperationDefinitionNode]:
        self.content = self._read_content()
        if self.content is None:
            return

        parsed = parse(self.content)
        a = self._unwrap(parsed)
        self.schema = self._operation_input_json_schema(parsed)
        self.operation_name = self._get_operation_name(parsed)
        self.params = a

    def validate(self, arguments: object) -> Optional[List[str]]:
        print("====={arguments}=====")
        print(arguments)
        print("====={Schema}=====")
        pp(self.schema)
        validator = Draft4Validator(self.schema)
        print(validator.validate(arguments))

    def run(self, arguments: Optional[object] = None):
        self.parse()

        print(f"Hello {arguments}")
        if arguments is not None:
            print("Hiya")
            input_type = self.schema["properties"]["query"]["type"]
            self.schema["properties"]["query"] = {
                "$ref": f"#/definitions/{input_type}"
            }
            self.validate_schema(input_type)
            self.validate(arguments)

    def validate_schema(self, input_type):
        shape = get_type_shape(input_type, username, password, url).json()
        print(f"Input type: {input_type}")
        definitions = build_definitions(input_type, shape)
        self.schema["definitions"] = definitions

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

    def _operation_input_json_schema(self, document: DocumentNode) -> Dict[Any, Any]:
        properties: Dict[str, str] = dict()
        required: List[str] = []

        for definition in document.definitions:
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
        }

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

    def _type_to_json_schema_object(self, node: TypeNode) -> dict[Any, Any]:
        match node:
            case NamedTypeNode():
                return {"type": self._object_to_json_schema(node)}
            case NonNullTypeNode():
                schema = self._type_to_json_schema_object(node.type)
                return {**schema, "required": True}
            case ListTypeNode():
                return {
                    "type": "array",
                    "items": self._type_to_json_schema_object(node.type),
                }

    def _object_to_json_schema(self, node: NamedTypeNode) -> str:
        match node.name.value:
            case "ID":
                return "string"
            case "String":
                return "string"
            case "Boolean":
                return "boolean"
            case "Integer":
                return "integer"
            case _:
                return node.name.value


def pnd(obj: object) -> None:
    print([method for method in obj.__dir__() if not method.startswith("__")])


def list_files_in_directory(directory):
    # Get a list of all files and directories
    all_items = os.listdir(directory)
    # Filter out directories, keeping only files
    files = [f for f in all_items if os.path.isdir(os.path.join(directory, f))]
    return files


def get_snippet_list(path: str = os.path.dirname(__file__)) -> List[Snippet]:
    current_dir = path
    snippets = [
        Snippet(name=snippet_name, path=os.path.join(current_dir, snippet_name))
        for snippet_name in list_files_in_directory(current_dir)
    ]
    return snippets


def run_snippet(
    snippet: Snippet, url: str, username: str, password: str, args: dict
) -> requests.Response:
    data = snippet.content
    payload = {
        "query": data,
        "variables": args,
        "operationName": snippet.operation_name,
    }
    pp(payload)

    response = requests.post(
        url=url,
        json=payload,
        auth=HTTPBasicAuth(username, password),
    )

    return response


class Client:
    def __init__(self, url, username, password) -> None:
        self.url = url
        self.username = username
        self.password = password


snippets = get_snippet_list()

for snippet in snippets:
    snippet.run()

username = os.getenv("ATL_USERNAME")
password = os.getenv("ATL_PASSWORD")
url = os.getenv("ATL_URL")


session = requests.Session()
session.headers.update({})

if username is None:
    print("ATL_USERNAME not set")
    exit(1)

if password is None:
    print("ATL_PASSWORD not set")
    exit(1)

if url is None:
    print("ATL_URL not set")
    exit(1)


def list_snippets():
    for s in snippets:
        print(s.name)


def run_specific_snippet(snippet_name, arguments_json):
    params = json.loads(arguments_json)
    snippet = next((s for s in snippets if s.name == snippet_name), None)
    if snippet:
        snippet.run(params)
        response = run_snippet(snippet, url, username, password, params)
        print(response.json())
    else:
        print(f"Snippet '{snippet_name}' not found")

def build_definitions(input_type, introspection_data: dict) -> dict:
    types, definitions = introspection_to_jsonschema_definition(introspection_data)
    definitions_by_name = {
        input_type: definitions
    }
    builtins = ["String"]
    for type in types:
        shape = get_type_shape(type, username, password, url).json()
        more_types, definition = introspection_to_jsonschema_definition(shape)
        definitions_by_name[type] = definition
        types.extend([t for t in more_types if t not in types and t not in builtins])

    return definitions_by_name


def introspection_to_jsonschema_definition(introspection_data: dict) -> Tuple[List[str], dict]:
    """
    Convert GraphQL introspection data to a JSON Schema definition
    """
    type_mapping = {
        'String': {'type': 'string'},
        'Int': {'type': 'integer'},
        'Float': {'type': 'number'},
        'Boolean': {'type': 'boolean'},
        'ID': {'type': 'string'}
    }

    def convert_field_type(field_type) -> Tuple[List[str], dict]:
        unknown_types = []
        if field_type['name'] in type_mapping.keys():
                   return [], type_mapping[field_type['name']]

        kind = field_type['kind']

        if kind == 'SCALAR':
            return unknown_types, type_mapping.get(field_type['name'], {'type': 'string'})

        elif kind == 'NON_NULL':
            # For NON_NULL, we process the ofType and pass along unknown types
            child_unknown_types, type_definition = convert_field_type(field_type['ofType'])
            unknown_types.extend(child_unknown_types)
            return unknown_types, type_definition

        elif kind == 'LIST':
            ofType = field_type['ofType']
            if ofType['name'] in type_mapping:
                return unknown_types, {
                    'type': 'array',
                    'items': type_mapping[ofType['name']]
                }
            unknown_types.append(ofType['name'])
            return unknown_types, {
                'type': 'array',
                'items': {'$ref': f"#/definitions/{ofType['name']}"}
            }

        elif kind == 'INPUT_OBJECT':
            unknown_types.append(field_type['name'])
            return unknown_types, {'$ref': f"#/definitions/{field_type['name']}"}

        unknown_types.append(field_type['name'])
        return unknown_types, {'$ref': f"#/definitions/{field_type['name']}"}

    if introspection_data['data']['__type'].get('enumValues'):
            enum_values = [ev['name'] for ev in introspection_data['data']['__type']['enumValues']]
            return [], {
                'type': 'string',
                'enum': enum_values
            }

    properties = {}
    required = []
    unknown_types = []

    for field in introspection_data['data']['__type']['inputFields']:
        field_name = field['name']
        field_type = field['type']

        types, type_definition = convert_field_type(field_type)
        unknown_types.extend(types)
        properties[field_name] = type_definition

    definition = {
        'type': 'object',
        'properties': properties
    }

    if required:
        definition['required'] = required

    # Remove duplicates from unknown_types
    unknown_types = list(set(unknown_types))

    return unknown_types, definition


def main():
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

    args = parser.parse_args()

    if args.subcommand == "list":
        list_snippets()
    elif args.subcommand == "run":
        run_specific_snippet(args.snippet, args.arguments[0])
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
