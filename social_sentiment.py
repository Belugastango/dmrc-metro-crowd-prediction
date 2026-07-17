import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import random
import datetime

class SocialSentimentAnalyzer:
    def __init__(self):
        # Simple keyword sets for basic sentiment analysis
        self.negative_keywords = {'crowd', 'crowded', 'rush', 'stuck', 'delay', 'delayed', 'late', 'terrible', 'worst', 'bad', 'packed', 'full', 'long line'}
        self.positive_keywords = {'smooth', 'fast', 'empty', 'clean', 'good', 'great', 'awesome', 'quick', 'love', 'best', 'comfortable'}

    def analyze_sentiment(self, text):
        text_lower = text.lower()
        
        neg_count = sum(1 for word in self.negative_keywords if word in text_lower)
        pos_count = sum(1 for word in self.positive_keywords if word in text_lower)
        
        if neg_count > pos_count:
            return "Negative", "🔴", -1
        elif pos_count > neg_count:
            return "Positive", "🟢", 1
        else:
            return "Neutral", "⚪", 0

    def fetch_google_news(self, query="Delhi Metro crowd OR ridership"):
        encoded_query = urllib.parse.quote(query)
        url = f'https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en'
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        articles = []
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                xml_data = response.read()
                root = ET.fromstring(xml_data)
                
                for item in root.findall('.//item')[:10]: # Top 10 articles
                    title = item.find('title').text
                    link = item.find('link').text
                    pubDate = item.find('pubDate').text
                    source = item.find('source').text if item.find('source') is not None else "News"
                    
                    sentiment, icon, score = self.analyze_sentiment(title)
                    
                    articles.append({
                        'title': title,
                        'link': link,
                        'date': pubDate,
                        'source': source,
                        'sentiment': sentiment,
                        'icon': icon
                    })
        except Exception as e:
            print(f"Error fetching news: {e}")
            # Fallback data if offline
            articles.append({
                'title': "Delhi Metro sees massive crowd on Blue Line",
                'link': "#",
                'date': "Just now",
                'source': "Mock News",
                'sentiment': "Negative",
                'icon': "🔴"
            })
        
        return articles

    def fetch_live_tweets(self, station_name=None):
        """
        Since Twitter API requires a paid key and free scrapers break frequently,
        this provides realistic simulated recent tweets based on the current time and station.
        """
        station_str = f" at {station_name}" if station_name else " on Delhi Metro"
        
        templates = [
            ("Negative", f"Stuck in a massive crowd{station_str}. Moving at a snail's pace! 😭 #DelhiMetro"),
            ("Negative", f"Why is there always a delay on the Blue Line? So crowded{station_str}. #DMRC"),
            ("Negative", f"Avoid{station_str} if you can. Packed like sardines right now."),
            ("Positive", f"Surprisingly empty{station_str} today. Smooth commute! ✨"),
            ("Positive", f"Kudos to DMRC for managing the rush hour so well{station_str}."),
            ("Neutral",  f"Waiting for my train{station_str}."),
            ("Neutral",  f"Just another day traveling on the Delhi Metro{station_str}."),
            ("Negative", f"AC not working and huge crowd{station_str}. Unbearable."),
            ("Positive", f"Got a seat right away{station_str}! Best day ever 🎉"),
        ]
        
        # Select 5 random tweets, skewing slightly negative during typical rush hours
        now = datetime.datetime.now()
        is_rush = (8 <= now.hour <= 11) or (17 <= now.hour <= 20)
        
        if is_rush:
            weights = [0.2, 0.2, 0.2, 0.05, 0.05, 0.1, 0.1, 0.1, 0.0]
        else:
            weights = [0.1, 0.1, 0.1, 0.15, 0.15, 0.15, 0.15, 0.05, 0.05]
            
        selected_tweets = random.choices(templates, weights=weights, k=5)
        
        tweets = []
        for i, (expected_sentiment, text) in enumerate(selected_tweets):
            sentiment, icon, _ = self.analyze_sentiment(text)
            
            # Generate realistic recent times (within the last 2 hours)
            minutes_ago = random.randint(1, 120)
            time_str = f"{minutes_ago}m ago" if minutes_ago < 60 else f"{minutes_ago//60}h {minutes_ago%60}m ago"
            
            tweets.append({
                'user': f"@MetroUser{random.randint(100,999)}",
                'text': text,
                'time': time_str,
                'sentiment': sentiment,
                'icon': icon
            })
            
        return sorted(tweets, key=lambda x: ("h" in x['time'], int(''.join(filter(str.isdigit, x['time'])))))

