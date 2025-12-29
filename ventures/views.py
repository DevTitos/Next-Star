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