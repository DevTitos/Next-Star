# ventures/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
import uuid
import json

class Venture(models.Model):
    """Minimal Venture Model with NFT Integration"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('funding', 'Funding'),
        ('funded', 'Funded'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    
    # Basic Info
    description = models.TextField()
    founder = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ventures')
    
    # Funding Details
    funding_goal = models.DecimalField(max_digits=12, decimal_places=2)  # Total needed
    funding_raised = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Ticket System
    ticket_price = models.DecimalField(max_digits=10, decimal_places=2)  # Price per ticket
    max_tickets = models.IntegerField(default=100)  # Max tickets available
    tickets_sold = models.IntegerField(default=0)  # Tickets sold so far
    
    # NFT Configuration
    nft_contract_address = models.CharField(max_length=100, blank=True)
    nft_base_metadata = models.JSONField(default=dict, blank=True)
    
    # Timeline
    created_at = models.DateTimeField(auto_now_add=True)
    funding_start = models.DateTimeField()
    funding_end = models.DateTimeField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def is_funding_active(self):
        """Check if funding is currently active"""
        now = timezone.now()
        return (self.status == 'funding' and 
                self.funding_start <= now <= self.funding_end)
    
    @property
    def funding_percentage(self):
        """Calculate funding progress"""
        if self.funding_goal > 0:
            return (self.funding_raised / self.funding_goal) * 100
        return 0
    
    @property
    def tickets_available(self):
        """Check if tickets are still available"""
        return self.tickets_sold < self.max_tickets
    
    @property
    def equity_per_ticket(self):
        """Calculate equity percentage per ticket"""
        if self.max_tickets > 0:
            return 100 / self.max_tickets  # Equal distribution
        return 0
    
    def can_user_buy_ticket(self, user):
        """Check if user can buy a ticket for this venture"""
        if not self.is_funding_active:
            return False, "Funding is not active"
        
        if not self.tickets_available:
            return False, "No tickets available"
        
        # Check if user already bought a ticket
        if VentureTicket.objects.filter(venture=self, buyer=user, status='purchased').exists():
            return False, "You already own a ticket for this venture"
        
        return True, "Can purchase"

class VentureTicket(models.Model):
    """NFT Ticket for Venture - ONE TICKET PER USER PER VENTURE"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('purchased', 'Purchased'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    venture = models.ForeignKey(Venture, on_delete=models.CASCADE, related_name='tickets')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='venture_tickets')
    
    # Ticket Details
    ticket_number = models.IntegerField()  # Sequential ticket number (1, 2, 3...)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # NFT Details
    nft_token_id = models.CharField(max_length=100, blank=True)
    nft_metadata = models.JSONField(default=dict, blank=True)
    
    # Purchase Info
    purchase_hash = models.CharField(max_length=200, blank=True)
    purchased_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['ticket_number']
        unique_together = ['venture', 'buyer']  # One ticket per user per venture
        unique_together = ['venture', 'ticket_number']  # Unique ticket numbers
    
    def __str__(self):
        return f"Ticket #{self.ticket_number} - {self.venture.name} - {self.buyer.username}"
    
    def save(self, *args, **kwargs):
        """Auto-assign ticket number if not set"""
        if not self.ticket_number:
            # Get next available ticket number for this venture
            last_ticket = VentureTicket.objects.filter(venture=self.venture).order_by('-ticket_number').first()
            self.ticket_number = (last_ticket.ticket_number + 1) if last_ticket else 1
        
        super().save(*args, **kwargs)
    
    @property
    def equity_percentage(self):
        """Calculate equity percentage for this ticket"""
        if self.venture.max_tickets > 0:
            return 100 / self.venture.max_tickets
        return 0
    
    def generate_nft_metadata(self):
        """Generate NFT metadata for the ticket"""
        metadata = {
            "name": f"{self.venture.name} - Ticket #{self.ticket_number}",
            "description": f"Venture ownership ticket for {self.venture.name}",
            "image": f"https://api.dicebear.com/7.x/identicon/svg?seed={self.id}",
            "attributes": [
                {
                    "trait_type": "Venture",
                    "value": self.venture.name
                },
                {
                    "trait_type": "Ticket Number",
                    "value": str(self.ticket_number)
                },
                {
                    "trait_type": "Equity",
                    "value": f"{self.equity_percentage:.2f}%"
                },
                {
                    "trait_type": "Purchase Price",
                    "value": str(self.purchase_price)
                }
            ],
            "properties": {
                "venture_id": str(self.venture.id),
                "ticket_id": str(self.id),
                "buyer": self.buyer.username,
                "purchase_date": self.purchased_at.isoformat() if self.purchased_at else None,
                "blockchain": "hedera",
                "type": "venture_ownership_ticket"
            }
        }
        return json.dumps(metadata, indent=2)

class VentureOwnership(models.Model):
    """Minimal ownership tracking"""
    venture = models.ForeignKey(Venture, on_delete=models.CASCADE, related_name='ownerships')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='venture_ownerships')
    ticket = models.OneToOneField(VentureTicket, on_delete=models.CASCADE, related_name='ownership')
    
    equity_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    investment_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    acquired_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['venture', 'owner']
    
    def __str__(self):
        return f"{self.owner.username} owns {self.equity_percentage}% of {self.venture.name}"