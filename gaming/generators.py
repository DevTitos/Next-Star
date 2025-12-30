import random
import numpy as np
import json
from typing import Dict, List, Tuple, Any
import string

class PuzzleGenerator:
    """Generates puzzles for different game types"""
    
    def __init__(self, venture_game):
        self.venture_game = venture_game
        self.game_type = venture_game.game_type
        self.difficulty = venture_game.difficulty
        self.grid_size = venture_game.grid_size
        
        # Set difficulty parameters
        self.difficulty_params = self._get_difficulty_params()
        
    def _get_difficulty_params(self):
        """Get parameters based on difficulty level"""
        params = {
            'easy': {'filled_cells': 0.5, 'complexity': 1},
            'medium': {'filled_cells': 0.4, 'complexity': 2},
            'hard': {'filled_cells': 0.3, 'complexity': 3},
            'expert': {'filled_cells': 0.2, 'complexity': 4}
        }
        return params.get(self.difficulty, params['medium'])
    
    def generate(self) -> Tuple[Dict, Dict, str, float]:
        """Generate puzzle and solution"""
        if self.game_type == 'sudoku':
            return self.generate_sudoku()
        elif self.game_type == 'kakuro':
            return self.generate_kakuro()
        elif self.game_type == 'cryptogram':
            return self.generate_cryptogram()
        else:
            raise ValueError(f"Unknown game type: {self.game_type}")
    
    def generate_sudoku(self) -> Tuple[Dict, Dict, str, float]:
        """Generate Sudoku puzzle (minimum 10x10)"""
        size = max(10, self.grid_size)
        
        # Generate solution
        solution = self._generate_sudoku_solution(size)
        
        # Create puzzle by removing cells
        puzzle = self._create_sudoku_puzzle(solution, size)
        
        # Calculate difficulty score
        difficulty_score = 0.5#self._calculate_sudoku_difficulty(puzzle, solution)
        
        return puzzle, solution, str(random.getrandbits(128)), difficulty_score
    
    def _generate_sudoku_solution(self, size: int) -> List[List[int]]:
        """Generate a valid Sudoku solution"""
        # For demonstration, generate a simpler version
        # In production, use proper Sudoku generation algorithm
        
        # Create base pattern
        base = list(range(1, size + 1))
        random.shuffle(base)
        
        solution = []
        for i in range(size):
            row = base[i:] + base[:i]
            solution.append(row)
        
        return solution
    
    def _create_sudoku_puzzle(self, solution: List[List[int]], size: int) -> List[List[int]]:
        """Create puzzle from solution by removing cells"""
        puzzle = [row.copy() for row in solution]
        
        # Remove cells based on difficulty
        cells_to_remove = int(size * size * (1 - self.difficulty_params['filled_cells']))
        
        removed_positions = []
        for _ in range(cells_to_remove):
            while True:
                row = random.randint(0, size - 1)
                col = random.randint(0, size - 1)
                if puzzle[row][col] != 0:
                    removed_positions.append((row, col, puzzle[row][col]))
                    puzzle[row][col] = 0
                    break
        
        return puzzle
    
    def generate_kakuro(self) -> Tuple[Dict, Dict, str, float]:
        """Generate Kakuro puzzle (minimum 10x10)"""
        size = max(10, self.grid_size)
        
        # Generate board with white and black cells
        board = self._generate_kakuro_board(size)
        
        # Generate solution
        solution = self._solve_kakuro_board(board)
        
        # Create puzzle (with sums only)
        puzzle = self._create_kakuro_puzzle(board, solution)
        
        difficulty_score = random.uniform(0.5, 0.9)
        
        return puzzle, solution, str(random.getrandbits(128)), difficulty_score
    
    def _generate_kakuro_board(self, size: int) -> Dict:
        """Generate Kakuro board structure"""
        board = {
            'size': size,
            'cells': [],
            'across_clues': {},
            'down_clues': {}
        }
        
        # Simple pattern: every other cell is white
        for r in range(size):
            row = []
            for c in range(size):
                # White if both coordinates are odd/even
                is_white = (r % 2 == 0 and c % 2 == 0) or (r % 2 == 1 and c % 2 == 1)
                row.append({
                    'is_white': is_white,
                    'value': None,
                    'across_clue': None,
                    'down_clue': None
                })
            board['cells'].append(row)
        
        return board
    
    def generate_cryptogram(self) -> Tuple[Dict, Dict, str, float]:
        """Generate Cryptogram puzzle"""
        # Sample quotes
        quotes = [
            "THE ONLY WAY TO DO GREAT WORK IS TO LOVE WHAT YOU DO",
            "IN THE MIDDLE OF DIFFICULTY LIES OPPORTUNITY",
            "THE FUTURE BELONGS TO THOSE WHO BELIEVE IN THE BEAUTY OF THEIR DREAMS",
            "IT DOES NOT MATTER HOW SLOWLY YOU GO AS LONG AS YOU DO NOT STOP"
        ]
        
        original_text = random.choice(quotes)
        
        # Create substitution cipher
        alphabet = list(string.ascii_uppercase)
        shuffled = alphabet.copy()
        random.shuffle(shuffled)
        
        cipher_map = {orig: sub for orig, sub in zip(alphabet, shuffled)}
        
        # Encrypt text
        encrypted_text = ''.join(
            cipher_map[char] if char in cipher_map else char 
            for char in original_text
        )
        
        puzzle = {
            'encrypted_text': encrypted_text,
            'hint_letters': 3,  # Number of letters to show as hint
            'cipher_type': 'simple_substitution'
        }
        
        solution = {
            'original_text': original_text,
            'cipher_map': cipher_map
        }
        
        # Difficulty based on text length and hint letters
        difficulty_score = min(0.9, len(original_text.replace(' ', '')) / 100)
        
        return puzzle, solution, str(random.getrandbits(128)), difficulty_score