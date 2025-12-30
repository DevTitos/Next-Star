from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('', include('matrix.urls')),
    path('', include('ventures.urls')),
    path('', include('gaming.urls')),
]
