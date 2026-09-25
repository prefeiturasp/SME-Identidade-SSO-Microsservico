"""Views da API da aplicação core."""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api.serializers import HealthStatusSerializer

_TAG = ["Core"]


@extend_schema(
    tags=_TAG,
    summary="Health Check",
    description="Verifica se a aplicação está disponível.",
    auth=[],
    responses={
        200: HealthStatusSerializer,
    },
)
class HealthCheckView(APIView):
    """Disponibiliza o endpoint de verificação de saúde da aplicação."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        """Retorna o estado de saúde da aplicação.

        Args:
            request: Requisição HTTP recebida.

        Returns:
            Resposta HTTP contendo o status da aplicação.
        """
        serializer = HealthStatusSerializer(
            {"status": "healthy"},
        )

        return Response(serializer.data)
