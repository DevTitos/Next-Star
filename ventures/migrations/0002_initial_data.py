from django.db import migrations
from django.utils import timezone
from datetime import timedelta

def create_sample_ventures(apps, schema_editor):
    Venture = apps.get_model('ventures', 'Venture')
    User = apps.get_model('auth', 'User')
    
    # Get admin user
    try:
        admin = User.objects.get(username='admin')
    except:
        admin = User.objects.create_user(
            username='venture_admin',
            email='admin@nextstar.africa',
            password='admin123'
        )
    
    # Create sample ventures
    ventures = [
        {
            'name': 'AgriTech Africa',
            'slug': 'agritech-africa',
            'description': 'Modernizing African agriculture with technology.',
            'founder': admin,
            'funding_goal': 50000,
            'ticket_price': 500,  # $500 per ticket
            'max_tickets': 100,   # 100 tickets available
            'funding_start': timezone.now(),
            'funding_end': timezone.now() + timedelta(days=30),
            'status': 'funding',
        },
        {
            'name': 'Solar Energy Solutions',
            'slug': 'solar-energy-solutions',
            'description': 'Affordable solar power for rural communities.',
            'founder': admin,
            'funding_goal': 100000,
            'ticket_price': 1000,  # $1000 per ticket
            'max_tickets': 100,    # 100 tickets available
            'funding_start': timezone.now(),
            'funding_end': timezone.now() + timedelta(days=45),
            'status': 'funding',
        },
    ]
    
    for data in ventures:
        Venture.objects.get_or_create(
            slug=data['slug'],
            defaults=data
        )

class Migration(migrations.Migration):
    dependencies = [
        ('ventures', '0001_initial'),
    ]
    
    operations = [
        migrations.RunPython(create_sample_ventures),
    ]