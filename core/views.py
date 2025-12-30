from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseRedirect
import json
import string
import random
import logging
import requests
import os
from dotenv import load_dotenv
from governance.models import GovernanceNFT, GovernanceTopic, GovernanceProposal, Vote, NFTMarketplace
from core.models import UserWallet
from hiero.utils import create_new_account
from hiero.ft import associate_token, transfer_tokens, fund_pool
from hiero.nft import create_nft, mint_nft, associate_nft
from hiero.hcs import submit_message
from core.main import generate_star_convergence_with_mapping
from hiero.mirror_node import get_balance
from django.core.paginator import Paginator
from django.db.models import F, ExpressionWrapper, DecimalField
from datetime import datetime, timedelta
import json
from hiero_sdk_python import (
    AccountId,
)
from ventures.models import Venture, VentureTicket, VentureOwnership

load_dotenv()
def id_generator(size=8, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

logger = logging.getLogger(__name__)

# Cache timeouts (in seconds)
CACHE_TIMEOUT_SHORT = 300  # 5 minutes
CACHE_TIMEOUT_LONG = 1800  # 30 minutes

def id_generator(size=8, chars=string.ascii_uppercase + string.digits):
    """Optimized random string generator"""
    return ''.join(random.choices(chars, k=size))

def assign_user_wallet(name):
    """Optimized wallet assignment with better error handling"""
    try:
        recipient_id, recipient_private_key, new_account_public_key = create_new_account(name)
        associate_token(recipient_id, recipient_private_key)
        
        return {
            'status': 'success',
            'new_account_public_key': new_account_public_key,
            'recipient_private_key': recipient_private_key,
            'recipient_id': recipient_id
        }
    except Exception as e:
        logger.error(f"Wallet assignment error: {e}")
        return {'status': 'failed', 'error': str(e)}

@require_http_methods(["GET", "POST"])
def register_view(request):
    """Optimized registration view with bulk operations"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == "POST":
        # Use dictionary for faster field access
        post_data = request.POST
        required_fields = ['email', 'first_name', 'last_name', 'password', 'password1']
        
        # Fast field validation
        if not all(post_data.get(field) for field in required_fields):
            messages.warning(request, "All fields are required")
            return redirect('register')
        
        if post_data['password'] != post_data['password1']:
            messages.warning(request, "Password does not match")
            return redirect('register')
        
        email = post_data['email'].lower().strip()  # Normalize email
        
        # Cache user existence check
        cache_key = f"user_exists_{email}"
        if cache.get(cache_key) or User.objects.filter(email=email).exists():
            cache.set(cache_key, True, 300)
            messages.warning(request, "User with this email already exists")
            return redirect('register')
        
        try:
            # Create wallet first (more expensive operation)
            wallet_response = assign_user_wallet(name=f"{post_data['first_name']} {post_data['last_name']}")
            
            if wallet_response['status'] != 'success':
                messages.warning(request, "Wallet creation failed")
                return redirect('register')
            
            # Bulk create user and wallet
            with transaction.atomic():  # Fixed transaction import
                user = User.objects.create_user(
                    username=email,  # Use email as username for faster lookup
                    email=email,
                    first_name=post_data['first_name'],
                    last_name=post_data['last_name'],
                    password=post_data['password']
                )
                
                UserWallet.objects.create(
                    user=user,
                    public_key=wallet_response['new_account_public_key'],
                    private_key=wallet_response['recipient_private_key'],
                    recipient_id=wallet_response['recipient_id']
                )
            
            # Cache the new user
            cache.set(cache_key, True, 300)
            messages.success(request, "Account created successfully")
            return redirect('login')
            
        except Exception as e:
            logger.error(f"Registration error: {e}")
            messages.warning(request, "Registration failed")
            return redirect('register')
    
    return render(request, 'accounts/register.html')

@require_http_methods(["GET", "POST"])
def login_view(request):
    """Optimized login with caching"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email', '').lower().strip()
        password = request.POST.get('password', '')
        
        if not email or not password:
            messages.warning(request, "All fields are required")
            return redirect('login')
        
        # Cache failed login attempts
        fail_key = f"login_fail_{email}"
        fail_count = cache.get(fail_key, 0)
        
        if fail_count >= 5:
            messages.warning(request, "Too many failed attempts. Try again later.")
            return redirect('login')
        
        # Authenticate using username (which is email)
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            # Prefetch related data in one query
            wallet = UserWallet.objects.only('id').filter(user=user).first()
            if not wallet:
                messages.warning(request, "Wallet not found")
                return redirect('login')
            
            login(request, user)
            cache.delete(fail_key)  # Clear fail counter
            
            # Cache user session data
            cache.set(f"user_{user.id}_wallet", wallet.id, 3600)
            messages.success(request, f"Welcome back, {user.first_name}!")
            return redirect('dashboard')
        else:
            cache.set(fail_key, fail_count + 1, 900)  # 15 minute timeout
            messages.warning(request, "Invalid credentials")
            return redirect('login')
    
    return render(request, 'accounts/auth.html')

def logout_view(request):
    """Optimized logout with cache cleanup"""
    user_id = request.user.id
    logout(request)
    # Cleanup user-specific cache
    cache.delete_many([f"user_{user_id}_wallet", f"user_{user_id}_keys"])
    return redirect("login")

@cache_page(300)  # Cache for 5 minutes
def landing(request):
    """Optimized landing page with selective field loading"""
    cache_key = "landing_page_data"
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return render(request, 'landing.html', cached_data)
    
   
    context = {
        
    }
    
    cache.set(cache_key, context, 300)
    return render(request, 'landing.html', context)


@login_required
def dashboard_view(request):
    """Main dashboard view with all sections"""
    user = request.user

    user_ventures = Venture.objects.filter(ownerships__owner=request.user).distinct()
    owned_tickets = VentureTicket.objects.filter(buyer=request.user, status='purchased')
    # Calculate user stats
    total_invested = VentureOwnership.objects.filter(
        owner=request.user
    ).aggregate(total=Sum('investment_amount'))['total'] or 0
    
    equity_total = VentureOwnership.objects.filter(
        owner=request.user
    ).aggregate(total=Sum('equity_percentage'))['total'] or 0
    
    # Active ventures for funding
    active_ventures_ = Venture.objects.filter(
        status='funding',
        funding_end__gte=timezone.now(),
        funding_start__lte=timezone.now()
    ).order_by('-created_at')[:3]
    
    all_ventures = Venture.objects.filter(
        status__in=['funding', 'active']
    ).order_by('-created_at')

    # Get 2 active ventures for overview
    active_ventures = all_ventures[:2]
    
    # Get user's venture investments
    user_investments = VentureOwnership.objects.filter(owner=request.user)
    user_ticket_ventures = VentureTicket.objects.filter(
        buyer=request.user, 
        status='purchased'
    ).values_list('venture_id', flat=True)
    
    # Calculate stats
    total_invested = user_investments.aggregate(
        total=Sum('investment_amount')
    )['total'] or 0
    
    equity_total = user_investments.aggregate(
        total=Sum('equity_percentage')
    )['total'] or 0
    
    portfolio_value = total_invested * 1.2  # Simple calculation
    
    # Get investor data for each venture
    for venture in all_ventures:
        # Get top 3 investors for each venture
        top_investors = VentureOwnership.objects.filter(
            venture=venture
        ).order_by('-investment_amount')[:3]
        venture.top_investors = list(top_investors)
        venture.investor_count = VentureOwnership.objects.filter(
            venture=venture
        ).count()
    
    
    try:
        # Get user wallet
        wallet = UserWallet.objects.select_related('user').get(user=user)
        
        # Get user stats
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        
        
        # Wallet data with simulated blockchain info
        wallet_data = {
            'public_key': wallet.public_key[:20] + '...' + wallet.public_key[-20:],
            'full_public_key': wallet.public_key,
            'hedera_id': wallet.recipient_id,
            'balance': get_balance(wallet.recipient_id) if hasattr(wallet, 'recipient_id') else 0,
            'star_tokens': get_balance(wallet.recipient_id) if hasattr(wallet, 'recipient_id') else 0,
            'tickets': owned_tickets.count(),
            'nfts': owned_tickets.count(),
            'recent_transactions': [
                {
                    'id': '0x1a2b...3c4d',
                    'type': 'received',
                    'amount': 500,
                    'token': 'STAR',
                    'from': 'Game Pool',
                    'time': '2 hours ago',
                    'status': 'confirmed'
                },
                {
                    'id': '0x2b3c...4d5e',
                    'type': 'sent',
                    'amount': 50,
                    'token': 'STAR',
                    'to': 'Venture Ticket',
                    'time': '1 day ago',
                    'status': 'confirmed'
                },
                {
                    'id': '0x3c4d...5e6f',
                    'type': 'received',
                    'amount': 1250,
                    'token': 'STAR',
                    'from': 'Venture Win',
                    'time': '3 days ago',
                    'status': 'confirmed'
                }
            ]
        }
        
        # User stats
        user_stats = {
            'total_ventures': active_ventures.count(),
            'total_invested': sum(v['value'] * v['equity'] / 100 for v in user_ventures),
            'total_wins': 3,
            'total_tickets': wallet_data['tickets'],
            'win_rate': 25,  # percentage
            'rank': 'Gold Venture Capitalist',
            'level': 12,
            'xp': 1250,
            'xp_needed': 2000,
            'streak': 7
        }
        
        
        
        # Leaderboard data
        leaderboard = [
            {'rank': 1, 'name': 'Alex Venture', 'score': 24500, 'ventures': 12, 'change': 'up'},
            {'rank': 2, 'name': 'Sarah Innovate', 'score': 19850, 'ventures': 9, 'change': 'up'},
            {'rank': 3, 'name': 'Marcus Capital', 'score': 18750, 'ventures': 11, 'change': 'down'},
            {'rank': 4, 'name': user.first_name, 'score': 16500, 'ventures': user_stats['total_ventures'], 'change': 'up'},
            {'rank': 5, 'name': 'Lena Startup', 'score': 15400, 'ventures': 8, 'change': 'same'},
        ]
        
        context = {
            'user': user,
            'wallet': wallet,
            'wallet_data': wallet_data,
            'active_ventures': active_ventures,
            'user_ventures': user_ventures,
            'user_stats': user_stats,
            'leaderboard': leaderboard,
            'today': today,
            'section': request.GET.get('section', 'overview'),

            # Stats for overview section
            'total_invested': total_invested,
            'equity_total': equity_total,
            'portfolio_value': portfolio_value,

            # For ventures section
            'all_ventures': all_ventures,
            'user_ticket_ventures': list(user_ticket_ventures),

            # Other existing context
            'today': timezone.now(),
            'investment_progress': min(100, (total_invested / 100000) * 100) if total_invested else 75,
            'active_percentage': min(100, (all_ventures.count() / 10) * 100) if all_ventures.exists() else 60,
            'portfolio_progress': min(100, (portfolio_value / 200000) * 100) if portfolio_value else 90,

            # Keep existing context if needed
            'user_stats': {
                'total_invested': total_invested,
                'total_ventures': user_investments.count(),
                'win_rate': 75,  # Placeholder
                'total_wins': user_investments.count(),  # Placeholder
            }
        }
        
        return render(request, 'dashboard/dashboard.html', context)
        
    except UserWallet.DoesNotExist:
        messages.error(request, "Wallet not found. Please contact support.")
        return redirect('login')
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        messages.error(request, "Error loading dashboard. Please try again.")
        return redirect('landing')

@login_required
@require_http_methods(["POST"])
def update_profile_view(request):
    """Update user profile"""
    if request.method == "POST":
        try:
            user = request.user
            data = request.POST
            
            user.first_name = data.get('first_name', user.first_name)
            user.last_name = data.get('last_name', user.last_name)
            user.email = data.get('email', user.email)
            
            # Update bio if exists
            if hasattr(user, 'profile'):
                user.profile.bio = data.get('bio', '')
                user.profile.location = data.get('location', '')
                user.profile.website = data.get('website', '')
                user.profile.save()
            
            user.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Profile updated successfully'
            })
            
        except Exception as e:
            logger.error(f"Profile update error: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


@login_required
def get_wallet_details(request):
    """Get detailed wallet information"""
    try:
        wallet = UserWallet.objects.get(user=request.user)
        
        # Get actual balance from Hedera (simulated)
        balance = get_balance(wallet.recipient_id) if hasattr(wallet, 'recipient_id') else 0
        
        return JsonResponse({
            'success': True,
            'wallet': {
                'public_key': wallet.public_key,
                'hedera_id': wallet.recipient_id,
                'balance': balance,
                'star_tokens': balance,  # Replace with actual
                'tickets': 15,
                'nft_count': 8
            }
        })
        
    except Exception as e:
        logger.error(f"Wallet details error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def submit_strategy_view(request):
    """Submit game strategy"""
    if request.method == "POST":
        try:
            data = request.POST
            game_id = data.get('game_id')
            strategy_text = data.get('strategy')
            
            # Save strategy logic here
            
            messages.success(request, "Strategy submitted successfully!")
            return JsonResponse({
                'success': True,
                'message': 'Strategy submitted for review'
            })
            
        except Exception as e:
            logger.error(f"Strategy submission error: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
        


@login_required
def get_wallet_balance(request):
    """API endpoint for wallet balance"""
    try:
        wallet = UserWallet.objects.get(user=request.user)
        balance = get_balance(wallet.recipient_id) if hasattr(wallet, 'recipient_id') else 0
        
        return JsonResponse({
            'success': True,
            'balance': balance,
            'star_tokens': 2450  # Replace with actual logic
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def get_active_games(request):
    """API endpoint for active games"""
    # Replace with actual game data
    games = [
        {'id': 1, 'name': 'Tech Venture Arena', 'players': 245, 'prize_pool': 12500},
        {'id': 2, 'name': 'AgriTech Challenge', 'players': 189, 'prize_pool': 8500},
        {'id': 3, 'name': 'FinTech Maze', 'players': 567, 'prize_pool': 21500},
    ]
    
    return JsonResponse({'success': True, 'games': games})

@login_required(login_url="login")
@require_http_methods(["POST"])
def buy_star(request):
    try:
        tel = request.POST.get("tel")
        amount = request.POST.get("amount")
        user = request.user
        user_wallet = UserWallet.objects.get(user=user)
        if not tel or not amount:
            messages.warning(request, "Pone Number and amount are required")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        try:
            amount = int(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            messages.warning(request, "Amount must be a positive integer.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        reference = id_generator()


        # Transfer Token to User Wallet
        process_buy = transfer_tokens(recipient_id=user_wallet.recipient_id, amount=amount*100)# Because of two decimal places
        if process_buy['status'] == "failed":
            messages.warning(request, "Failed to Transfer ASTRA. Try again later.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        else:
            messages.success(request, f"{amount} ASTRA Transfered successfully to your account. Check your phone.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
    except requests.RequestException as e:
        logger.error(f"M-Pesa API Error: {e}")
        messages.warning(request, "Payment gateway unreachable.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    except Exception as e:
        logger.exception("Unexpected error in buy_astra view")
        messages.warning(request, "nternal server error.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

'''
@login_required(login_url="login")
def pay_mpesa(request):
    user = request.user
    if request.method == "POST":
        tel = request.POST['tel']
        amount = request.POST['amount']
        if tel and amount:
            reference = id_generator()
            ua = {
                    'Content-Type': 'application/json',
                    'Authorization':'Basic WDFkN3VBYVYzTUxsYjI1VmNhS2U6UHBEMlFnVkMxUXJOalNWTWU4bHhXejd6RFVNNWwzcldnQlcwZkR6cQ==',
                }
            url = 'https://backend.payhero.co.ke/api/v2/payments'
            
            data = {
                "amount": int(amount),
                "phone_number": f"{tel}",
                "channel_id": 947, 
                "provider": "m-pesa",
                "external_reference": f"{reference}",
                "callback_url": "https://astraldraw.com/payment/mpesa/success/"
            }
            res = requests.post(url=url, json=data, headers=ua)
            js = res.json()
            print(js)
            if js['success'] == True:
                # Add EXception to handle Already Exists subscription
                #Transaction.objects.create(user=user, amount=amount, reference=reference)
                messages.success(request, f"STK push initiated successfully, If you did not get any pop up on your phone try following this manual steps to complete your payment: {js['manual_instructions']}")
            else:
                messages.warning(request, "An error occured while trying to process your payment, please try again later")
        else:
            messages.warning(request, "All Fields are requeired!")
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@csrf_exempt
def contributeSuccess(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            response_data = data.get('response', {})
            reference = response_data.get("ExternalReference")
            status = response_data.get("Status")
            payment =  None#Contribute.objects.get(reference=reference)
            if status == "Success":
                payment.status = "Completed"
                payment.save()
            else:
                payment.status = "Cancelled"
                payment.save()
        except Exception as e:
            print(e)




'''