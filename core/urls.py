from django.urls import path
from . import views

urlpatterns = [
    # Authentication URLs
    path('', views.landing, name='landing'),
    #path('faqs/', views.faqs, name='faqs'),
    path('accounts/register/', views.register_view, name='register'),
    path('accounts/login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/update-profile/', views.update_profile_view, name='update_profile'),
    path('dashboard/wallet-details/', views.get_wallet_details, name='wallet_details'),
    path('dashboard/submit-strategy/', views.submit_strategy_view, name='submit_strategy'),
    
    # API endpoints
    path('api/wallet/balance/', views.get_wallet_balance, name='api_wallet_balance'),
    path('api/games/active/', views.get_active_games, name='api_active_games'),
]