import os, time, sys
import pandas as pd
from pathlib import Path
from typing import Literal
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_PATH = DATA_DIR / "classified.csv"
MODEL = "gemini-3.1-flash-lite"
BATCH_SIZE = 25
client = genai.Client(api_key=os.getenv("GEMINI_KEY"))

class Classification(BaseModel):
    paper_id: str
    is_relevant: bool
    maturity: Literal["Fundamental research", "Lab prototype",
                      "Field demonstration", "Commercial deployment"]
    confidence: Literal["low", "medium", "high"]
    evidence: str

PROMPT = """You are a technology analyst assessing how close research is to market.
Technology area: {tech}

For each paper, return:
- is_relevant: true only if the paper is genuinely about {tech}. False if it only mentions
  it in passing, or if the text is not a real research abstract (e.g. publisher boilerplate).
- maturity, based on Technology Readiness Levels:
  - "Fundamental research" (TRL 1-3): theory, modelling, simulation, materials or concept
    studies with no physical prototype.
  - "Lab prototype" (TRL 4-5): a device or system built and tested in a laboratory.
  - "Field demonstration" (TRL 6-7): tested in a real operating environment or pilot site.
  - "Commercial deployment" (TRL 8-9): commercial products or installed systems, including
    their optimisation, operation, market or regulation.
- confidence: how clearly the abstract supports your maturity choice.
- evidence: max 20 words, in English, explaining the choice.

Abstracts may be in any language. Judge only from the text given.
Return exactly one entry per paper, using the exact paper_id.

Papers:
{papers}"""

abstracts = pd.read_csv(DATA_DIR / "abstracts.csv")
done = pd.read_csv(OUT_PATH) if OUT_PATH.exists() else pd.DataFrame(columns=["paper_id"])
todo = abstracts[~abstracts.paper_id.isin(done.paper_id)]
print(f"Already classified: {len(done)} | To do: {len(todo)}")
results = []

def save_and_report():
    combined = done
    if results:
        new = todo.drop(columns="abstract").merge(pd.DataFrame(results), on="paper_id")
        combined = pd.concat([done, new], ignore_index=True)
    combined.to_csv(OUT_PATH, index=False, encoding="utf-8")
    print(f"\nSaved {len(combined)} of {len(abstracts)} papers.")
    if len(combined) == len(abstracts):
        print("\nShare relevant:\n", combined.groupby("technology").is_relevant.mean().round(2))
        rel = combined[combined.is_relevant == True]
        print("\nMaturity (relevant papers only):\n", pd.crosstab(rel.technology, rel.maturity))

for tech, group in todo.groupby("technology"):
    for start in range(0, len(group), BATCH_SIZE):
        batch = group.iloc[start:start + BATCH_SIZE]
        papers = "\n\n".join(
            f"paper_id: {r.paper_id}\nTitle: {r.title}\nAbstract: {r.abstract}"
            for r in batch.itertuples())

        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=MODEL,
                    contents=PROMPT.format(tech=tech, papers=papers),
                    config={"response_mime_type": "application/json",
                            "response_schema": list[Classification],
                            "temperature": 0},
                )
                parsed = resp.parsed
                expected = set(batch.paper_id)
                seen = set()
                for c in parsed:
                    if c.paper_id in expected and c.paper_id not in seen:  # skip unknown or duplicate IDs
                        results.append(c.model_dump())
                        seen.add(c.paper_id)
                missing = expected - seen
                if missing:
                    print(f"  {len(missing)} paper(s) missing, will retry on next run: {missing}")
                break
            except Exception as e:
                if "RESOURCE_EXHAUSTED" in str(e):
                    print("Daily quota reached. Saving progress; rerun later to continue.")
                    save_and_report()
                    sys.exit()
                print(f"  retry {attempt + 1}: {str(e)[:150]}")
                time.sleep(20)
        else:
            print(f"  WARNING: batch skipped for {tech} (will retry on next run)")

        print(f"{tech}: {min(start + BATCH_SIZE, len(group))}/{len(group)}")
        time.sleep(7)

save_and_report()