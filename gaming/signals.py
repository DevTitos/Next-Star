from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import VentureGame, Leaderboard, PlayerSession

@receiver(post_save, sender=VentureGame)
def create_leaderboard_for_game(sender, instance, created, **kwargs):
    """Create leaderboard when new game is created"""
    if created:
        Leaderboard.objects.create(venture_game=instance)

@receiver(post_save, sender=PlayerSession)
def update_leaderboard_on_completion(sender, instance, **kwargs):
    """Update leaderboard when session is completed"""
    if instance.is_completed and instance.is_correct:
        try:
            leaderboard = Leaderboard.objects.get(venture_game=instance.venture_game)
            leaderboard.update_leaderboard()
        except Leaderboard.DoesNotExist:
            pass

@receiver(post_save, sender=VentureGame)
def generate_puzzles_for_game(sender, instance, created, **kwargs):
    """Auto-generate puzzles when game is created"""
    if created and instance.auto_generate:
        from .models import Puzzle
        
        # Generate 10 puzzles for this game
        for i in range(1, 11):
            Puzzle.objects.create(
                venture_game=instance,
                puzzle_number=i
            )