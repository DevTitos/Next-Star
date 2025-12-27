from django.db import migrations, models
import uuid
from django.utils import timezone
from datetime import timedelta
import json

def create_initial_game(apps, schema_editor):
    MatrixGame = apps.get_model('matrix', 'MatrixGame')
    
    # Create sample matrix data
    matrix_data = {}
    business_categories = ['Finance', 'Marketing', 'Operations', 'Strategy', 'Leadership']
    challenge_icons = ['💼', '📈', '💡', '🚀', '🏆', '⚡', '🎯', '🤔', '⭐', '💰']
    
    for layer in range(3):
        matrix_data[str(layer)] = {}
        for row in range(5):
            matrix_data[str(layer)][str(row)] = {}
            for col in range(5):
                category = business_categories[(layer + row + col) % len(business_categories)]
                icon = challenge_icons[(layer * row * col) % len(challenge_icons)]
                
                matrix_data[str(layer)][str(row)][str(col)] = {
                    'id': f"{layer}-{row}-{col}",
                    'value': (layer * 100) + (row * 10) + col + 1,
                    'category': category,
                    'type': 'challenge',
                    'icon': icon,
                    'visited': False,
                    'description': f"{category} Challenge",
                    'hint': f"Think about {category.lower()} strategy",
                    'position': {'layer': layer, 'row': row, 'col': col}
                }
    
    # Create solution path
    solution_path = [
        {'layer': 0, 'row': 0, 'col': 0, 'step': 1},
        {'layer': 0, 'row': 1, 'col': 1, 'step': 2},
        {'layer': 0, 'row': 2, 'col': 2, 'step': 3},
        {'layer': 1, 'row': 2, 'col': 2, 'step': 4},
        {'layer': 1, 'row': 3, 'col': 3, 'step': 5},
        {'layer': 2, 'row': 3, 'col': 3, 'step': 6},
        {'layer': 2, 'row': 4, 'col': 4, 'step': 7},
    ]
    
    # Create the game
    game = MatrixGame.objects.create(
        id=uuid.uuid4(),
        name="CEO Matrix Challenge",
        difficulty="genius",
        rows=5,
        cols=5,
        layers=3,
        categories=json.dumps(business_categories),
        is_active=True,
        expires_at=timezone.now() + timedelta(days=7),
        max_moves=100,
        matrix_data=matrix_data,
        solution_path=solution_path,
        total_players=0
    )
    
    print(f"✅ Created CEO Matrix Game: {game.name}")
    print(f"   Game ID: {game.id}")
    print(f"   Expires: {game.expires_at}")
    print(f"   Solution Path Length: {len(solution_path)} steps")

class Migration(migrations.Migration):
    dependencies = [
        # Replace with your actual dependency
        ('matrix', '0001_initial'),
    ]
    
    operations = [
        migrations.RunPython(create_initial_game),
    ]