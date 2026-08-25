from __future__ import annotations

from idesktop_v2.api.app import app


def test_openapi_operation_ids_are_present_and_unique() -> None:
    schema = app.openapi()
    operation_ids = [
        operation["operationId"]
        for path_item in schema["paths"].values()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    assert operation_ids
    assert len(operation_ids) == len(set(operation_ids))
