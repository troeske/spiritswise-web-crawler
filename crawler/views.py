"""
Crawler API views.

Views will be implemented in later task groups as needed.
This file serves as a placeholder to allow Django app initialization.
"""

from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health_check(request):
    """
    Health check endpoint for the crawler service.

    Returns:
        Response: JSON response with service status
    """
    return Response({
        "status": "healthy",
        "service": "web-crawler",
    })
