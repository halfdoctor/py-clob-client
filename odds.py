import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from datetime import datetime
import time
import random
import os
from dotenv import load_dotenv

class IPLOddsAnalyzer:
    def __init__(self, team_a, team_b, match_date):
        self.team_a = team_a
        self.team_b = team_b
        self.match_date = datetime.strptime(match_date, "%Y-%m-%d")
        self.betting_sites = [
            {"name": "Bet365", "url": "https://www.bet365.com/#/AC/B13/C1/D50/E2/F163/"},
            {"name": "Betway", "url": "https://betway.com/en/sports/cat/cricket"},
            {"name": "10CRIC", "url": "https://www.10cric.com/sports/cricket/t20-cup/"},
            {"name": "Dafabet", "url": "https://www.dafabet.com/in/sports"}
        ]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.odds_data = []
        
    def format_team_name(self, team_name):
        """Formats team name to handle different naming conventions across betting sites"""
        # Dictionary of common IPL team name variations
        team_variations = {
            "Mumbai Indians": ["MI", "Mumbai", "Mumbai I"],
            "Chennai Super Kings": ["CSK", "Chennai", "Chennai SK"],
            "Royal Challengers Bangalore": ["RCB", "Bangalore", "Royal Challengers"],
            "Kolkata Knight Riders": ["KKR", "Kolkata", "Knight Riders"],
            "Delhi Capitals": ["DC", "Delhi", "Capitals"],
            "Sunrisers Hyderabad": ["SRH", "Hyderabad", "Sunrisers"],
            "Punjab Kings": ["PBKS", "Punjab", "Kings XI Punjab"],
            "Rajasthan Royals": ["RR", "Rajasthan", "Royals"],
            "Lucknow Super Giants": ["LSG", "Lucknow", "Super Giants"],
            "Gujarat Titans": ["GT", "Gujarat", "Titans"]
        }
        
        # Return the standardized team name or the original if not found
        for full_name, variations in team_variations.items():
            if team_name in variations or team_name == full_name:
                return full_name
        return team_name
    
    def convert_to_decimal_odds(self, odds_str):
        """Convert various odds formats to decimal format"""
        # Check if already in decimal format (e.g., 1.50)
        if re.match(r'^\d+\.\d+$', odds_str):
            return float(odds_str)
        
        # Check if in fractional format (e.g., 1/2)
        if '/' in odds_str:
            num, denom = map(int, odds_str.split('/'))
            return 1 + (num / denom)
        
        # Check if in American format (e.g., +150 or -200)
        if odds_str.startswith('+'):
            return 1 + (int(odds_str[1:]) / 100)
        elif odds_str.startswith('-'):
            return 1 + (100 / int(odds_str[1:]))
        
        # If format not recognized, return None
        return None
    
    def calculate_implied_probability(self, decimal_odds):
        """Calculate implied probability from decimal odds"""
        return 1 / decimal_odds if decimal_odds else None
    
    def scrape_bet365(self):
        """Scrape odds from Bet365"""
        try:
            # Add delay to avoid detection as a bot
            time.sleep(random.uniform(1, 3))
            
            response = requests.get(self.betting_sites[0]["url"], headers=self.headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find the match section - this would need to be updated based on actual HTML structure
                match_elements = soup.find_all('div', class_=re.compile('event-item'))
                
                for match in match_elements:
                    match_title = match.find('div', class_='event-name').text.strip()
                    
                    if self.team_a in match_title and self.team_b in match_title:
                        odds_elements = match.find_all('div', class_='odds')
                        if len(odds_elements) >= 2:
                            team_a_odds = odds_elements[0].text.strip()
                            team_b_odds = odds_elements[1].text.strip()
                            
                            self.odds_data.append({
                                'platform': 'Bet365',
                                'team_a': self.team_a,
                                'team_a_odds': team_a_odds,
                                'team_a_odds_format': 'decimal',
                                'team_b': self.team_b,
                                'team_b_odds': team_b_odds,
                                'team_b_odds_format': 'decimal'
                            })
                            break
            else:
                print(f"Failed to access Bet365: Status code {response.status_code}")
                
        except Exception as e:
            print(f"Error scraping Bet365: {e}")
    
    def fetch_odds_api(self):
        """Fetch odds from an odds API service like The Odds API"""
        # Note: You would need to sign up for an API key
        # This is a placeholder for the actual API call

        load_dotenv()
        API_KEY = os.getenv("ODDS_API_KEY")  # Replace with actual API key
        try:
            api_url = f"https://api.the-odds-api.com/v4/sports/cricket_ipl/odds/?apiKey={API_KEY}&regions=us,uk,eu,au&markets=h2h"
            response = requests.get(api_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                for match in data:
                    home_team = self.format_team_name(match.get('home_team', ''))
                    away_team = self.format_team_name(match.get('away_team', ''))
                    
                    # Check if this is the match we're looking for
                    if ((home_team == self.team_a and away_team == self.team_b) or 
                        (home_team == self.team_b and away_team == self.team_a)):
                        
                        match_time = datetime.strptime(match.get('commence_time', ''), "%Y-%m-%dT%H:%M:%SZ")
                        
                        # Check if the match date matches
                        if match_time.date() == self.match_date.date():
                            for bookmaker in match.get('bookmakers', []):
                                bookmaker_name = bookmaker.get('title', '')
                                markets = bookmaker.get('markets', [])
                                
                                for market in markets:
                                    if market.get('key') == 'h2h':  # head to head market
                                        outcomes = market.get('outcomes', [])
                                        
                                        team_a_odds = None
                                        team_b_odds = None
                                        
                                        for outcome in outcomes:
                                            team_name = self.format_team_name(outcome.get('name', ''))
                                            if team_name == self.team_a:
                                                team_a_odds = outcome.get('price')
                                            elif team_name == self.team_b:
                                                team_b_odds = outcome.get('price')
                                        
                                        if team_a_odds and team_b_odds:
                                            self.odds_data.append({
                                                'platform': bookmaker_name,
                                                'team_a': self.team_a,
                                                'team_a_odds': str(team_a_odds),
                                                'team_a_odds_format': 'decimal',
                                                'team_b': self.team_b,
                                                'team_b_odds': str(team_b_odds),
                                                'team_b_odds_format': 'decimal'
                                            })
            else:
                print(f"API request failed with status code: {response.status_code}")
                
        except Exception as e:
            print(f"Error fetching from odds API: {e}")
    
    def scrape_all_platforms(self):
        """Scrape odds from all configured platforms"""
        print(f"Analyzing odds for {self.team_a} vs {self.team_b} on {self.match_date.strftime('%Y-%m-%d')}")
        
        # Scrape from Bet365
        self.scrape_bet365()
        
        # We'd add similar methods for other betting sites
        # self.scrape_betway()
        # self.scrape_10cric()
        # self.scrape_dafabet()
        
        # Use odds API as a fallback or additional source
        self.fetch_odds_api()
        
        # If we didn't get any odds data, add some sample data for testing
        if not self.odds_data:
            print("Warning: Using sample data as no odds could be scraped")
            self.add_sample_data()
    
    def add_sample_data(self):
        """Add sample data for testing when scraping fails"""
        self.odds_data = [
            {
                'platform': 'Sample Bookmaker 1',
                'team_a': self.team_a,
                'team_a_odds': '1.90',
                'team_a_odds_format': 'decimal',
                'team_b': self.team_b,
                'team_b_odds': '2.10',
                'team_b_odds_format': 'decimal'
            },
            {
                'platform': 'Sample Bookmaker 2',
                'team_a': self.team_a,
                'team_a_odds': '4/5',
                'team_a_odds_format': 'fractional',
                'team_b': self.team_b,
                'team_b_odds': '11/10',
                'team_b_odds_format': 'fractional'
            },
            {
                'platform': 'Sample Bookmaker 3',
                'team_a': self.team_a,
                'team_a_odds': '1.85',
                'team_a_odds_format': 'decimal',
                'team_b': self.team_b,
                'team_b_odds': '2.05',
                'team_b_odds_format': 'decimal'
            }
        ]
    
    def analyze_odds(self):
        """Analyze the collected odds data"""
        if not self.odds_data:
            print("No odds data available for analysis")
            return None
        
        # Create DataFrame for analysis
        df = pd.DataFrame(self.odds_data)
        
        # Convert all odds to decimal format
        df['team_a_decimal_odds'] = df['team_a_odds'].apply(self.convert_to_decimal_odds)
        df['team_b_decimal_odds'] = df['team_b_odds'].apply(self.convert_to_decimal_odds)
        
        # Calculate implied probabilities
        df['team_a_implied_prob'] = df['team_a_decimal_odds'].apply(self.calculate_implied_probability)
        df['team_b_implied_prob'] = df['team_b_decimal_odds'].apply(self.calculate_implied_probability)
        
        # Calculate average implied probabilities
        avg_prob_a = df['team_a_implied_prob'].mean()
        avg_prob_b = df['team_b_implied_prob'].mean()
        
        # Convert to percentages
        pct_a = avg_prob_a * 100
        pct_b = avg_prob_b * 100
        
        # Determine predicted winner
        if avg_prob_a > avg_prob_b:
            predicted_winner = self.team_a
            win_pct = pct_a
            lose_pct = pct_b
        else:
            predicted_winner = self.team_b
            win_pct = pct_b
            lose_pct = pct_a
        
        # Prepare result
        result = {
            'match': f"{self.team_a} vs {self.team_b}",
            'date': self.match_date.strftime("%Y-%m-%d"),
            'platforms_analyzed': len(df),
            'team_a': self.team_a,
            'team_a_win_pct': round(pct_a, 2),
            'team_b': self.team_b,
            'team_b_win_pct': round(pct_b, 2),
            'predicted_winner': predicted_winner,
            'win_probability': round(win_pct, 2),
            'detailed_odds': df.to_dict('records')
        }
        
        return result
    
    def print_results(self, results):
        """Print the analysis results"""
        if not results:
            print("No results to display")
            return
        
        print("\n" + "="*50)
        print(f"MATCH ANALYSIS: {results['match']} on {results['date']}")
        print("="*50)
        
        print(f"\nPlatforms analyzed: {results['platforms_analyzed']}")
        
        print("\nOdds Summary:")
        for platform in results['detailed_odds']:
            print(f"  {platform['platform']}: {platform['team_a']} @ {platform['team_a_odds']} vs {platform['team_b']} @ {platform['team_b_odds']}")
        
        print("\nImplied Win Probabilities:")
        print(f"  {results['team_a']}: {results['team_a_win_pct']}%")
        print(f"  {results['team_b']}: {results['team_b_win_pct']}%")
        
        print("\nPREDICTION:")
        print(f"Based on the analysis of betting odds, {results['predicted_winner']} has a {results['win_probability']}% chance of winning, "
              f"while {'the opponent' if results['predicted_winner'] == results['team_a'] else results['team_a']} "
              f"has a {results['team_b_win_pct'] if results['predicted_winner'] == results['team_a'] else results['team_a_win_pct']}% chance.")
    
    def run_analysis(self):
        """Run the complete analysis process"""
        self.scrape_all_platforms()
        results = self.analyze_odds()
        self.print_results(results)
        return results


def read_matches_from_file(file_path):
    """Reads matches and dates from the specified file."""
    matches = []
    try:
        with open(file_path, 'r') as file:
            for line in file:
                match_string = line.strip()
                # Split on the last space to separate the date
                last_space_index = match_string.rfind(' ')
                if last_space_index != -1:
                    teams = match_string[:last_space_index].strip()
                    match_date = match_string[last_space_index + 1:].strip()
                    team_a, team_b = map(str.strip, teams.split(' vs. '))
                    matches.append((team_a, team_b, match_date))
                else:
                    print(f"Invalid match format: {match_string}")
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
        return None
    except Exception as e:
        print(f"Error reading matches from file: {e}")
        return None
    return matches

import sys

if __name__ == "__main__":
    # Read matches from file
    matches = read_matches_from_file('matches.txt')
    
    if matches:
        # Check if a match number is provided as a command line argument
        if len(sys.argv) > 1:
            print(f"Command line arguments: {sys.argv}")  # Debugging print
            try:
                match_number = int(sys.argv[1])
                print(f"Match number: {match_number}")  # Debugging print
                # Adjust match_number to be zero-based index
                match_index = match_number - 1
                if 0 <= match_index < len(matches):
                    team_a, team_b, match_date = matches[match_index]
                    # Convert date format from YYYY.MM.DD to YYYY-MM-DD
                    match_date = match_date.replace('.', '-')
                    analyzer = IPLOddsAnalyzer(team_a, team_b, match_date)
                    analyzer.run_analysis()
                else:
                    print(f"Invalid match number. Please provide a number between 1 and {len(matches)}.")
            except ValueError:
                print("Invalid match number. Please provide an integer.")
        else:
            print("Please provide the match number as a command line argument.")
            print("For example: python3 odds.py 1")
    else:
        print("No matches found. Please check the matches file.")