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
    
    try:
        # Get user wallet
        wallet = UserWallet.objects.select_related('user').get(user=user)
        
        # Get user stats
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Simulate game data (replace with actual models)
        active_games = [
            {
                'id': 1,
                'name': 'Tech Venture Arena',
                'type': 'Venture Arena',
                'players': 245,
                'prize_pool': 12500,
                'ends_in': '2 days',
                'progress': 65,
                'status': 'active',
                'icon': 'fa-crosshairs',
                'color': 'primary'
            },
            {
                'id': 2,
                'name': 'AgriTech Challenge',
                'type': 'CEO Matrix',
                'players': 189,
                'prize_pool': 8500,
                'ends_in': '1 day',
                'progress': 85,
                'status': 'active',
                'icon': 'fa-chess-king',
                'color': 'success'
            },
            {
                'id': 3,
                'name': 'FinTech Maze',
                'type': 'Infinite Maze',
                'players': 567,
                'prize_pool': 21500,
                'ends_in': '3 days',
                'progress': 45,
                'status': 'active',
                'icon': 'fa-infinity',
                'color': 'accent'
            }
        ]
        
        # User ventures (owned/participated)
        user_ventures = [
            {
                'id': 1,
                'name': 'EcoEnergy Africa',
                'industry': 'Energy',
                'equity': 5.2,
                'value': 12500,
                'growth': 15.3,
                'status': 'active',
                'role': 'Investor',
                'members': 45
            },
            {
                'id': 2,
                'name': 'FarmChain AI',
                'industry': 'Agriculture',
                'equity': 12.8,
                'value': 28750,
                'growth': 32.7,
                'status': 'active',
                'role': 'CEO',
                'members': 23
            },
            {
                'id': 3,
                'name': 'MediTech Connect',
                'industry': 'Healthcare',
                'equity': 3.5,
                'value': 8750,
                'growth': 8.2,
                'status': 'funding',
                'role': 'Investor',
                'members': 67
            }
        ]
        
        # Wallet data with simulated blockchain info
        wallet_data = {
            'public_key': wallet.public_key[:20] + '...' + wallet.public_key[-20:],
            'full_public_key': wallet.public_key,
            'hedera_id': wallet.recipient_id,
            'balance': get_balance(wallet.recipient_id) if hasattr(wallet, 'recipient_id') else 0,
            'star_tokens': 2450,
            'tickets': 15,
            'nfts': 8,
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
            'total_ventures': len(user_ventures),
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
        
        # Recent activity
        recent_activity = [
            {
                'type': 'game_win',
                'title': 'Won Venture Arena',
                'description': 'First place in Tech Innovation Challenge',
                'amount': '+1250 STAR',
                'time': '2 hours ago',
                'icon': 'fa-trophy',
                'color': 'success',
                'color_code': '123,63,228'
            },
            {
                'type': 'investment',
                'title': 'Invested in EcoEnergy',
                'description': 'Purchased 5.2% equity',
                'amount': '-500 STAR',
                'time': '1 day ago',
                'icon': 'fa-chart-line',
                'color': 'primary',
                'color_code': '123,63,228'
            },
            {
                'type': 'nft_minted',
                'title': 'NFT Minted',
                'description': 'Equity Certificate #4589',
                'amount': 'NFT',
                'time': '2 days ago',
                'icon': 'fa-certificate',
                'color': 'accent',
                'color_code': '0,255,157'
            },
            {
                'type': 'ticket_purchase',
                'title': 'Ticket Purchased',
                'description': 'AgriTech Challenge entry',
                'amount': '-50 STAR',
                'time': '3 days ago',
                'icon': 'fa-ticket-alt',
                'color': 'warning',
                'color_code': '0,255,157'
            }
        ]
        
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
            'active_games': active_games,
            'user_ventures': user_ventures,
            'user_stats': user_stats,
            'recent_activity': recent_activity,
            'leaderboard': leaderboard,
            'today': today,
            'section': request.GET.get('section', 'overview')
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
@require_http_methods(["POST"])
def buy_ticket_view(request):
    """Buy game tickets"""
    try:
        data = json.loads(request.body)
        game_id = data.get('game_id')
        amount = data.get('amount', 1)
        
        # Here you would integrate with payment system
        # For now, simulate successful purchase
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully purchased {amount} ticket(s)',
            'tickets': 15 + amount,  # Update with actual logic
            'balance': 2450 - (50 * amount)  # Update with actual logic
        })
        
    except Exception as e:
        logger.error(f"Ticket purchase error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Purchase failed'
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
                'star_tokens': 2450,  # Replace with actual
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
        


# Add to views.py

from django.http import JsonResponse
import json

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



'''

@login_required
@require_http_methods(["POST"])
def submit_keys(request):
    """Optimized key submission with transaction"""
    try:
        draw_id = request.POST['draw_id']
        key_1 = request.POST['key-1']
        key_2 = request.POST['key-2']
        key_3 = request.POST['key-3']
        key_4 = request.POST['key-4']
        key_5 = request.POST['key-5']
        key_6 = request.POST['key-6']
        if not draw_id and key_1 and key_2 and key_3 and key_4 and key_5 and key_6:
            messages.warning(request, "All Fields are required to initiate Draw Key Forging!")
            return redirect(request.META.get('HTTP_REFERER', '/'))
        draw = get_object_or_404(Draw, id=draw_id)
        
        if not draw.is_active():
            messages.warning(request, "Draw Not Active for Key Forging, try again later!")
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        user_wallet_id = cache.get(f"user_{request.user.id}_wallet")
        user_wallet = get_object_or_404(UserWallet, user=request.user)
        if not user_wallet_id:
            user_wallet_id = user_wallet.id
            cache.set(f"user_{request.user.id}_wallet", user_wallet_id, 3600)
        
        # Check existing submission using exists() for speed
        if ForgedKey.objects.filter(user_wallet=user_wallet, draw=draw).exists():
            messages.warning(request, "Keys already submitted for this draw!")
            return redirect(request.META.get('HTTP_REFERER', '/'))
    
        try:
            astra_bal = get_balance(user_wallet.recipient_id)
        except Exception as e:
            astra_bal = 0
        if astra_bal < 100:
            messages.warning(request, "Insufficient Astral to Participate in this draw, please top up your account and try again!")
            return redirect(request.META.get('HTTP_REFERER', '/'))
        # Check user Astra balance using Mirror Node
        star_keys = [key_1, key_2, key_3, key_4, key_5, key_6]
        
        with transaction.atomic():
            user_wallet = get_object_or_404(UserWallet, user=request.user)
            # FOrge NFT TIcket
            ticket_metadata = f"title:{draw.title} Convergence - Keys: {star_keys} - User :{user_wallet_id}"
            print(draw.nft_id)
            nft_ = mint_nft(nft_token_id=draw.nft_id, metadata=ticket_metadata)
            if nft_['status'] == 'success':
                assc=associate_nft(account_id=user_wallet.recipient_id, token_id=draw.nft_id, account_private_key=user_wallet.decrypt_key(), nft_id=nft_['message'])
                if assc['status'] == 'success':
                    # Create forged key
                    serial_number = f"AK{draw_id}{user_wallet_id}{nft_['serial']}"
                    forged_key = ForgedKey.objects.create(
                        user_wallet=user_wallet,
                        draw=draw,
                        serial_number=serial_number,
                        star_keys=str(star_keys),
                    )
                    draw.total_tickets_sold += 1
                    draw.save()
                    # CReate HCS Message for immutability
                    submit_message(message=ticket_metadata)
                    # Transfer Astra from user wallet to Nebula Pool
                    transfer = fund_pool(recipient_id=user_wallet.recipient_id, amount=100, account_private_key=user_wallet.decrypt_key())
                    if transfer['status'] == 'failed':
                        messages.warning(request, f"Token Transfer Failed")
                        return redirect(request.META.get('HTTP_REFERER', '/'))
            else:
                messages.warning(request, f"Forging Failed: {nft_['message']}")
                return redirect(request.META.get('HTTP_REFERER', '/'))
        
        # Invalidate relevant caches
        cache.delete_many([f"dashboard_{request.user.id}", f"user_{request.user.id}_keys"])
        
        messages.success(request, "Keys submitted successfully!")
        return redirect(request.META.get('HTTP_REFERER', '/'))
        
    except Exception as e:
        messages.warning(request, f"An Error Occured while Forging your star keys, please try again later: {e}")
        return redirect(request.META.get('HTTP_REFERER', '/'))

@login_required
@require_http_methods(["POST"])
def create_draw(request):
    """Admin view to create new draws"""
    if not request.user.is_staff:
        messages.warning(request, "admin access required!")
        return redirect(request.META.get('HTTP_REFERER', '/'))
    
    try:
        
        title = request.POST['title']
        symbol = request.POST['symbol']
        status = request.POST['status'].upper()
        prize_pool = request.POST['prize_pool']
        draw_datetime = request.POST['draw_datetime']
        
        # Validate required fields
        if not title and  symbol and status and prize_pool and draw_datetime:
            messages.warning(request, "All Field are required!")
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        # Generate winning star keys (6 random numbers 0-9)
        #winning_keys = [random.randint(0, 9) for _ in range(6)]
        # CREATE ASTRAL NFT DRAW
        draw_nft = create_nft(title=title, symbol=symbol)
        if draw_nft['status'] == 'failed':
            messages.warning(request, "Draw creation failed, NFT creation was not successful")
            return redirect(request.META.get('HTTP_REFERER', '/'))
        else:
            draw = Draw.objects.create(
                title=title,
                prize_pool=prize_pool,
                draw_datetime=draw_datetime,
                status=status,
                nft_id=draw_nft['token_id']
            )
            Alert.objects.create(title="New Convergence Launched", content=f"{title} Convergence is now active with {prize_pool} ASTRA prize pool", icon='rocket')
        
        # Clear relevant caches
        cache.delete_many(["platform_stats", "landing_page_data"])
        messages.success(request, f"{draw.title} Convergence Draw created successfully")
        return redirect(request.META.get('HTTP_REFERER', '/'))
        
    except Exception as e:
        messages.warning(request, f"An error occured: {e}")
        return redirect(request.META.get('HTTP_REFERER', '/'))

# Optimized API views with selective field loading
@login_required
def draw_detail(request, draw_id):
    user = request.user
    """Optimized draw detail with field selection"""
    draw = get_object_or_404(Draw.objects.only(
        'id', 'title', 'status', 'prize_pool', 'draw_datetime', 'total_tickets_sold', 'winner_wallet_id', 'winning_ticket_serial'
    ), id=draw_id)

    # Get user's star keys for this draw
    user_star_keys = ForgedKey.objects.filter(
        user_wallet__user=user,
        draw=draw
    ).values_list('serial_number', flat=True)

    draw_data = {
        "success": True,
        "draw": {
            "id": draw.id,
            "title": draw.title,
            "symbol": "NEB7",
            "prize_pool": draw.prize_pool,
            "status": draw.status,
            "draw_datetime": draw.draw_datetime,
            "nft_token_id": draw.nft_id,
            "nft_contract": draw.nft_id
        },
        "participants_count": draw.total_tickets_sold,
        "user_keys": len(user_star_keys),
        "star_keys": list(user_star_keys),
    }
    print(draw.nft_id)
    if draw.status == "ENDED":
        draw_data['winning_keys'] = draw.get_star_keys()
        if draw.winner_wallet_id:
            # Efficiently get winner username
            winner_username = User.objects.filter(
                id=draw.winner_wallet.user.id
            ).values_list('username', flat=True).first()
            draw_data['winner'] = {
                'username': winner_username,
                'ticket_serial': draw.winning_ticket_serial
            }
    
    return JsonResponse(draw_data)

@login_required
def user_keys(request):
    """Optimized user keys with efficient query"""
    cache_key = f"user_{request.user.id}_keys"
    cached_keys = cache.get(cache_key)
    
    if cached_keys:
        return JsonResponse({'keys': cached_keys})
    
    user_wallet = get_object_or_404(UserWallet, user=request.user)
    keys = ForgedKey.objects.filter(
        user_wallet=user_wallet
    ).select_related('draw').only(
        'id', 'serial_number', 'created_at', 'nft_metadata',
        'draw__title', 'draw__status'
    ).order_by('-created_at')[:50]  # Limit results
    
    keys_data = []
    for key in keys:
        keys_data.append({
            'id': key.id,
            'serial_number': key.serial_number,
            'draw_title': key.draw.title,
            'draw_status': key.draw.status,
            'created_at': key.created_at,
            'is_winner': key.is_winner(),
            'match_count': key.get_match_count() if key.draw.status == Draw.DrawStatus.ENDED else None,
        })
    
    cache.set(cache_key, keys_data, 300)
    return JsonResponse({'keys': keys_data})

@cache_page(600)  # Cache for 10 minutes
def platform_stats(request):
    """Optimized platform stats with caching"""
    cache_key = "platform_stats"
    cached_stats = cache.get(cache_key)
    
    if cached_stats:
        return JsonResponse(cached_stats)
    
    # Single query for all stats
    stats = {
        'total_draws': Draw.objects.count(),
        'active_draws': Draw.objects.filter(
            status__in=[Draw.DrawStatus.UPCOMING, Draw.DrawStatus.ACTIVE]
        ).count(),
        'total_prizes': float(Draw.objects.aggregate(Sum('prize_pool'))['prize_pool__sum'] or 0),
        'total_players': UserWallet.objects.count(),
        'keys_forged': ForgedKey.objects.count(),
    }
    
    # Recent winners with efficient query
    recent_winners = list(Draw.objects.filter(
        status=Draw.DrawStatus.ENDED,
        winner_wallet__isnull=False
    ).select_related('winner_wallet__user').values(
        'title', 'prize_pool', 'draw_datetime', 'winner_wallet__user__username'
    )[:5])
    
    result = {'stats': stats, 'recent_winners': recent_winners}
    cache.set(cache_key, result, 600)
    return JsonResponse(result)

# Batch processing optimization for admin functions
@login_required
@require_http_methods(["POST"])
def process_draw(request, draw_id):
    """Optimized draw processing with bulk operations"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Admin access required'})
    
    try:
        draw = get_object_or_404(Draw, id=draw_id)
        if draw.status != Draw.DrawStatus.ACTIVE and draw.draw_datetime < timezone.now():
            return JsonResponse({'success': False, 'error': 'Draw cannot be processed'})
        
        try:
            star_keys = generate_star_convergence_with_mapping()
            print(star_keys)
            msg = {
                'draw':draw.title,
                'contract_id':draw.nft_id,
                'star_keys':star_keys,
                'timestamp':timezone.now()
            }
            hcs_msg = submit_message(message=f"{msg}")
            if hcs_msg['status'] == 'success':
                draw.star_keys = str(star_keys)
                draw.save()
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Star Key Initialization Failed: {e}'})
        
        winner = draw.map_winner()
        with transaction.atomic():
            if winner:
                prize_amount = draw.prize_pool * 0.7
                # Update draw in single query
                Draw.objects.filter(id=draw_id).update(
                    total_prize_distributed=prize_amount,
                    status=Draw.DrawStatus.ENDED,
                    winner_wallet=winner.user_wallet,
                    winning_ticket_serial=winner.serial_number
                )
                Draw.objects.filter(status=Draw.DrawStatus.UPCOMING).update(status=Draw.DrawStatus.ACTIVE)
                Alert.objects.create(title="Cosmic Victory!", icon="trophy", content=f"{draw.title} Convergence Winner announced! ")
            else:
                Draw.objects.filter(id=draw_id).update(status=Draw.DrawStatus.ENDED)
                Draw.objects.filter(status=Draw.DrawStatus.UPCOMING).update(status=Draw.DrawStatus.ACTIVE)
        # Clear relevant caches
        cache.delete_many(["platform_stats", "landing_page_data"])
        
        return JsonResponse({
            'success': True,
            'winner': {
                'username': winner.user_wallet.user.username,
                'serial_number': winner.serial_number,
                'prize_amount': float(prize_amount)
            } if winner else None,
            'message': 'Draw processed successfully'
        })
        
    except Exception as e:
        logger.error(f"Draw processing error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
    
def faqs(request):
    return render(request, 'faqs.html')


def id_generator():
    # ✅ Replace with your actual reference generator
    import uuid
    return str(uuid.uuid4())[:10]

@login_required(login_url="login")
@require_http_methods(["POST"])
def buy_astra(request):
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