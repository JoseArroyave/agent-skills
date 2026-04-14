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

import os
import sys
import json
import time
import re
import html
import random
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime

# =============================================================================
# CONSTANTS
# =============================================================================

MAX_MATCHES = 10
MAX_WORKERS = 6
API_SLEEP_INITIAL = 1.0
API_SLEEP_BETWEEN = 0.4

# Football domain constants
PARTY_MINUTES = 90.0          # minutes per match for per-90 calculations
FORM_DIFF_THRESHOLD = 0.5    # goal-average threshold for market incoherence check
FAVOURITE_STRONG_THRESHOLD = 60.0   # market prob (%) for strong favourite
FAVOURITE_LEAN_THRESHOLD = 50.0     # market prob (%) for lean favourite
MAX_AVG_GOALS_H2H = 5        # alert threshold for H2H avg goals

# =============================================================================
# CONFIGURATION
# =============================================================================

def load_rapidapi_key() -> str:
    # 1. Environment variable (works in any agent/environment)
    env_key = os.environ.get("RAPIDAPI_KEY", "").strip()
    if env_key:
        return env_key

    # 2. Claude settings files (default for Claude Code users)
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

    # 3. Local .rapidapi_key file in the script's directory (fallback for other agents)
    script_dir = Path(__file__).parent
    local_key_file = script_dir / ".rapidapi_key"
    if local_key_file.exists():
        try:
            return local_key_file.read_text().strip()
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


def fetch_match_stats(event_id: str) -> Optional[Dict]:
    """Get match statistics (possession, shots, corners, cards, xG)."""
    return api_get("/matches/match/stats", params={"match_id": event_id})


def fetch_match_player_stats(event_id: str) -> Optional[Dict]:
    """Get per-player statistics for the match."""
    return api_get("/matches/match/player-stats", params={"match_id": event_id})


def fetch_match_lineups(event_id: str) -> Optional[List]:
    """Get lineups + missing players."""
    return api_get("/matches/match/lineups", params={"match_id": event_id})


def fetch_team_results(team_id: str, page: int = 1) -> Optional[Dict]:
    """Get recent match results for a team."""
    return api_get("/teams/results", params={"team_id": team_id, "page": page})


def build_preview_slug(team_url: str) -> str:
    """Convert team URL to URL slug format for FlashScore preview URL."""
    if not team_url: return ""
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
    text = text.replace("\\/", "/")
    text = fix_mojibake(text)

    # Remove sponsored section first (before tag replacements)
    text = re.split(r"Patrocinado:", text, flags=re.IGNORECASE)[0]

    # Structural replacements: close tag -> separator, open tag -> delete
    TAG_REPLACEMENTS = {
        "[/h2]": ". ", "[/p]": " ", "[/b]": "", "[/a]": "",
        "[h2]": "", "[p]": "", "[b]": "", "[a]": "",
    }
    for tag, replacement in TAG_REPLACEMENTS.items():
        text = text.replace(tag, replacement)

    # Remove remaining opening pseudo-tags like [a ...]
    text = re.sub(r"\[a[^\]]*\]", "", text)

    # Normalize whitespace
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

def _extract_1x2_odds(market_group: Dict, home_epid: str, away_epid: str) -> tuple:
    """Extract 1X2 odds. Returns (home, draw, away) odds."""
    home_odd, draw_odd, away_odd = None, None, None
    for odd in market_group.get("odds", []):
        epid = odd.get("eventParticipantId")
        val = parse_odd(odd.get("value"))
        if epid == home_epid:
            home_odd = best_odd(home_odd, val)
        elif epid == away_epid:
            away_odd = best_odd(away_odd, val)
        elif epid is None:
            draw_odd = best_odd(draw_odd, val)
    return home_odd, draw_odd, away_odd


def _extract_overunder_odds(market_group: Dict) -> tuple:
    """Extract Over/Under 2.5 odds. Returns (over_25, under_25)."""
    over_odd, under_odd = None, None
    for odd in market_group.get("odds", []):
        handicap = odd.get("handicap") or {}
        line = str(handicap.get("value", ""))
        sel = (odd.get("selection") or "").upper()
        val = parse_odd(odd.get("value"))
        if line == "2.5":
            if sel == "OVER":
                over_odd = best_odd(over_odd, val)
            elif sel == "UNDER":
                under_odd = best_odd(under_odd, val)
    return over_odd, under_odd


def _extract_btts_odds(market_group: Dict) -> tuple:
    """Extract BTTS odds. Returns (btts_yes, btts_no)."""
    yes_odd, no_odd = None, None
    for odd in market_group.get("odds", []):
        btts = odd.get("bothTeamsToScore")
        val = parse_odd(odd.get("value"))
        if btts is True:
            yes_odd = best_odd(yes_odd, val)
        elif btts is False:
            no_odd = best_odd(no_odd, val)
    return yes_odd, no_odd


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
                h, d, a = _extract_1x2_odds(market_group, home_epid, away_epid)
                result["odds_home"] = best_odd(result["odds_home"], h)
                result["odds_draw"] = best_odd(result["odds_draw"], d)
                result["odds_away"] = best_odd(result["odds_away"], a)

            elif betting_type == "OVER_UNDER" and scope == "FULL_TIME":
                o, u = _extract_overunder_odds(market_group)
                result["odds_over_25"] = best_odd(result["odds_over_25"], o)
                result["odds_under_25"] = best_odd(result["odds_under_25"], u)

            elif betting_type == "BOTH_TEAMS_TO_SCORE" and scope == "FULL_TIME":
                y, n = _extract_btts_odds(market_group)
                result["odds_btts_yes"] = best_odd(result["odds_btts_yes"], y)
                result["odds_btts_no"] = best_odd(result["odds_btts_no"], n)

    result["available_markets"] = sorted(list(all_markets))
    return result


def parse_odd(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def best_odd(current: Optional[float], new: Optional[float]) -> Optional[float]:
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


def _resolve_goals(m: Dict) -> tuple:
    """
    Extract goals_for, goals_against, total_goals from a match record.
    Supports two formats:
    - h2h: home_score, away_score + team_is_home
    - team results: goals_for, goals_against + total_goals
    Returns (goals_for, goals_against, total_goals).
    """
    if "home_score" in m and "away_score" in m:
        is_home = m.get("team_is_home", True)
        hs = m.get("home_score", 0) or 0
        aw = m.get("away_score", 0) or 0
        return (hs if is_home else aw), (aw if is_home else hs), hs + aw
    return (
        m.get("goals_for", 0) or 0,
        m.get("goals_against", 0) or 0,
        m.get("total_goals", 0),
    )


def _compute_results_basic_stats(matches: List[Dict]) -> Dict:
    """
    Compute basic stats (all_matches, form_string, points, gf_avg, gc_avg,
    over_25_freq, btts_freq, home_*/away_*) from a list of matches.
    """
    n = len(matches)
    if n == 0:
        return {
            "all_matches": 0, "form_string": None, "points": 0,
            "gf_avg": None, "gc_avg": None,
            "over_25_freq": None, "btts_freq": None,
        }

    form_records, pts = [], 0
    gf, gc = 0, 0
    over_count, btts_count = 0, 0

    for m in matches:
        goals_for, goals_against, total_goals = _resolve_goals(m)
        gf += goals_for
        gc += goals_against
        if total_goals > 2.5:
            over_count += 1
        if goals_for > 0 and goals_against > 0:
            btts_count += 1
        if goals_for > goals_against:
            form_records.append("W")
            pts += 3
        elif goals_for == goals_against:
            form_records.append("D")
            pts += 1
        else:
            form_records.append("L")

    result = {
        "all_matches": n,
        "form_string": "".join(form_records) or None,
        "points": pts,
        "gf_avg": round(gf / n, 2),
        "gc_avg": round(gc / n, 2),
        "over_25_freq": f"{over_count}/{n}",
        "btts_freq": f"{btts_count}/{n}",
    }

    home_matches = [m for m in matches if m.get("team_is_home")]
    away_matches = [m for m in matches if not m.get("team_is_home")]

    if home_matches:
        h_gf = sum(_resolve_goals(m)[0] for m in home_matches)
        h_gc = sum(_resolve_goals(m)[1] for m in home_matches)
        h_pts = sum(3 if _resolve_goals(m)[0] > _resolve_goals(m)[1]
                    else 1 if _resolve_goals(m)[0] == _resolve_goals(m)[1]
                    else 0 for m in home_matches)
        k = len(home_matches)
        result["home_ppg"] = round(h_pts / k, 2)
        result["home_gf_avg"] = round(h_gf / k, 2)
        result["home_gc_avg"] = round(h_gc / k, 2)

    if away_matches:
        a_gf = sum(_resolve_goals(m)[0] for m in away_matches)
        a_gc = sum(_resolve_goals(m)[1] for m in away_matches)
        a_pts = sum(3 if _resolve_goals(m)[0] > _resolve_goals(m)[1]
                    else 1 if _resolve_goals(m)[0] == _resolve_goals(m)[1]
                    else 0 for m in away_matches)
        k = len(away_matches)
        result["away_ppg"] = round(a_pts / k, 2)
        result["away_gf_avg"] = round(a_gf / k, 2)
        result["away_gc_avg"] = round(a_gc / k, 2)

    return result


def build_h2h_from_results(team_home_results: Dict, team_away_results: Dict, home_name: str, away_name: str) -> Dict:
    """
    Build H2H matches from the two teams' match histories.
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
            is_home = m.get("team_is_home", True)

            match_map[mid] = {
                "match_id": mid,
                "timestamp": m.get("timestamp"),
                "home_score": home_score,
                "away_score": away_score,
                "home_team": actual_home_team,
                "away_team": actual_away_team,
                "tournament_id": m.get("tournament_id", ""),
                "tournament_name": m.get("tournament_name", ""),
                "team_is_home": is_home,
            }

    # From away team's history
    for m in away_matches:
        if m.get("opponent") == home_name:
            mid = m.get("match_id")
            if mid in match_map:
                continue

            home_score, away_score = to_actual_scores(m)
            actual_home_team, actual_away_team = to_actual_teams(m, away_name)
            is_home = False  # away team in analysis was away in this match

            match_map[mid] = {
                "match_id": mid,
                "timestamp": m.get("timestamp"),
                "home_score": home_score,
                "away_score": away_score,
                "home_team": actual_home_team,
                "away_team": actual_away_team,
                "tournament_id": m.get("tournament_id", ""),
                "tournament_name": m.get("tournament_name", ""),
                "team_is_home": is_home,
            }

    matches = sorted(match_map.values(), key=lambda r: r.get("timestamp") or 0, reverse=True)

    # Compute form.basic from h2h matches (with team_is_home orientation)
    form_basic = _compute_results_basic_stats(matches)

    return {
        "matches": matches,
        "basic_stats": form_basic,
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
    all_matches = all_matches[:MAX_MATCHES]

    # Compute basic stats via shared helper
    basic_stats = _compute_results_basic_stats(all_matches)

    result = {
        "matches": all_matches,
        "basic_stats": basic_stats,
        "warnings": [],
    }

    return result


# =============================================================================
# ADVANCED STATS NORMALIZATION
# =============================================================================

STAT_NAME_TO_KEY = {
    "Expected goals (xG)": "xg",
    "Goals": "goals",
    "Ball possession": "possession",
    "Total shots": "shots",
    "Shots on target": "shots_on_target",
    "Shots off target": "shots_off_target",
    "Blocked shots": "blocked_shots",
    "Shots inside the box": "shots_inside_box",
    "Shots outside the box": "shots_outside_box",
    "Big chances": "big_chances",
    "Corner kicks": "corners",
    "Touches in opposition box": "touches_in_opposition_box",
    "Hit the woodwork": "hit_woodwork",
    "Accurate through passes": "accurate_through_passes",
    "Offsides": "offsides",
    "Free kicks": "free_kicks",
    "Throw ins": "throw_ins",
    "Passes": "passes",
    "Long passes": "long_passes",
    "Passes in final third": "passes_final_third",
    "Crosses": "crosses",
    "Expected assists (xA)": "xa",
    "xG on target (xGOT)": "xgot",
    "Headed goals": "headed_goals",
    "Fouls": "fouls",
    "Tackles": "tackles",
    "Duels won": "duels_won",
    "Clearances": "clearances",
    "Interceptions": "interceptions",
    "Errors leading to shot": "errors_leading_to_shot",
    "Errors leading to goal": "errors_leading_to_goal",
    "Goalkeeper saves": "goalkeeper_saves",
    "xGOT faced": "xgot_faced",
    "Goals prevented": "goals_prevented",
    "Yellow cards": "yellow_cards",
    "Red cards": "red_cards",
}

PASS_TYPE_STATS = {"passes", "long_passes", "passes_final_third", "crosses", "tackles"}


def stat_name_to_key(name: str) -> Optional[str]:
    """Map API stat name to normalized key."""
    return STAT_NAME_TO_KEY.get(name)


def parse_stat_value(name: str, home_val: Any, away_val: Any) -> Dict:
    """
    Parse raw stat values into {for, against} structure.
    Uses parse_pass_stat for pass-type stats, extracts possession percentage,
    and direct value extraction for everything else.
    """
    key = stat_name_to_key(name)

    if key in PASS_TYPE_STATS:
        home_parsed = parse_pass_stat(home_val)
        away_parsed = parse_pass_stat(away_val)
        return {
            "for": home_parsed,
            "against": away_parsed,
        }

    if key == "possession":
        home_int = int(re.sub(r"\D", "", str(home_val))) if home_val else 0
        away_int = int(re.sub(r"\D", "", str(away_val))) if away_val else 0
        # Ensure for+against sums to 100
        return {"for": home_int, "against": away_int}

    def direct(val: Any) -> Any:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return val
        s = str(val).strip()
        if s == "-" or s == "":
            return None
        try:
            return float(s)
        except ValueError:
            return s

    return {"for": direct(home_val), "against": direct(away_val)}


def normalize_advanced_stats(raw_stats: Optional[Dict], *, team_is_home: bool = True) -> Dict:
    """
    Normalize raw output from fetch_match_stats() into structured advanced_stats.
    Handles local/away orientation: the API always returns home_team/away_team from
    the perspective of who was home in that specific match. When team_is_home=False
    we swap "for" and "against" to express stats from the visitor's perspective.

    Returns:
        {
          "match":     { stat_key: { "for": value, "against": value }, ... },
          "1st-half":  { stat_key: { "for": value, "against": value }, ... },
          "2nd-half":  { stat_key: { "for": value, "against": value }, ... },
          "warnings":  []
        }
    """
    result = {
        "match": {},
        "1st-half": {},
        "2nd-half": {},
        "warnings": [],
    }

    if not raw_stats:
        return result

    for period_key in ("match", "1st-half", "2nd-half"):
        period_data = raw_stats.get(period_key, [])
        if not isinstance(period_data, list):
            continue

        seen_names: set = set()

        for item in period_data:
            if not isinstance(item, dict):
                continue

            stat_name = item.get("name")
            if not stat_name:
                continue

            # Deduplicate by stat name within each period
            if stat_name in seen_names:
                continue
            seen_names.add(stat_name)

            key = stat_name_to_key(stat_name)
            if key is None:
                continue

            home_val = item.get("home_team")
            away_val = item.get("away_team")
            parsed = parse_stat_value(stat_name, home_val, away_val)
            # API returns home_team/away_team from the perspective of who was home
            # in that match. When team_is_home=False (we were the away team), swap
            # "for" and "against" so stats are always expressed from our team's view.
            if not team_is_home:
                parsed = {"for": parsed.get("against"), "against": parsed.get("for")}
            result[period_key][key] = parsed

    return result


# =============================================================================
# =============================================================================
# ADVANCED FORM AGGREGATION
# =============================================================================

def _avg_stat(matches, period, key, side, sub_key=None):
    vals = []
    for m in matches:
        stats = m.get('advanced_stats', {}).get(period, {})
        val = stats.get(key, {}).get(side)
        if sub_key and isinstance(val, dict):
            val = val.get(sub_key)
        if val is not None:
            vals.append(val)
    return round(sum(vals) / len(vals), 2) if vals else None


def _avg_goals_from_result(matches, side):
    key = 'goals_for' if side == 'for' else 'goals_against'
    vals = [m.get(key) for m in matches if m.get(key) is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def _avg_bc_conversion(matches, period):
    vals = []
    for m in matches:
        bc = m.get('advanced_stats', {}).get(period, {}).get('big_chances', {}).get('for')
        gf = m.get('goals_for')
        if bc is not None and bc > 0 and gf is not None:
            vals.append(gf / bc)
    return round(sum(vals) / len(vals) * 100, 2) if vals else None


def _safe(val, default=0.0):
    return val if val is not None else default


def _category_attack(matches, period):
    return {
        'goals_for_avg': _avg_goals_from_result(matches, 'for'),
        'xg_for_avg': _avg_stat(matches, period, 'xg', 'for'),
        'xgot_for_avg': _avg_stat(matches, period, 'xgot', 'for'),
        'xa_for_avg': _avg_stat(matches, period, 'xa', 'for'),
        'shots_for_avg': _avg_stat(matches, period, 'shots', 'for'),
        'shots_on_target_for_avg': _avg_stat(matches, period, 'shots_on_target', 'for'),
        'shots_off_target_for_avg': _avg_stat(matches, period, 'shots_off_target', 'for'),
        'blocked_shots_for_avg': _avg_stat(matches, period, 'blocked_shots', 'for'),
        'shots_inside_box_for_avg': _avg_stat(matches, period, 'shots_inside_box', 'for'),
        'shots_outside_box_for_avg': _avg_stat(matches, period, 'shots_outside_box', 'for'),
        'big_chances_for_avg': _avg_stat(matches, period, 'big_chances', 'for'),
        'touches_in_opposition_box_avg': _avg_stat(matches, period, 'touches_in_opposition_box', 'for'),
        'hit_woodwork_avg': _avg_stat(matches, period, 'hit_woodwork', 'for'),
    }


def _category_defense(matches, period):
    return {
        'goals_against_avg': _avg_goals_from_result(matches, 'against'),
        'xg_against_avg': _avg_stat(matches, period, 'xg', 'against'),
        'xgot_faced_avg': _avg_stat(matches, period, 'xgot_faced', 'for'),
        'shots_against_avg': _avg_stat(matches, period, 'shots', 'against'),
        'shots_on_target_against_avg': _avg_stat(matches, period, 'shots_on_target', 'against'),
        'shots_off_target_against_avg': _avg_stat(matches, period, 'shots_off_target', 'against'),
        'blocked_shots_against_avg': _avg_stat(matches, period, 'blocked_shots', 'against'),
        'shots_inside_box_against_avg': _avg_stat(matches, period, 'shots_inside_box', 'against'),
        'shots_outside_box_against_avg': _avg_stat(matches, period, 'shots_outside_box', 'against'),
        'big_chances_against_avg': _avg_stat(matches, period, 'big_chances', 'against'),
        'touches_in_opposition_box_against_avg': _avg_stat(matches, period, 'touches_in_opposition_box', 'against'),
        'goalkeeper_saves_avg': _avg_stat(matches, period, 'goalkeeper_saves', 'for'),
        'errors_leading_to_shot_avg': _avg_stat(matches, period, 'errors_leading_to_shot', 'for'),
        'errors_leading_to_goal_avg': _avg_stat(matches, period, 'errors_leading_to_goal', 'for'),
        'goals_prevented_avg': _avg_stat(matches, period, 'goals_prevented', 'for'),
    }


def _category_control(matches, period):
    return {
        'possession_avg': _avg_stat(matches, period, 'possession', 'for'),
        'passes_accuracy_avg': _avg_stat(matches, period, 'passes', 'for', 'pct'),
        'passes_completed_avg': _avg_stat(matches, period, 'passes', 'for', 'completed'),
        'passes_attempted_avg': _avg_stat(matches, period, 'passes', 'for', 'attempted'),
        'long_pass_accuracy_avg': _avg_stat(matches, period, 'long_passes', 'for', 'pct'),
        'long_passes_completed_avg': _avg_stat(matches, period, 'long_passes', 'for', 'completed'),
        'long_passes_attempted_avg': _avg_stat(matches, period, 'long_passes', 'for', 'attempted'),
        'final_third_pass_accuracy_avg': _avg_stat(matches, period, 'passes_final_third', 'for', 'pct'),
        'final_third_passes_completed_avg': _avg_stat(matches, period, 'passes_final_third', 'for', 'completed'),
        'final_third_passes_attempted_avg': _avg_stat(matches, period, 'passes_final_third', 'for', 'attempted'),
        'accurate_through_passes_avg': _avg_stat(matches, period, 'accurate_through_passes', 'for'),
    }


def _category_set_pieces(matches, period):
    return {
        'corners_for_avg': _avg_stat(matches, period, 'corners', 'for'),
        'corners_against_avg': _avg_stat(matches, period, 'corners', 'against'),
        'offsides_for_avg': _avg_stat(matches, period, 'offsides', 'for'),
        'offsides_against_avg': _avg_stat(matches, period, 'offsides', 'against'),
        'free_kicks_for_avg': _avg_stat(matches, period, 'free_kicks', 'for'),
        'free_kicks_against_avg': _avg_stat(matches, period, 'free_kicks', 'against'),
        'throw_ins_for_avg': _avg_stat(matches, period, 'throw_ins', 'for'),
        'throw_ins_against_avg': _avg_stat(matches, period, 'throw_ins', 'against'),
        'cross_accuracy_avg': _avg_stat(matches, period, 'crosses', 'for', 'pct'),
        'crosses_completed_avg': _avg_stat(matches, period, 'crosses', 'for', 'completed'),
        'crosses_attempted_avg': _avg_stat(matches, period, 'crosses', 'for', 'attempted'),
    }


def _category_discipline(matches, period):
    yf = _avg_stat(matches, period, 'yellow_cards', 'for')
    ya = _avg_stat(matches, period, 'yellow_cards', 'against')
    rf = _avg_stat(matches, period, 'red_cards', 'for')
    if rf is None and yf is not None:
        rf = 0.0
    if yf is not None and rf is not None:
        cards_total = round(yf + rf, 2)
    elif yf is not None:
        cards_total = yf
    elif rf is not None:
        cards_total = rf
    else:
        cards_total = 0.0
    return {
        'yellow_cards_avg': yf,
        'red_cards_avg': rf,
        'cards_total_avg': cards_total,
        'fouls_committed_avg': _avg_stat(matches, period, 'fouls', 'for'),
    }


def _category_duels(matches, period):
    return {
        'tackles_success_pct_avg': _avg_stat(matches, period, 'tackles', 'for', 'pct'),
        'tackles_won_avg': _avg_stat(matches, period, 'tackles', 'for', 'completed'),
        'tackles_attempted_avg': _avg_stat(matches, period, 'tackles', 'for', 'attempted'),
        'duels_won_avg': _avg_stat(matches, period, 'duels_won', 'for'),
        'clearances_avg': _avg_stat(matches, period, 'clearances', 'for'),
        'interceptions_avg': _avg_stat(matches, period, 'interceptions', 'for'),
    }


def _category_efficiency(matches, period):
    sf = _avg_stat(matches, period, 'shots', 'for')
    sot_f = _avg_stat(matches, period, 'shots_on_target', 'for')
    sot_a = _avg_stat(matches, period, 'shots_on_target', 'against')
    xgf = _avg_stat(matches, period, 'xg', 'for')
    xga = _avg_stat(matches, period, 'xg', 'against')
    bcf = _avg_stat(matches, period, 'big_chances', 'for')
    sv_f = _avg_stat(matches, period, 'goalkeeper_saves', 'for')
    gf = _avg_goals_from_result(matches, 'for')
    ga = _avg_goals_from_result(matches, 'against')

    def pct(a, b):
        return round(a / b * 100, 2) if a is not None and b and b > 0 else None

    return {
        'shot_accuracy_pct': pct(sot_f, sf),
        'goal_conversion_pct': min(pct(gf, sf), 100.0) if gf is not None and sf and sf > 0 else None,
        'big_chance_conversion_pct': _avg_bc_conversion(matches, period),
        'xg_per_shot': round(xgf / sf, 2) if xgf is not None and sf and sf > 0 else None,
        'shots_on_target_faced_per_goal_against': (None if ga == 0 else round(sot_a / ga, 2)) if sot_a is not None and ga is not None else None,
        'save_pct': pct(sv_f, sot_a),
        'finishing_overperformance': round(gf - xgf, 2) if gf is not None and xgf is not None else None,
        'conceding_overperformance': round(ga - xga, 2) if ga is not None and xga is not None else None,
    }


def _category_derived(matches, period):
    xgf = _avg_stat(matches, period, 'xg', 'for')
    xga = _avg_stat(matches, period, 'xg', 'against')
    sf = _avg_stat(matches, period, 'shots', 'for')
    sot_f = _avg_stat(matches, period, 'shots_on_target', 'for')
    sot_a = _avg_stat(matches, period, 'shots_on_target', 'against')
    bcf = _avg_stat(matches, period, 'big_chances', 'for')
    bca = _avg_stat(matches, period, 'big_chances', 'against')
    cf = _avg_stat(matches, period, 'corners', 'for')
    ca = _avg_stat(matches, period, 'corners', 'against')
    ycf = _avg_stat(matches, period, 'yellow_cards', 'for')
    yca = _avg_stat(matches, period, 'yellow_cards', 'against')
    s = _safe
    return {
        'xg_balance_avg': round(s(xgf) - s(xga), 2),
        'xg_ratio': round(xgf / s(xga), 2) if xga and xga > 0 else None,
        'shots_share': round(sf / (sf + s(sot_a)), 2) if sf and sf > 0 else None,
        'shots_on_target_share': round(sot_f / (sot_f + s(sot_a)), 2) if sot_f and sot_f > 0 else None,
        'big_chances_balance_avg': round(s(bcf) - s(bca), 2) if bcf is not None else None,
        'corners_balance_avg': round(s(cf) - s(ca), 2) if cf is not None else None,
        'discipline_balance_avg': round(s(ycf) - s(yca), 2) if ycf is not None else None,
    }


def compute_category_averages(matches, period):
    return {
        'attack': _category_attack(matches, period),
        'defense': _category_defense(matches, period),
        'control': _category_control(matches, period),
        'set_pieces_and_territory': _category_set_pieces(matches, period),
        'discipline': _category_discipline(matches, period),
        'duels_and_defending': _category_duels(matches, period),
        'efficiency': _category_efficiency(matches, period),
        'derived': _category_derived(matches, period),
    }


def compute_advanced_form(matches: List[Dict]) -> Dict:
    """Aggregate advanced_stats from matches into organized categories."""
    # Only exclude matches that truly lack advanced_stats (not just because they have warnings)
    valid = [m for m in matches if m.get("advanced_stats")]
    n = len(valid)
    total = len(matches)

    result = {
        "overall": compute_category_averages(valid, "match"),
        "first_half": compute_category_averages(valid, "1st-half"),
        "second_half": compute_category_averages(valid, "2nd-half"),
        "warnings": [],
    }
    if n < total:
        result["warnings"].append(f"advanced_stats_partial: {n}/{total} matches con stats")
    if n == 0:
        result = {
            "overall": {},
            "first_half": {},
            "second_half": {},
            "warnings": ["No advanced stats available"],
        }
    return result


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


def parse_pass_stat(value: Any) -> Dict:
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


def compute_team_player_aggregates(matches: List[Dict]) -> Dict:
    """
    Aggregate player stats across all historical matches for one team.
    Collects all player records from each match's player_stats,
    orienting by team_is_home to select the right player list per match,
    then computes totals across the full sample.
    """
    all_home_players: List[Dict] = []
    all_away_players: List[Dict] = []

    for match in matches:
        ps = match.get("player_stats", {})
        if not ps or ps.get("warnings"):
            continue
        is_home = match.get("team_is_home", True)
        if is_home:
            all_home_players.extend(ps.get("home_players", []))
            all_away_players.extend(ps.get("away_players", []))
        else:
            # When the analyzed team was away, their players are in away_players from API perspective
            all_away_players.extend(ps.get("home_players", []))
            all_home_players.extend(ps.get("away_players", []))

    return {
        "as_historical_home": compute_player_aggregates(all_home_players),
        "as_historical_away": compute_player_aggregates(all_away_players),
    }


def compute_player_aggregates(players: List[Dict]) -> Dict:
    """
    Aggregate stats across all players of a team within a single match.
    Produces totals, per-90-minute rates, and distribution breakdowns.
    """
    if not players:
        return {}

    def g(player: Dict, key: str) -> float:
        v = player.get(key, 0)
        return float(v) if v is not None else 0.0

    total_minutes = sum(g(p, "minutes") for p in players)
    n = len(players)

    totals = {
        "minutes_total": total_minutes,
        "goals_total": sum(g(p, "goals") for p in players),
        "assists_total": sum(g(p, "assists") for p in players),
        "shots_total": sum(g(p, "shots") for p in players),
        "shots_on_target_total": sum(g(p, "shots_on_target") for p in players),
        "key_passes_total": sum(g(p, "key_passes") for p in players),
        "tackles_won_total": sum(g(p, "tackles_won") for p in players),
        "interceptions_total": sum(g(p, "interceptions") for p in players),
        "ball_recoveries_total": sum(g(p, "ball_recoveries") for p in players),
        "yellow_cards_total": sum(g(p, "yellow_cards") for p in players),
        "red_cards_total": sum(g(p, "red_cards") for p in players),
    }

    total_90 = total_minutes / PARTY_MINUTES
    totals["goals_per_90"] = round(totals["goals_total"] / total_90, 2) if total_90 > 0 else None
    totals["assists_per_90"] = round(totals["assists_total"] / total_90, 2) if total_90 > 0 else None
    totals["shots_per_90"] = round(totals["shots_total"] / total_90, 2) if total_90 > 0 else None

    pos_count: Dict[str, int] = {}
    for p in players:
        pos = p.get("position") or "Unknown"
        pos_count[pos] = pos_count.get(pos, 0) + 1
    totals["position_distribution"] = pos_count

    lineup_count = sum(1 for p in players if p.get("in_base_lineup"))
    totals["in_base_lineup_count"] = lineup_count
    totals["substitute_count"] = n - lineup_count

    return totals



def normalize_player_stats(player_data: Any, home_team_id: str, away_team_id: str) -> Dict:
    """
    Normalize per-player stats for the current match.
    Extracts ALL available stat keys from the raw API response (not just a fixed set).
    Each player's `stats` dict contains every stat key the API provides for that match.
    No aggregations — for the current match only raw normalized data per player.
    """
    if not player_data:
        return {"home_players": [], "away_players": [], "warnings": ["Player stats not available [N/A]"]}

    all_players = player_data.get("players", []) if isinstance(player_data, dict) else []

    home_players = []
    away_players = []

    for p in all_players:
        pid = p.get("player_id")
        tid = p.get("team_id")
        raw_stats = p.get("stats", {})

        # Extract every stat key present in the raw dict (dynamic — no fixed list)
        stats_record: Dict[str, Any] = {}
        if isinstance(raw_stats, dict):
            for stat_key, stat_val in raw_stats.items():
                if not isinstance(stat_val, dict):
                    continue
                raw_v = stat_val.get("raw_value") or stat_val.get("value")
                str_v = str(raw_v) if raw_v is not None else None
                rank = stat_val.get("rank")

                if str_v is not None and re.search(r"\d+%?\s*\(", str_v):
                    parsed = parse_pass_stat(str_v)
                    stats_record[stat_key] = {
                        "value": parsed.get("pct"),
                        "pct": parsed.get("pct"),
                        "completed": parsed.get("completed"),
                        "attempted": parsed.get("attempted"),
                        "rank": rank,
                    }
                else:
                    if str_v is not None:
                        try:
                            num_val = int(str_v)
                        except (ValueError, TypeError):
                            try:
                                num_val = float(str_v)
                            except (ValueError, TypeError):
                                num_val = str_v
                    else:
                        num_val = None
                    stats_record[stat_key] = {
                        "value": num_val,
                        "rank": rank,
                    }

        # Fixed extraction — always present for backwards compatibility
        def g(key):
            if not isinstance(raw_stats, dict):
                return 0
            s = raw_stats.get(key, {})
            v = s.get("value", "0") if isinstance(s, dict) else "0"
            try:
                return int(v)
            except (ValueError, TypeError):
                return 0

        player_rec = {
            "player_id": pid,
            "name": p.get("name"),
            "short_name": p.get("short_name"),
            "position": p.get("position"),
            "in_base_lineup": p.get("in_base_lineup"),
            "is_goalkeeper": p.get("is_goalkeeper", False),
            "stats": stats_record,
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

    return {
        "home_players": home_players,
        "away_players": away_players,
        "warnings": [],
    }


def normalize_lineups(lineup_data: Any) -> Dict:
    """
    Normalize lineups + extract missingPlayers for each team.
    """
    if not lineup_data:
        return {"home": None, "away": None, "warnings": ["Lineup data not available [N/A]"]}

    result = {"home": None, "away": None, "warnings": []}
    
    def parse_lineups(lineups: List, include_reason: bool = False) -> List[Dict]:
        parsed = []
        for m in lineups:
            player_data = {
                "country": m.get("country_name"),
                "player_id": m.get("player_id"),
                "name": m.get("name"),
            }
            if include_reason:
                player_data["reason"] = m.get("reason")
            parsed.append(player_data)
        return parsed

    for team_block in lineup_data:
        unsureMissingPlayers = team_block.get("unsureMissingPlayers", [])
        predictedLineups = team_block.get("predictedLineups", [])
        startingLineups = team_block.get("startingLineups", [])
        missingPlayers = team_block.get("missingPlayers", [])
        formation = team_block.get("predictedFormation")
        substitutes = team_block.get("substitutes", [])
        side = team_block.get("side")

        team_data = {
            "missing_players": parse_lineups(missingPlayers, True),
            "predicted_lineups": [],
            "formation": formation,
            "starting_lineups": [],
            "unsure_missing": [],
            "substitutes": [],
        }
        
        if startingLineups:
            team_data["starting_lineups"] = parse_lineups(startingLineups)
            team_data["substitutes"] = parse_lineups(substitutes)
        elif predictedLineups:
            team_data["unsure_missing"] = parse_lineups(unsureMissingPlayers, True)
            team_data["predicted_lineups"] = parse_lineups(predictedLineups)

        if side == "home":
            result["home"] = team_data
        elif side == "away":
            result["away"] = team_data

    return result

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

def detect_h2h_inconsistencies(h2h: Dict) -> List[str]:
    """Check H2H for suspicious patterns."""
    warnings = []
    matches = h2h.get("matches", [])
    if not matches:
        return warnings

    # Check for future dates (shouldn't happen but check anyway)
    now = datetime.now().timestamp()
    future = [r for r in matches if r.get("timestamp", 0) > now]
    if future:
        warnings.append(f"H2H contains {len(future)} future-dated matches (possible data issue)")

    # Check for very high-scoring matches (potential data error if avg > 5)
    total = h2h.get("total_matches", 0)
    total_goals_sum = h2h.get("total_goals", 0)
    if total > 0 and total_goals_sum / total > MAX_AVG_GOALS_H2H:
        warnings.append(f"H2H avg goals unusually high: {round(total_goals_sum / total, 2)}")

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
    team_h = ctx.get("team_home_results", {}).get("basic_stats", {})
    team_a = ctx.get("team_away_results", {}).get("basic_stats", {})

    prob_h = odds.get("prob_home")
    if prob_h and team_h.get("gf_avg") and team_a.get("gf_avg"):
        form_diff = team_h["gf_avg"] - team_a["gf_avg"]
        if form_diff > FORM_DIFF_THRESHOLD and prob_h < 40:
            result["odds"].append("Market undervaluing home team despite stronger recent form [IND]")
        elif form_diff < -FORM_DIFF_THRESHOLD and prob_h > 60:
            result["odds"].append("Market overvaluing home team despite weaker recent form [IND]")

    return result


def _compute_top_level_stats(matches: List[Dict]) -> Dict:
    """
    Compute top-level summary stats (total_matches, wins, draws, losses,
    goals_for, goals_against, total_goals, both_teams_scored) from a list
    of matches. Supports two formats:
    - team_home_results/away_results: goals_for, goals_against, total_goals
    - h2h: home_score, away_score, team_is_home (computes goals_for from orientation)
    """
    wins = draws = losses = 0
    goals_for = goals_against = total_goals = 0
    btts_count = 0
    n = len(matches)

    for m in matches:
        # h2h format: home_score, away_score, team_is_home
        if "home_score" in m and "away_score" in m:
            hs = m.get("home_score", 0) or 0
            aw = m.get("away_score", 0) or 0
            is_home = m.get("team_is_home", True)
            gf = hs if is_home else aw
            ga = aw if is_home else hs
            tg = hs + aw
        # team results format: goals_for, goals_against
        else:
            gf = m.get("goals_for", 0) or 0
            ga = m.get("goals_against", 0) or 0
            tg = m.get("total_goals", gf + ga)

        goals_for += gf
        goals_against += ga
        total_goals += tg
        if gf > ga:
            wins += 1
        elif gf == ga:
            draws += 1
        else:
            losses += 1
        if gf > 0 and ga > 0:
            btts_count += 1

    return {
        "total_matches": n,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "total_goals": total_goals,
        "both_teams_scored": f"{btts_count}/{n}" if n > 0 else None,
    }


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
    final["team_home_results"] = {"warnings": [f"Team results for {home_name} not available [N/A]"]}
    tr_home = fetch_team_results(home_team_id)
    if tr_home is not None:
        final["team_home_results"] = normalize_team_results(tr_home, home_name, home_team_id)

    final["team_away_results"] = {"warnings": [f"Team results for {away_name} not available [N/A]"]}
    tr_away = fetch_team_results(away_team_id)
    if tr_away is not None:
        final["team_away_results"] = normalize_team_results(tr_away, away_name, away_team_id)

    # -------------------------------------------------------------------------
    # 4. H2H — built from team_results (no extra API call)
    # -------------------------------------------------------------------------
    h2h = build_h2h_from_results(
        final["team_home_results"],
        final["team_away_results"],
        home_name,
        away_name,
    )
    final["h2h"] = h2h

    # --- ADVANCED STATS: Fetch in parallel for all historical matches ---
    # Deduplicate AND filter to past matches only (skip future fixtures)
    now = datetime.now().timestamp()
    seen = set()
    past_match_ids = []
    for match_list in [
        final["team_home_results"].get("matches", []),
        final["team_away_results"].get("matches", []),
    ]:
        for m in match_list:
            ts = m.get("timestamp", 0)
            mid = m.get("match_id")
            if mid and ts and ts < now and mid not in seen:
                seen.add(mid)
                past_match_ids.append(mid)

    all_match_ids = past_match_ids

    stats_map: Dict[str, Any] = {}
    player_stats_map: Dict[str, Any] = {}

    def _fetch_with_jitter(mid: str, fetch_func: Callable[..., Any]) -> tuple:
        time.sleep(API_SLEEP_BETWEEN + random.uniform(0, 0.2))
        try:
            result = fetch_func(mid)
        except Exception as e:
            print(f"[WARNING] {fetch_func.__name__}({mid}) failed: {e}", file=sys.stderr)
            result = None
        return mid, result

    if all_match_ids:
        time.sleep(API_SLEEP_INITIAL)

        # Fetch stats in parallel
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(_fetch_with_jitter, mid, fetch_match_stats): mid for mid in all_match_ids}
            for future in as_completed(futures):
                mid, result = future.result()
                stats_map[mid] = result

        # Fetch player stats in parallel
        time.sleep(API_SLEEP_INITIAL)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(_fetch_with_jitter, mid, fetch_match_player_stats): mid for mid in all_match_ids}
            for future in as_completed(futures):
                mid, result = future.result()
                player_stats_map[mid] = result

    def _enrich_match(
        match: Dict, stats_map: Dict, player_stats_map: Dict,
        home_tid: str, away_tid: str
    ) -> None:
        """Attach advanced_stats and player_stats to a single match record."""
        mid = match.get("match_id")
        is_home = match.get("team_is_home", True)
        raw_stats = stats_map.get(mid)
        match["advanced_stats"] = (
            normalize_advanced_stats(raw_stats, team_is_home=is_home)
            if raw_stats else {"warnings": ["Stats not available"]}
        )

        raw_ps = player_stats_map.get(mid)
        api_home_id = away_tid if not is_home else home_tid
        api_away_id = home_tid if not is_home else away_tid

        if raw_ps:
            match["player_stats"] = normalize_player_stats(raw_ps, api_home_id, api_away_id)
        else:
            match["player_stats"] = {"home_players": [], "away_players": [], "warnings": ["Player stats not available [N/A]"]}

    # Enrich all three collections with the shared helper
    for match in final["team_home_results"].get("matches", []):
        _enrich_match(match, stats_map, player_stats_map, home_team_id, away_team_id)

    for match in final["team_away_results"].get("matches", []):
        _enrich_match(match, stats_map, player_stats_map, home_team_id, away_team_id)

    for rec in final["h2h"].get("matches", []):
        _enrich_match(rec, stats_map, player_stats_map, home_team_id, away_team_id)

    # Compute advanced stats for each team (basic_stats already at top level)
    final["team_home_results"]["advanced_stats"] = compute_advanced_form(
        final["team_home_results"]["matches"]
    )
    final["team_away_results"]["advanced_stats"] = compute_advanced_form(
        final["team_away_results"]["matches"]
    )
    final["h2h"]["advanced_stats"] = compute_advanced_form(
        final["h2h"].get("matches", [])
    )

    # Aggregate player stats across all historical matches per team
    _home_ps = compute_team_player_aggregates(final["team_home_results"].get("matches", []))
    _away_ps = compute_team_player_aggregates(final["team_away_results"].get("matches", []))
    _h2h_ps = compute_team_player_aggregates(final["h2h"].get("matches", []))

    # Promote player_stats inner keys and remove wrapper
    final["team_home_results"]["player_stats_as_home"] = _home_ps.get("as_historical_home", {})
    final["team_home_results"]["player_stats_as_away"] = _home_ps.get("as_historical_away", {})
    final["team_away_results"]["player_stats_as_home"] = _away_ps.get("as_historical_home", {})
    final["team_away_results"]["player_stats_as_away"] = _away_ps.get("as_historical_away", {})
    final["h2h"]["player_stats_as_home"] = _h2h_ps.get("as_historical_home", {})
    final["h2h"]["player_stats_as_away"] = _h2h_ps.get("as_historical_away", {})

    # Remove leftover wrappers (player_stats only — form was already replaced)
    for _section in [final["team_home_results"], final["team_away_results"], final["h2h"]]:
        _section.pop("player_stats", None)

    # Strip individual match-level advanced_stats and player_stats from JSON output.
    # Aggregates (advanced_stats, player_stats_as_*) were already computed above.
    for _matches_list in [
        final["team_home_results"].get("matches", []),
        final["team_away_results"].get("matches", []),
        final["h2h"].get("matches", []),
    ]:
        for _m in _matches_list:
            _m.pop("advanced_stats", None)
            _m.pop("player_stats", None)

    # Add top-level summary stats to team_home_results and team_away_results
    final["team_home_results"] = {
        **final["team_home_results"],
        **_compute_top_level_stats(final["team_home_results"].get("matches", [])),
    }
    final["team_away_results"] = {
        **final["team_away_results"],
        **_compute_top_level_stats(final["team_away_results"].get("matches", [])),
    }

    # Add top-level summary stats to h2h with team-oriented naming for clarity
    _h2h_stats = _compute_top_level_stats(final["h2h"].get("matches", []))
    final["h2h"] = {
        **final["h2h"],
        "total_matches": _h2h_stats["total_matches"],
        "team_home_wins": _h2h_stats["wins"],
        "team_away_wins": _h2h_stats["losses"],
        "draws": _h2h_stats["draws"],
        "team_home_goals_for": _h2h_stats["goals_for"],
        "team_away_goals_for": _h2h_stats["goals_against"],
        "total_goals": _h2h_stats["total_goals"],
        "both_teams_scored": _h2h_stats["both_teams_scored"],
    }

    # -------------------------------------------------------------------------
    # 5. LINEUPS / MISSING PLAYERS
    # -------------------------------------------------------------------------
    lineup_raw = fetch_match_lineups(event_id)
    if lineup_raw:
        final["match"]["lineups"] = normalize_lineups(lineup_raw)
    else:
        final["match"]["lineups"] = {"warnings": ["Lineup data not available [N/A]"]}

    # -------------------------------------------------------------------------
    # 6. PREVIEW (web scraping)
    # -------------------------------------------------------------------------
    home_slug = {"slug": build_preview_slug(home_url), "id": home_team_id}
    away_slug = {"slug": build_preview_slug(away_url), "id": away_team_id}
    preview_raw = fetch_preview(home_slug, away_slug, event_id)
    if preview_raw:
        final["match"]["preview"] = preview_raw
    else:
        final["match"]["preview"] = None

    # -------------------------------------------------------------------------
    # 10. TOURNAMENT STANDINGS
    # -------------------------------------------------------------------------
    if tournament_id and tournament_stage_id:
        ts_raw = fetch_tournament_standings(tournament_id, tournament_stage_id)
        if ts_raw:
            final["standings"] = normalize_standings(ts_raw, team_ids)
        else:
            final["standings"] = {"warnings": ["Tournament standings not available [N/A]"]}

    # -------------------------------------------------------------------------
    # 11. MATCH FORM STANDINGS
    # -------------------------------------------------------------------------
    form_st_raw = fetch_match_standings_form(event_id)
    if form_st_raw:
        final["form_standings"] = normalize_form_st(form_st_raw, team_ids)
    else:
        final["form_standings"] = {"warnings": ["Form standings not available [N/A]"]}

    # -------------------------------------------------------------------------
    # 12. OVER/UNDER STANDINGS
    # -------------------------------------------------------------------------
    ou_raw = fetch_match_standings_overunder(event_id)
    if ou_raw:
        final["overunder_standings"] = normalize_overunder_st(ou_raw, team_ids)
    else:
        final["overunder_standings"] = {"warnings": ["Over/Under standings not available [N/A]"]}

    # -------------------------------------------------------------------------
    # 13. MATCH TOP SCORERS
    # -------------------------------------------------------------------------
    mts_raw = fetch_match_top_scorers(event_id)
    if mts_raw:
        final["top_scorers"] = normalize_top_scorers(mts_raw, team_ids)
    else:
        final["top_scorers"] = {"warnings": ["Match top scorers not available [N/A]"]}

    # -------------------------------------------------------------------------
    # 14. TOURNAMENT TOP SCORERS
    # -------------------------------------------------------------------------
    if tournament_id and tournament_stage_id:
        tts_raw = fetch_tournament_top_scorers(tournament_id, tournament_stage_id)
        if tts_raw:
            final["tournament_top_scorers"] = normalize_top_scorers(tts_raw, team_ids)
        else:
            final["tournament_top_scorers"] = {"warnings": ["Tournament top scorers not available [N/A]"]}

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

    # Output JSON to stdout only if connected to a TTY (not piped)
    if sys.stdout.isatty():
        print(json.dumps(ctx, indent=2, ensure_ascii=False))

    # Save JSON to ../analysis/ directory
    analysis_dir = Path(__file__).parent.parent / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    output_file = analysis_dir / f"{event_id}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(ctx, f, indent=2, ensure_ascii=False)

    print(f"[INFO] JSON guardado en {output_file}", file=sys.stderr)
