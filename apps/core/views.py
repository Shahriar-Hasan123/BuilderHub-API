from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


@api_view(["GET"])
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "connected"
    except Exception:
        db_status = "unavailable"

    return Response({"status": "ok", "database": db_status}, status=status.HTTP_200_OK)
