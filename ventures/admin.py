from django.contrib import admin
from django.utils.html import format_html
from .models import Venture, VentureTicket, VentureOwnership

@admin.register(Venture)
class VentureAdmin(admin.ModelAdmin):
    list_display = ['name', 'founder', 'funding_goal', 'ticket_price', 
                    'tickets_sold', 'max_tickets', 'status', 'funding_progress']
    list_filter = ['status', 'funding_start', 'funding_end']
    search_fields = ['name', 'description', 'founder__username']
    
    def funding_progress(self, obj):
        return f"{obj.funding_percentage:.1f}%"
    funding_progress.short_description = 'Funding'

@admin.register(VentureTicket)
class VentureTicketAdmin(admin.ModelAdmin):
    list_display = ['venture', 'buyer', 'ticket_number', 'purchase_price', 
                    'status', 'purchased_at']
    list_filter = ['status', 'purchased_at']
    search_fields = ['venture__name', 'buyer__username', 'ticket_number']

@admin.register(VentureOwnership)
class VentureOwnershipAdmin(admin.ModelAdmin):
    list_display = ['venture', 'owner', 'equity_percentage', 'investment_amount', 'acquired_at']
    list_filter = ['venture', 'owner']