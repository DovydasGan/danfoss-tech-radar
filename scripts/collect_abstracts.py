import os, requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from scripts.technologies import TECHNOLOGIES, MATURITY_YEARS
load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
KEY = os.getenv("OPENALEX_KEY")
SAMPLE_SIZE = 50

def rebuild_abstract(inv_index):
    """Turn OpenAlex's {word: [positions]} format back into text."""
    if not inv_index:
        return None
    positions = [(pos, word) for word, poss in inv_index.items() for pos in poss]
    return " ".join(word for _, word in sorted(positions))

rows = []
for name, query in TECHNOLOGIES.items():
    r = requests.get("https://api.openalex.org/works", params={
        "filter": f"title_and_abstract.search:{query},publication_year:{MATURITY_YEARS},"
                  f"type:article,has_abstract:true",
        "sample": SAMPLE_SIZE,
        "seed": 42,  # same random sample every run, so results are reproducible
        "per_page": SAMPLE_SIZE,
        "select": "id,display_name,publication_year,abstract_inverted_index",
        "api_key": KEY,
    })
    r.raise_for_status()
    for w in r.json()["results"]:
        abstract = rebuild_abstract(w["abstract_inverted_index"])
        if abstract:
            rows.append({
                "paper_id": w["id"].split("/")[-1],
                "technology": name,
                "year": w["publication_year"],
                "title": w["display_name"],
                "abstract": abstract,
            })
    print(f"{name}: {sum(1 for x in rows if x['technology'] == name)} abstracts")

pd.DataFrame(rows).to_csv(DATA_DIR / "abstracts.csv", index=False, encoding="utf-8")