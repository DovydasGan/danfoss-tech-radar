import os, requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from scripts.technologies import TECHNOLOGIES, RECENT_YEARS
load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
URL = "https://api.openalex.org/works"
KEY = os.getenv("OPENALEX_KEY")

def grouped(filter_str, group_by):
    r = requests.get(URL, params={"filter": filter_str, "group_by": group_by, "api_key": KEY})
    r.raise_for_status()
    return r.json()["group_by"]

def institution_details(ids):
    """Look up type and country for a batch of institution IDs."""
    short = [i.split("/")[-1] for i in ids]
    r = requests.get("https://api.openalex.org/institutions", params={
        "filter": "openalex:" + "|".join(short),
        "select": "id,type,country_code",
        "per_page": 100,
        "api_key": KEY,
    })
    r.raise_for_status()
    return {i["id"]: i for i in r.json()["results"]}

players, sectors, countries = [], [], []

for name, query in TECHNOLOGIES.items():
    base = f"title_and_abstract.search:{query},publication_year:{RECENT_YEARS}"

    # Top institutions overall + top companies
    top_all = grouped(base, "authorships.institutions.id")[:15]
    comp_groups = grouped(base + ",authorships.institutions.type:company",
                          "authorships.institutions.id")[:50]
    details = institution_details([g["key"] for g in top_all + comp_groups])
    top_comp = [g for g in comp_groups
                if details.get(g["key"], {}).get("type") == "company"][:10]

    for list_name, groups in [("overall", top_all), ("companies", top_comp)]:
        for rank, g in enumerate(groups, 1):
            d = details.get(g["key"], {})
            players.append({
                "technology": name, "list": list_name, "rank": rank,
                "institution": g["key_display_name"], "papers": g["count"],
                "type": d.get("type"), "country_code": d.get("country_code"),
            })

    # Sector split (company / education / government ...)
    for g in grouped(base, "authorships.institutions.type"):
        sectors.append({"technology": name, "sector": g["key_display_name"], "papers": g["count"]})

    # Countries
    for g in grouped(base, "authorships.countries")[:20]:
        countries.append({"technology": name, "country": g["key_display_name"],
                          "country_code": g["key"].split("/")[-1], "papers": g["count"]})
    print(f"{name}: done")

pd.DataFrame(players).to_csv(DATA_DIR / "players.csv", index=False)
pd.DataFrame(sectors).to_csv(DATA_DIR / "sectors.csv", index=False)
pd.DataFrame(countries).to_csv(DATA_DIR / "countries.csv", index=False)

top_companies = pd.DataFrame(players).query("list == 'companies' and rank <= 3")
print(top_companies[["technology", "rank", "institution", "papers"]].to_string(index=False))