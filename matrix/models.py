from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone
import random

class MatrixGame(models.Model):
    """CEO Matrix Game Instance"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, default="CEO Matrix Challenge")
    difficulty = models.CharField(max_length=50, choices=[
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
        ('genius', 'Genius Only')
    ], default='medium')
    
    # Matrix dimensions
    rows = models.IntegerField(default=5)
    cols = models.IntegerField(default=5)
    layers = models.IntegerField(default=3)
    
    # Business/Entrepreneurship categories
    categories = models.JSONField(default=list)  # e.g., ['Finance', 'Marketing', 'Operations', 'Strategy', 'Leadership']
    
    # Game state
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    # Game data
    matrix_data = models.JSONField(default=dict)  # Stores the 3D matrix cells
    solution_path = models.JSONField(default=list)  # The correct path through matrix
    max_moves = models.IntegerField(default=100)  # Maximum moves allowed
    
    # Statistics
    total_players = models.IntegerField(default=0)
    solved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='solved_games')
    solved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.difficulty})"
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def generate_matrix(self):
        """Generate a new 3D matrix with business challenges"""
        import random
        
        # Business challenges categories
        business_categories = [
            'Market Analysis', 'Funding Strategy', 'Team Building', 
            'Product Development', 'Customer Acquisition', 'Scaling Operations',
            'Risk Management', 'Innovation Strategy', 'Competitive Advantage',
            'Revenue Model', 'Exit Strategy', 'Stakeholder Management'
        ]
        
        # Challenge types
        challenge_types = {
            'question': ['?', '❓', '🤔'],
            'problem': ['💼', '⚡', '🔥'],
            'solution': ['💡', '🚀', '⭐'],
            'decision': ['⚖️', '🎯', '📍'],
            'opportunity': ['💰', '📈', '🏆']
        }
        
        matrix = {}
        for layer in range(self.layers):
            matrix[layer] = {}
            for row in range(self.rows):
                matrix[layer][row] = {}
                for col in range(self.cols):
                    category = random.choice(business_categories)
                    challenge_type = random.choice(list(challenge_types.keys()))
                    icon = random.choice(challenge_types[challenge_type])
                    
                    # Create cell data
                    matrix[layer][row][col] = {
                        'id': f"{layer}-{row}-{col}",
                        'value': random.randint(1, 9),
                        'category': category,
                        'type': challenge_type,
                        'icon': icon,
                        'visited': False,
                        'description': f"{category} {challenge_type.title()}",
                        'hint': self.generate_hint(category, challenge_type),
                        'position': {'layer': layer, 'row': row, 'col': col}
                    }
        
        self.matrix_data = matrix
        self.generate_solution_path()
        return matrix
    
    def generate_solution_path(self):
        """Generate a solution path through the matrix"""
        import random
        
        # Start at a random position
        start_layer = random.randint(0, self.layers - 1)
        start_row = random.randint(0, self.rows - 1)
        start_col = random.randint(0, self.cols - 1)
        
        path = []
        visited = set()
        current = (start_layer, start_row, start_col)
        
        # Generate path of 8-12 steps
        path_length = random.randint(8, 12)
        
        for step in range(path_length):
            path.append({
                'layer': current[0],
                'row': current[1],
                'col': current[2],
                'step': step + 1
            })
            visited.add(current)
            
            # Find next valid move
            possible_moves = []
            for dl in [-1, 0, 1]:
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        # Skip staying in same place
                        if dl == 0 and dr == 0 and dc == 0:
                            continue
                        
                        new_layer = current[0] + dl
                        new_row = current[1] + dr
                        new_col = current[2] + dc
                        
                        # Check bounds
                        if (0 <= new_layer < self.layers and 
                            0 <= new_row < self.rows and 
                            0 <= new_col < self.cols):
                            
                            new_pos = (new_layer, new_row, new_col)
                            if new_pos not in visited:
                                possible_moves.append(new_pos)
            
            if possible_moves:
                current = random.choice(possible_moves)
            else:
                break
        
        self.solution_path = path
        return path
    
    def generate_hint(self, category, challenge_type):
        """Generate a hint based on category and challenge type"""
        hints = {
            'Market Analysis': [
                "Study customer demographics",
                "Analyze competitor strategies",
                "Identify market trends",
                "Evaluate market size",
                "Understand customer pain points"
            ],
            'Funding Strategy': [
                "Consider VC funding",
                "Explore bootstrapping options",
                "Look into angel investors",
                "Prepare pitch deck",
                "Calculate burn rate"
            ],
            'Team Building': [
                "Define roles clearly",
                "Hire for cultural fit",
                "Establish clear communication",
                "Set team objectives",
                "Foster collaboration"
            ],
            'Product Development': [
                "Start with MVP",
                "Gather user feedback",
                "Prioritize features",
                "Test thoroughly",
                "Iterate quickly"
            ]
        }
        
        default_hints = [
            "Think strategically",
            "Consider long-term impact",
            "Balance risk and reward",
            "Innovate but validate",
            "Focus on execution"
        ]
        
        return random.choice(hints.get(category, default_hints))
    
    def check_solution(self, player_path):
        """Check if player's path matches solution"""
        return player_path == self.solution_path

class PlayerGameSession(models.Model):
    """Tracks player's progress in a matrix game"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name='matrix_sessions')
    game = models.ForeignKey(MatrixGame, on_delete=models.CASCADE, related_name='sessions')
    
    # Game state
    current_position = models.JSONField(default=dict)  # {layer: 0, row: 0, col: 0}
    moves_made = models.IntegerField(default=0)
    cells_visited = models.JSONField(default=list)  # List of visited cell IDs
    player_path = models.JSONField(default=list)  # Player's attempted solution path
    
    # Session data
    started_at = models.DateTimeField(auto_now_add=True)
    last_move_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    is_winner = models.BooleanField(default=False)
    
    # Score and metrics
    score = models.IntegerField(default=0)
    efficiency = models.FloatField(default=0.0)  # Moves vs optimal path
    time_taken = models.DurationField(null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at']
        unique_together = ['player', 'game']
    
    def __str__(self):
        return f"{self.player.username} - {self.game.name}"
    
    def move_to(self, layer, row, col):
        """Move player to a new position"""
        # Check if move is valid (adjacent position)
        current = self.current_position
        if not self.is_valid_move(current, {'layer': layer, 'row': row, 'col': col}):
            return False, "Invalid move! You can only move to adjacent cells."
        
        # Update position
        self.current_position = {'layer': layer, 'row': row, 'col': col}
        
        # Track visited cells
        cell_id = f"{layer}-{row}-{col}"
        if cell_id not in self.cells_visited:
            self.cells_visited.append(cell_id)
        
        # Add to player path
        self.player_path.append({
            'layer': layer,
            'row': row,
            'col': col,
            'move': self.moves_made + 1,
            'timestamp': timezone.now().isoformat()
        })
        
        self.moves_made += 1
        self.save()
        
        # Check if reached max moves
        if self.moves_made >= self.game.max_moves:
            self.complete_session()
            return False, "Maximum moves reached! Game over."
        
        # Get cell info
        cell_data = self.get_current_cell_data()
        
        return True, {
            'message': f"Moved to Layer {layer+1}, Row {row+1}, Col {col+1}",
            'cell': cell_data,
            'moves_left': self.game.max_moves - self.moves_made,
            'score': self.calculate_score()
        }
    
    def is_valid_move(self, from_pos, to_pos):
        """Check if move from one position to another is valid"""
        # Can move to any adjacent cell (including diagonals in 3D space)
        dl = abs(from_pos['layer'] - to_pos['layer'])
        dr = abs(from_pos['row'] - to_pos['row'])
        dc = abs(from_pos['col'] - to_pos['col'])
        
        # Allow moves to adjacent cells (max 1 step in any dimension)
        return max(dl, dr, dc) <= 1
    
    def get_current_cell_data(self):
        """Get data for current cell"""
        pos = self.current_position
        try:
            cell = self.game.matrix_data[str(pos['layer'])][str(pos['row'])][str(pos['col'])]
            return cell
        except:
            return None
    
    def calculate_score(self):
        """Calculate current score"""
        base_score = len(self.cells_visited) * 10
        efficiency_bonus = max(0, (self.game.max_moves - self.moves_made) * 5)
        unique_cells_bonus = len(set(self.cells_visited)) * 3
        
        self.score = base_score + efficiency_bonus + unique_cells_bonus
        self.save()
        return self.score
    
    def complete_session(self):
        """Mark session as completed"""
        self.is_completed = True
        self.completed_at = timezone.now()
        
        # Calculate time taken
        if self.started_at:
            self.time_taken = self.completed_at - self.started_at
        
        # Check if winner
        if self.game.check_solution(self.player_path):
            self.is_winner = True
            self.score += 1000  # Big bonus for solving
            
            # Mark game as solved
            if not self.game.solved_by:
                self.game.solved_by = self.player
                self.game.solved_at = timezone.now()
                self.game.is_active = False
                self.game.save()
        
        self.save()
        return self.is_winner
    
    def get_game_state(self):
        """Return complete game state for frontend"""
        return {
            'session_id': str(self.id),
            'game_id': str(self.game.id),
            'player': self.player.username,
            'current_position': self.current_position,
            'moves_made': self.moves_made,
            'moves_left': self.game.max_moves - self.moves_made,
            'cells_visited': self.cells_visited,
            'score': self.score,
            'is_completed': self.is_completed,
            'is_winner': self.is_winner,
            'matrix_dimensions': {
                'layers': self.game.layers,
                'rows': self.game.rows,
                'cols': self.game.cols
            }
        }

class MatrixLeaderboard(models.Model):
    """Leaderboard for CEO Matrix game"""
    game = models.ForeignKey(MatrixGame, on_delete=models.CASCADE, related_name='leaderboard')
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name='matrix_scores')
    session = models.OneToOneField(PlayerGameSession, on_delete=models.CASCADE, related_name='leaderboard_entry')
    
    score = models.IntegerField(default=0)
    moves = models.IntegerField(default=0)
    time_taken = models.DurationField()
    solved_at = models.DateTimeField()
    
    rank = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-score', 'time_taken', 'moves']
    
    def __str__(self):
        return f"{self.player.username}: {self.score} points"
    
    def update_rank(self):
        """Update rank based on score"""
        entries = MatrixLeaderboard.objects.filter(game=self.game).order_by('-score', 'time_taken', 'moves')
        for i, entry in enumerate(entries, 1):
            entry.rank = i
            entry.save()