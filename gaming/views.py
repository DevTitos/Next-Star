from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from .models import VentureGame, Puzzle, PlayerSession, Leaderboard
from ventures.models import Venture

def is_admin(user):
    return user.is_staff


@login_required
def game_hub(request, venture_id):
    venture = get_object_or_404(Venture, id=venture_id)
    print(venture)
    games = VentureGame.objects.filter(venture=venture, is_active=True)
    
    # Get completion stats
    completed_puzzles = {}
    for game in games:
        completed = PlayerSession.objects.filter(
            player=request.user,
            venture_game=game,
            is_completed=True,
            is_correct=True
        ).count()
        completed_puzzles[game.id] = completed
    
    # Get leaderboard data
    leaderboard_data = []
    for game in games:
        leaderboard = Leaderboard.objects.filter(venture_game=game).first()
        if leaderboard:
            leaderboard_data.extend(leaderboard.top_scores[:10])
    
    context = {
        'venture': venture,
        'games': games,
        'completed_puzzles': completed_puzzles,
        'leaderboards': leaderboard_data,
    }
    return render(request, 'gaming/game_hub.html', context)

@login_required
def play_game(request, venture_id, game_type):
    venture = get_object_or_404(Venture, id=venture_id)
    venture_game = get_object_or_404(
        VentureGame, 
        venture=venture, 
        game_type=game_type,
        is_active=True
    )
    
    # Get or create puzzle for this game
    puzzle = Puzzle.objects.filter(venture_game=venture_game).first()
    if not puzzle:
        messages.error(request, "No puzzles available for this game.")
        return redirect('game_hub', venture_id=venture_id)
    
    # Get or create player session
    session, created = PlayerSession.objects.get_or_create(
        player=request.user,
        puzzle=puzzle,
        venture_game=venture_game,
        defaults={'session_state': {}}
    )
    
    # Decrypt puzzle data for frontend
    puzzle_data = puzzle.decrypt_data(puzzle.puzzle_data)
    solution_data = puzzle.decrypt_data(puzzle.solution_data)
    
    # Choose template based on game type
    template_map = {
        'sudoku': 'gaming/sudoku.html',
        'kakuro': 'gaming/kakuro.html',
        'cryptogram': 'gaming/cryptogram.html',
    }
    
    context = {
        'venture': venture,
        'venture_game': venture_game,
        'puzzle': puzzle,
        'session': session,
        'puzzle_data': json.dumps(puzzle_data),
        'solution_data': json.dumps(solution_data),
        'session_id': session.id,
        'time_limit': venture_game.time_limit_seconds,
        'base_points': venture_game.base_points,
        'size': venture_game.grid_size,
    }
    
    return render(request, template_map[game_type], context)

@user_passes_test(is_admin)
def create_venture_game(request):
    if request.method == 'POST':
        try:
            venture_id = request.POST.get('venture_id')
            game_type = request.POST.get('game_type')
            difficulty = request.POST.get('difficulty')
            grid_size = int(request.POST.get('grid_size', 10))
            
            venture = get_object_or_404(Venture, id=venture_id)
            
            # Create venture game
            venture_game = VentureGame.objects.create(
                venture=venture,
                game_type=game_type,
                difficulty=difficulty, 
                grid_size=grid_size,
                base_points=int(request.POST.get('base_points', 100)),
                time_limit_seconds=int(request.POST.get('time_limit', 3600)),
                auto_generate=request.POST.get('auto_generate') == 'on',
                time_bonus=request.POST.get('time_bonus') == 'on',
            )
            
            # Auto-generate puzzles if enabled
            if venture_game.auto_generate:
                for i in range(1, 11):
                    Puzzle.objects.create(venture_game=venture_game, puzzle_number=i)
            
            messages.success(request, f"{game_type.title()} game created successfully!")
            return redirect('admin:gaming_venturegame_changelist')
            
        except Exception as e:
            messages.error(request, f"Error creating game: {str(e)}")
    
    # GET request - show form
    ventures = Venture.objects.all()
    context = {
        'ventures': ventures,
    }
    return render(request, 'gaming/admin/create_game.html', context)

@login_required
@require_POST
def submit_solution(request, session_id):
    try:
        session = get_object_or_404(PlayerSession, id=session_id, player=request.user)
        data = json.loads(request.body)
        
        session.complete_session(data.get('solution'))
        
        return JsonResponse({
            'success': True,
            'correct': session.is_correct,
            'score': session.total_score,
            'venture_completed': False,  # Check if all games completed
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
def leaderboard(request, venture_id):
    venture = get_object_or_404(Venture, id=venture_id)
    
    # Get all leaderboards for this venture
    games = VentureGame.objects.filter(venture=venture, is_active=True)
    leaderboards = []
    
    for game in games:
        leaderboard_obj = Leaderboard.objects.filter(venture_game=game).first()
        if leaderboard_obj:
            leaderboards.append({
                'game': game,
                'scores': leaderboard_obj.top_scores[:20]
            })
    
    # Calculate user stats
    user_stats = None
    total_sessions = PlayerSession.objects.filter(
        player=request.user,
        venture_game__venture=venture,
        is_completed=True,
        is_correct=True
    )
    
    if total_sessions.exists():
        total_score = sum(session.total_score for session in total_sessions)
        avg_time = sum(session.time_spent_seconds for session in total_sessions) / total_sessions.count()
        
        user_stats = {
            'rank': 1,  # Calculate actual rank
            'total_score': total_score,
            'completed_games': total_sessions.count(),
            'avg_time': avg_time,
        }
    
    context = {
        'venture': venture,
        'leaderboards': leaderboards,
        'user_stats': user_stats,
    }
    return render(request, 'gaming/leaderboard.html', context)

def download_puzzle(request, venture_id):
    venture = get_object_or_404(Venture, id=venture_id)
    games = VentureGame.objects.filter(venture=venture, is_active=True)
    
    context = {
        'venture': venture,
        'games': games,
    }
    return render(request, 'gaming/download_puzzle.html', context)

# API Views
@csrf_exempt
@require_POST
def api_use_hint(request, session_id):
    try:
        data = json.loads(request.body)
        hint_type = data.get('hint_type')
        
        session = get_object_or_404(PlayerSession, id=session_id, player=request.user)
        session.hints_used += 1
        session.save()
        
        # Logic to generate hint based on type
        hint_data = generate_hint(session.puzzle, hint_type)
        
        return JsonResponse({
            'success': True,
            'hint': hint_data,
            'hints_remaining': max(0, 10 - session.hints_used)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

def api_download_puzzle(request, puzzle_id, format):
    puzzle = get_object_or_404(Puzzle, id=puzzle_id)
    
    # Generate file based on format
    if format == 'pdf':
        # Generate PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="puzzle_{puzzle_id}.pdf"'
        # PDF generation logic here
        return response
    
    elif format == 'json':
        data = {
            'puzzle': puzzle.decrypt_data(puzzle.puzzle_data),
            'solution': puzzle.decrypt_data(puzzle.solution_data),
            'metadata': {
                'id': puzzle.id,
                'game_type': puzzle.venture_game.game_type,
                'difficulty': puzzle.venture_game.difficulty,
                'created_at': puzzle.created_at.isoformat(),
            }
        }
        return JsonResponse(data)
    
    return HttpResponse(status=400)

def generate_hint(puzzle, hint_type):
    """Generate hint data based on puzzle state and hint type"""
    # Implementation depends on game type
    pass