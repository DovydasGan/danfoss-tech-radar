from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT_DIR = ROOT / "knowledge"
OUT_DIR.mkdir(exist_ok=True)

START, END = 2020, 2025          # growth window
PLAYERS_PERIOD = "2021–2025"
STAGES = ["Fundamental research", "Lab prototype", "Field demonstration", "Commercial deployment"]

# ---------- load ----------
trends = pd.read_csv(DATA / "trends.csv")
baseline = pd.read_csv(DATA / "baseline.csv")
players = pd.read_csv(DATA / "players.csv")
sectors = pd.read_csv(DATA / "sectors.csv")
countries = pd.read_csv(DATA / "countries.csv")
classified = pd.read_csv(DATA / "classified.csv")


def as_bool(series):
    return series.astype(str).str.strip().str.lower().eq("true")


classified["is_relevant"] = as_bool(classified["is_relevant"])

# Merge companies listed per country, e.g. "Infineon Technologies (Germany)" + "(Austria)"
players["organisation"] = players["institution"].str.split(" (", n=1, regex=False).str[0]

# Papers per million (share of all research)
trends = trends.merge(baseline, on="year")
trends["per_million"] = trends["papers"] / trends["total_papers"] * 1e6


def cagr(start, end, years):
    return (end / start) ** (1 / years) - 1 if start > 0 else float("nan")


def pct(x, decimals=0):
    return f"{x * 100:.{decimals}f}%"


# ---------- per-technology metrics ----------
metrics = {}
for tech, g in trends.groupby("technology"):
    g = g.set_index("year")
    m = {
        "papers_recent": int(g.loc[2021:2025, "papers"].sum()),
        "papers_start": int(g.loc[START, "papers"]),
        "papers_end": int(g.loc[END, "papers"]),
        "papers_2015": int(g.loc[2015, "papers"]),
        "pm_start": g.loc[START, "per_million"],
        "pm_end": g.loc[END, "per_million"],
    }
    m["cagr"] = cagr(m["papers_start"], m["papers_end"], END - START)
    m["rel_cagr"] = cagr(m["pm_start"], m["pm_end"], END - START)
    m["share_multiple"] = m["pm_end"] / m["pm_start"]

    s = sectors[sectors.technology == tech]
    m["company_share"] = s.loc[s.sector == "company", "papers"].sum() / s["papers"].sum()

    rel = classified[(classified.technology == tech) & classified.is_relevant]
    m["n_classified"] = len(rel)
    m["maturity"] = rel["maturity"].value_counts(normalize=True).reindex(STAGES, fill_value=0)
    metrics[tech] = m

techs = sorted(metrics, key=lambda t: metrics[t]["rel_cagr"], reverse=True)
total = len(techs)


def ordinal(n):
    if n == total:
        return "slowest"
    return {1: "fastest", 2: "second fastest", 3: "third fastest", 4: "fourth fastest"}.get(n, f"{n}th fastest")


lines = []
add = lines.append

# ---------- header ----------
add("# Technology Scouting Radar: knowledge brief")
add("")
add("This brief summarises research activity in five technologies relevant to Danfoss: "
    + ", ".join(techs[:-1]) + f" and {techs[-1]}. "
    "Data comes from OpenAlex, an open index of research papers, retrieved in October 2026. "
    "All figures describe published research, not market sales or adoption.")
add("")

# ---------- cross-technology overview ----------
add("## Overview: comparing the five technologies")
add("")
add(f"Ranking by growth in share of all research, {START}–{END} (fastest first):")
for i, t in enumerate(techs, 1):
    m = metrics[t]
    add(f"{i}. {t}: {pct(m['rel_cagr'], 1)} per year relative to all research "
        f"({pct(m['cagr'], 1)} per year in raw paper counts).")
add("")
by_size = sorted(techs, key=lambda t: metrics[t]["papers_recent"], reverse=True)
add(f"Ranking by research volume, papers published {PLAYERS_PERIOD} (largest first):")
for i, t in enumerate(by_size, 1):
    add(f"{i}. {t}: {metrics[t]['papers_recent']:,} papers.")
add("")
by_company = sorted(techs, key=lambda t: metrics[t]["company_share"], reverse=True)
add(f"Ranking by share of research involving companies, {PLAYERS_PERIOD} (a sign of closeness to market):")
for i, t in enumerate(by_company, 1):
    add(f"{i}. {t}: {pct(metrics[t]['company_share'])} of research.")
add("")
falling = [t for t in techs if metrics[t]["rel_cagr"] < 0]
if falling:
    add("Technologies growing slower than research overall (losing share): " + ", ".join(falling) + ".")
    add("")

# ---------- one section per technology ----------
for rank, tech in enumerate(techs, 1):
    m = metrics[tech]
    add(f"## {tech}")
    add("")

    # Growth
    direction = "faster" if m["rel_cagr"] >= 0 else "slower"
    add(f"**{tech}: growth.** {tech} is the {ordinal(rank)}-growing of the five technologies. "
        f"Papers on {tech} rose from {m['papers_2015']} in 2015 to {m['papers_end']} in {END}. "
        f"From {START} to {END}, {tech} papers grew {pct(m['cagr'], 1)} per year. "
        f"Measured as a share of all research, {tech} grew {pct(abs(m['rel_cagr']), 1)} per year "
        f"{direction} than research overall, going from {m['pm_start']:.1f} to {m['pm_end']:.1f} "
        f"papers per million published ({m['share_multiple']:.1f}× change).")
    add("")

    # Organisations
    overall = (players[(players.technology == tech) & (players.list == "overall")]
               .groupby(["organisation", "type"], as_index=False)["papers"].sum()
               .sort_values("papers", ascending=False).head(15))
    add(f"**{tech}: leading organisations, {PLAYERS_PERIOD}.** "
        f"The top research organisations in {tech} by number of papers were:")
    for i, r in enumerate(overall.itertuples(), 1):
        add(f"{i}. {r.organisation} ({r.type}), {r.papers} papers")
    comp_in_top = overall[overall.type == "company"]["organisation"].tolist()
    if comp_in_top:
        add(f"Companies among the top {len(overall)} organisations in {tech}: {', '.join(comp_in_top)}.")
    else:
        add(f"No companies are among the top {len(overall)} organisations in {tech}.")
    add("")

    # Companies
    comps = (players[(players.technology == tech) & (players.list == "companies")]
             .groupby("organisation", as_index=False)["papers"].sum()
             .sort_values("papers", ascending=False).head(10))
    if len(comps):
        leader, runner = comps.iloc[0], comps.iloc[1] if len(comps) > 1 else None
        sentence = (f"**{tech}: leading companies, {PLAYERS_PERIOD}.** "
                    f"The leading company in {tech} research is {leader.organisation} "
                    f"with {leader.papers} papers")
        if runner is not None and runner.papers > 0:
            sentence += (f", {leader.papers / runner.papers:.1f} times as many as "
                         f"the next company, {runner.organisation} ({runner.papers})")
        add(sentence + f". Top companies in {tech}:")
        for i, r in enumerate(comps.itertuples(), 1):
            add(f"{i}. {r.organisation}, {r.papers} papers")
        add(f"Companies account for {pct(m['company_share'])} of {tech} research.")
        add("")

    # Countries
    ctry = countries[countries.technology == tech].sort_values("papers", ascending=False).head(8)
    add(f"**{tech}: leading countries, {PLAYERS_PERIOD}.** "
        f"Countries with the most {tech} papers (at least one author from the country): "
        + "; ".join(f"{r.country} ({r.papers})" for r in ctry.itertuples()) + ".")
    add("")

    # Maturity
    mat = m["maturity"]
    top_stage = mat.idxmax()
    add(f"**{tech}: research maturity.** Based on AI classification of {m['n_classified']} "
        f"recent {tech} papers (2024–2025), {tech} research is mostly at the "
        f"'{top_stage}' stage ({pct(mat[top_stage])}). Full split for {tech}: "
        + "; ".join(f"{s} {pct(mat[s])}" for s in STAGES) + ". "
        f"Field demonstration and commercial deployment together make up "
        f"{pct(mat['Field demonstration'] + mat['Commercial deployment'])} of {tech} research.")
    add("")

# ---------- method, validation, limitations ----------
add("## Method and definitions")
add("")
add(f"Growth is measured from {START} to {END}. 'Growth relative to all research' compares each "
    "technology's share of all papers published worldwide, which corrects for overall growth in "
    "research and for OpenAlex expanding its index in 2025. Organisations, companies and countries "
    f"cover {PLAYERS_PERIOD}. Maturity stages follow Technology Readiness Levels: fundamental "
    "research (TRL 1–3), lab prototype (TRL 4–5), field demonstration (TRL 6–7) and commercial "
    "deployment (TRL 8–9), assigned by Google Gemini from paper abstracts.")
add("")

add("## Limitations")
add("")
add("Maturity describes where published research is focused, not market maturity: companies rarely "
    "publish details of finished products, so research skews towards earlier stages. Publication "
    "counts miss patented or confidential work, so company activity is underrepresented. In smaller "
    "fields most companies have only a few papers, so rankings beyond the top few are indicative. "
    "Technologies are defined by keyword searches, which include some borderline papers.")

out = OUT_DIR / "technology_brief.md"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {out} ({len(lines)} lines)")