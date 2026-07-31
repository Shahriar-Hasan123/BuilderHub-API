from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view


def build_schema(tag, summary, description, request=None, responses=None, **kwargs):
    return extend_schema(
        tags=[tag],
        summary=summary,
        description=description,
        request=request,
        responses=responses,
        **kwargs,
    )


def auth_schema(summary, description, request=None, responses=None, **kwargs):
    return build_schema("Auth", summary, description, request=request, responses=responses, **kwargs)


def page_schema(summary, description, request=None, responses=None, **kwargs):
    return build_schema("Pages", summary, description, request=request, responses=responses, **kwargs)


def site_schema(summary, description, request=None, responses=None, **kwargs):
    return build_schema("Sites", summary, description, request=request, responses=responses, **kwargs)


def object_response():
    return OpenApiTypes.OBJECT


def no_content_response():
    return {204: None}


def schema_view(**operations):
    return extend_schema_view(**operations)


def page_schema_view(**operations):
    return schema_view(**operations)


def site_schema_view(**operations):
    return schema_view(**operations)
