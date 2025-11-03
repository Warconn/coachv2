from datetime import datetime, timezone
from sqlalchemy import select
from app import create_app, db
from app.models import Recommendation, Event

def cleanup_resolved_recommendations():
    """
    Cleanup inconsistent recommendation and event data by:
    1. Ensuring all resolved recommendations have a resolved_at timestamp
    2. Ensuring all events with scores have a resolved_at timestamp
    3. Setting commence_time to resolved_at for any completed events that 
       incorrectly show future start times
    """
    with create_app().app_context():
        # Get recommendations with outcomes but no resolved_at
        recs_to_fix = Recommendation.query.filter(
            Recommendation.resolved_result.isnot(None),
            Recommendation.resolved_at.is_(None)
        ).all()
        
        now = datetime.now(timezone.utc)
        fixed_recs = 0
        fixed_events = 0

        # Fix recommendations without resolved_at
        for rec in recs_to_fix:
            rec.resolved_at = now
            fixed_recs += 1
            
            # Also fix the associated event if it has scores but no resolved_at
            if rec.event and rec.event.resolved_at is None and (
                rec.event.home_score is not None or rec.event.away_score is not None
            ):
                rec.event.resolved_at = now
                fixed_events += 1

        # Find events with scores but no resolved_at
        events_to_fix = Event.query.filter(
            Event.resolved_at.is_(None),
            (Event.home_score.isnot(None) | Event.away_score.isnot(None))
        ).all()

        # Fix events with scores but no resolved_at
        for event in events_to_fix:
            event.resolved_at = now
            fixed_events += 1

        # Fix events with future commence_times but resolved status
        future_events = Event.query.filter(
            Event.resolved_at.isnot(None),
            Event.commence_time > now
        ).all()

        fixed_commence = 0
        for event in future_events:
            event.commence_time = event.resolved_at
            fixed_commence += 1

        db.session.commit()

        return {
            'fixed_recommendations': fixed_recs,
            'fixed_events': fixed_events,
            'fixed_commence_times': fixed_commence
        }

if __name__ == '__main__':
    results = cleanup_resolved_recommendations()
    print(f"Fixed {results['fixed_recommendations']} recommendations")
    print(f"Fixed {results['fixed_events']} events")
    print(f"Fixed {results['fixed_commence_times']} commence times")