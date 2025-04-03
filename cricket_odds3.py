#!/usr/bin/env python3
"""
Improved Cricket Odds Fetcher with Market Slug Search
This script uses the Polymarket CLOB client library to search for cricket markets
and displays detailed information about odds.
"""

import sys
import os
import re
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

# Load environment variables from .env file
load_dotenv()

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
    
    return client

def extract_slug_from_url(url):
    """Extract the market slug from a Polymarket URL."""
    # Extract event name from path
    event_match = re.search(r'/event/([^/?]+)', url)
    if event_match:
        return event_match.group(1)
        
    return None

def normalize_team_name(name):
    """Normalize team names by removing common suffixes and converting to lowercase."""
    if not name:
        return ""
    
    name = name.lower()
    
    # Remove common suffixes
    suffixes = [" kings", " super kings", " royals", " indians", " capitals", 
                " knight riders", " titans", " super giants", " sunrisers"]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name.replace(suffix, "")
            break
    
    return name.strip()

def list_all_cricket_markets(client, search_term=None):
    """List all markets matching cricket or the search term, showing slug and question."""
    print("\nSearching for cricket markets...")
    all_markets = []

    # Define team mappings with more variations
    team_mappings = {
        "rcb": ["royal challengers", "bangalore", "rcb", "royal challengers bangalore"],
        "gt": ["gujarat", "titans", "gt", "gujarat titans"],
        "mi": ["mumbai", "indians", "mi", "mumbai indians"],
        "csk": ["chennai", "super kings", "csk", "chennai super kings"],
        "srh": ["sunrisers", "hyderabad", "srh", "sunrisers hyderabad"],
        "kkr": ["kolkata", "knight riders", "kkr", "kolkata knight riders"],
        "rr": ["rajasthan", "royals", "rr", "rajasthan royals"],
        "pbks": ["punjab", "kings", "pbks", "punjab kings"],
        "dc": ["delhi", "capitals", "dc", "delhi capitals"],
        "lsg": ["lucknow", "super giants", "lsg", "lucknow super giants"]
    }
    
    try:
        # First try to get simplified markets
        print("Fetching simplified markets...")
        markets_response = client.get_simplified_markets()
        
        # Debug the response structure
        print(f"\nAPI Response Type: {type(markets_response)}")
        
        # Process the response based on its structure
        if isinstance(markets_response, dict) and "data" in markets_response:
            markets_data = markets_response["data"]
            print(f"Found {len(markets_data)} markets in 'data' field")
            all_markets.extend(markets_data)
        elif isinstance(markets_response, list):
            print(f"Found {len(markets_response)} markets in response list")
            all_markets.extend(markets_response)
        else:
            print("Unexpected response format, trying to extract data...")
            if isinstance(markets_response, dict):
                for key, value in markets_response.items():
                    if isinstance(value, list) and len(value) > 0:
                        print(f"Found potential market data in key: {key} with {len(value)} items")
                        all_markets.extend(value)

    except Exception as e:
        print(f"Error fetching markets: {str(e)}")
        return []

    # Log the structure of the first item to understand the response format
    if all_markets and len(all_markets) > 0:
        sample = all_markets[0]
        print("\nSample market structure:")
        for key in sorted(sample.keys()):
            print(f"  {key}: {type(sample.get(key))}")
        
        # Print first few markets for debugging
        print("\nFirst few markets:")
        for i, market in enumerate(all_markets[:3]):
            if isinstance(market, dict):
                print(f"Market {i+1}:")
                for key in ['question', 'slug', 'eventSlug', 'conditionId']:
                    if key in market:
                        print(f"  {key}: {market.get(key)}")
    else:
        print("No markets found in the response")
        return []

    # Filter for cricket markets with improved logic
    cricket_markets = []
    cricket_terms = ["ipl", "cricket", "t20", "vs.", "vs", "match"]
    
    for market in all_markets:
        if not isinstance(market, dict):
            continue
            
        # Extract and normalize fields
        market_data = {
            'id': str(market.get('id', '')),
            'conditionId': str(market.get('conditionId', '')),
            'slug': str(market.get('slug', '')).lower(),
            'eventSlug': str(market.get('eventSlug', '')).lower(),
            'question': str(market.get('question', '')).lower(),
            'description': str(market.get('description', '')).lower(),
            'outcomes': market.get('outcomes', '[]')
        }
        
        # Check if it's a cricket market based on content
        is_cricket = False
        
        # Check for cricket terms
        if any(term in value for term in cricket_terms for value in market_data.values() if isinstance(value, str)):
            is_cricket = True
        
        # Check for team names
        all_team_terms = [term.lower() for terms in team_mappings.values() for term in terms]
        has_teams = any(team in value for team in all_team_terms for value in market_data.values() if isinstance(value, str))
        
        # Check if it's a match between two teams (contains 'vs' or 'vs.')
        vs_pattern = r'\b(vs\.?|versus)\b'
        has_vs = any(re.search(vs_pattern, value) for value in market_data.values() if isinstance(value, str))
        
        if is_cricket or (has_teams and has_vs):
            cricket_markets.append(market)
            print(f"\nFound cricket market: {market.get('question', 'N/A')}")
    
    print(f"\nFound {len(cricket_markets)} cricket-related markets")
    
    # Now search within cricket markets with improved matching
    matching_markets = []
    if search_term:
        search_term = search_term.lower()
        print(f"Searching for term: {search_term}")
        
        # Handle "vs" format
        if " vs " in search_term or " vs. " in search_term:
            # Extract team names
            parts = re.split(r'\s+vs\.?\s+', search_term)
            team1, team2 = [normalize_team_name(part) for part in parts]
            print(f"Looking for match between: {team1} and {team2}")
            
            # Find markets that have both teams
            for market in cricket_markets:
                market_text = " ".join([
                    str(market.get("slug", "")),
                    str(market.get("question", "")),
                    str(market.get("eventSlug", "")),
                    str(market.get("description", ""))
                ]).lower()
                
                # Check if both teams are present
                if team1 in market_text and team2 in market_text:
                    matching_markets.append({
                        "market_id": market.get("conditionId"),
                        "market_slug": market.get("slug") or market.get("eventSlug"),
                        "question": market.get("question"),
                        "token_id": extract_token_id(market)
                    })
                    print(f"Found match: {market.get('question')}")
        else:
            # Handle single team or keyword search
            search_parts = search_term.split()
            
            for market in cricket_markets:
                market_text = " ".join([
                    str(market.get("slug", "")),
                    str(market.get("question", "")),
                    str(market.get("eventSlug", "")),
                    str(market.get("description", ""))
                ]).lower()
                
                # Check if all search parts are in the market text
                if all(part in market_text for part in search_parts):
                    matching_markets.append({
                        "market_id": market.get("conditionId"),
                        "market_slug": market.get("slug") or market.get("eventSlug"),
                        "question": market.get("question"),
                        "token_id": extract_token_id(market)
                    })
                    print(f"Found match: {market.get('question')}")
    
    return matching_markets

def extract_token_id(market):
    """Extract token ID from a market object with improved handling."""
    # Try multiple approaches to extract token IDs
    if "tokenIds" in market and market["tokenIds"]:
        if isinstance(market["tokenIds"], list) and len(market["tokenIds"]) > 0:
            return market["tokenIds"][0]
    
    if "token_ids" in market and market["token_ids"]:
        if isinstance(market["token_ids"], list) and len(market["token_ids"]) > 0:
            return market["token_ids"][0]
    
    if "outcome_token_ids" in market:
        outcomes = market["outcome_token_ids"]
        if isinstance(outcomes, list) and len(outcomes) > 0:
            if all(isinstance(item, dict) for item in outcomes):
                return outcomes[0].get("id")
            else:
                return outcomes[0]
        elif isinstance(outcomes, dict):
            return outcomes.get("id")
    
    # For YES tokens, often token ID is directly available
    if "tokenId" in market:
        return market["tokenId"]
    
    # Use condition ID as fallback
    return market.get("conditionId")

def search_by_market_slug(client, search_term_or_url):
    """Search for markets where the slug contains the search term."""
    # Check if input is a URL
    if search_term_or_url.startswith("http"):
        print("URL detected, extracting slug...")
        search_term = extract_slug_from_url(search_term_or_url)
        if not search_term:
            print("Could not extract slug from URL. Using full URL as search term.")
            search_term = search_term_or_url
    else:
        search_term = search_term_or_url
    
    print(f"Searching for market with term: {search_term}")
    
    # Get all markets matching the search term
    matching_markets = list_all_cricket_markets(client, search_term)
    
    return matching_markets

def get_market_odds(client, market):
    """Get the current odds for a specific market."""
    print(f"Getting odds for market: {market['market_id']}")
    print(f"Market slug: {market['market_slug']}")
    print(f"Using token ID: {market['token_id']}")
    
    token_id = market["token_id"]
    if not token_id:
        return "No token ID available for this market"
    
    try:
        # Try to get order book for the market
        try:
            order_book = client.get_order_book(token_id)
        except Exception as e:
            print(f"Error getting order book: {str(e)}")
            return f"Could not get order book: {str(e)}"
        
        if not order_book:
            return "No orderbook found for this market"
        
        # Try to get mid-point price
        midpoint = None
        try:
            midpoint = client.get_midpoint(token_id)
        except Exception as e:
            print(f"Couldn't get midpoint: {str(e)}")
            # Calculate midpoint manually if API call fails
            if hasattr(order_book, 'bids') and order_book.bids and hasattr(order_book, 'asks') and order_book.asks:
                best_bid = float(order_book.bids[0].price)
                best_ask = float(order_book.asks[0].price)
                midpoint = {"mid": (best_bid + best_ask) / 2}
                print(f"Calculated midpoint manually: {midpoint['mid']}")
        
        # Format the output
        formatted_output = f"Market Question: {market['question']}\n"
        formatted_output += f"Market Slug: {market['market_slug']}\n"
        formatted_output += f"Market ID: {market['market_id']}\n"
        formatted_output += f"Token ID: {market['token_id']}\n\n"
        
        if midpoint and "mid" in midpoint:
            probability = float(midpoint["mid"]) * 100
            formatted_output += f"Current probability: {probability:.2f}%\n\n"
        else:
            formatted_output += "Current probability: Not available\n\n"
        
        # Add bid and ask information
        if hasattr(order_book, 'bids') and order_book.bids:
            formatted_output += "Top bids (BUY orders):\n"
            for i, bid in enumerate(order_book.bids[:5]):  # Show top 5 bids
                formatted_output += f"  Price: ${bid.price} | Size: {bid.size}\n"
        else:
            formatted_output += "No bid orders found.\n"
        
        if hasattr(order_book, 'asks') and order_book.asks:
            formatted_output += "\nTop asks (SELL orders):\n"
            for i, ask in enumerate(order_book.asks[:5]):  # Show top 5 asks
                formatted_output += f"  Price: ${ask.price} | Size: {ask.size}\n"
        else:
            formatted_output += "\nNo ask orders found.\n"
        
        return formatted_output
    except Exception as e:
        return f"Error getting odds: {str(e)}"

def read_matches_from_file(filename):
    """Read match search terms or URLs from a file."""
    try:
        with open(filename, 'r') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        print(f"Error: File {filename} not found.")
        return []

def main():
    """Script entry point."""
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python slug_search.py search_terms.txt [term_number]")
        print("       python slug_search.py --search \"search term\"")
        return
    
    # Check for direct search mode
    if sys.argv[1] == "--search" and len(sys.argv) >= 3:
        search_term = sys.argv[2]
        print(f"Direct search mode: {search_term}")
        
        # Initialize the CLOB client
        client = get_clob_client()
        
        # Search for markets
        markets = search_by_market_slug(client, search_term)
        
        if not markets:
            print(f"No markets found for: {search_term}")
            return
        
        # Print found markets
        print(f"\nFound {len(markets)} markets:")
        for i, market in enumerate(markets):
            print(f"{i+1}. Question: {market['question']}")
            print(f"   Slug: {market['market_slug']}")
            print()
        
        # Ask user to select a market
        selected_idx = int(input("Enter the number of the market to view (0 to exit): ")) - 1
        if selected_idx < 0 or selected_idx >= len(markets):
            print("Exiting...")
            return
        
        # Get and show odds for selected market
        odds = get_market_odds(client, markets[selected_idx])
        print("\nCurrent odds:")
        print(odds)
        return
    
    # File-based search mode
    matches_file = sys.argv[1]
    search_terms = read_matches_from_file(matches_file)
    
    if not search_terms:
        print("No search terms found in the file or file is empty.")
        return
    
    # Initialize the CLOB client
    client = get_clob_client()
    
    # If term number provided, search for that specific term
    if len(sys.argv) >= 3:
        try:
            term_idx = int(sys.argv[2]) - 1
            if term_idx < 0 or term_idx >= len(search_terms):
                print(f"Invalid term number. Please choose between 1 and {len(search_terms)}.")
                return
            
            search_term = search_terms[term_idx]
            print(f"Selected search term #{term_idx + 1}: {search_term}")
            
            # Search for markets
            markets = search_by_market_slug(client, search_term)
            
            if not markets:
                print(f"No markets found for: {search_term}")
                return
            
            # Print found markets
            print(f"\nFound {len(markets)} markets:")
            for i, market in enumerate(markets):
                print(f"{i+1}. Question: {market['question']}")
                print(f"   Slug: {market['market_slug']}")
                print()
            
            # If multiple markets found, ask user to select one
            if len(markets) > 1:
                selected_idx = int(input("Enter the number of the market to view (0 to exit): ")) - 1
                if selected_idx < 0 or selected_idx >= len(markets):
                    print("Exiting...")
                    return
            else:
                selected_idx = 0
            
            # Get and show odds for selected market
            odds = get_market_odds(client, markets[selected_idx])
            print("\nCurrent odds:")
            print(odds)
            
        except ValueError:
            print("Term number must be an integer.")
    else:
        # List all search terms and let user choose
        print("Available search terms:")
        for i, term in enumerate(search_terms):
            print(f"{i+1}. {term}")
        
        try:
            term_idx = int(input("Enter the number of the term to search for: ")) - 1
            if term_idx < 0 or term_idx >= len(search_terms):
                print(f"Invalid term number. Please choose between 1 and {len(search_terms)}.")
                return
            
            search_term = search_terms[term_idx]
            
            # Search for markets
            markets = search_by_market_slug(client, search_term)
            
            if not markets:
                print(f"No markets found for: {search_term}")
                return
            
            # Print found markets
            print(f"\nFound {len(markets)} markets:")
            for i, market in enumerate(markets):
                print(f"{i+1}. Question: {market['question']}")
                print(f"   Slug: {market['market_slug']}")
                print()
            
            # If multiple markets found, ask user to select one
            if len(markets) > 1:
                selected_idx = int(input("Enter the number of the market to view (0 to exit): ")) - 1
                if selected_idx < 0 or selected_idx >= len(markets):
                    print("Exiting...")
                    return
            else:
                selected_idx = 0
            
            # Get and show odds for selected market
            odds = get_market_odds(client, markets[selected_idx])
            print("\nCurrent odds:")
            print(odds)
            
        except ValueError:
            print("Term number must be an integer.")

if __name__ == "__main__":
    print("Cricket Odds Fetcher with Market Slug Search")
    main()