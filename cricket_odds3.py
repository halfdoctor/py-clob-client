#!/usr/bin/env python3
"""
Cricket Odds Fetcher for Polymarket
This script finds cricket markets where the match has already started (gameStartTime > current UTC time)
and displays their details, with optional search functionality to filter specific matches
"""

import sys
import os
import json
import requests
import subprocess
import datetime
import logging
import time
from datetime import timezone
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

# Load environment variables from .env file
load_dotenv()

# Configure logging
LOG_FILE = "polymarket_odds.txt"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='a'), # Append mode
        logging.StreamHandler() # Also print to console
    ]
)

# Discord Webhook URL from environment variables
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
# Set to True for detailed logging (can be kept for specific debug prints)
DEBUG = False # Set DEBUG to False by default, enable if needed

def debug_print(message, obj=None):
    """Print debug information if DEBUG is True"""
    # Keep debug_print for very specific, optional verbose output if needed
    if DEBUG:
        logging.debug(f"DEBUG: {message}")
        if obj is not None:
            if isinstance(obj, dict) or isinstance(obj, list):
                logging.debug(json.dumps(obj, indent=2))
            else:
                logging.debug(str(obj)) # Ensure obj is string for logging

def get_clob_client():
    """Initialize and return a CLOB client with API credentials."""
    host = os.getenv("CLOB_HOST", "https://clob.polymarket.com")
    key = os.getenv("PK")  # Private key
    
    # Create the CLOB client
    client = ClobClient(host, key=key, chain_id=POLYGON)
    
    # If you have API credentials, set them
    if os.getenv("CLOB_API_KEY") and os.getenv("CLOB_SECRET") and os.getenv("CLOB_PASS_PHRASE"):
        from py_clob_client.clob_types import ApiCreds
        creds = ApiCreds(
            api_key=os.getenv("CLOB_API_KEY"),
            api_secret=os.getenv("CLOB_SECRET"),
            api_passphrase=os.getenv("CLOB_PASS_PHRASE"),
        )
        client.set_api_creds(creds)
        logging.info("API credentials set.")
    else:
        logging.info("No API credentials found, running in read-only mode.")
    
    return client

def send_discord_alert(message):
    """Sends a message to the Discord webhook URL."""
    """Sends a message to the Discord webhook URL."""
    if not DISCORD_WEBHOOK_URL:
        logging.error("DISCORD_WEBHOOK_URL not set in environment variables. Cannot send Discord alert.")
        return

    try:
        # Escape message for JSON payload
        escaped_message = json.dumps(message)
        payload = f'{{"content": {escaped_message}}}'
        
        debug_print(f"Sending Discord alert: {payload}")
        
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=payload,
            timeout=10  # Add a timeout
        )
        
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        logging.info(f"Discord alert sent successfully (Status: {response.status_code})")

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send Discord alert: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while sending Discord alert: {e}", exc_info=True)


def search_cricket_markets():
    """Search for cricket markets directly using the Gamma API"""
    try:
        logging.info("Searching for cricket markets via Gamma API...")
        
        # We'll search a few known cricket market IDs and use them to find related markets
        # These are reference IDs for cricket markets
        reference_ids = ["531894", "531899", "531895", "531896"]
        all_markets = []
        found_markets_count = 0
        
        for market_id in reference_ids:
            try:
                # Try to get related markets for this cricket market
                gamma_url = f"https://gamma-api.polymarket.com/markets/{market_id}/related-markets"
                params = {
                    "limit": 50,      # Get more related markets
                    "offset": 0
                }
                
                response = requests.get(gamma_url, params=params)
                
                if response.status_code == 200:
                    markets = response.json()
                    found_markets_count += len(markets)
                    logging.info(f"Found {len(markets)} cricket markets related to ID {market_id}")
                    all_markets.extend(markets)
            except Exception as e:
                logging.warning(f"Error fetching related markets for ID {market_id}: {e}", exc_info=True)
                continue
        
        # Try direct request to all markets with filters for cricket
        logging.info("Trying direct search for cricket markets via Gamma API...")
        gamma_url = "https://gamma-api.polymarket.com/markets"
        params = {"limit": 100}
        
        response = requests.get(gamma_url, params=params)
        
        if response.status_code == 200:
            markets = response.json()
            debug_print(f"Found {len(markets)} total markets in direct search")
            
            # Filter for cricket matches (look for team names)
            cricket_keywords = ["vs", "knight riders", "super kings", "capitals", 
                              "indians", "royals", "sunrisers", "kings", "titans", 
                              "super giants", "ipl", "cricket", "t20"]
            
            cricket_markets = []
            for market in markets:
                market_text = " ".join([
                    str(market.get("question", "")),
                    str(market.get("slug", "")),
                    str(market.get("eventSlug", ""))
                ]).lower()
                
                if any(keyword in market_text for keyword in cricket_keywords):
                    cricket_markets.append(market)
            
            logging.info(f"Found {len(cricket_markets)} potential cricket markets through direct search.")
            all_markets.extend(cricket_markets)
        
        debug_print(f"Total markets found before filtering: {len(all_markets)}")
        
        # Print a sample market to check its structure
        if all_markets and DEBUG:
            debug_print("Sample market structure:", all_markets[0])
        
        # Get current UTC time for filtering
        current_utc_time = datetime.datetime.now(timezone.utc)
        debug_print(f"Current UTC time: {current_utc_time.isoformat()}")
        
        # Remove duplicates and filter for active markets with gameStartTime > current time
        seen_ids = set()
        unique_markets = []
        started_matches = []
        
        for market in all_markets:
            market_id = market.get("id")
            
            # Skip if we've seen this ID already
            if market_id in seen_ids:
                continue
                
            seen_ids.add(market_id)
            
            # Check if market is active
            is_active = True
            if market.get("closed") == True:
                is_active = False
            
            # Include the market if it's active
            if is_active:
                # Fetch more detailed info for each market to get gameStartTime
                try:
                    gamma_url = f"https://gamma-api.polymarket.com/markets/{market_id}"
                    response = requests.get(gamma_url)
                    
                    if response.status_code == 200:
                        market_details = response.json()
                        
                        # Add or update market with details
                        for key, value in market_details.items():
                            market[key] = value
                        
                        # Check if gameStartTime exists and is before current time
                        game_start_time = market.get("gameStartTime")
                        if game_start_time:
                            try:
                                # Parse ISO format datetime
                                start_time = datetime.datetime.fromisoformat(game_start_time.replace('Z', '+00:00'))
                                
                                # Compare with current UTC time
                                if start_time >= current_utc_time:
                                    started_matches.append(market)
                                    debug_print(f"Match started at {start_time}, adding to results")
                                else:
                                    debug_print(f"Match starts at {start_time}, which is in the past")
                            except ValueError:
                                debug_print(f"Could not parse gameStartTime: {game_start_time}")
                                # Add to general active markets if we can't parse time
                                unique_markets.append(market)
                        else:
                            # If no gameStartTime, add to general active markets
                            unique_markets.append(market)
                except Exception as e:
                    logging.warning(f"Error fetching details for market {market_id}: {e}", exc_info=True)
                    # Add to general active markets if we can't get details
                    unique_markets.append(market)
        
        # Combine started matches with unique markets that didn't have gameStartTime
        # but prioritize the started matches in the final list
        final_markets = started_matches + [m for m in unique_markets if m["id"] not in [sm["id"] for sm in started_matches]]
        
        debug_print(f"Markets with started matches: {len(started_matches)}")
        debug_print(f"Total unique active markets: {len(final_markets)}")
        
        return final_markets
        
    except Exception as e:
        logging.error(f"Error searching for cricket markets: {e}", exc_info=True)
        return []



def get_market_details(market_id):
    """Fetch detailed information for a single market using its ID."""
    try:
        gamma_url = f"https://gamma-api.polymarket.com/markets/{market_id}"
        response = requests.get(gamma_url, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        market_data = response.json()
        debug_print(f"Successfully fetched details for market {market_id}")
        return market_data
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching details for market {market_id}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error fetching details for market {market_id}: {e}", exc_info=True)
        return None

def find_match(markets, search_term):
    """Find a specific match from the list of markets"""
    search_term = search_term.lower()
    matching_markets = []
    
    for market in markets:
        market_text = " ".join([
            str(market.get("question", "")),
            str(market.get("slug", "")),
            str(market.get("eventSlug", ""))
        ]).lower()
        
        # Check for matches
        if search_term in market_text:
            matching_markets.append(market)
        
        # If search term has "vs", check individual team names
        if " vs " in search_term:
            teams = search_term.split(" vs ")
            team1 = teams[0].strip()
            team2 = teams[1].strip()
            
            if team1 in market_text and team2 in market_text:
                if market not in matching_markets:
                    matching_markets.append(market)
    
    return matching_markets

def extract_token_id(market):
    """Extract token ID from a market"""
    if "conditionId" in market:
        return market["conditionId"]
    
    if "clobTokenIds" in market:
        try:
            token_ids = json.loads(market["clobTokenIds"])
            if token_ids and len(token_ids) > 0:
                return token_ids[0]
        except:
            pass

    return None

def get_market_summary(market):
    """Get a summary of market details"""
    try:
        # Format the output
        summary = f"Market: {market['question']}\n"
        summary += f"Market ID: {market['id']}\n"
        
        # Check and display game start time
        if "gameStartTime" in market and market["gameStartTime"]:
            try:
                # Parse ISO format datetime
                start_time = datetime.datetime.fromisoformat(market["gameStartTime"].replace('Z', '+00:00'))
                current_time = datetime.datetime.now(timezone.utc)
                time_diff = current_time - start_time
                
                # Calculate hours and minutes elapsed
                hours_elapsed = time_diff.total_seconds() / 3600
                
                if hours_elapsed < 0:
                    summary += f"Game Start Time: {market['gameStartTime']} (Hasn't started yet)\n"
                else:
                    if hours_elapsed < 1:
                        minutes_elapsed = int(time_diff.total_seconds() / 60)
                        summary += f"Game Start Time: {market['gameStartTime']} (Started {minutes_elapsed} minutes ago)\n"
                    else:
                        summary += f"Game Start Time: {market['gameStartTime']} (Started {hours_elapsed:.1f} hours ago)\n"
            except ValueError:
                summary += f"Game Start Time: {market['gameStartTime']}\n"
        
        # Parse outcomes and prices from the market data
        outcomes = []
        outcome_prices = []
        
        if "outcomes" in market:
            try:
                if isinstance(market["outcomes"], str):
                    outcomes = json.loads(market["outcomes"])
                else:
                    outcomes = market["outcomes"]
            except:
                outcomes = []
        
        if "outcomePrices" in market:
            try:
                if isinstance(market["outcomePrices"], str):
                    outcome_prices = json.loads(market["outcomePrices"])
                else:
                    outcome_prices = market["outcomePrices"]
            except:
                outcome_prices = []
        
        # Add outcomes if available
        if outcomes and outcome_prices:
            summary += "Current probabilities:\n"
            for i, outcome in enumerate(outcomes):
                if i < len(outcome_prices):
                    price = float(outcome_prices[i])
                    summary += f"  {outcome}: {price * 100:.2f}%\n"
        else:
            summary += "Current probability: Not available\n"
        
        # Market dates
        if "startDate" in market and market["startDate"]:
            summary += f"Market Start Date: {market['startDate']}\n"
        
        if "endDate" in market and market["endDate"]:
            summary += f"Market End Date: {market['endDate']}\n"
        
        # Market stats
        if "volume" in market and market["volume"]:
            try:
                volume = float(market["volume"])
                summary += f"Volume: ${volume:.2f}\n"
            except:
                pass
        
        if "liquidity" in market and market["liquidity"]:
            try:
                liquidity = float(market["liquidity"])
                summary += f"Liquidity: ${liquidity:.2f}\n"
            except:
                pass
        
        # Add Polymarket link
        event_slug = market.get('eventSlug', '')
        if event_slug:
            summary += f"Link: https://polymarket.com/event/{event_slug}\n"
        
        return summary
    
    except Exception as e:
        return f"Error getting market summary: {str(e)}"
    
def main():
    """Script entry point"""
    search_term = None
    
    # Check if search parameter was provided
    if len(sys.argv) >= 3 and sys.argv[1] == "--search":
        search_term = sys.argv[2]
        logging.info(f"Filtering markets with search term: '{search_term}'")
    
    # Get current UTC time and display it
    current_utc_time = datetime.datetime.now(timezone.utc)
    logging.info(f"Current UTC time: {current_utc_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Search for all active cricket markets
    logging.info("Searching for cricket markets. This may take a moment...")
    cricket_markets = search_cricket_markets()
    
    if not cricket_markets:
        logging.warning("No cricket markets found where the match has already started.")
        logging.warning("There may be no active cricket matches currently in progress.")
        return
    
    logging.info(f"Found {len(cricket_markets)} total cricket markets where matches have started or may be in progress.")
    
    # Filter markets if a search term was provided
    if search_term:
        matching_markets = find_match(cricket_markets, search_term)
        if not matching_markets:
            logging.warning(f"No markets found matching search term: '{search_term}'")
            logging.info("Showing all available started cricket markets instead.")
            matching_markets = cricket_markets
    else:
        matching_markets = cricket_markets
    
    # Sort markets by gameStartTime (most recently started first)
    try:
        def get_start_time(market):
            game_start = market.get("gameStartTime", "9999-12-31T00:00:00Z")
            try:
                return datetime.datetime.fromisoformat(game_start.replace('Z', '+00:00'))
            except:
                return datetime.datetime.max
        
        matching_markets.sort(key=get_start_time, reverse=True)
    except Exception as e:
        logging.warning(f"Error sorting markets by gameStartTime: {e}", exc_info=True)
        # If sorting fails, keep original order
    # Check markets for high probability, send initial alerts, and identify markets to monitor
    logging.info("\nChecking markets for initial high probability alerts (>70%)...")
    monitoring_markets = {} # Stores {market_id: market_data} for markets > 70%

    for market in matching_markets:
        market_id = market.get("id")
        # Skip if already being monitored from a previous check in this run
        if market_id in monitoring_markets:
            continue

        outcome_prices_raw = market.get("outcomePrices")
        outcomes_raw = market.get("outcomes")
        question = market.get("question", "N/A")
        game_start_time_raw = market.get("gameStartTime", "N/A")
        
        outcome_prices = []
        outcomes = []

        # Parse outcome prices
        if outcome_prices_raw:
            try:
                if isinstance(outcome_prices_raw, str):
                    outcome_prices = json.loads(outcome_prices_raw)
                else:
                    outcome_prices = outcome_prices_raw
                
                # Ensure prices are floats
                outcome_prices = [float(p) for p in outcome_prices]
            except (json.JSONDecodeError, ValueError) as e:
                debug_print(f"Could not parse outcomePrices for market {market_id}: {e}")
                outcome_prices = []

        # Parse outcomes
        if outcomes_raw:
             try:
                if isinstance(outcomes_raw, str):
                    outcomes = json.loads(outcomes_raw)
                else:
                    outcomes = outcomes_raw
             except json.JSONDecodeError as e:
                debug_print(f"Could not parse outcomes for market {market_id}: {e}")
                outcomes = []

        # Check probabilities
        high_prob_found = False
        probabilities_text = ""
        if outcomes and outcome_prices and len(outcomes) == len(outcome_prices):
             probabilities_text = "\n".join([f"  - {outcomes[i]}: {price * 100:.1f}%" for i, price in enumerate(outcome_prices)])
             for i, price in enumerate(outcome_prices):
                 if price > 0.60:
                     high_prob_found = True
                     break # Found one, no need to check further for this market

        # Send alert if high probability found
        if high_prob_found:
            alert_message = (
                f"**High Probability Alert (>70%)**\n\n"
                f"**Market:** {question}\n"
                f"**Game Start Time:** {game_start_time_raw}\n"
                f"**Probabilities:**\n{probabilities_text}"
            )
            logging.info(f"Sending high probability alert for market: {question} (ID: {market_id})")
            send_discord_alert(alert_message)
            # Add to monitoring list
            monitoring_markets[market_id] = {
                "question": question,
                "outcomes": outcomes, # Store the initial outcomes for context
                "initial_probabilities_text": probabilities_text # Store initial state
            }

    # --- Continuous Monitoring Loop ---
    if monitoring_markets:
        logging.info(f"\n--- Starting continuous monitoring for {len(monitoring_markets)} market(s) with >70% probability ---")

    while monitoring_markets:
        market_ids_to_check = list(monitoring_markets.keys()) # Iterate over a copy
        all_below_threshold = True # Assume all will drop below threshold in this check

        logging.info(f"\n--- Checking {len(market_ids_to_check)} monitored market(s) at {datetime.datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} ---")

        for market_id in market_ids_to_check:
            if market_id not in monitoring_markets: # Might have been removed in this loop run
                continue

            original_market_data = monitoring_markets[market_id]
            logging.info(f"Checking market: {original_market_data.get('question', market_id)}")
            latest_market_data = get_market_details(market_id)

            if latest_market_data is None:
                logging.warning(f"Could not fetch latest details for market {market_id}. Will retry next cycle.")
                all_below_threshold = False # Keep monitoring if fetch fails
                continue

            # Re-parse latest outcomes and prices
            latest_outcome_prices_raw = latest_market_data.get("outcomePrices")
            latest_outcomes_raw = latest_market_data.get("outcomes")
            latest_question = latest_market_data.get("question", "N/A")

            latest_outcome_prices = []
            latest_outcomes = []

            # Determine the iterable source for prices
            iterable_source = []
            if isinstance(latest_outcome_prices_raw, str):
                try:
                    iterable_source = json.loads(latest_outcome_prices_raw)
                except (json.JSONDecodeError, ValueError):
                    logging.warning(f"Could not parse outcomePrices string for market {market_id}: {latest_outcome_prices_raw}")
                    # iterable_source remains []
            elif isinstance(latest_outcome_prices_raw, list): # Check if it's already a list
                 iterable_source = latest_outcome_prices_raw
            elif latest_outcome_prices_raw is not None: # Handle cases where it's not None but also not str/list
                logging.warning(f"Unexpected type for outcomePrices for market {market_id}: {type(latest_outcome_prices_raw)}")
                # iterable_source remains []

            # Now create the list of floats if iterable_source is valid
            if iterable_source:
                try:
                    latest_outcome_prices = [float(p) for p in iterable_source]
                except (ValueError, TypeError) as e:
                    logging.warning(f"Could not convert all outcome prices to float for market {market_id}: {e}. Prices: {iterable_source}")
                    latest_outcome_prices = [] # Default to empty list if conversion fails

            if latest_outcomes_raw:
                 try:
                    latest_outcomes = json.loads(latest_outcomes_raw) if isinstance(latest_outcomes_raw, str) else latest_outcomes_raw
                 except json.JSONDecodeError:
                    latest_outcomes = []

            # Check latest probabilities
            still_high_prob = False
            latest_probabilities_text = "N/A"
            if latest_outcomes and latest_outcome_prices and len(latest_outcomes) == len(latest_outcome_prices):
                latest_probabilities_text = "\\n".join([f"  - {latest_outcomes[i]}: {price * 100:.1f}%" for i, price in enumerate(latest_outcome_prices)])
                for price in latest_outcome_prices:
                    if price > 0.60:
                        still_high_prob = True
                        break

            if still_high_prob:
                logging.info(f"Market '{latest_question}' (ID: {market_id}) still has >70% probability. Continuing monitoring.")
                # Replace backslashes before using in f-string
                send_discord_alert(alert_message)
                debug_probs = latest_probabilities_text.replace('\\n', '\n')
                logging.debug(f"Latest probabilities:\n{debug_probs}")
                all_below_threshold = False # At least one market is still high
            else:
                logging.info(f"Market '{latest_question}' (ID: {market_id}) probability dropped below 70%. Stopping monitoring for this market.")
                resolved_message = (
                    f"**Probability Resolved (<70%)**\n\n"
                    f"**Market:** {latest_question}\n"
                    f"**Initial Alert Probabilities:**\n{original_market_data.get('initial_probabilities_text', 'N/A')}\n"
                    f"**Current Probabilities:**\n{latest_probabilities_text}"
                )
                send_discord_alert(resolved_message)
                del monitoring_markets[market_id] # Remove from monitoring

        # Wait only if there are still markets to monitor
        if monitoring_markets:
            logging.info(f"--- {len(monitoring_markets)} market(s) still being monitored. Waiting 10 minutes... ---")
            time.sleep(30) # Wait for 10 minutes
        else:
            logging.info("\n--- All monitored markets have dropped below 70%. Stopping continuous monitoring. ---")

    # --- End of Continuous Monitoring Loop ---

    # Log final summaries of initially found markets (optional, could be removed if noisy)
    logging.info("\n=== SUMMARY OF INITIALLY FOUND ACTIVE CRICKET MARKETS ===\n")
    if not matching_markets:
         logging.info("No relevant cricket markets were found in the initial search.")
    else:
        for i, market in enumerate(matching_markets):
            summary = get_market_summary(market)
            logging.info(f"--- Initial Market {i+1} of {len(matching_markets)} ---\n{summary}\n")

    logging.info("\nScript finished processing markets.")

if __name__ == "__main__":
    logging.info("="*50)
    logging.info("Starting Cricket Odds Fetcher for Polymarket")
    logging.info(f"Logging to: {LOG_FILE}")
    logging.info("Filtering for matches that have already started (gameStartTime >= current UTC time)")
    try:
        main()
    except Exception as e:
        logging.error(f"An unhandled exception occurred in main execution: {e}", exc_info=True)
    finally:
        logging.info("Cricket Odds Fetcher finished.")
        logging.info("="*50 + "\n")