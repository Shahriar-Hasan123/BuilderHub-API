from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .serializers import RegisterSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer


@extend_schema(
    tags=["Auth"],
    summary="Health check",
    description="Returns the API health status and database connectivity.",
)
@api_view(["GET"])
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "connected"
    except Exception:
        db_status = "unavailable"

    return Response({"status": "ok", "database": db_status}, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Auth"],
    summary="Register user",
    description="Create a new user account with a username and password.",
)
@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response(
        {"id": user.id, "username": user.username}, status=status.HTTP_201_CREATED
    )


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
