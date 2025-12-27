from django.urls import path
from . import views

urlpatterns = [
    # CEO Matrix Game URLs
    path('game/matrix/', views.matrix_game_view, name='matrix_game'),
    path('game/matrix/<uuid:game_id>/', views.matrix_game_view, name='matrix_game_detail'),
    
    # API Endpoints
    path('api/matrix/game/<uuid:game_id>/state/', views.get_matrix_game_state, name='matrix_game_state'),
    path('api/matrix/move/', views.make_move, name='matrix_move'),
    path('api/matrix/<uuid:game_id>/leaderboard/', views.get_matrix_leaderboard, name='matrix_leaderboard'),
    path('api/matrix/reset/', views.reset_matrix_session, name='reset_matrix_session'),
]