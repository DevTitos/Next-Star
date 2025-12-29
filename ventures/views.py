from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404
from core.models import UserWallet
from hiero.ft import transfer_tokens
from hiero.mirror_node import get_balance
from hiero.nft import mint_nft, associate_nft
from hiero.hcs import submit_message
from ventures.models import Venture, VentureTicket, VentureOwnership
from datetime import timedelta, timezone, datetime
import json
import logging
from django.views.decorators.http import require_POST
from django.core.cache import cache
from hiero.nft import create_nft
from hiero_sdk_python import (
    AccountId,
)

logger = logging.getLogger(__name__)

from django.core.paginator import Paginator
from django.db.models import Sum, Count

@login_required
def dashboard(request):
    """Updated dashboard view without games"""
    from core.models import UserWallet
    from ventures.models import Venture, VentureTicket, VentureOwnership
    
    # Get user's wallet data
    try:
        wallet = UserWallet.objects.get(user=request.user)
        star_balance = get_balance(wallet.recipient_id)
    except:
        star_balance = 0
    
    # Get user's ventures and tickets
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
    active_ventures = Venture.objects.filter(
        status='funding',
        funding_end__gte=timezone.now(),
        funding_start__lte=timezone.now()
    ).order_by('-created_at')[:3]
    
    context = {
        'user_stats': {
            'total_invested': total_invested,
            'ventures_count': user_ventures.count(),
            'equity_total': equity_total,
            'portfolio_value': total_invested * 1.2,  # Simplified calculation
        },
        'wallet_data': {
            'star_tokens': star_balance,
            'tickets': owned_tickets.count(),
        },
        'user_ventures': user_ventures[:3],
        'owned_tickets': owned_tickets,
        'active_ventures': active_ventures,
        'today': timezone.now(),
    }
    return render(request, 'dashboard/dashboard.html', context)

@login_required
def ventures_list(request):
    """List all ventures with filters"""
    from ventures.models import Venture, VentureOwnership
    
    ventures = Venture.objects.filter(status__in=['funding', 'active']).order_by('-created_at')
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        ventures = ventures.filter(status=status_filter)
    
    search_query = request.GET.get('search')
    if search_query:
        ventures = ventures.filter(name__icontains=search_query)
    
    # Pagination
    paginator = Paginator(ventures, 12)  # 12 ventures per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get user's investments for quick reference
    user_investments = VentureOwnership.objects.filter(owner=request.user)
    invested_venture_ids = user_investments.values_list('venture_id', flat=True)
    
    context = {
        'ventures': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'user_investments': list(invested_venture_ids),
        'today': timezone.now(),
    }
    return render(request, 'ventures/ventures_list.html', context)

@login_required
def venture_detail(request, slug):
    """Detailed venture view with investor leaderboard"""
    from ventures.models import Venture, VentureTicket, VentureOwnership
    
    venture = get_object_or_404(Venture, slug=slug)
    
    # Check if user has already purchased a ticket
    has_ticket = VentureTicket.objects.filter(
        venture=venture,
        buyer=request.user,
        status='purchased'
    ).exists()
    
    user_ticket = None
    if has_ticket:
        user_ticket = VentureTicket.objects.get(
            venture=venture,
            buyer=request.user,
            status='purchased'
        )
    
    # Get investor leaderboard
    ownerships = VentureOwnership.objects.filter(venture=venture).select_related('owner')
    
    # Process investor data for display
    investors_data = []
    for ownership in ownerships:
        # Count tickets for this user
        ticket_count = VentureTicket.objects.filter(
            venture=venture,
            buyer=ownership.owner,
            status='purchased'
        ).count()
        
        investors_data.append({
            'user': ownership.owner,
            'tickets': ticket_count,
            'investment': ownership.investment_amount,
            'equity': ownership.equity_percentage,
            'joined_date': ownership.acquired_at,
        })
    
    # Sort by investment amount (descending)
    investors_data.sort(key=lambda x: x['investment'], reverse=True)
    
    # Get timeline data
    timeline_data = {
        'first_investment_date': None,
        'first_investment_amount': None,
        'funding_complete_date': None,
    }
    
    if ownerships.exists():
        first_investment = ownerships.order_by('acquired_at').first()
        timeline_data['first_investment_date'] = first_investment.acquired_at
        timeline_data['first_investment_amount'] = first_investment.investment_amount
    
    if venture.status == 'funded':
        last_investment = ownerships.order_by('-acquired_at').first()
        timeline_data['funding_complete_date'] = last_investment.acquired_at
    
    context = {
        'venture': venture,
        'has_ticket': has_ticket,
        'user_ticket': user_ticket,
        'investors': investors_data,
        'timeline_data': timeline_data,
        'today': timezone.now(),
    }
    return render(request, 'ventures/venture_detail.html', context)

# API Views for AJAX calls
@login_required
@require_http_methods(["GET"])
def api_check_investment(request, slug):
    """API endpoint to check if user can invest in venture"""
    from ventures.models import Venture, VentureTicket
    
    venture = get_object_or_404(Venture, slug=slug)
    
    # Check investment conditions
    can_invest, message = venture.can_user_buy_ticket(request.user)
    
    if not can_invest:
        return JsonResponse({
            'can_invest': False,
            'message': message
        })
    
    # Check user balance
    from core.models import UserWallet
    try:
        wallet = UserWallet.objects.get(user=request.user)
        star_balance = get_balance(wallet.recipient_id)
    except:
        star_balance = 0
    
    if star_balance < float(venture.ticket_price):
        return JsonResponse({
            'can_invest': False,
            'message': f"Insufficient STAR tokens. Need {venture.ticket_price}, have {star_balance}"
        })
    
    # Get next ticket number
    last_ticket = VentureTicket.objects.filter(venture=venture).order_by('-ticket_number').first()
    next_ticket_number = (last_ticket.ticket_number + 1) if last_ticket else 1
    
    return JsonResponse({
        'can_invest': True,
        'venture_name': venture.name,
        'ticket_price': float(venture.ticket_price),
        'equity_percentage': float(venture.equity_per_ticket),
        'next_ticket_number': next_ticket_number,
        'equity_remaining': 100 - (venture.tickets_sold * venture.equity_per_ticket),
    })

@login_required
@require_http_methods(["GET"])
def api_get_investors(request, slug):
    """API endpoint to get investor list"""
    from ventures.models import Venture, VentureOwnership
    
    venture = get_object_or_404(Venture, slug=slug)
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 20))
    
    ownerships = VentureOwnership.objects.filter(
        venture=venture
    ).select_related('owner').order_by('-investment_amount')
    
    # Pagination
    paginator = Paginator(ownerships, limit)
    page_obj = paginator.get_page(page)
    
    investors_data = []
    for ownership in page_obj:
        investors_data.append({
            'id': ownership.owner.id,
            'name': ownership.owner.get_full_name(),
            'username': ownership.owner.username,
            'investment': float(ownership.investment_amount),
            'equity': float(ownership.equity_percentage),
            'joined_date': ownership.acquired_at.isoformat(),
            'is_current_user': (ownership.owner == request.user),
        })
    
    return JsonResponse({
        'investors': investors_data,
        'total': paginator.count,
        'pages': paginator.num_pages,
        'current_page': page,
    })

@login_required
@require_http_methods(["POST"])
def api_purchase_ticket(request, slug):
    """API endpoint to purchase ticket (calls existing buy_venture_ticket)"""
    # This will redirect to your existing buy_venture_ticket function
    # We need to adapt it for web vs JSON response
    venture = get_object_or_404(Venture, slug=slug)
    
    # Call your existing function
    response = buy_venture_ticket(request, venture.id)
    
    # Ensure it returns proper JSON
    if hasattr(response, 'content'):
        return response
    
    # Fallback response
    return JsonResponse({
        'success': False,
        'error': 'Purchase failed'
    })

@login_required
@require_http_methods(["GET"])
def api_wallet_balance(request):
    """API endpoint to get user's STAR balance"""
    from core.models import UserWallet
    
    try:
        wallet = UserWallet.objects.get(user=request.user)
        star_balance = get_balance(wallet.recipient_id)
        
        return JsonResponse({
            'success': True,
            'balance': star_balance,
            'address': wallet.recipient_id,
        })
    except Exception as e:
        logger.error(f"Balance check error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'balance': 0,
        })
@login_required
@require_http_methods(["POST"])
def buy_venture_ticket(request, venture_id):
    """Buy NFT ticket for a venture - ONE TICKET PER USER PER VENTURE"""
    try:
        data = json.loads(request.body)
        venture = get_object_or_404(Venture, id=venture_id)
        user_wallet = get_object_or_404(UserWallet, user=request.user)
        
        # Check if user can buy ticket
        can_buy, message = venture.can_user_buy_ticket(request.user)
        if not can_buy:
            return JsonResponse({
                'success': False,
                'error': message
            })
        
        # Check user STAR balance
        try:
            star_balance = get_balance(user_wallet.recipient_id)
        except Exception as e:
            logger.error(f"Balance check error: {e}")
            star_balance = 0
        
        # Check if user has enough STAR tokens
        ticket_price = float(venture.ticket_price)
        if star_balance < ticket_price:
            return JsonResponse({
                'success': False,
                'error': f"Insufficient STAR tokens. Need {ticket_price} STAR, but have {star_balance} STAR"
            })
        
        with transaction.atomic():
            # Generate NFT metadata
            # First create ticket instance to get ticket number
            ticket = VentureTicket.objects.create(
                venture=venture,
                buyer=request.user,
                purchase_price=venture.ticket_price,
                status='processing'
            )
            
            ticket_metadata = ticket.generate_nft_metadata()
            
            # Mint NFT on Hedera
            if venture.nft_contract_address:
                # Mint NFT using existing contract
                nft_result = mint_nft(
                    nft_token_id=venture.nft_contract_address,
                    metadata=ticket_metadata
                )
            else:
                # You'll need to create NFT token first for the venture
                # For now, simulate or create new NFT token
                return JsonResponse({
                    'success': False,
                    'error': 'Venture NFT contract not configured'
                })
            
            if nft_result['status'] == 'success':
                # Associate NFT with user's wallet
                associate_result = associate_nft(
                    account_id=user_wallet.recipient_id,
                    token_id=venture.nft_contract_address,
                    account_private_key=user_wallet.decrypt_key(),
                    nft_id=nft_result.get('serial_number', nft_result.get('message'))
                )
                
                if associate_result['status'] == 'success':
                    # Transfer STAR tokens from user to venture pool
                    transfer_result = transfer_tokens(
                        sender_id=user_wallet.recipient_id,
                        receiver_id=venture.founder.wallet.recipient_id,  # Assuming founder has wallet
                        amount=ticket_price,
                        sender_private_key=user_wallet.decrypt_key(),
                        token_id="0.0.XXXXXX"  # Replace with actual STAR token ID
                    )
                    
                    if transfer_result['status'] == 'failed':
                        logger.error(f"Token transfer failed: {transfer_result.get('message')}")
                        # Update ticket status
                        ticket.status = 'failed'
                        ticket.status_message = f"Payment failed: {transfer_result.get('message')}"
                        ticket.save()
                        
                        return JsonResponse({
                            'success': False,
                            'error': 'Payment processing failed'
                        })
                    
                    # Record HCS message for immutability
                    hcs_message = f"Venture Ticket Purchase - Venture: {venture.id}, Ticket: {ticket.id}, Buyer: {request.user.id}, Price: {ticket_price}"
                    submit_message(message=hcs_message)
                    
                    # Update ticket with success details
                    ticket.status = 'purchased'
                    ticket.purchased_at = timezone.now()
                    ticket.nft_token_id = nft_result.get('serial_number', nft_result.get('message'))
                    ticket.nft_metadata = json.loads(ticket_metadata)
                    ticket.purchase_hash = transfer_result.get('transaction_id', '')
                    ticket.save()
                    
                    # Update venture stats
                    venture.tickets_sold += 1
                    venture.funding_raised += ticket.purchase_price
                    
                    # Check if venture is fully funded
                    if venture.tickets_sold >= venture.max_tickets:
                        venture.status = 'funded'
                    
                    venture.save()
                    
                    # Create ownership record
                    VentureOwnership.objects.create(
                        venture=venture,
                        owner=request.user,
                        ticket=ticket,
                        equity_percentage=venture.equity_per_ticket,
                        investment_amount=ticket.purchase_price
                    )
                    
                    return JsonResponse({
                        'success': True,
                        'message': f'Successfully purchased ticket #{ticket.ticket_number} for {venture.name}',
                        'ticket_id': str(ticket.id),
                        'ticket_number': ticket.ticket_number,
                        'equity_percentage': float(venture.equity_per_ticket),
                        'nft_token_id': ticket.nft_token_id,
                        'remaining_tickets': venture.max_tickets - venture.tickets_sold
                    })
                else:
                    # NFT association failed
                    ticket.status = 'failed'
                    ticket.status_message = f"NFT association failed: {associate_result.get('message')}"
                    ticket.save()
                    
                    return JsonResponse({
                        'success': False,
                        'error': 'NFT association failed'
                    })
            else:
                # NFT minting failed
                ticket.status = 'failed'
                ticket.status_message = f"NFT minting failed: {nft_result.get('message')}"
                ticket.save()
                
                return JsonResponse({
                    'success': False,
                    'error': 'NFT minting failed'
                })
                
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        })
    except Exception as e:
        logger.error(f"Venture ticket purchase error: {e}")
        return JsonResponse({
            'success': False,
            'error': f'Purchase failed: {str(e)}'
        })
    


@login_required
@require_http_methods(["POST"])
def create_venture(request):
    """Admin view to create new ventures with NFT integration"""
    if not request.user.is_staff:
        messages.warning(request, "Admin access required!")
        return redirect(request.META.get('HTTP_REFERER', '/'))
    
    try:
        # Extract form data
        name = request.POST.get('name', '').strip()
        slug = request.POST.get('slug', '').strip()
        description = request.POST.get('description', '').strip()
        problem_statement = request.POST.get('problem_statement', '').strip()
        solution = request.POST.get('solution', '').strip()
        
        # Funding details
        funding_goal = request.POST.get('funding_goal', '0')
        ticket_price = request.POST.get('ticket_price', '0')
        max_tickets = request.POST.get('max_tickets', '100')
        
        # Timeline
        funding_start = request.POST.get('funding_start', '')
        funding_end = request.POST.get('funding_end', '')
        
        # Validate required fields
        required_fields = {
            'name': name,
            'slug': slug,
            'description': description,
            'problem_statement': problem_statement,
            'solution': solution,
            'funding_goal': funding_goal,
            'ticket_price': ticket_price,
            'funding_start': funding_start,
            'funding_end': funding_end
        }
        
        missing_fields = [field for field, value in required_fields.items() if not value]
        if missing_fields:
            messages.warning(request, f"Missing required fields: {', '.join(missing_fields)}")
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        # Convert numeric fields
        try:
            funding_goal = float(funding_goal)
            ticket_price = float(ticket_price)
            max_tickets = int(max_tickets)
        except ValueError:
            messages.warning(request, "Invalid numeric values!")
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        # Convert datetime strings
        try:
            funding_start_dt = datetime.fromisoformat(funding_start.replace('Z', '+00:00'))
            funding_end_dt = datetime.fromisoformat(funding_end.replace('Z', '+00:00'))
        except ValueError:
            messages.warning(request, "Invalid date format!")
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        # Create NFT for the venture
        nft_symbol = slug[:5].upper() + "VENT"
        nft_result = create_nft(
            title=f"{name} Venture",
            symbol=nft_symbol,
            metadata={
                "name": name,
                "description": description[:100] + "..." if len(description) > 100 else description,
                "type": "venture_collection",
                "properties": {
                    "category": "business_venture",
                    "funding_goal": str(funding_goal),
                    "ticket_price": str(ticket_price)
                }
            }
        )
        
        if nft_result['status'] == 'failed':
            messages.warning(request, f"Venture creation failed: {nft_result.get('message', 'NFT creation was not successful')}")
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        venture = Venture.objects.create(
            name=name,
            slug=slug,
            description=description,
            problem_statement=problem_statement,
            solution=solution,
            founder=request.user,
            funding_goal=funding_goal,
            ticket_price=ticket_price,
            max_tickets=max_tickets,
            funding_start=funding_start_dt,
            funding_end=funding_end_dt,
            nft_contract_address=nft_result['token_id'],
            nft_base_metadata={
                "name": name,
                "description": description,
                "image": f"https://api.dicebear.com/7.x/identicon/svg?seed={slug}",
                "attributes": [
                    {"trait_type": "Category", "value": "Venture"},
                    {"trait_type": "Funding Goal", "value": str(funding_goal)},
                    {"trait_type": "Ticket Price", "value": str(ticket_price)},
                    {"trait_type": "Max Tickets", "value": str(max_tickets)}
                ]
            },
            status='funding'
        )
        
        # Create initial notification
        from core.models import Alert  # Assuming you have an Alert model
        Alert.objects.create(
            title="New Venture Launched",
            content=f"{name} is now accepting investments! Goal: ${funding_goal:,.0f}, Tickets: ${ticket_price:,.0f} each",
            icon='rocket'
        )
        
        # Clear relevant caches
        cache.delete_many(["active_ventures", "featured_ventures", "landing_page_data"])
        
        messages.success(request, f"Venture '{name}' created successfully with NFT contract!")
        return redirect('venture_detail', slug=venture.slug)
        
    except Exception as e:
        logger.error(f"Venture creation error: {e}")
        messages.warning(request, f"An error occurred: {str(e)}")
        return redirect(request.META.get('HTTP_REFERER', '/'))
    

@login_required
def create_venture_page(request):
    """Page for creating new ventures (admin only)"""
    if not request.user.is_staff:
        messages.warning(request, "Admin access required!")
        return redirect('dashboard')
    
    return render(request, 'ventures/create_venture.html')