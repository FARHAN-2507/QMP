"""Test generator — creates test cases from API understanding.

Takes parsed API information (endpoints, parameters, schemas)
and generates structured test cases that the runner can execute.
"""

from __future__ import annotations

from typing import Any

from querymind.testing.models import (
    ApiTestCase,
    ApiTestRequest,
    Assertion,
    AssertionType,
)


def generate_tests_from_endpoints(
    base_url: str,
    endpoints: list[dict[str, Any]],
) -> list[ApiTestCase]:
    """Generate test cases for a list of API endpoints.

    Each endpoint dict should have:
        - path: str (e.g., "/api/users")
        - method: str (e.g., "GET")
        - parameters: list[dict] (optional)
        - request_body: dict (optional)
        - responses: dict (optional)
    """
    tests: list[ApiTestCase] = []

    for ep in endpoints:
        path = ep.get("path", "/")
        method = ep.get("method", "GET").upper()
        parameters = ep.get("parameters", [])
        request_body = ep.get("request_body")
        responses = ep.get("responses", {})

        url = f"{base_url.rstrip('/')}{path}"

        # Build request
        headers = {"Content-Type": "application/json"}
        body = None
        if request_body and method in ("POST", "PUT", "PATCH"):
            body = _generate_sample_body(request_body)

        request = ApiTestRequest(
            method=method,
            url=url,
            headers=headers,
            body=body,
        )

        # Build assertions
        assertions = _generate_assertions(method, responses)

        # Create test case
        test_name = f"{method} {path}"
        tests.append(ApiTestCase(
            name=test_name,
            description=f"Test {method} {path}",
            request=request,
            assertions=assertions,
        ))

        # Generate error test cases
        error_tests = _generate_error_cases(
            method=method,
            url=url,
            path=path,
            parameters=parameters,
            request_body=request_body,
        )
        tests.extend(error_tests)

    return tests


def _generate_sample_body(request_body: dict[str, Any]) -> dict[str, Any]:
    """Generate a sample request body from schema."""
    if "properties" not in request_body:
        return {}

    body: dict[str, Any] = {}
    required = request_body.get("required", [])

    for prop_name, prop_schema in request_body["properties"].items():
        # Always include required fields, skip optional ones
        if prop_name not in required:
            continue

        prop_type = prop_schema.get("type", "string")

        if prop_type == "string":
            # Generate reasonable defaults based on name
            if "email" in prop_name.lower():
                body[prop_name] = "test@example.com"
            elif "password" in prop_name.lower():
                body[prop_name] = "securePassword123!"
            elif "name" in prop_name.lower():
                body[prop_name] = "Test User"
            elif "url" in prop_name.lower() or "link" in prop_name.lower():
                body[prop_name] = "https://example.com"
            elif "description" in prop_name.lower():
                body[prop_name] = "Test description"
            else:
                body[prop_name] = "test_value"
        elif prop_type == "integer":
            body[prop_name] = 1
        elif prop_type == "number":
            body[prop_name] = 1.0
        elif prop_type == "boolean":
            body[prop_name] = True
        elif prop_type == "array":
            body[prop_name] = []
        elif prop_type == "object":
            body[prop_name] = {}
        else:
            body[prop_name] = None

    return body


def _generate_assertions(
    method: str,
    responses: dict[str, Any],
) -> list[Assertion]:
    """Generate assertions based on method and expected responses."""
    assertions: list[Assertion] = []

    # Always check status code
    if "200" in responses:
        assertions.append(Assertion(
            type=AssertionType.STATUS_CODE,
            expected=200,
            description="Returns 200 OK",
        ))
    elif "201" in responses:
        assertions.append(Assertion(
            type=AssertionType.STATUS_CODE,
            expected=201,
            description="Returns 201 Created",
        ))
    elif "204" in responses:
        assertions.append(Assertion(
            type=AssertionType.STATUS_CODE,
            expected=204,
            description="Returns 204 No Content",
        ))
    else:
        # Default: expect 2xx
        assertions.append(Assertion(
            type=AssertionType.STATUS_CODE_RANGE,
            expected=[200, 299],
            description="Returns 2xx success",
        ))

    # Check response time
    assertions.append(Assertion(
        type=AssertionType.RESPONSE_TIME_MS,
        expected=5000,
        description="Responds within 5 seconds",
    ))

    # For GET requests, check body is not empty
    if method == "GET":
        assertions.append(Assertion(
            type=AssertionType.BODY_NOT_EMPTY,
            description="Response body is not empty",
        ))

    return assertions


def _generate_error_cases(
    method: str,
    url: str,
    path: str,
    parameters: list[dict[str, Any]],
    request_body: dict[str, Any] | None,
) -> list[ApiTestCase]:
    """Generate test cases for error scenarios."""
    tests: list[ApiTestCase] = []

    # 404 test for non-root paths
    if path != "/":
        tests.append(ApiTestCase(
            name=f"{method} {path} (non-existent)",
            description=f"Test {method} with invalid resource ID",
            request=ApiTestRequest(
                method=method,
                url=f"{url}/nonexistent_12345",
                headers={"Content-Type": "application/json"},
            ),
            assertions=[
                Assertion(
                    type=AssertionType.STATUS_CODE_RANGE,
                    expected=[400, 499],
                    description="Returns 4xx for invalid resource",
                ),
            ],
        ))

    # Missing required fields for POST/PUT
    if method in ("POST", "PUT", "PATCH") and request_body:
        required = request_body.get("required", [])
        if required:
            tests.append(ApiTestCase(
                name=f"{method} {path} (missing fields)",
                description=f"Test {method} without required fields",
                request=ApiTestRequest(
                    method=method,
                    url=url,
                    headers={"Content-Type": "application/json"},
                    body={},
                ),
                assertions=[
                    Assertion(
                        type=AssertionType.STATUS_CODE_RANGE,
                        expected=[400, 499],
                        description="Returns 4xx for missing required fields",
                    ),
                ],
            ))

    return tests


def generate_crud_tests(
    base_url: str,
    resource_path: str,
) -> list[ApiTestCase]:
    """Generate CRUD test suite for a resource.

    Creates tests for:
    - GET all (list)
    - GET by ID
    - POST (create)
    - PUT (update)
    - DELETE
    """
    tests: list[ApiTestCase] = []
    base = f"{base_url.rstrip('/')}{resource_path}"

    # GET list
    tests.append(ApiTestCase(
        name=f"GET {resource_path}",
        description="List all resources",
        request=ApiTestRequest(method="GET", url=base),
        assertions=[
            Assertion(type=AssertionType.STATUS_CODE, expected=200),
            Assertion(type=AssertionType.RESPONSE_TIME_MS, expected=5000),
        ],
    ))

    # GET by ID
    tests.append(ApiTestCase(
        name=f"GET {resource_path}/:id",
        description="Get resource by ID",
        request=ApiTestRequest(method="GET", url=f"{base}/1"),
        assertions=[
            Assertion(type=AssertionType.STATUS_CODE_RANGE, expected=[200, 404]),
            Assertion(type=AssertionType.RESPONSE_TIME_MS, expected=5000),
        ],
    ))

    # POST
    tests.append(ApiTestCase(
        name=f"POST {resource_path}",
        description="Create new resource",
        request=ApiTestRequest(
            method="POST",
            url=base,
            headers={"Content-Type": "application/json"},
            body={"name": "test"},
        ),
        assertions=[
            Assertion(type=AssertionType.STATUS_CODE_RANGE, expected=[200, 201]),
            Assertion(type=AssertionType.RESPONSE_TIME_MS, expected=5000),
        ],
    ))

    # PUT
    tests.append(ApiTestCase(
        name=f"PUT {resource_path}/:id",
        description="Update resource",
        request=ApiTestRequest(
            method="PUT",
            url=f"{base}/1",
            headers={"Content-Type": "application/json"},
            body={"name": "updated"},
        ),
        assertions=[
            Assertion(type=AssertionType.STATUS_CODE_RANGE, expected=[200, 204]),
            Assertion(type=AssertionType.RESPONSE_TIME_MS, expected=5000),
        ],
    ))

    # DELETE
    tests.append(ApiTestCase(
        name=f"DELETE {resource_path}/:id",
        description="Delete resource",
        request=ApiTestRequest(method="DELETE", url=f"{base}/1"),
        assertions=[
            Assertion(type=AssertionType.STATUS_CODE_RANGE, expected=[200, 204]),
        ],
    ))

    return tests
