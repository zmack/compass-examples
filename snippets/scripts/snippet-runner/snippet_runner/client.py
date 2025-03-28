"""GraphQL client for interacting with the API."""
import requests
from requests.auth import HTTPBasicAuth
from typing import Dict


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

    def get_type_shape(self, type_name: str) -> Dict:
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
