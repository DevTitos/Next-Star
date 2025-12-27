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
    path('dashboard/buy-ticket/', views.buy_ticket_view, name='buy_ticket'),
    path('dashboard/wallet-details/', views.get_wallet_details, name='wallet_details'),
    path('dashboard/submit-strategy/', views.submit_strategy_view, name='submit_strategy'),
    
    # API endpoints
    path('api/wallet/balance/', views.get_wallet_balance, name='api_wallet_balance'),
    path('api/games/active/', views.get_active_games, name='api_active_games'),
]

'''
    # Dashboard & User URLs
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.dashboard, name='profile'),  # Alias for profile
    
    # Draw Management URLs
    path('draws/', views.dashboard, name='draws_list'),  # Uses dashboard template
    path('draws/<int:draw_id>/', views.draw_detail, name='draw_detail'),
    path('draws/submit-keys/', views.submit_keys, name='submit_keys'),
    path('draws/create/', views.create_draw, name='create_draw'),
    path('draws/<int:draw_id>/process/', views.process_draw, name='process_draw'),
    
    # User Data URLs
    path('my-keys/', views.user_keys, name='user_keys'),
    path('platform-stats/', views.platform_stats, name='platform_stats'),
    path('buy/ASTRA/mpesa/', views.buy_astra, name='buy_astra'),
    
    # API URLs (JSON endpoints)
    path('api/draws/<int:draw_id>/', views.draw_detail, name='api_draw_detail'),
    path('api/my-keys/', views.user_keys, name='api_user_keys'),
    path('api/platform-stats/', views.platform_stats, name='api_platform_stats'),
    #path('api/draws/<int:draw_id>/submit-keys/', views.submit_keys, name='api_submit_keys'),
    path('api/draws/create/', views.create_draw, name='api_create_draw'),
    path('api/draws/<int:draw_id>/process/', views.process_draw, name='api_process_draw'),
    '''