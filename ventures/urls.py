# ventures/urls.py
from django.urls import path
from . import views

urlpatterns = [
    
    path('ventures/', views.ventures_list, name='ventures_list'),
    path('ventures/create/', views.create_venture_page, name='create_venture_page'),
    path('ventures/admin/create/', views.create_venture, name='create_venture'),
    path('ventures/<slug:slug>/', views.venture_detail, name='venture_detail'),
    path('api/ventures/<slug:slug>/invest/', views.api_check_investment, name='api_check_investment'),
    path('api/ventures/<slug:slug>/invest/confirm/', views.api_purchase_ticket, name='api_purchase_ticket'),
    path('api/ventures/<slug:slug>/investors/', views.api_get_investors, name='api_get_investors'),
    path('ventures/<int:venture_id>/buy-ticket/', views.buy_venture_ticket, name='buy_venture_ticket'),
    
    # API endpoints
    path('api/wallet/balance/', views.api_wallet_balance, name='api_wallet_balance'),
]