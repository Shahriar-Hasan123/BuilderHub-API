from django.db import connection
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.core.schema import auth_schema, object_response

from .serializers import CustomTokenObtainPairSerializer, RegisterSerializer


@auth_schema(
    "Health check",
    "Returns the API health status and database connectivity.",
    responses={200: object_response()},
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


@auth_schema(
    "Register user",
    "Create a new user account with a username and password.",
    request=RegisterSerializer,
    responses={201: object_response()},
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


@auth_schema(
    "Obtain JWT tokens with user info",
    "Authenticate and return JWT tokens along with basic user info.",
)
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
