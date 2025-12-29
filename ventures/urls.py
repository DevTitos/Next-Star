# ventures/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('admin/ventures/create/', views.create_venture, name='create_venture'),
    path('ventures/create/', views.create_venture_page, name='create_venture_page'),
]