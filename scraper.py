import requests
from bs4 import BeautifulSoup

TARGETS = [
    {"name": "Demo Store A", "url": "https://books.toscrape.com/catalogue/category/books/travel_2/index.html"},
    {"name": "Demo Store B", "url": "https://books.toscrape.com/catalogue/category/books/fiction_10/index.html"},
    {"name": "Demo Store C", "url": "https://books.toscrape.com/catalogue/category/books/sports-and-games_17/index.html"},
]

def scrape_site(target):
    resp = requests.get(target["url"], timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    products = []
    for item in soup.select(".product_pod"):
        products.append({
            "name": item.select_one("h3 a")["title"],
            "price": item.select_one(".price_color").text.strip(),
        })
    return {"source": target["name"], "products": products}

def scrape_all():
    return [scrape_site(t) for t in TARGETS]