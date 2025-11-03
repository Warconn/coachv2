from datetime import datetime, timezone
from app import create_app, db
from app.models import Event, Recommendation, BetResult

def fix_bulls_knicks_game():
    """Fix the incorrect outcome for Bulls @ Knicks game"""
    with create_app().app_context():
        game = Event.query.filter(
            Event.home_team.ilike('%Knicks%'),
            Event.away_team.ilike('%Bulls%')
        ).first()
        
        if game:
            print(f"\nFixing {game.away_team} @ {game.home_team}")
            print(f"Current score: {game.away_score}-{game.home_score}")
            
            # Knicks won, so recommendations on Bulls should be LOST
            recs = Recommendation.query.filter_by(event_id=game.id).all()
            for rec in recs:
                old_result = rec.resolved_result
                if rec.bet_side == 'away':  # If we bet on Bulls (away team)
                    rec.resolved_result = BetResult.LOST
                elif rec.bet_side == 'home':  # If we bet on Knicks (home team)
                    rec.resolved_result = BetResult.WON
                print(f"Updated recommendation {rec.id} from {old_result} to {rec.resolved_result}")
                
                # Update any associated bets
                for bet in rec.bets:
                    bet.result = rec.resolved_result
        
            db.session.commit()
            print("\nChanges committed to database")

if __name__ == '__main__':
    fix_bulls_knicks_game()