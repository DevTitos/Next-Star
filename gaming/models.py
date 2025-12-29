from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
import json
from django.core.exceptions import ValidationError
import random
import string
from datetime import timedelta
from django.utils import timezone

class VentureGame(models.Model):
    """
    Links a Venture to a specific game type and settings
    """
    VENTURE_GAME_TYPES = [
        ('sudoku', 'Sudoku'),
        ('kakuro', 'Kakuro'),
        ('cryptogram', 'Cryptogram'),
    ]
    
    DIFFICULTY_LEVELS = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
        ('expert', 'Expert'),
    ]
    
    venture = models.ForeignKey('ventures.Venture', on_delete=models.CASCADE, related_name='games')
    game_type = models.CharField(max_length=20, choices=VENTURE_GAME_TYPES)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_LEVELS, default='medium')
    
    # Game-specific configurations
    grid_size = models.IntegerField(default=10)  # For Sudoku/Kakuro: 9, 10, 12, etc.
    
    # Auto-generation settings
    auto_generate = models.BooleanField(default=True)
    generation_algorithm = models.CharField(max_length=50, default='backtracking')
    
    # Scoring
    base_points = models.IntegerField(default=100)
    time_bonus = models.BooleanField(default=True)
    time_limit_seconds = models.IntegerField(default=3600)  # 1 hour
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['venture', 'game_type']
        ordering = ['game_type']
    
    def __str__(self):
        return f"{self.venture.name} - {self.get_game_type_display()}"


class Puzzle(models.Model):
    """
    Base model for all puzzles
    """
    venture_game = models.ForeignKey(VentureGame, on_delete=models.CASCADE, related_name='puzzles')
    puzzle_number = models.IntegerField(default=1)  # Which puzzle in sequence
    
    # Puzzle data (encrypted/encoded)
    puzzle_data = models.TextField()  # JSON encrypted/encoded
    solution_data = models.TextField()  # Encrypted solution
    
    # Metadata
    seed = models.CharField(max_length=100)  # For reproducible generation
    difficulty_score = models.FloatField(default=0.0)  # 0-1 scale
    
    # Stats
    times_solved = models.IntegerField(default=0)
    average_solve_time = models.FloatField(default=0.0)  # in seconds
    min_solve_time = models.FloatField(default=0.0)
    max_solve_time = models.FloatField(default=0.0)
    
    # Validation
    is_valid = models.BooleanField(default=True)
    validation_hash = models.CharField(max_length=64)  # SHA256 of puzzle+solution
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['venture_game', 'puzzle_number']
        unique_together = ['venture_game', 'puzzle_number']
    
    def save(self, *args, **kwargs):
        # Auto-generate puzzle if not provided
        if not self.puzzle_data:
            self.generate_puzzle()
        
        # Set expiration (e.g., 7 days for active puzzles)
        if not self.expires_at and self.venture_game.is_active:
            self.expires_at = timezone.now() + timedelta(days=7)
        
        super().save(*args, **kwargs)
    
    def generate_puzzle(self):
        """Generate puzzle based on game type"""
        from .generators import PuzzleGenerator
        
        generator = PuzzleGenerator(self.venture_game)
        puzzle, solution, seed, diff_score = generator.generate()
        
        self.puzzle_data = self.encrypt_data(puzzle)
        self.solution_data = self.encrypt_data(solution)
        self.seed = seed
        self.difficulty_score = diff_score
        self.validation_hash = self.calculate_hash(puzzle, solution)
    
    def encrypt_data(self, data):
        """Simple encryption for puzzle data (use Django's crypto for production)"""
        import base64
        from django.conf import settings
        
        # In production, use proper encryption
        data_str = json.dumps(data)
        # Simple base64 for demonstration
        return base64.b64encode(data_str.encode()).decode()
    
    def decrypt_data(self, encrypted_data):
        import base64
        data_str = base64.b64decode(encrypted_data.encode()).decode()
        return json.loads(data_str)
    
    def calculate_hash(self, puzzle, solution):
        import hashlib
        combined = json.dumps(puzzle) + json.dumps(solution)
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def verify_solution(self, user_solution):
        """Verify user's solution against stored solution"""
        solution = self.decrypt_data(self.solution_data)
        return self._compare_solutions(user_solution, solution)
    
    def _compare_solutions(self, user_sol, correct_sol):
        """Game-specific solution comparison"""
        game_type = self.venture_game.game_type
        
        if game_type == 'sudoku':
            return user_sol == correct_sol
        
        elif game_type == 'kakuro':
            # For Kakuro, compare filled cells
            return all(
                user_sol.get(cell, None) == correct_sol.get(cell, None)
                for cell in correct_sol.keys()
            )
        
        elif game_type == 'cryptogram':
            # For cryptogram, compare decoded text
            return user_sol.strip().upper() == correct_sol.strip().upper()
        
        return False
    
    def __str__(self):
        return f"Puzzle {self.puzzle_number} for {self.venture_game}"


class PlayerSession(models.Model):
    """
    Tracks a player's session for a specific puzzle
    """
    player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='game_sessions')
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE, related_name='sessions')
    venture_game = models.ForeignKey(VentureGame, on_delete=models.CASCADE, related_name='sessions')
    
    # Session state
    session_state = models.JSONField(default=dict)  # Current game state
    moves_history = models.JSONField(default=list)  # List of moves for undo/redo
    
    # Timing
    start_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
    # Completion
    is_completed = models.BooleanField(default=False)
    is_correct = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Stats
    hints_used = models.IntegerField(default=0)
    errors_made = models.IntegerField(default=0)
    time_spent_seconds = models.FloatField(default=0.0)
    
    # Score
    base_score = models.IntegerField(default=0)
    time_bonus = models.IntegerField(default=0)
    penalty_points = models.IntegerField(default=0)
    total_score = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['player', 'puzzle']
        ordering = ['-start_time']
    
    def save(self, *args, **kwargs):
        # Calculate time spent if completed
        if self.is_completed and not self.time_spent_seconds and self.start_time and self.completed_at:
            self.time_spent_seconds = (self.completed_at - self.start_time).total_seconds()
        
        # Calculate score
        if self.is_completed and self.is_correct:
            self.calculate_score()
        
        super().save(*args, **kwargs)
    
    def calculate_score(self):
        """Calculate score based on difficulty, time, hints, errors"""
        game = self.venture_game
        base = game.base_points
        
        # Difficulty multiplier
        diff_multiplier = {
            'easy': 1.0,
            'medium': 1.5,
            'hard': 2.0,
            'expert': 3.0
        }.get(game.difficulty, 1.0)
        
        # Time bonus (if enabled)
        time_bonus = 0
        if game.time_bonus and self.time_spent_seconds > 0:
            time_limit = game.time_limit_seconds
            if self.time_spent_seconds <= time_limit:
                # More bonus for faster completion
                time_ratio = 1 - (self.time_spent_seconds / time_limit)
                time_bonus = int(base * 0.5 * time_ratio)
        
        # Penalties
        penalty = self.hints_used * 5 + self.errors_made * 10
        
        # Calculate total
        self.base_score = int(base * diff_multiplier)
        self.time_bonus = time_bonus
        self.penalty_points = penalty
        self.total_score = max(0, self.base_score + self.time_bonus - penalty)
    
    def complete_session(self, user_solution):
        """Mark session as completed and verify solution"""
        self.is_completed = True
        self.completed_at = timezone.now()
        self.is_correct = self.puzzle.verify_solution(user_solution)
        
        if self.is_correct:
            # Update puzzle stats
            self.puzzle.times_solved += 1
            
            # Update average solve time
            total_time = (self.puzzle.average_solve_time * (self.puzzle.times_solved - 1) + 
                         self.time_spent_seconds) / self.puzzle.times_solved
            self.puzzle.average_solve_time = total_time
            
            # Update min/max times
            if self.time_spent_seconds < self.puzzle.min_solve_time or self.puzzle.min_solve_time == 0:
                self.puzzle.min_solve_time = self.time_spent_seconds
            if self.time_spent_seconds > self.puzzle.max_solve_time:
                self.puzzle.max_solve_time = self.time_spent_seconds
            
            self.puzzle.save()
            
            # Mark venture as solved if all puzzles completed
            self.mark_venture_solved()
        
        self.save()
    
    def mark_venture_solved(self):
        """Check if all puzzles for this venture are solved by this player"""
        from ventures.models import Venture
        
        venture = self.venture_game.venture
        all_games = VentureGame.objects.filter(venture=venture, is_active=True)
        
        # Check if player has solved all puzzles for all games in this venture
        all_solved = True
        for game in all_games:
            puzzles = Puzzle.objects.filter(venture_game=game, is_valid=True)
            for puzzle in puzzles:
                if not PlayerSession.objects.filter(
                    player=self.player,
                    puzzle=puzzle,
                    is_completed=True,
                    is_correct=True
                ).exists():
                    all_solved = False
                    break
            if not all_solved:
                break
        
        if all_solved:
            # Mark venture as solved for this player
            # You'll need a VentureCompletion model in venture app
            from ventures.models import VentureCompletion
            VentureCompletion.objects.get_or_create(
                venture=venture,
                player=self.player,
                defaults={'completed_at': timezone.now()}
            )
    
    def __str__(self):
        return f"{self.player.username} - {self.puzzle}"


class Leaderboard(models.Model):
    """
    Leaderboard for each venture game
    """
    venture_game = models.OneToOneField(VentureGame, on_delete=models.CASCADE, related_name='leaderboard')
    last_updated = models.DateTimeField(auto_now=True)
    
    # Cache top scores
    top_scores = models.JSONField(default=list)  # List of {player_id, score, time}
    
    class Meta:
        ordering = ['venture_game']
    
    def update_leaderboard(self):
        """Update leaderboard with latest scores"""
        from django.db.models import Max
        
        # Get all completed sessions for this game
        sessions = PlayerSession.objects.filter(
            venture_game=self.venture_game,
            is_completed=True,
            is_correct=True
        ).select_related('player')
        
        # Group by player, get best score
        player_scores = {}
        for session in sessions:
            player_id = session.player_id
            if player_id not in player_scores or session.total_score > player_scores[player_id]['score']:
                player_scores[player_id] = {
                    'player_id': player_id,
                    'username': session.player.username,
                    'score': session.total_score,
                    'time_spent': session.time_spent_seconds,
                    'completed_at': session.completed_at.isoformat() if session.completed_at else None
                }
        
        # Sort by score (descending), then by time (ascending)
        sorted_scores = sorted(
            player_scores.values(),
            key=lambda x: (-x['score'], x['time_spent'])
        )[:100]  # Top 100
        
        self.top_scores = sorted_scores
        self.save()
    
    def get_rank(self, player):
        """Get player's rank on leaderboard"""
        for i, entry in enumerate(self.top_scores, 1):
            if entry['player_id'] == player.id:
                return i
        return None
    
    def __str__(self):
        return f"Leaderboard for {self.venture_game}"


class Hint(models.Model):
    """
    Available hints for puzzles
    """
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE, related_name='hints')
    hint_type = models.CharField(max_length=50)  # 'reveal_cell', 'eliminate_option', 'check_errors'
    hint_data = models.JSONField()  # Specific hint data
    cost = models.IntegerField(default=10)  # Points deducted for using hint
    
    class Meta:
        ordering = ['cost']
    
    def __str__(self):
        return f"Hint for {self.puzzle}"