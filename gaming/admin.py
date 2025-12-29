from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.http import HttpResponseRedirect
from .models import VentureGame, Puzzle, PlayerSession, Leaderboard, Hint

class PuzzleInline(admin.TabularInline):
    model = Puzzle
    extra = 0
    readonly_fields = ['difficulty_score', 'times_solved']
    fields = ['puzzle_number', 'difficulty_score', 'times_solved', 'is_valid']
    can_delete = True

@admin.register(VentureGame)
class VentureGameAdmin(admin.ModelAdmin):
    list_display = ['venture', 'game_type', 'difficulty', 'grid_size', 
                   'is_active', 'puzzle_count', 'play_link']
    list_filter = ['game_type', 'difficulty', 'is_active']
    search_fields = ['venture__name']
    inlines = [PuzzleInline]
    actions = ['generate_puzzles', 'activate_games', 'deactivate_games']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('venture', 'game_type', 'difficulty', 'is_active')
        }),
        ('Game Configuration', {
            'fields': ('grid_size', 'auto_generate', 'generation_algorithm')
        }),
        ('Scoring System', {
            'fields': ('base_points', 'time_bonus', 'time_limit_seconds')
        }),
        ('Statistics', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def puzzle_count(self, obj):
        return obj.puzzles.count()
    puzzle_count.short_description = 'Puzzles'
    
    def play_link(self, obj):
        url = reverse('play_game', args=[obj.venture.id, obj.game_type])
        return format_html('<a href="{}" target="_blank">Play Game</a>', url)
    play_link.short_description = 'Action'
    
    def generate_puzzles(self, request, queryset):
        for game in queryset:
            # Generate 10 puzzles for each game
            for i in range(1, 11):
                Puzzle.objects.get_or_create(
                    venture_game=game,
                    puzzle_number=i
                )
        self.message_user(request, f"Puzzles generated for {queryset.count()} games.")
    
    def activate_games(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} games activated.")
    
    def deactivate_games(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} games deactivated.")
    
    def response_add(self, request, obj, post_url_continue=None):
        """Redirect to custom creation page after add"""
        if '_addanother' in request.POST:
            return HttpResponseRedirect(reverse('create_venture_game'))
        return super().response_add(request, obj, post_url_continue)

@admin.register(Puzzle)
class PuzzleAdmin(admin.ModelAdmin):
    list_display = ['venture_game', 'puzzle_number', 'difficulty_score', 
                   'times_solved', 'is_valid', 'created_at']
    list_filter = ['venture_game__game_type', 'is_valid']
    search_fields = ['venture_game__venture__name']
    readonly_fields = ['validation_hash', 'seed', 'created_at']
    actions = ['regenerate_puzzles', 'validate_puzzles']
    
    def regenerate_puzzles(self, request, queryset):
        for puzzle in queryset:
            puzzle.generate_puzzle()
            puzzle.save()
        self.message_user(request, f"{queryset.count()} puzzles regenerated.")
    
    def validate_puzzles(self, request, queryset):
        invalid = []
        for puzzle in queryset:
            if not puzzle.is_valid:
                invalid.append(puzzle.id)
        self.message_user(request, f"Found {len(invalid)} invalid puzzles.")

@admin.register(PlayerSession)
class PlayerSessionAdmin(admin.ModelAdmin):
    list_display = ['player', 'venture_game', 'puzzle', 'is_completed', 
                   'is_correct', 'total_score', 'time_spent_seconds']
    list_filter = ['is_completed', 'is_correct', 'venture_game__game_type']
    search_fields = ['player__username', 'venture_game__venture__name']
    readonly_fields = ['start_time', 'last_activity', 'completed_at']
    
    def has_add_permission(self, request):
        return False  # Sessions are created automatically

@admin.register(Leaderboard)
class LeaderboardAdmin(admin.ModelAdmin):
    list_display = ['venture_game', 'last_updated', 'top_player']
    readonly_fields = ['top_scores', 'last_updated']
    
    def top_player(self, obj):
        if obj.top_scores:
            return obj.top_scores[0].get('username', 'N/A')
        return 'No scores'
    top_player.short_description = 'Top Player'
    
    def has_add_permission(self, request):
        return False  # Leaderboards are created automatically

@admin.register(Hint)
class HintAdmin(admin.ModelAdmin):
    list_display = ['puzzle', 'hint_type', 'cost']
    list_filter = ['hint_type']
    search_fields = ['puzzle__venture_game__venture__name']