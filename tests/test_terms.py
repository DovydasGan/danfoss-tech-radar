import os, requests
from dotenv import load_dotenv
from scripts.technologies import TECHNOLOGIES, YEARS
load_dotenv()

for name, query in TECHNOLOGIES.items():
    r = requests.get("https://api.openalex.org/works", params={
        "filter": f"title_and_abstract.search:{query},publication_year:{YEARS}",
        "sort": "cited_by_count:desc",
        "per_page": 5,
        "select": "display_name,publication_year",
        "api_key": os.getenv("OPENALEX_KEY"),
    }).json()
    print(f"\n=== {name}: {r['meta']['count']:,} papers ===")
    for w in r["results"]:
        print(f"  {w['publication_year']} | {w['display_name']}")