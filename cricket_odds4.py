#!/usr/bin/env python3
"""
Cricket Odds Fetcher for Polymarket
This script finds all active cricket markets and displays their details,
with optional search functionality to filter specific matches
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
    try:
        print("Searching for cricket markets...")
        
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
                    print(f"Found {len(markets)} cricket markets related to ID {market_id}")
                    all_markets.extend(markets)
            except Exception as e:
                print(f"Error with market ID {market_id}: {e}")
                continue
        
        # Try direct request to all markets with filters for cricket
        print("Trying direct search for cricket markets...")
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
            
            print(f"Found {len(cricket_markets)} cricket markets through direct search")
            all_markets.extend(cricket_markets)
        
        debug_print(f"Total markets found before filtering: {len(all_markets)}")
        
        # Print a sample market to check its structure
        if all_markets and DEBUG:
            debug_print("Sample market structure:", all_markets[0])
        
        # Remove duplicates and filter for active markets
        seen_ids = set()
        unique_markets = []
        for market in all_markets:
            market_id = market.get("id")
            
            # Skip if we've seen this ID already
            if market_id in seen_ids:
                continue
                
            seen_ids.add(market_id)
            
            # Check if market is active - be lenient with criteria
            is_active = True
            if market.get("closed") == True:
                is_active = False
            
            # Include the market if it's active
            if is_active:
                unique_markets.append(market)
                
        debug_print(f"Unique active markets after filtering: {len(unique_markets)}")
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
        
        # Try to get more market details via Gamma API
        try:
            gamma_url = f"https://gamma-api.polymarket.com/markets/{market['id']}"
            response = requests.get(gamma_url)
            
            if response.status_code == 200:
                market_details = response.json()
                
                if "volume" in market_details and market_details["volume"]:
                    summary += f"Volume: ${float(market_details['volume']):.2f}\n"
                
                if "liquidity" in market_details and market_details["liquidity"]:
                    summary += f"Liquidity: ${float(market_details['liquidity']):.2f}\n"
                
                if "startDate" in market_details and market_details["startDate"]:
                    summary += f"Start Date: {market_details['startDate']}\n"
                
                if "endDate" in market_details and market_details["endDate"]:
                    summary += f"End Date: {market_details['endDate']}\n"
                    
                if "gameStartTime" in market_details and market_details["gameStartTime"]:
                    summary += f"Game Start Time: {market_details['gameStartTime']}\n"
        except Exception as e:
            print(f"Error getting additional market details: {e}")
            
            # Fallback to data in the original market object
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
            
            if "startDate" in market and market["startDate"]:
                summary += f"Start Date: {market['startDate']}\n"
            
            if "endDate" in market and market["endDate"]:
                summary += f"End Date: {market['endDate']}\n"
        
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
        print(f"Searching for: {search_term}")
    
    # Search for all active cricket markets
    print("Searching for cricket markets. This may take a moment...")
    cricket_markets = search_cricket_markets()
    
    if not cricket_markets:
        print("No cricket markets found. Make sure Polymarket has active cricket markets available.")
        return
    
    print(f"Found {len(cricket_markets)} active cricket markets.")
    
    # Filter markets if a search term was provided
    if search_term:
        matching_markets = find_match(cricket_markets, search_term)
        if not matching_markets:
            print(f"No markets found matching: {search_term}")
            print("\nShowing all available cricket markets instead:")
            matching_markets = cricket_markets
    else:
        matching_markets = cricket_markets
    
    # Sort markets by end date (if available)
    try:
        matching_markets.sort(key=lambda x: x.get("endDate", "9999-12-31"))
    except Exception:
        pass  # If sorting fails, keep original order
    
    # Print market summaries
    print("\n=== ACTIVE CRICKET MARKETS ===\n")
    for i, market in enumerate(matching_markets):
        print(f"--- Market {i+1} of {len(matching_markets)} ---")
        print(get_market_summary(market))
        print()
    
    # Initialize CLOB client only if needed for detailed views
    client = None
    
    # End program if no markets were found
    if not matching_markets:
        return

    # Allow user to select a market for detailed view
    while True:
        try:
            choice = input("\nEnter market number for detailed view (0 to exit): ")
            if choice == '0':
                break
            
            selected_idx = int(choice) - 1
            if selected_idx < 0 or selected_idx >= len(matching_markets):
                print("Invalid selection.")
                continue
            
            # Initialize CLOB client only when needed
            if client is None:
                client = get_clob_client()
            
            # Get market details
            selected_market = matching_markets[selected_idx]
            print(f"\n=== DETAILED MARKET INFORMATION: {selected_market['question']} ===\n")
            
            # Try to get more market details via Gamma API
            try:
                gamma_url = f"https://gamma-api.polymarket.com/markets/{selected_market['id']}"
                response = requests.get(gamma_url)
                
                if response.status_code == 200:
                    market_details = response.json()
                    debug_print("Detailed market data:", market_details)
                    # Use the more detailed market data
                    selected_market = market_details
            except Exception as e:
                print(f"Note: Could not get additional market details: {e}")
            
            # Display comprehensive information about the market
            print(f"Market ID: {selected_market['id']}")
            token_id = extract_token_id(selected_market)
            if token_id:
                print(f"Token ID: {token_id}")
            
            # Parse outcomes and prices
            outcomes = []
            outcome_prices = []
            if "outcomes" in selected_market:
                try:
                    if isinstance(selected_market["outcomes"], str):
                        outcomes = json.loads(selected_market["outcomes"])
                    else:
                        outcomes = selected_market["outcomes"]
                except:
                    pass
            
            if "outcomePrices" in selected_market:
                try:
                    if isinstance(selected_market["outcomePrices"], str):
                        outcome_prices = json.loads(selected_market["outcomePrices"])
                    else:
                        outcome_prices = selected_market["outcomePrices"]
                except:
                    pass
            
            if outcomes and outcome_prices:
                print("\nCurrent probabilities:")
                for i, outcome in enumerate(outcomes):
                    if i < len(outcome_prices):
                        price = float(outcome_prices[i])
                        print(f"  {outcome}: {price * 100:.2f}%")
            
            # Market dates
            if "startDate" in selected_market and selected_market["startDate"]:
                print(f"\nStart Date: {selected_market['startDate']}")
            if "endDate" in selected_market and selected_market["endDate"]:
                print(f"End Date: {selected_market['endDate']}")
            if "gameStartTime" in selected_market and selected_market["gameStartTime"]:
                print(f"Game Start Time: {selected_market['gameStartTime']}")
            
            # Market status
            status = []
            if selected_market.get("active", False):
                status.append("Active")
            if selected_market.get("closed", False):
                status.append("Closed")
            if status:
                print(f"Status: {', '.join(status)}")
            
            # Market volume and liquidity
            if "volume" in selected_market and selected_market["volume"]:
                try:
                    volume = float(selected_market["volume"])
                    print(f"Volume: ${volume:.2f}")
                except:
                    pass
            
            if "liquidity" in selected_market and selected_market["liquidity"]:
                try:
                    liquidity = float(selected_market["liquidity"])
                    print(f"Liquidity: ${liquidity:.2f}")
                except:
                    pass
            
            # Show Polymarket link
            event_slug = selected_market.get('eventSlug', '')
            if event_slug:
                print(f"\nPolymarket link: https://polymarket.com/event/{event_slug}")
            
            # Try to get order book if token ID is available
            if token_id:
                try:
                    print("\nAttempting to fetch order book data...")
                    order_book = client.get_order_book(token_id)
                    
                    if order_book:
                        # Add bid and ask information
                        if hasattr(order_book, 'bids') and order_book.bids:
                            print("\nTop bids (BUY orders):")
                            for i, bid in enumerate(order_book.bids[:3]):  # Show top 3 bids
                                print(f"  Price: ${bid.price} | Size: {bid.size}")
                        else:
                            print("\nNo bid orders found.")
                        
                        if hasattr(order_book, 'asks') and order_book.asks:
                            print("\nTop asks (SELL orders):")
                            for i, ask in enumerate(order_book.asks[:3]):  # Show top 3 asks
                                print(f"  Price: ${ask.price} | Size: {ask.size}")
                        else:
                            print("\nNo ask orders found.")
                    else:
                        print("\nNo order book data available.")
                except Exception as e:
                    print(f"\nCould not fetch order book: {e}")
            
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    print("Cricket Odds Fetcher for Polymarket")
    print("-----------------------------------")
    main()