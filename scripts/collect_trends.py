import os, requests
import pandas as pd
from dotenv import load_dotenv
from technologies import TECHNOLOGIES, YEARS
from pathlib import Path
load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
URL = "https://api.openalex.org/works"
KEY = os.getenv("OPENALEX_KEY")

def yearly_counts(filter_str):
    r = requests.get(URL, params={
        "filter": filter_str,
        "group_by": "publication_year",
        "api_key": KEY,
    })
    r.raise_for_status()
    return {int(g["key"]): g["count"] for g in r.json()["group_by"]}

rows = []
for name, query in TECHNOLOGIES.items():
    counts = yearly_counts(f"title_and_abstract.search:{query},publication_year:{YEARS}")
    for year, n in counts.items():
        rows.append({"technology": name, "year": year, "papers": n})
    print(f"{name}: done")

# Baseline: all research published per year
baseline = yearly_counts(f"publication_year:{YEARS}")
base_df = pd.DataFrame([{"year": y, "total_papers": n} for y, n in baseline.items()])

trends = pd.DataFrame(rows).sort_values(["technology", "year"])
trends.to_csv(DATA_DIR / "trends.csv", index=False)
base_df.sort_values("year").to_csv(DATA_DIR / "baseline.csv", index=False)

print(trends.pivot(index="year", columns="technology", values="papers"))