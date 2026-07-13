from django.urls import path
from .views import PageListCreateAPIView, PageDetailAPIView

urlpatterns = [
    path('pages/', PageListCreateAPIView.as_view(), name='page-list-create'),
    path('pages/<int:pk>/', PageDetailAPIView.as_view(), name='page-detail'),
]