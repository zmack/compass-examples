import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from pprint import pp
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from graphql import (
    ListTypeNode,
    NonNullTypeNode,
    OperationDefinitionNode,
    TypeNode,
    VariableDefinitionNode,
    build_ast_schema,
    graphql_sync,
    parse,
    print_schema,
)
from graphql.language.ast import DocumentNode, NamedTypeNode
from jsonschema import validate
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
        schema = self._operation_input_json_schema(parsed)
        self.schema = schema
        self.operation_name = self._get_operation_name(parsed)
        print(a)
        self.params = a

    def validate(self, arguments: object) -> Optional[List[str]]:
        print(arguments)
        print(self.schema)
        print(validate(arguments, self.schema))

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

        return {"type": "object", "properties": properties, "required": required}

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
    snippet: Snippet, url: str, username: str, password: str
) -> requests.Response:
    data = snippet.content
    component_id = "ari:cloud:compass:02b76147-4f85-43e7-bd20-a167bc77571e:component/c0c2e7bf-173c-4ae8-ba9f-c021b8d78e9b/2ad9daf6-115a-4fc4-ad60-dd457b60a02e"
    payload = {
        "query": data,
        "variables": {"componentID": component_id},
        "operationName": snippet.operation_name,
    }

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
params = json.loads(sys.argv[1])

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

# response = get_type_shape("AddPolarisColumnInput", username, password, url)
# pp(response.json())
# pp(response.json())

snippet = next(
    (
        snippet
        for snippet in snippets
        if snippet.name == "get-metric-values-for-component"
    ),
    None,
)

if snippet is None:
    exit(1)

snippet.run(params)

print(snippet)
print(sys.argv[1])
response = run_snippet(snippet, url, username, password)
print(response.json())
