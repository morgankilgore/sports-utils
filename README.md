# sports-utils
Collection of utilities for sports data


## NBA
### Slog Detector
Analyzes the NBA schedule to identify instances of high schedule density (or "slogs") for teams. 
This includes detecting back-to-back games (B2Bs) and three games in three days (3-in-3) stretches. 
#### Requirements:
1. Signup for a free API key at https://www.balldontlie.io/
2. You must set your API key as an environment variable. Create a file named `.env` in the root directory or 
set the environment variable directly: `BALLDONTLIE_API_KEY=your_api_key_here`
3. `uv` package manager

#### Example Usage:
```
# Analyze the schedule for games on October 28th, 2025
uv run nba/slog-detector.py --date 2025-10-28
```