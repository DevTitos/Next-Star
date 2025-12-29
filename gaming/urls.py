from django.urls import path
from . import views

urlpatterns = [
    # Game Hub & Navigation
    path('venture/<int:venture_id>/hub/', views.game_hub, name='game_hub'),
    path('venture/<int:venture_id>/play/<str:game_type>/', views.play_game, name='play_game'),
    path('venture/<int:venture_id>/leaderboard/', views.leaderboard, name='leaderboard'),
    path('venture/<int:venture_id>/download/', views.download_puzzle, name='download_puzzle'),
    
    # Admin
    path('admin/games/create/', views.create_venture_game, name='create_venture_game'),
    
    # API Endpoints
    path('api/sessions/<int:session_id>/submit/', views.submit_solution, name='submit_solution'),
    path('api/sessions/<int:session_id>/hint/', views.api_use_hint, name='use_hint'),
    path('api/download/puzzle/<int:puzzle_id>/<str:format>/', 
         views.api_download_puzzle, name='download_puzzle_api'),
    
    # Auto-redirect for convenience
    path('', views.game_hub, name='gaming_home'),
]