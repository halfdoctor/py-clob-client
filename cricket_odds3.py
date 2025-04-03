#!/usr/bin/env python3
"""
Improved Cricket Odds Fetcher for Polymarket
This script directly accesses the Gamma API to find cricket markets and display odds,
with fallback methods when orderbook is not available
"""

import sys
import os
import json
import requests
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

# Load environment variables from .env file
load_dotenv()

# Set to True for detailed logging
DEBUG = True

def debug_print(message, obj=None):
    """Print debug information if DEBUG is True"""
    if DEBUG:
        print(f"DEBUG: {message}")
        if obj is not None:
            if isinstance(obj, dict) or isinstance(obj, list):
                print(json.dumps(obj, indent=2))
            else:
                print(obj)

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
        print("API credentials set")
    else:
        print("No API credentials found, running in read-only mode")
    
    return client

def search_cricket_markets():
    """Search for cricket markets directly using the Gamma API"""
    # First find any cricket market to use as a reference
    try:
        print("Searching for cricket markets...")
        
        # We'll search a few known cricket market IDs and use them to find related markets
        # These are reference IDs for cricket markets
        reference_ids = ["531894", "531899", "531895", "531896"]
        all_markets = []
        
        for market_id in reference_ids:
            try:
                # Try to get related markets for this cricket market
                gamma_url = f"https://gamma-api.polymarket.com/markets/{market_id}/related-markets"
                params = {
                    "limit": 20,      # Get more related markets
                    "offset": 0,
                    "closed": "false"  # Only active markets
                }
                
                response = requests.get(gamma_url, params=params)
                
                if response.status_code == 200:
                    markets = response.json()
                    print(f"Found {len(markets)} cricket markets related to ID {market_id}")
                    all_markets.extend(markets)
                    
                    # If we found markets, we can stop searching
                    if len(markets) > 0:
                        break
                else:
                    print(f"Error with market ID {market_id}: Status {response.status_code}")
            except Exception as e:
                print(f"Error with market ID {market_id}: {e}")
                continue
        
        # If we didn't find any markets with related-markets, try direct API call
        if not all_markets:
            # Try direct request to all markets with filters for cricket
            print("Trying direct search...")
            gamma_url = "https://gamma-api.polymarket.com/markets"
            params = {"limit": 100}
            
            response = requests.get(gamma_url, params=params)
            
            if response.status_code == 200:
                markets = response.json()
                
                # Filter for cricket matches (look for team names)
                cricket_markets = []
                cricket_keywords = ["vs", "knight riders", "super kings", "capitals", 
                                   "indians", "royals", "sunrisers", "kings", "titans", 
                                   "super giants", "ipl", "cricket"]
                
                for market in markets:
                    market_text = " ".join([
                        str(market.get("question", "")),
                        str(market.get("slug", "")),
                        str(market.get("eventSlug", ""))
                    ]).lower()
                    
                    if any(keyword in market_text for keyword in cricket_keywords):
                        cricket_markets.append(market)
                
                all_markets.extend(cricket_markets)
                print(f"Found {len(cricket_markets)} cricket markets through direct search")
        
        # Remove duplicates
        seen_ids = set()
        unique_markets = []
        for market in all_markets:
            if market["id"] not in seen_ids:
                seen_ids.add(market["id"])
                unique_markets.append(market)
        
        return unique_markets
        
    except Exception as e:
        print(f"Error searching for cricket markets: {e}")
        return []

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
    token_id = None
    
    # Get the condition ID
    if "conditionId" in market:
        return market["conditionId"]
    
    return token_id

def get_market_details(client, market):
    """Get market details - provides data even when orderbook isn't available"""
    token_id = extract_token_id(market)
    if not token_id:
        return "No token ID available for this market"
    
    try:
        # Format the output
        formatted_output = f"Market: {market['question']}\n"
        formatted_output += f"Market ID: {market['id']}\n"
        formatted_output += f"Token ID: {token_id}\n\n"
        
        # Parse outcomes and prices from the market data
        outcomes = []
        outcome_prices = []
        
        if "outcomes" in market:
            try:
                outcomes = json.loads(market["outcomes"])
            except:
                outcomes = []
        
        if "outcomePrices" in market:
            try:
                outcome_prices = json.loads(market["outcomePrices"])
            except:
                outcome_prices = []
        
        # Add outcomes if available
        if outcomes and outcome_prices:
            formatted_output += "Current probabilities:\n"
            for i, outcome in enumerate(outcomes):
                if i < len(outcome_prices):
                    price = float(outcome_prices[i])
                    formatted_output += f"  {outcome}: {price * 100:.2f}%\n"
            formatted_output += "\n"
        else:
            formatted_output += "Current probability: Not available\n\n"
        
        # Try to get more market details via Gamma API
        try:
            gamma_url = f"https://gamma-api.polymarket.com/markets/{market['id']}"
            response = requests.get(gamma_url)
            
            if response.status_code == 200:
                market_details = response.json()
                
                if "volume" in market_details and market_details["volume"]:
                    formatted_output += f"Volume: ${float(market_details['volume']):.2f}\n"
                
                if "liquidity" in market_details and market_details["liquidity"]:
                    formatted_output += f"Liquidity: ${float(market_details['liquidity']):.2f}\n"
                
                if "startDate" in market_details and market_details["startDate"]:
                    formatted_output += f"Start Date: {market_details['startDate']}\n"
                
                if "endDate" in market_details and market_details["endDate"]:
                    formatted_output += f"End Date: {market_details['endDate']}\n"
                
                formatted_output += "\n"
        except Exception as e:
            print(f"Error getting market details: {e}")
        
        # Try to get order book - but this part might fail if no orders exist
        try:
            order_book = client.get_order_book(token_id)
            
            if order_book:
                # Add bid and ask information
                if hasattr(order_book, 'bids') and order_book.bids:
                    formatted_output += "Top bids (BUY orders):\n"
                    for i, bid in enumerate(order_book.bids[:5]):
                        formatted_output += f"  Price: ${bid.price} | Size: {bid.size}\n"
                else:
                    formatted_output += "No bid orders found.\n"
                
                if hasattr(order_book, 'asks') and order_book.asks:
                    formatted_output += "\nTop asks (SELL orders):\n"
                    for i, ask in enumerate(order_book.asks[:5]):
                        formatted_output += f"  Price: ${ask.price} | Size: {ask.size}\n"
                else:
                    formatted_output += "\nNo ask orders found.\n"
            else:
                formatted_output += "No order book data available (market may be new or inactive).\n"
                formatted_output += "Check Polymarket website for trading:\n"
                formatted_output += f"https://polymarket.com/event/{market.get('eventSlug', '')}\n"
        except Exception as e:
            formatted_output += "\nOrder book not available for this market.\n"
            formatted_output += "This could be because:\n"
            formatted_output += "1. The market is new and has no active orders yet\n"
            formatted_output += "2. Trading hasn't started for this match\n"
            formatted_output += "3. The API format has changed\n\n"
            formatted_output += "Check Polymarket website for trading:\n"
            formatted_output += f"https://polymarket.com/event/{market.get('eventSlug', '')}\n"
        
        # Add trading advice
        formatted_output += "\n---\n"
        formatted_output += "To trade on this market:\n"
        formatted_output += "1. Visit Polymarket.com and search for this match\n"
        formatted_output += "2. Or use the token ID with py-clob-client when trading becomes available\n"
        
        return formatted_output
    except Exception as e:
        return f"Error getting market details: {str(e)}"

def main():
    """Script entry point"""
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python cricket_odds.py --search \"team1 vs team2\"")
        return
    
    # Direct search mode
    if sys.argv[1] == "--search" and len(sys.argv) >= 3:
        search_term = sys.argv[2]
        print(f"Searching for: {search_term}")
        
        # Search for cricket markets
        print("Searching for cricket markets. This may take a moment...")
        cricket_markets = search_cricket_markets()
        
        if not cricket_markets:
            print("No cricket markets found.")
            return
        
        print(f"Found {len(cricket_markets)} cricket markets.")
        
        # Find the specific match
        matching_markets = find_match(cricket_markets, search_term)
        
        if not matching_markets:
            print(f"No markets found matching: {search_term}")
            
            # Show all available markets as a hint
            print("\nAvailable cricket markets:")
            for i, market in enumerate(cricket_markets):
                print(f"{i+1}. {market['question']}")
            
            # Offer alternative search suggestions
            if " vs " in search_term:
                teams = search_term.lower().split(" vs ")
                print(f"\nTry these alternative searches:")
                print(f"- python cricket_odds.py --search \"{teams[1]} vs {teams[0]}\"")  # Reverse order
                
            return
        
        # Print found markets
        print(f"\nFound {len(matching_markets)} matching markets:")
        for i, market in enumerate(matching_markets):
            print(f"{i+1}. {market['question']}")
            
            # Parse and print outcomes
            try:
                outcomes = json.loads(market['outcomes'])
                prices = json.loads(market['outcomePrices'])
                outcomes_str = ", ".join([f"{outcomes[j]} ({float(prices[j])*100:.0f}%)" for j in range(len(outcomes))])
                print(f"   Outcomes: {outcomes_str}")
            except:
                pass
            
            # Print token ID
            token_id = extract_token_id(market)
            if token_id:
                print(f"   Token ID: {token_id}")
            
            print()
        
        # Select a market
        if len(matching_markets) > 1:
            try:
                selected_idx = int(input("Enter the number of the market to view (0 to exit): ")) - 1
                if selected_idx < 0 or selected_idx >= len(matching_markets):
                    print("Exiting...")
                    return
            except ValueError:
                print("Invalid input. Exiting...")
                return
        else:
            selected_idx = 0
        
        # Initialize CLOB client and get market details
        client = get_clob_client()
        market_details = get_market_details(client, matching_markets[selected_idx])
        
        print("\nMarket Details:")
        print(market_details)
        
        # Print direct Polymarket link
        event_slug = matching_markets[selected_idx].get('eventSlug', '')
        if event_slug:
            print(f"\nDirect link: https://polymarket.com/event/{event_slug}")

if __name__ == "__main__":
    print("Improved Cricket Odds Fetcher for Polymarket")
    main()