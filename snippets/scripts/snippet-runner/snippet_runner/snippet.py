"""Snippet management for GraphQL queries."""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from graphql import (
    DocumentNode,
    OperationDefinitionNode,
    NamedTypeNode,
    ListTypeNode,
    NonNullTypeNode,
    VariableDefinitionNode,
    TypeNode,
    parse,
)
from jsonschema import Draft4Validator

from .client import Client
from .schema_generator import SnippetInputSchemaGenerator


@dataclass
class Snippet:
    name: str
    path: str
    client: Client
    arguments: Optional[List[str]] = None

    def parse(self) -> Optional[OperationDefinitionNode]:
        self.content = self._read_content()
        if self.content is None:
            return None

        parsed = parse(self.content)
        self.params = self._unwrap(parsed)
        self.schema_generator = SnippetInputSchemaGenerator(self, parsed, self.client)
        self.operation_name = self._get_operation_name(parsed)
        return None

    def generate_validation_schema(self) -> dict:
        return self.schema_generator.generate_schema()

    def validate(self, arguments: object) -> Optional[List[str]]:
        schema = self.generate_validation_schema()
        return validator.validate(arguments)

    def run(self, arguments: Optional[object] = None) -> None:
        self.parse()
        if arguments is not None:
            self.validate(arguments)

    def _read_content(self) -> Optional[str]:
        path = self._find_graphql_file()
        if path is None:
            return None
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
        return None

    def _unwrap(self, document: DocumentNode) -> Dict[str, str]:
        params: Dict[str, str] = dict()
        for definition in document.definitions:
            if not isinstance(definition, OperationDefinitionNode):
                continue
            for variable in definition.variable_definitions:
                if (tuple := self._parse_variable_definition(variable)) is not None:
                    name, kind = tuple
                    params[name] = kind
        return params

    def _parse_variable_definition(
        self, node: VariableDefinitionNode
    ) -> Optional[Tuple[str, str]]:
        if (type_name := self._type_to_schema(node.type)) is not None:
            return node.variable.name.value, type_name
        return None

    def _type_to_schema(self, node: TypeNode) -> Optional[str]:
        match node:
            case NamedTypeNode():
                return node.name.value
            case ListTypeNode():
                return f"[{self._type_to_schema(node.type)}]"
            case NonNullTypeNode():
                return f"{self._type_to_schema(node.type)}!"
        return None
