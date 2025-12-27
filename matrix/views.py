from django.http import JsonResponse
import json
from .models import MatrixGame, PlayerGameSession, MatrixLeaderboard
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from datetime import timedelta

logger = logging.getLogger(__name__)

@login_required
def matrix_game_view(request, game_id=None):
    """Main view for CEO Matrix game"""
    if game_id:
        try:
            game = MatrixGame.objects.get(id=game_id, is_active=True)
        except MatrixGame.DoesNotExist:
            messages.error(request, "Game not found or expired")
            return redirect('dashboard')
    else:
        # Get latest active game
        game = MatrixGame.objects.filter(is_active=True).first()
        if not game:
            # Create a new game
            game = create_new_matrix_game()
    
    # Get or create player session
    session, created = PlayerGameSession.objects.get_or_create(
        player=request.user,
        game=game,
        defaults={
            'current_position': {'layer': 0, 'row': 0, 'col': 0}
        }
    )
    
    # If session is completed, create new one
    if session.is_completed:
        session = PlayerGameSession.objects.create(
            player=request.user,
            game=game,
            current_position={'layer': 0, 'row': 0, 'col': 0}
        )
    
    context = {
        'game': game,
        'session': session,
        'game_state': session.get_game_state(),
        'matrix_data': json.dumps(game.matrix_data) if game.matrix_data else '{}',
    }
    
    return render(request, 'games/matrix_game.html', context)

def create_new_matrix_game():
    """Create a new CEO Matrix game"""
    from datetime import timedelta
    from django.utils import timezone
    
    game = MatrixGame.objects.create(
        name="CEO Matrix Challenge",
        difficulty="genius",
        rows=5,
        cols=5,
        layers=3,
        expires_at=timezone.now() + timedelta(hours=24),
        max_moves=100
    )
    
    # Generate matrix
    game.generate_matrix()
    game.save()
    
    return game

@login_required
@require_http_methods(["GET"])
def get_matrix_game_state(request, game_id):
    """API endpoint to get game state"""
    try:
        game = MatrixGame.objects.get(id=game_id)
        session = PlayerGameSession.objects.get(player=request.user, game=game)
        
        return JsonResponse({
            'success': True,
            'game_state': session.get_game_state(),
            'matrix_data': game.matrix_data,
            'solution_exists': bool(game.solved_by)
        })
        
    except (MatrixGame.DoesNotExist, PlayerGameSession.DoesNotExist) as e:
        return JsonResponse({
            'success': False,
            'error': 'Game or session not found'
        }, status=404)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def make_move(request):
    """API endpoint to make a move in the matrix"""
    try:
        data = json.loads(request.body)
        game_id = data.get('game_id')
        layer = data.get('layer')
        row = data.get('row')
        col = data.get('col')
        
        if None in [game_id, layer, row, col]:
            return JsonResponse({
                'success': False,
                'error': 'Missing parameters'
            }, status=400)
        
        game = MatrixGame.objects.get(id=game_id, is_active=True)
        session = PlayerGameSession.objects.get(player=request.user, game=game)
        
        # Check if game already solved
        if game.solved_by:
            return JsonResponse({
                'success': False,
                'error': 'Game already solved by another player'
            })
        
        # Make the move
        success, result = session.move_to(layer, row, col)
        
        if not success:
            return JsonResponse({
                'success': False,
                'error': result if isinstance(result, str) else 'Invalid move'
            })
        
        # Check if this move completes the solution
        if session.is_completed:
            session.complete_session()
            
            if session.is_winner:
                # Update leaderboard
                leaderboard_entry, created = MatrixLeaderboard.objects.update_or_create(
                    game=game,
                    player=request.user,
                    session=session,
                    defaults={
                        'score': session.score,
                        'moves': session.moves_made,
                        'time_taken': session.time_taken or timedelta(0),
                        'solved_at': session.completed_at
                    }
                )
                leaderboard_entry.update_rank()
        
        return JsonResponse({
            'success': True,
            'message': result['message'] if isinstance(result, dict) else result,
            'game_state': session.get_game_state(),
            'cell_data': result.get('cell') if isinstance(result, dict) else None,
            'is_completed': session.is_completed,
            'is_winner': session.is_winner
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except MatrixGame.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Game not found'
        }, status=404)
    except PlayerGameSession.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Session not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Move error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_http_methods(["GET"])
def get_matrix_leaderboard(request, game_id):
    """Get leaderboard for a matrix game"""
    try:
        game = MatrixGame.objects.get(id=game_id)
        
        leaderboard = MatrixLeaderboard.objects.filter(game=game).order_by('-score', 'time_taken', 'moves')[:10]
        
        leaderboard_data = []
        for entry in leaderboard:
            leaderboard_data.append({
                'rank': entry.rank,
                'player': entry.player.username,
                'score': entry.score,
                'moves': entry.moves,
                'time_taken': str(entry.time_taken),
                'solved_at': entry.solved_at.isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'game': game.name,
            'leaderboard': leaderboard_data,
            'solved_by': game.solved_by.username if game.solved_by else None
        })
        
    except MatrixGame.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Game not found'
        }, status=404)

@login_required
@require_http_methods(["POST"])
def reset_matrix_session(request):
    """Reset player's game session"""
    try:
        data = json.loads(request.body)
        game_id = data.get('game_id')
        
        game = MatrixGame.objects.get(id=game_id, is_active=True)
        
        # Delete existing session
        PlayerGameSession.objects.filter(player=request.user, game=game).delete()
        
        # Create new session
        session = PlayerGameSession.objects.create(
            player=request.user,
            game=game,
            current_position={'layer': 0, 'row': 0, 'col': 0}
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Session reset successfully',
            'game_state': session.get_game_state()
        })
        
    except MatrixGame.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Game not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)