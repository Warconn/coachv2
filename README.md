# CoachV2 Sports Betting Monitor

CoachV2 is a work-in-progress platform for monitoring moneyline movements across multiple sportsbooks, flagging reverse line moves, and tracking recommended wagers alongside bankroll performance.

## High-Level Components
- **Worker Service** – pulls odds snapshots on a configurable schedule, detects reverse movement, and stores recommendations.
- **Flask Web App** – surfaces dashboards for current alerts, historical recommendations, and bankroll tracking while exposing configuration controls.
- **PostgreSQL Database** – persists events, sportsbook odds history, recommendations, bet ledger, and configuration overrides.

## Local Development
1. Copy `.env.example` to `.env` and fill in API keys (free tier keys for data providers like The Odds API are sufficient to start).
2. Build and start the stack:
   ```bash
   docker-compose up --build
   ```
3. Access the web UI at `http://localhost:5000` (includes one-click ingestion and live recommendations table).

### Python 3.14 note
The `psycopg2-binary` package does not yet ship wheels for Python 3.14. If you are running Python 3.14 locally, replace the dependency and use the new driver instead:
```bash
pip uninstall psycopg2-binary
pip install 'psycopg[binary]'
```
Update `requirements.txt` so future installs use `psycopg[binary]`, and set `DATABASE_URL` to use the `postgresql+psycopg://` driver string in your `.env`.

### Reverse line movement API
- `GET /api/recommendations?limit=50` – returns the most recent reverse line movement alerts persisted by the ingestion worker.
- `POST /api/ingest` – runs an on-demand ingestion cycle (also wired to the dashboard button).

## Project Status
- [x] Repository scaffolding
- [ ] Database schema & migrations
- [ ] Odds ingestion & reverse movement detection
- [ ] Flask UI
- [ ] Notification hooks and bankroll management

## Next Steps
1. Implement SQLAlchemy models and Alembic migrations for events, odds snapshots, recommendations, bets, and bankroll ledger.
2. Create odds API abstraction and first ingestion job using The Odds API free tier.
3. Wire worker scheduling (APScheduler) and basic dashboard endpoints.

## License
TBD
