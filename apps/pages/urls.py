from django.urls import path
from .views import PageListCreateAPIView, PageDetailAPIView

urlpatterns = [
    path('sites/<int:site_pk>/pages/', PageListCreateAPIView.as_view(), name='page-list-create'),
    path('sites/<int:site_pk>/pages/<int:pk>/', PageDetailAPIView.as_view(), name='page-detail'),
]