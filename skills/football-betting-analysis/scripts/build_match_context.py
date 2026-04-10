#!/usr/bin/env python3
"""
build_match_context.py
=====================
Pre-match football context builder for FlashScore data.
Receives event_id, home_team_id, away_team_id as arguments,
executes all FlashScore endpoint calls, normalizes the data,
and emits a single `final_context` JSON to stdout.

Usage:
    python build_match_context.py <event_id> <home_team_id> <away_team_id>
"""

import sys
import json
import requests
import re
import html
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

def load_rapidapi_key() -> str:
    """Load RAPIDAPI_KEY from settings files, or return empty string if not found."""
    settings_paths = [
        Path.home() / ".claude" / "settings.json",
        Path.home() / ".claude" / "settings.local.json",
    ]
    for path in settings_paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "RAPIDAPI_KEY" in data:
                        return data["RAPIDAPI_KEY"]
            except Exception:
                pass
    return ""

RAPIDAPI_KEY = load_rapidapi_key()
RAPIDAPI_HOST = "flashscore4.p.rapidapi.com"

HEADERS = {
    "Content-Type": "application/json",
    "x-rapidapi-host": RAPIDAPI_HOST,
    "x-rapidapi-key": RAPIDAPI_KEY,
    "timezone": "America/New_York",
}

BASE_URL = f"https://{RAPIDAPI_HOST}/api/flashscore/v2"

# =============================================================================
# HTTP CLIENT
# =============================================================================

def api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Make a GET request to the FlashScore RapidAPI endpoint."""
    url = BASE_URL + path
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[WARNING] API call failed for {path}: {e}", file=sys.stderr)
        return None


# =============================================================================
# FETCH FUNCTIONS — one per endpoint
# =============================================================================

def fetch_match_details(event_id: str) -> Optional[Dict]:
    """Get full event details + tournament/team info + initial odds."""
    return api_get("/matches/details", params={"match_id": event_id})


def fetch_match_odds(event_id: str, geo: str = "US") -> Optional[List]:
    """Get all betting markets/odds for the event."""
    return api_get("/matches/odds", params={"match_id": event_id, "geo_ip_code": geo})


def fetch_h2h(event_id: str) -> Optional[List]:
    """Get head-to-head history between the two teams.
    DEPRECATED: H2H is now built from team_results to avoid redundancy.
    Kept for compatibility but not called by build_context."""
    return None  # Replaced by build_h2h_from_results


def fetch_match_stats(event_id: str) -> Optional[Dict]:
    """Get match statistics (possession, shots, corners, cards, xG)."""
    return api_get("/matches/match/stats", params={"match_id": event_id})


def fetch_match_player_stats(event_id: str) -> Optional[Dict]:
    """Get per-player statistics for the match."""
    return api_get("/matches/match/player-stats", params={"match_id": event_id})


def fetch_match_lineups(event_id: str) -> Optional[List]:
    """Get lineups + missing players."""
    return api_get("/matches/match/lineups", params={"match_id": event_id})


def fetch_match_summary(event_id: str) -> Optional[List]:
    """Get match summary (key events: goals, cards)."""
    return api_get("/matches/match/summary", params={"match_id": event_id})


def fetch_match_commentary(event_id: str) -> Optional[List]:
    """Get minute-by-minute commentary."""
    return api_get("/matches/match/commentary", params={"match_id": event_id})


def fetch_team_results(team_id: str, page: int = 1) -> Optional[Dict]:
    """Get recent match results for a team."""
    return api_get("/teams/results", params={"team_id": team_id, "page": page})


def fetch_team_fixtures(team_id: str, page: int = 1) -> Optional[Dict]:
    """Get upcoming fixtures for a team."""
    return api_get("/teams/fixtures", params={"team_id": team_id, "page": page})


def build_preview_slug(team_url: str) -> str:
    """Convert team URL to URL slug format for FlashScore preview URL."""
    if not team_url: return ""
    slug = team_url.lower()
    slug = team_url.split("/")[2]
    slug = re.sub(r"[áàä]", "a", slug)
    slug = re.sub(r"[éèë]", "e", slug)
    slug = re.sub(r"[íìï]", "i", slug)
    slug = re.sub(r"[óòö]", "o", slug)
    slug = re.sub(r"[úùü]", "u", slug)
    slug = slug.replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")

import re
import sys
import html
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional


def fix_mojibake(text: str) -> str:
    """
    Fix common mojibake issues like:
    'PeÃ±arol' -> 'Peñarol'
    'verÃ¡n' -> 'verán'
    """
    if not text:
        return text

    # Caso típico: UTF-8 interpretado como latin1
    try:
        repaired = text.encode("latin1").decode("utf-8")
        text = repaired
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    replacements = {
        "â€œ": '"',
        "â€\x9d": '"',
        "â€˜": "'",
        "â€™": "'",
        "â€“": "–",
        "â€”": "—",
        "â€¦": "…",
        "Â ": " ",
        "Â": "",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    return text


def clean_preview(preview: Optional[str]) -> Optional[str]:
    """
    Clean Flashscore preview text:
    - fixes encoding issues
    - removes pseudo-tags
    - removes sponsored section
    - removes line breaks (returns single paragraph)
    """
    if not preview:
        return None

    text = html.unescape(preview)

    # Fix escaped slashes: \/ -> /
    text = text.replace("\\/", "/")

    # Fix encoding
    text = fix_mojibake(text)

    # Remove opening pseudo-tags like [a ...]
    text = re.sub(r"\[a[^\]]*\]", "", text)

    # Replace structural tags
    text = text.replace("[/h2]", ". ")
    text = text.replace("[/p]", " ")
    text = text.replace("[/b]", "")
    text = text.replace("[/a]", "")

    # Remove simple opening tags
    text = text.replace("[h2]", "")
    text = text.replace("[p]", "")
    text = text.replace("[b]", "")
    text = text.replace("[a]", "")

    # 🔥 Eliminar todo desde "Patrocinado:"
    text = re.split(r"Patrocinado:", text, flags=re.IGNORECASE)[0]

    # Normalizar espacios
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()

def extract_preview_from_dom(resp_text: str) -> Optional[str]:
    """
    Try to extract preview from rendered HTML block.
    """
    soup = BeautifulSoup(resp_text, "html.parser")

    selectors = [
        "div.section--preview div.fp-body_9caht",
        "div.section--preview div.preview__block",
        "div.loadable.complete.section.section--preview div.preview__block",
    ]

    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            text = element.get_text(" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                return text

    return None


def extract_preview_from_content_parsed(resp_text: str) -> Optional[str]:
    """
    Extract preview from embedded eventPreview.contentParsed JSON-like string.
    """
    patterns = [
        r'"eventPreview":\{.*?"contentParsed":"(.*?)","editedAt":',
        r'"contentParsed":"(.*?)","editedAt":',
    ]

    for pattern in patterns:
        match = re.search(pattern, resp_text, re.DOTALL)
        if match:
            return match.group(1)

    return None


def fetch_preview(home_slug: Dict, away_slug: Dict, event_id: str) -> Optional[str]:
    """
    Scrape and clean preview text from FlashScore page.
    Tries both URL orders, DOM extraction first, then embedded contentParsed fallback.
    """
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    }

    candidate_urls = [
        (
            f"https://www.flashscore.co/partido/futbol/"
            f"{home_slug['slug']}-{home_slug['id']}/"
            f"{away_slug['slug']}-{away_slug['id']}/?mid={event_id}"
        ),
        (
            f"https://www.flashscore.co/partido/futbol/"
            f"{away_slug['slug']}-{away_slug['id']}/"
            f"{home_slug['slug']}-{home_slug['id']}/?mid={event_id}"
        ),
    ]

    for url in candidate_urls:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()

            # 1) Try DOM
            preview = extract_preview_from_dom(resp.text)
            if preview:
                cleaned = clean_preview(preview)
                if cleaned:
                    return cleaned

            # 2) Try embedded eventPreview.contentParsed
            preview = extract_preview_from_content_parsed(resp.text)
            if preview:
                cleaned = clean_preview(preview)
                if cleaned:
                    return cleaned

        except Exception as e:
            print(f"[WARNING] Preview scrape failed for {event_id} in {url}: {e}", file=sys.stderr)

    return None

def fetch_tournament_standings(tournament_id: str, tournament_stage_id: str, stype: str = "overall") -> Optional[List]:
    """Get tournament standings (overall/home/away)."""
    return api_get(
        "/tournaments/standings",
        params={
            "tournament_id": tournament_id,
            "tournament_stage_id": tournament_stage_id,
            "type": stype,
        },
    )


def fetch_match_standings_form(event_id: str, stype: str = "overall") -> Optional[List]:
    """Get recent form standings for teams in the match context."""
    return api_get(
        "/matches/standings/form",
        params={"match_id": event_id, "type": stype},
    )


def fetch_match_standings_overunder(event_id: str, sub_type: str = "2.5", stype: str = "overall") -> Optional[List]:
    """Get Over/Under standings for the match context."""
    return api_get(
        "/matches/standings/over-under",
        params={"match_id": event_id, "type": stype, "sub_type": sub_type},
    )


def fetch_match_standings_htft(event_id: str, stype: str = "overall") -> Optional[List]:
    """Get HT/FT standings for the match context."""
    return api_get(
        "/matches/standings/ht-ft",
        params={"match_id": event_id, "type": stype},
    )


def fetch_match_top_scorers(event_id: str) -> Optional[List]:
    """Get top scorers related to the match."""
    return api_get("/matches/standings/top-scorers", params={"match_id": event_id})


def fetch_tournament_top_scorers(tournament_id: str, tournament_stage_id: str) -> Optional[List]:
    """Get tournament top scorers."""
    return api_get(
        "/tournaments/standings/top-scorers",
        params={"tournament_id": tournament_id, "tournament_stage_id": tournament_stage_id},
    )


# =============================================================================
# NORMALIZE FUNCTIONS
# =============================================================================

def normalize_odds(odds_data: List, home_epid: str, away_epid: str) -> Dict:
    """
    Extract and normalize the most relevant odds markets.
    Returns available markets + best odds for 1X2, Over/Under, BTTS.
    """
    result = {
        "available_markets": [],
        "odds_home": None,
        "odds_draw": None,
        "odds_away": None,
        "odds_over_25": None,
        "odds_under_25": None,
        "odds_btts_yes": None,
        "odds_btts_no": None,
        "warnings": [],
    }

    if not odds_data:
        result["warnings"].append("No odds data available [N/A]")
        return result

    all_markets = set()

    for bookmaker in odds_data:
        for market_group in bookmaker.get("odds", []):
            betting_type = market_group.get("bettingType", "")
            scope = market_group.get("bettingScope", "")
            key = f"{scope}_{betting_type}"
            all_markets.add(key)

            if betting_type == "HOME_DRAW_AWAY" and scope == "FULL_TIME":
                for odd in market_group.get("odds", []):
                    epid = odd.get("eventParticipantId")
                    val = _parse_odd(odd.get("value"))
                    if epid == home_epid:
                        result["odds_home"] = _best_odd(result["odds_home"], val)
                    elif epid == away_epid:
                        result["odds_away"] = _best_odd(result["odds_away"], val)
                    elif epid is None:
                        result["odds_draw"] = _best_odd(result["odds_draw"], val)

            elif betting_type == "OVER_UNDER" and scope == "FULL_TIME":
                # Line (e.g. 2.5) is in handicap.value, selection is OVER/UNDER
                for odd in market_group.get("odds", []):
                    handicap = odd.get("handicap") or {}
                    line = str(handicap.get("value", ""))
                    sel = (odd.get("selection") or "").upper()
                    val = _parse_odd(odd.get("value"))
                    if line == "2.5":
                        if sel == "OVER":
                            result["odds_over_25"] = _best_odd(result["odds_over_25"], val)
                        elif sel == "UNDER":
                            result["odds_under_25"] = _best_odd(result["odds_under_25"], val)

            elif betting_type == "BOTH_TEAMS_TO_SCORE" and scope == "FULL_TIME":
                for odd in market_group.get("odds", []):
                    btts = odd.get("bothTeamsToScore")
                    val = _parse_odd(odd.get("value"))
            
                    if btts is True:
                        result["odds_btts_yes"] = _best_odd(result["odds_btts_yes"], val)
                    elif btts is False:
                        result["odds_btts_no"] = _best_odd(result["odds_btts_no"], val)

    result["available_markets"] = sorted(list(all_markets))
    return result


def _parse_odd(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _best_odd(current: Optional[float], new: Optional[float]) -> Optional[float]:
    """Prefer higher odds (best market value)."""
    if current is None:
        return new
    if new is None:
        return current
    return max(current, new)


def normalize_implied_probs(odds_data: Dict) -> Dict:
    """Calculate implied probabilities from normalized odds."""
    probs = {}
    for market, odd_key in [
        ("prob_home", "odds_home"),
        ("prob_draw", "odds_draw"),
        ("prob_away", "odds_away"),
        ("prob_over_25", "odds_over_25"),
        ("prob_btts_yes", "odds_btts_yes"),
    ]:
        odd = odds_data.get(odd_key)
        if odd and odd > 0:
            probs[market] = round((1 / odd) * 100, 2)
        else:
            probs[market] = None
    return probs


def normalize_h2h(h2h_data: List) -> Dict:
    """
    Normalize H2H records.
    Discard incoherent records (e.g., score parse fails).
    Returns list of valid matches + summary stats.
    """
    if not h2h_data:
        return {"records": [], "summary": None, "warnings": ["H2H data not available [N/A]"]}

    records = []
    home_wins, away_wins, draws = 0, 0, 0
    total_goals = 0
    warnings = []

    for match in h2h_data:
        try:
            scores = match.get("scores", {})
            home_score = int(scores.get("home", 0) or 0)
            away_score = int(scores.get("away", 0) or 0)
        except (TypeError, ValueError):
            warnings.append(f"Skipped H2H record with unparseable score: {match.get('match_id')}")
            continue

        if home_score is None or away_score is None:
            continue

        total_goals += home_score + away_score
        status = match.get("status", "").upper()
        tournament = match.get("tournament_name", "")

        records.append({
            "match_id": match.get("match_id"),
            "timestamp": match.get("timestamp"),
            "tournament": None if not tournament else tournament,
            "home_team": match.get("home_team", {}).get("name"),
            "away_team": match.get("away_team", {}).get("name"),
            "home_score": home_score,
            "away_score": away_score,
            "status": None if not status else status,
        })

        if status == "W":
            home_wins += 1
        elif status == "L":
            away_wins += 1
        else:
            draws += 1

    total = len(records)
    avg_goals = round(total_goals / total, 2) if total > 0 else None

    summary = None
    if total > 0:
        summary = {
            "total_matches": total,
            "home_wins": home_wins,
            "draws": draws,
            "away_wins": away_wins,
            "avg_goals": avg_goals,
        }

    return {
        "records": records,
        "summary": summary,
        "warnings": [] if not warnings else warnings,
    }


def build_h2h_from_results(team_home_results: Dict, team_away_results: Dict, home_name: str, away_name: str) -> Dict:
    """
    Build H2H records from the two teams' match histories.
    Filters matches where the opponent was the direct rival.
    This replaces the separate H2H API call to avoid redundancy.
    """
    match_map: Dict[str, Dict] = {}
    home_matches = team_home_results.get("matches", [])
    away_matches = team_away_results.get("matches", [])

    def to_actual_scores(m: Dict) -> tuple[int, int]:
        """
        Convert team-perspective goals_for/goals_against into actual
        home_score and away_score based on team_is_home.
        """
        gf = m.get("goals_for", 0)
        ga = m.get("goals_against", 0)
        is_home = m.get("team_is_home")

        if is_home is True:
            return gf, ga
        else:
            return ga, gf

    def to_actual_teams(m: Dict, team_name: str) -> tuple[str, str]:
        """
        Resolve actual home_team and away_team names using team_is_home.
        """
        opponent = m.get("opponent", "")
        is_home = m.get("team_is_home")

        if is_home is True:
            return team_name, opponent
        else:
            return opponent, team_name

    # From home team's history
    for m in home_matches:
        if m.get("opponent") == away_name:
            mid = m.get("match_id")
            home_score, away_score = to_actual_scores(m)
            actual_home_team, actual_away_team = to_actual_teams(m, home_name)

            match_map[mid] = {
                "match_id": mid,
                "timestamp": m.get("timestamp"),
                "home_score": home_score,
                "away_score": away_score,
                "home_team": actual_home_team,
                "away_team": actual_away_team,
                "tournament_id": m.get("tournament_id", ""),
                "tournament_name": m.get("tournament_name", ""),
            }

    # From away team's history
    for m in away_matches:
        if m.get("opponent") == home_name:
            mid = m.get("match_id")
            if mid in match_map:
                continue

            home_score, away_score = to_actual_scores(m)
            actual_home_team, actual_away_team = to_actual_teams(m, away_name)

            match_map[mid] = {
                "match_id": mid,
                "timestamp": m.get("timestamp"),
                "home_score": home_score,
                "away_score": away_score,
                "home_team": actual_home_team,
                "away_team": actual_away_team,
                "tournament_id": m.get("tournament_id", ""),
                "tournament_name": m.get("tournament_name", ""),
            }

    records = sorted(match_map.values(), key=lambda r: r.get("timestamp") or 0, reverse=True)

    total_goals = 0
    home_wins, away_wins, draws = 0, 0, 0

    for r in records:
        gf = r["home_score"]
        gc = r["away_score"]
        total_goals += gf + gc

        # Ojo: aquí "home_wins" y "away_wins" significan local/visitante real,
        # NO team_home vs team_away del análisis
        if gf > gc:
            home_wins += 1
        elif gf == gc:
            draws += 1
        else:
            away_wins += 1

    total = len(records)
    avg_goals = round(total_goals / total, 2) if total > 0 else None

    summary = None
    if total > 0:
        summary = {
            "total_matches": total,
            "home_wins": home_wins,
            "draws": draws,
            "away_wins": away_wins,
            "avg_goals": avg_goals,
        }

    return {
        "records": records,
        "summary": summary,
        "warnings": [],
    }


def normalize_team_results(team_results_data: Dict, team_name: str, team_id: str) -> Dict:
    """
    Normalize a team's match history.
    Compute form (W/D/L), points, GF/GA averages, Over 2.5/BTTS frequency.
    """
    if not team_results_data:
        return {"matches": [], "form": None, "warnings": [f"Team results not available for {team_name} [N/A]"]}

    leagues = team_results_data if isinstance(team_results_data, list) else [team_results_data]
    all_matches = []

    for league_block in leagues:
        for league in league_block.get("leagues", []) if "leagues" in league_block else [league_block]:
            tournament_id = league.get("tournament_id")
            tournament_name = league.get("full_name")
            
            for match in league.get("matches", []):
                try:
                    ts = match.get("timestamp")
                    home_t = match.get("home_team", {})
                    away_t = match.get("away_team", {})
                    scores = match.get("scores", {})

                    h_score = int(scores.get("home", 0) or 0)
                    a_score = int(scores.get("away", 0) or 0)

                    # The API returns the team in the "away_team" field of the response,
                    # regardless of whether they were home or away in the actual match.
                    # We determine their real role by checking which field contains them.
                    team_in_home = home_t.get("team_id") == team_id
                    team_in_away = away_t.get("team_id") == team_id

                    if team_in_home and not team_in_away:
                        # Team was actually home in this match
                        is_home = True
                        opponent_name = away_t.get("name")
                        goals_for = h_score
                        goals_against = a_score
                    elif team_in_away and not team_in_home:
                        # Team was actually away in this match
                        is_home = False
                        opponent_name = home_t.get("name")
                        goals_for = a_score
                        goals_against = h_score
                    else:
                        # Team not found in either position — skip
                        continue

                    all_matches.append({
                        "tournament_id": tournament_id,
                        "tournament_name": tournament_name,
                        "match_id": match.get("match_id"),
                        "timestamp": ts,
                        "team_is_home": is_home,
                        "opponent": opponent_name,
                        "goals_for": goals_for,
                        "goals_against": goals_against,
                        "total_goals": h_score + a_score,
                        "both_teams_scored": h_score > 0 and a_score > 0,
                    })
                except (TypeError, ValueError):
                    continue

    # Sort by timestamp descending (most recent first)
    all_matches.sort(key=lambda m: m.get("timestamp") or 0, reverse=True)
    last_n = all_matches[:15]  # last 15

    form_records = []
    pts = 0
    gf = 0
    gc = 0
    over_count = 0
    btts_count = 0

    for m in last_n:
        gf += m["goals_for"]
        gc += m["goals_against"]
        if m["total_goals"] > 2.5:
            over_count += 1
        if m["both_teams_scored"]:
            btts_count += 1

        if m["goals_for"] > m["goals_against"]:
            form_records.append("W")
            pts += 3
        elif m["goals_for"] == m["goals_against"]:
            form_records.append("D")
            pts += 1
        else:
            form_records.append("L")

    n = len(last_n)
    form_string = "".join(form_records) if form_records else None

    result = {
        "matches": all_matches,
        "form": {
            "last_n": n,
            "form_string": form_string,
            "points": pts,
            "gf_avg": round(gf / n, 2) if n > 0 else None,
            "gc_avg": round(gc / n, 2) if n > 0 else None,
            "over_25_freq": f"{over_count}/{n}" if n > 0 else None,
            "btts_freq": f"{btts_count}/{n}" if n > 0 else None,
        },
        "warnings": [],
    }

    # Home / away split
    home_matches = [m for m in last_n if m["team_is_home"]]
    away_matches = [m for m in last_n if not m["team_is_home"]]

    if home_matches:
        h_pts = 0
        h_gf = sum(m["goals_for"] for m in home_matches)
        h_gc = sum(m["goals_against"] for m in home_matches)
        for m in home_matches:
            if m["goals_for"] > m["goals_against"]:
                h_pts += 3
            elif m["goals_for"] == m["goals_against"]:
                h_pts += 1
        result["form"]["home_ppg"] = round(h_pts / len(home_matches), 2)
        result["form"]["home_gf_avg"] = round(h_gf / len(home_matches), 2)
        result["form"]["home_gc_avg"] = round(h_gc / len(home_matches), 2)

    if away_matches:
        a_pts = 0
        a_gf = sum(m["goals_for"] for m in away_matches)
        a_gc = sum(m["goals_against"] for m in away_matches)
        for m in away_matches:
            if m["goals_for"] > m["goals_against"]:
                a_pts += 3
            elif m["goals_for"] == m["goals_against"]:
                a_pts += 1
        result["form"]["away_ppg"] = round(a_pts / len(away_matches), 2)
        result["form"]["away_gf_avg"] = round(a_gf / len(away_matches), 2)
        result["form"]["away_gc_avg"] = round(a_gc / len(away_matches), 2)

    return result


def _parse_pass_stat(value: Any) -> Dict:
    """
    Parse pass-type stat strings like '81% (256/316)'.
    Returns {pct: float, completed: int, attempted: int}.
    """
    if not isinstance(value, str):
        return {"pct": None, "completed": None, "attempted": None}

    pct_match = re.match(r"(\d+(?:\.\d+)?)", value)
    pct = float(pct_match.group(1)) if pct_match else None

    paren_match = re.search(r"\((\d+)/(\d+)\)", value)
    if paren_match:
        completed = int(paren_match.group(1))
        attempted = int(paren_match.group(2))
    else:
        completed = None
        attempted = None

    return {"pct": pct, "completed": completed, "attempted": attempted}


def normalize_match_status(status_data: Optional[Dict]) -> str:
    """
    Normalize match status object to a flat string:
    'notstarted', 'inprogress', 'finished'.
    """
    if not status_data:
        return "notstarted"

    is_started = status_data.get("is_started", False)
    is_finished = status_data.get("is_finished", False)
    is_in_progress = status_data.get("is_in_progress", False)

    if is_finished:
        return "finished"
    elif is_in_progress:
        return "inprogress"
    elif is_started:
        return "inprogress"  # started but not yet in-progress = kickoff moment
    else:
        return "notstarted"


def _parse_pass_stat(value: Any) -> Dict:
    """
    Parse pass-type stat strings like '81% (256/316)'.
    Returns {pct: float, completed: int, attempted: int}.
    """
    if value is None:
        return {"pct": None, "completed": None, "attempted": None}
    if isinstance(value, (int, float)):
        return {"pct": float(value), "completed": None, "attempted": None}
    s = str(value)
    pct_match = re.match(r"(\d+(?:\.\d+)?)%", s)
    pct = float(pct_match.group(1)) if pct_match else None
    bracket_match = re.search(r"\((\d+)/(\d+)\)", s)
    if bracket_match:
        completed = int(bracket_match.group(1))
        attempted = int(bracket_match.group(2))
    else:
        completed = attempted = None
    return {"pct": pct, "completed": completed, "attempted": attempted}


def _parse_possession(value: Any) -> Optional[float]:
    """Parse possession value like '46%' to float 46.0."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.match(r"(\d+(?:\.\d+)?)", value)
        return float(m.group(1)) if m else None
    return None

def normalize_match_stats(stats_data: Any, home_team_name: str, away_team_name: str) -> Dict:
    """
    Normalize match statistics.
    Extract possession, shots, corners, cards, xG, etc.
    Handles FlashScore API returning full-time, first-half, second-half blocks
    in the same list — keeps only the first occurrence of each stat name
    to avoid duplicates (first occurrence = full-time).
    """
    if not stats_data:
        return {"stats": [], "warnings": ["Match stats not available [N/A]"]}

    # The API returns stats_data as {"match": [...list of stat entries...]}
    # where the list mixes full-time, 1st-half, 2nd-half blocks.
    # We iterate once, deduplicating by name (first occurrence wins).
    raw_list = stats_data.get("match", []) if isinstance(stats_data, dict) else (stats_data or [])

    seen_names: set = set()
    unique_list: List[Dict] = []
    for stat in raw_list:
        name = stat.get("name", "")
        if name and name not in seen_names:
            seen_names.add(name)
            unique_list.append(stat)

    normalized = []
    stat_dict: Dict[str, Dict] = {}

    pass_types = {"Passes", "Long passes", "Crosses", "Passes in final third"}

    for stat in unique_list:
        name = stat.get("name", "")
        home_val = stat.get("home_team")
        away_val = stat.get("away_team")
        home_pct = None
        away_pct = None

        if name in pass_types and isinstance(home_val, str):
            # e.g. "81% (256/316)"
            hp = _parse_pass_stat(home_val)
            ap = _parse_pass_stat(away_val)
            home_pct = hp["pct"]
            away_pct = ap["pct"]
            home_val = hp["completed"]
            away_val = ap["completed"]
        elif isinstance(home_val, str) and "%" in home_val:
            m = re.match(r"(\d+(?:\.\d+)?)", home_val)
            home_pct = home_val
            home_val = float(m.group(1)) if m else None
        elif isinstance(away_val, str) and "%" in away_val:
            m = re.match(r"(\d+(?:\.\d+)?)", away_val)
            away_pct = away_val
            away_val = float(m.group(1)) if m else None

        rec = {
            "name": name,
            "home_team": home_val,
            "away_team": away_val,
            "home_pct": home_pct,
            "away_pct": away_pct,
        }
        normalized.append(rec)
        stat_dict[name] = rec

    result: Dict[str, Any] = {"stats": normalized, "warnings": []}

    def get_num(name: str, side: str) -> Optional[float]:
        s = stat_dict.get(name)
        if s:
            val = s.get(side)
            if isinstance(val, (int, float)):
                return float(val)
        return None

    def get_pct(name: str, side: str) -> Optional[float]:
        s = stat_dict.get(name)
        if s:
            # side is "home_team" or "away_team", pct key is "home_pct" or "away_pct"
            pct_key = side.replace("_team", "_pct")  # home_team -> home_pct
            return s.get(pct_key)
        return None

    result["possession"] = {"home": get_num("Ball possession", "home_team"), "away": get_num("Ball possession", "away_team")}
    result["total_shots"] = {"home": get_num("Total shots", "home_team"), "away": get_num("Total shots", "away_team")}
    result["shots_on_target"] = {"home": get_num("Shots on target", "home_team"), "away": get_num("Shots on target", "away_team")}
    result["corners"] = {"home": get_num("Corner kicks", "home_team"), "away": get_num("Corner kicks", "away_team")}
    result["yellow_cards"] = {"home": get_num("Yellow cards", "home_team"), "away": get_num("Yellow cards", "away_team")}
    result["red_cards"] = {"home": get_num("Red cards", "home_team"), "away": get_num("Red cards", "away_team")}
    result["xg"] = {"home": get_num("Expected goals (xG)", "home_team"), "away": get_num("Expected goals (xG)", "away_team")}
    result["xgotal"] = {"home": get_num("xG on target (xGOT)", "home_team"), "away": get_num("xG on target (xGOT)", "away_team")}

    # Pass stats with structured breakdown
    result["passes"] = {
        "home": {"accuracy_pct": get_pct("Passes", "home_team"), "completed": get_num("Passes", "home_team")},
        "away": {"accuracy_pct": get_pct("Passes", "away_team"), "completed": get_num("Passes", "away_team")},
    }

    return result


def normalize_player_stats(player_data: Any, home_team_id: str, away_team_id: str) -> Dict:
    """
    Normalize per-player stats.
    Returns top players per team by goals, assists, shots, key_passes.
    """
    if not player_data:
        return {"home_players": [], "away_players": [], "warnings": ["Player stats not available [N/A]"]}

    all_players = player_data.get("players", []) if isinstance(player_data, dict) else []

    home_players = []
    away_players = []

    for p in all_players:
        pid = p.get("player_id")
        tid = p.get("team_id")
        stats = p.get("stats", {})

        def g(key):
            s = stats.get(key, {})
            v = s.get("value", "0")
            try:
                return int(v)
            except (TypeError, ValueError):
                return 0

        player_rec = {
            "player_id": pid,
            "name": p.get("name"),
            "short_name": p.get("short_name"),
            "position": p.get("position"),
            "in_base_lineup": p.get("in_base_lineup"),
            "goals": g("GOALS"),
            "assists": g("ASSISTS_GOAL"),
            "shots": g("TOTAL_SHOTS"),
            "shots_on_target": g("SHOTS_ON_TARGET_STATE"),
            "key_passes": g("KEY_PASSES"),
            "tackles_won": g("TACKLES_WON"),
            "interceptions": g("INTERCEPTIONS"),
            "ball_recoveries": g("BALL_RECOVERIES"),
            "yellow_cards": g("CARDS_YELLOW"),
            "red_cards": g("CARDS_RED"),
            "minutes": g("MINUTES"),
        }

        if tid == home_team_id:
            home_players.append(player_rec)
        elif tid == away_team_id:
            away_players.append(player_rec)

    def top_by_metric(players: List, metric: str, n: int = 5) -> List:
        valid = [p for p in players if p.get(metric, 0) > 0]
        return sorted(valid, key=lambda x: x.get(metric, 0), reverse=True)[:n]

    return {
        "home_players": home_players,
        "away_players": away_players,
        "top_scorers_home": top_by_metric(home_players, "goals"),
        "top_scorers_away": top_by_metric(away_players, "goals"),
        "top_assists_home": top_by_metric(home_players, "assists"),
        "top_assists_away": top_by_metric(away_players, "assists"),
        "top_shots_home": top_by_metric(home_players, "shots"),
        "top_shots_away": top_by_metric(away_players, "shots"),
        "top_key_passes_home": top_by_metric(home_players, "key_passes"),
        "top_key_passes_away": top_by_metric(away_players, "key_passes"),
        "warnings": [],
    }


def normalize_lineups(lineup_data: Any, home_team_id: str, away_team_id: str) -> Dict:
    """
    Normalize lineups + extract missingPlayers for each team.
    """
    if not lineup_data:
        return {"home": None, "away": None, "warnings": ["Lineup data not available [N/A]"]}

    result = {"home": None, "away": None, "warnings": []}

    for team_block in lineup_data:
        side = team_block.get("side")
        formation = team_block.get("predictedFormation")
        players = team_block.get("predictedLineups", [])
        missing = team_block.get("missingPlayers", [])
        unsure = team_block.get("unsureMissingPlayers", [])

        team_data = {
            "formation": formation,
            "lineup_count": len(players),
            "missing_players": [
                {
                    "name": m.get("name"),
                    "player_id": m.get("player_id"),
                    "reason": m.get("reason"),
                    "country": m.get("country_name"),
                }
                for m in missing
            ],
            "unsure_missing": [
                {
                    "name": u.get("name"),
                    "player_id": u.get("player_id"),
                    "reason": u.get("reason"),
                    "country": u.get("country_name"),
                }
                for u in unsure
            ],
        }

        if side == "home":
            result["home"] = team_data
        elif side == "away":
            result["away"] = team_data

    return result


def detect_event_type(players: List[Dict], description: str = "") -> str:
    """
    Detect normalized event type from players/types/description.
    Returns one of:
    - goal
    - own_goal
    - penalty_goal
    - missed_penalty
    - yellow_card
    - red_card
    - second_yellow_red
    - substitution
    - var
    - unknown
    """
    desc_l = (description or "").lower()
    player_types = [str(p.get("type", "")).lower() for p in players]

    # Priority matters
    for t in player_types:
        if "substitution" in t:
            return "substitution"
        if "second yellow" in t:
            return "second_yellow_red"
        if "red" in t:
            return "red_card"
        if "yellow" in t:
            return "yellow_card"
        if "own goal" in t:
            return "own_goal"
        if "missed penalty" in t or "penalty missed" in t:
            return "missed_penalty"
        if "penalty" in t and "goal" in t:
            return "penalty_goal"
        if "goal" in t:
            return "goal"
        if "var" in t:
            return "var"

    # Fallback with description
    if "substitution" in desc_l:
        return "substitution"
    if "second yellow" in desc_l:
        return "second_yellow_red"
    if "red" in desc_l:
        return "red_card"
    if "yellow" in desc_l:
        return "yellow_card"
    if "own goal" in desc_l:
        return "own_goal"
    if "missed penalty" in desc_l or "penalty missed" in desc_l:
        return "missed_penalty"
    if "penalty" in desc_l and "goal" in desc_l:
        return "penalty_goal"
    if "goal" in desc_l:
        return "goal"
    if "var" in desc_l:
        return "var"

    return "unknown"

def normalize_summary(summary_data: Any) -> Dict:
    """
    Normalize match summary including all events:
    goals, cards, substitutions, VAR, penalties, etc.
    """
    if not summary_data:
        return {"events": [], "goals_home": 0, "goals_away": 0, "warnings": []}

    events = []
    goals_home, goals_away = 0, 0

    for evt in summary_data:
        minutes = evt.get("minutes")
        team = evt.get("team")
        desc = evt.get("description", "") or ""
        players = evt.get("players", []) or []

        event_type = detect_event_type(players, desc)

        # Count scoreboard goals only
        # Normally own goals still count to scoreboard, but the API team field
        # usually indicates the side associated with the event. If later you detect
        # own-goal semantics differently, you can adjust this rule.
        if event_type in {"goal", "penalty_goal", "own_goal"}:
            if team == "home":
                goals_home += 1
            elif team == "away":
                goals_away += 1

        events.append({
            "minutes": minutes,
            "team": team,
            "type": event_type,
            "description": desc,
            "players": [
                {
                    "name": p.get("name"),
                    "type": p.get("type"),
                }
                for p in players
            ]
        })

    return {
        "events": events,
        "goals_home": goals_home,
        "goals_away": goals_away,
        "warnings": [],
    }

def normalize_standings(standings_data: List, team_ids: set) -> Dict:
    """
    Extract standings rows for the two teams in the match.
    """
    if not standings_data:
        return {"teams": {}, "warnings": ["Standings not available [N/A]"]}

    teams = {}
    for row in standings_data:
        tid = row.get("team_id")
        if tid in team_ids:
            teams[tid] = {
                "position": None,  # will be set by enumerate
                "name": row.get("name"),
                "matches_played": row.get("matches_played"),
                "wins": row.get("wins"),
                "draws": row.get("draws"),
                "losses": row.get("losses"),
                "goals": row.get("goals"),
                "goal_difference": row.get("goal_difference"),
                "points": row.get("points"),
            }

    # Assign positions
    sorted_teams = sorted(standings_data, key=lambda x: x.get("points", 0), reverse=True)
    for idx, row in enumerate(sorted_teams):
        tid = row.get("team_id")
        if tid in teams and teams[tid]:
            teams[tid]["position"] = idx + 1

    return {"teams": teams, "warnings": []}


def normalize_overunder_st(ou_data: List, team_ids: set) -> Dict:
    """Extract Over/Under standings for both teams."""
    if not ou_data:
        return {"teams": {}, "warnings": ["Over/Under standings not available [N/A]"]}

    teams = {}
    for row in ou_data:
        tid = row.get("team_id")
        if tid in team_ids:
            teams[tid] = {
                "name": row.get("name"),
                "matches_played": row.get("matches_played"),
                "over": row.get("over"),
                "under": row.get("under"),
                "average_goals": row.get("average_goals_per_match"),
            }
    return {"teams": teams, "warnings": []}


def normalize_form_st(form_data: List, team_ids: set) -> Dict:
    """Extract form standings (last 5 matches) for both teams."""
    if not form_data:
        return {"teams": {}, "warnings": ["Form standings not available [N/A]"]}

    teams = {}
    for row in form_data:
        tid = row.get("team_id")
        if tid in team_ids:
            teams[tid] = {
                "name": row.get("name"),
                "matches_played": row.get("matches_played"),
                "wins": row.get("wins"),
                "draws": row.get("draws"),
                "losses": row.get("losses"),
                "goals": row.get("goals"),
                "goal_difference": row.get("goal_difference"),
                "points": row.get("points"),
            }
    return {"teams": teams, "warnings": []}


def normalize_top_scorers(scorers_data: List, team_ids: set) -> Dict:
    """Extract top scorers for the tournament, filtered by the two teams."""
    if not scorers_data:
        return {"home_scorers": [], "away_scorers": [], "warnings": ["Top scorers not available [N/A]"]}

    home_scorers = []
    away_scorers = []

    for s in scorers_data:
        tid = s.get("team_id")
        rec = {
            "name": s.get("player_name"),
            "player_id": s.get("player_id"),
            "team": s.get("team_name"),
            "goals": s.get("goals"),
            "assists": s.get("assists"),
        }
        if tid == team_ids.get("home"):
            home_scorers.append(rec)
        elif tid == team_ids.get("away"):
            away_scorers.append(rec)

    return {
        "home_scorers": sorted(home_scorers, key=lambda x: x.get("goals", 0), reverse=True),
        "away_scorers": sorted(away_scorers, key=lambda x: x.get("goals", 0), reverse=True),
        "warnings": [],
    }


# =============================================================================
# AGGREGATE / CROSS-FUNCTION INDICATORS
# =============================================================================

def compute_offensive_dependency(player_stats: Dict, team_results: Dict, top_scorers: Dict) -> List[Dict]:
    """
    Compute offensive dependency: what % of team goals does each top scorer represent.
    Returns list of {player, team, goals_team, goals_player, pct, dependency_level}.
    """
    indicators = []

    for side in ["home", "away"]:
        scorers = top_scorers.get(f"{side}_scorers", [])
        results = team_results.get(side, {})
        form = results.get("form", {})
        total_gf = form.get("gf_avg") or 0
        n = form.get("last_n", 0)
        total_goals_team = (total_gf * n) if total_gf and n else 0

        for s in scorers[:3]:
            goals_p = s.get("goals", 0)
            if total_goals_team > 0:
                pct = round((goals_p / total_goals_team) * 100, 1)
            else:
                pct = None

            dep_level = None
            if pct is not None:
                if pct > 50:
                    dep_level = "alta"
                elif pct > 30:
                    dep_level = "moderada"
                elif pct is not None:
                    dep_level = "baja"

            indicators.append({
                "side": side,
                "player": s.get("name"),
                "team_goals_in_sample": total_goals_team,
                "player_goals": goals_p,
                "pct_team_goals": pct,
                "dependency": dep_level,
            })

    return indicators


def compute_sample_stability(team_results: Dict) -> Dict:
    """Check if the sample size (N matches) is reliable for indicators."""
    stabilities = {}
    for side in ["home", "away"]:
        results = team_results.get(side, {})
        form = results.get("form", {})
        n = form.get("last_n", 0)
        if n >= 5:
            stabilities[side] = {"n": n, "stability": "suficiente"}
        elif n >= 3:
            stabilities[side] = {"n": n, "stability": "limitada"}
        else:
            stabilities[side] = {"n": n, "stability": "muy_limitada"}
    return stabilities


def detect_h2h_inconsistencies(h2h: Dict) -> List[str]:
    """Check H2H for suspicious patterns."""
    warnings = []
    records = h2h.get("records", [])
    if not records:
        return warnings

    # Check for future dates (shouldn't happen but check anyway)
    now = datetime.now().timestamp()
    future = [r for r in records if r.get("timestamp", 0) > now]
    if future:
        warnings.append(f"H2H contains {len(future)} future-dated records (possible data issue)")

    # Check for very high-scoring matches (potential data error if avg > 5)
    if h2h.get("summary") and h2h["summary"].get("avg_goals"):
        if h2h["summary"]["avg_goals"] > 5:
            warnings.append(f"H2H avg goals unusually high: {h2h['summary']['avg_goals']}")

    return warnings


def validate_data_completeness(ctx: Dict) -> Dict[str, List[str]]:
    """
    Cross-check: do stats suggest one team is stronger but odds don't reflect?
    Returns a dict with warnings categorized by section.
    """
    result: Dict[str, List[str]] = {
        "team_home_results": [],
        "team_away_results": [],
        "odds": [],
    }

    odds = ctx.get("odds", {})
    team_h = ctx.get("team_home_results", {}).get("form", {})
    team_a = ctx.get("team_away_results", {}).get("form", {})

    # Check sample stability
    for side, label, key in [("home", "Home", "team_home_results"), ("away", "Away", "team_away_results")]:
        form = team_h if side == "home" else team_a
        n = form.get("last_n", 0)
        if n < 3:
            result[key].append(f"{label} team form sample too small (N={n}) [IND]")

    # Check if market is coherent with form
    prob_h = odds.get("prob_home")
    if prob_h and team_h.get("gf_avg") and team_a.get("gf_avg"):
        form_diff = team_h["gf_avg"] - team_a["gf_avg"]
        if form_diff > 0.5 and prob_h < 40:
            result["odds"].append("Market undervaluing home team despite stronger recent form [IND]")
        elif form_diff < -0.5 and prob_h > 60:
            result["odds"].append("Market overvaluing home team despite weaker recent form [IND]")

    return result


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

def build_context(event_id: str, home_team_id: str, away_team_id: str) -> Dict:
    """
    Main function. Fetches all endpoints, normalizes, aggregates, returns final_context.
    """
    final = {
        "meta": {
            "event_id": event_id,
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "generated_at": datetime.now().isoformat(),
        },
        "match": {"warnings": []},
        "odds": {},
        "implied_probs": {},
        "h2h": {},
        "team_home_results": {},
        "team_away_results": {},
        "match_stats": {},
        "player_stats": {},
        "lineups": {},
        "summary": {},
        "preview": {},  # string o null — web scraping de FlashScore preview
        "commentary": None,
        "standings": {},
        "overunder_standings": {},
        "form_standings": {},
        "top_scorers": {},
        "tournament_top_scorers": {},
        "indicators": {},
    }

    # -------------------------------------------------------------------------
    # 1. MATCH DETAILS (blocking)
    # -------------------------------------------------------------------------
    details = fetch_match_details(event_id)

    if not details:
        final["match"]["warnings"].append("CRITICAL: Could not fetch match details. Analysis not viable.")
        return final

    home_epid = details.get("home_team", {}).get("event_participant_id")
    away_epid = details.get("away_team", {}).get("event_participant_id")
    home_url = details.get("home_team", {}).get("team_url")
    away_url = details.get("away_team", {}).get("team_url")
    home_name = details.get("home_team", {}).get("name")
    away_name = details.get("away_team", {}).get("name")
    tournament_id = details.get("tournament", {}).get("tournament_id")
    tournament_stage_id = details.get("tournament", {}).get("tournament_stage_id")
    tournament_name = details.get("tournament", {}).get("name")
    match_timestamp = details.get("timestamp")
    country = details.get("country", {}).get("name")
    referee = details.get("referee")

    final["match"] = {
        "event_id": event_id,
        "home_team": {"id": home_team_id, "name": home_name, "event_participant_id": home_epid},
        "away_team": {"id": away_team_id, "name": away_name, "event_participant_id": away_epid},
        "tournament": {"id": tournament_id, "stage_id": tournament_stage_id, "name": tournament_name},
        "country": country,
        "referee": referee,
        "timestamp": match_timestamp,
        "datetime": datetime.fromtimestamp(match_timestamp).isoformat() if match_timestamp else None,
        "status": normalize_match_status(details.get("match_status")),
        "scores": details.get("scores"),
        "warnings": [],
    }

    team_ids = {"home": home_team_id, "away": away_team_id}

    # -------------------------------------------------------------------------
    # 2. ODDS
    # -------------------------------------------------------------------------
    odds_raw = fetch_match_odds(event_id)
    # print(f"Fetched raw odds data: {odds_raw}")
    if odds_raw:
        final["odds"] = normalize_odds(odds_raw, home_epid, away_epid)
        final["implied_probs"] = normalize_implied_probs(final["odds"])
    else:
        final["odds"]["warnings"] = ["Odds not available [N/A]"]

    # -------------------------------------------------------------------------
    # 3. TEAM RESULTS (historical form) — H2H is built from these below
    # -------------------------------------------------------------------------
    tr_home = fetch_team_results(home_team_id)
    if tr_home is not None:
        final["team_home_results"] = normalize_team_results(tr_home, home_name, home_team_id)
    else:
        final["team_home_results"]["warnings"] = [f"Team results for {home_name} not available [N/A]"]

    tr_away = fetch_team_results(away_team_id)
    if tr_away is not None:
        final["team_away_results"] = normalize_team_results(tr_away, away_name, away_team_id)
    else:
        final["team_away_results"]["warnings"] = [f"Team results for {away_name} not available [N/A]"]

    # -------------------------------------------------------------------------
    # 4. H2H — built from team_results (no extra API call)
    # -------------------------------------------------------------------------
    h2h = build_h2h_from_results(
        final["team_home_results"],
        final["team_away_results"],
        home_name,
        away_name,
    )
    if h2h.get("records") and len(h2h["records"]) < 3:
        h2h["warnings"] = (h2h.get("warnings") or []) + ["derived_h2h_partial: fewer than 3 shared matches found"]
    final["h2h"] = h2h

    # -------------------------------------------------------------------------
    # 5. MATCH STATS
    # -------------------------------------------------------------------------
    final["match_stats"] = {"stats": [], "warnings": ["Match stats not available [N/A]"]}
    if final["match"]["status"] != "notstarted":
        stats_raw = fetch_match_stats(event_id)
        if stats_raw:
            final["match_stats"] = normalize_match_stats(stats_raw, home_name, away_name)

    # -------------------------------------------------------------------------
    # 6. PLAYER STATS
    # -------------------------------------------------------------------------
    ps_raw = fetch_match_player_stats(event_id)
    if ps_raw:
        final["player_stats"] = normalize_player_stats(ps_raw, home_team_id, away_team_id)
    else:
        final["player_stats"]["warnings"] = ["Player stats not available [N/A]"]

    # -------------------------------------------------------------------------
    # 7. LINEUPS / MISSING PLAYERS
    # -------------------------------------------------------------------------
    lineup_raw = fetch_match_lineups(event_id)
    if lineup_raw:
        final["lineups"] = normalize_lineups(lineup_raw, home_team_id, away_team_id)
    else:
        final["lineups"]["warnings"] = ["Lineup data not available [N/A]"]

    # -------------------------------------------------------------------------
    # 8. SUMMARY
    # -------------------------------------------------------------------------
    summary_raw = fetch_match_summary(event_id)
    if summary_raw:
        final["summary"] = normalize_summary(summary_raw)
    else:
        final["summary"]["warnings"] = ["Match summary not available [N/A]"]

    # -------------------------------------------------------------------------
    # 9. COMMENTARY (minute-by-minute live commentary — solo para partidos inprogress/finished, no para notstarted)
    # -------------------------------------------------------------------------
    final["commentary"] = []
    
    if final["match"]["status"] == "notstarted":
        final["commentary"] = {"warnings": ["Commentary not available for matches that have not started [N/A]"]}
    else:
        commentary_raw = fetch_match_commentary(event_id)
        if commentary_raw:
            final["commentary"] = commentary_raw

    # -------------------------------------------------------------------------
    # PREVIEW (web scraping)
    # -------------------------------------------------------------------------
    home_slug = {"slug": build_preview_slug(home_url), "id": home_team_id}
    away_slug = {"slug": build_preview_slug(away_url), "id": away_team_id}
    preview_raw = fetch_preview(home_slug, away_slug, event_id)
    final["preview"] = preview_raw
    if not preview_raw:
        final["preview"] = {"warnings": ["Match preview not available [N/A]"]}

    # -------------------------------------------------------------------------
    # 10. TOURNAMENT STANDINGS
    # -------------------------------------------------------------------------
    if tournament_id and tournament_stage_id:
        ts_raw = fetch_tournament_standings(tournament_id, tournament_stage_id)
        if ts_raw:
            final["standings"] = normalize_standings(ts_raw, team_ids)
        else:
            final["standings"]["warnings"] = ["Tournament standings not available [N/A]"]

    # -------------------------------------------------------------------------
    # 11. MATCH FORM STANDINGS
    # -------------------------------------------------------------------------
    form_st_raw = fetch_match_standings_form(event_id)
    if form_st_raw:
        final["form_standings"] = normalize_form_st(form_st_raw, team_ids)
    else:
        final["form_standings"]["warnings"] = ["Form standings not available [N/A]"]

    # -------------------------------------------------------------------------
    # 12. OVER/UNDER STANDINGS
    # -------------------------------------------------------------------------
    ou_raw = fetch_match_standings_overunder(event_id)
    if ou_raw:
        final["overunder_standings"] = normalize_overunder_st(ou_raw, team_ids)
    else:
        final["overunder_standings"]["warnings"] = ["Over/Under standings not available [N/A]"]

    # -------------------------------------------------------------------------
    # 13. MATCH TOP SCORERS
    # -------------------------------------------------------------------------
    mts_raw = fetch_match_top_scorers(event_id)
    if mts_raw:
        final["top_scorers"] = normalize_top_scorers(mts_raw, team_ids)
    else:
        final["top_scorers"]["warnings"] = ["Match top scorers not available [N/A]"]

    # -------------------------------------------------------------------------
    # 14. TOURNAMENT TOP SCORERS
    # -------------------------------------------------------------------------
    if tournament_id and tournament_stage_id:
        tts_raw = fetch_tournament_top_scorers(tournament_id, tournament_stage_id)
        if tts_raw:
            final["tournament_top_scorers"] = normalize_top_scorers(tts_raw, team_ids)
        else:
            final["tournament_top_scorers"]["warnings"] = ["Tournament top scorers not available [N/A]"]

    # -------------------------------------------------------------------------
    # 15. AGGREGATE INDICATORS
    # -------------------------------------------------------------------------
    final["indicators"]["offensive_dependency"] = compute_offensive_dependency(
        final["player_stats"],
        {"home": final["team_home_results"], "away": final["team_away_results"]},
        final["top_scorers"],
    )
    final["indicators"]["sample_stability"] = compute_sample_stability({
        "home": final["team_home_results"],
        "away": final["team_away_results"],
    })

    # H2H inconsistencies
    h2h_warnings = detect_h2h_inconsistencies(final["h2h"])
    final["h2h"]["warnings"].extend(h2h_warnings)

    # Cross-check warnings
    completeness = validate_data_completeness(final)
    final["team_home_results"]["warnings"].extend(completeness["team_home_results"])
    final["team_away_results"]["warnings"].extend(completeness["team_away_results"])
    final["odds"]["warnings"].extend(completeness["odds"])

    return final


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python build_match_context.py <event_id> <home_team_id> <away_team_id>", file=sys.stderr)
        sys.exit(1)

    event_id = sys.argv[1]
    home_team_id = sys.argv[2]
    away_team_id = sys.argv[3]
    
    ctx = build_context(event_id, home_team_id, away_team_id)

    # Output JSON to stdout
    print(json.dumps(ctx, indent=2, ensure_ascii=False))
