from django.urls import path
from . import views

urlpatterns = [
    path('trends/', views.trends, name='trends'),
]
