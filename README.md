# LineBuilder — cleanroom process line → carbon footprint

LineBuilder is a small web tool that lets you **assemble a semiconductor / photonics
cleanroom process line step by step** (or from ready-made standard flows) and get its
**cradle-to-gate carbon footprint** (EF 3.1, climate change / GWP100), computed with
**Brightway2** against **ecoinvent 3.12 cutoff** plus a bundled library of custom
foreground datasets (III-V and Ge material chains, precursors, sputter targets,
thickness-correct wafers, …).

It runs **entirely on your own computer** — nothing is uploaded anywhere. The result is
a real Brightway inventory you can open and audit in Activity Browser.

> **This is not a website.** LineBuilder is a local app you install and run. GitHub only
> hosts the code; each user sets it up on their own machine as described below.

---

## What you need first (prerequisites)

1. **Python via conda** (Miniconda or Anaconda). The legacy Brightway2 stack installs
   most smoothly with conda.
2. **A licensed copy of ecoinvent 3.12, cutoff system model.** ecoinvent is **not** and
   cannot be included here — you provide your own (from your ecoinvent account, or an
   existing Brightway/Activity Browser project that already has it). *Requires exactly
   3.12 cutoff; other versions will leave links unresolved.*
3. That's it. The custom foreground datasets are bundled in `data/`.

If you already use **Activity Browser** with ecoinvent 3.12 cutoff imported, you are
90 % of the way there — see Option A.

---

## Install

### Option A — reuse your Activity Browser / Brightway environment (recommended if you have one)

Your AB environment already contains Brightway2 and your ecoinvent. Just add the three
small extras:

```bash
conda activate <your-activity-browser-env>
pip install flask pyyaml xlsxwriter
```

### Option B — a fresh, self-contained environment

```bash
conda env create -f environment.yml
conda activate linebuilder
```

Then get the code:

```bash
git clone https://github.com/<your-user>/linebuilder-lca.git
cd linebuilder-lca
```

---

## Set up the Brightway project (once)

`setup_project.py` creates a Brightway project and fills it with the three databases the
tool needs: `biosphere3` (made automatically), your `ecoinvent-3.12-cutoff`, and the
bundled `Input Flows Collection`.

**If ecoinvent 3.12 cutoff is already imported in a Brightway project**, set that project
up by name:

```bash
python setup_project.py --project <name-of-your-project-with-ecoinvent>
```

**If you have ecoinvent as ecoSpold files** (the `datasets` folder from ecoinvent), let
the script import it into a new project:

```bash
python setup_project.py --project LineBuilder --ecoinvent  "C:\path\to\ecoinvent 3.12 cutoff\datasets"
```

A successful run ends with `0 unresolved links` and writes `linebuilder_config.json`
(which project to use). The ecoinvent database **must be named exactly
`ecoinvent-3.12-cutoff`** — the bundled datasets reference it by that name.

---

## Run it

```bash
python app.py
```

Open **http://127.0.0.1:5000** in your browser. Pick a substrate, load a standard flow or
add steps, choose your electricity grid, and click **Compute GWP**. **Download database
(Excel)** exports the assembled line as a native Brightway/Excel file you can re-import
into Brightway or Activity Browser.

To use a different port: `set PORT=5050` (Windows) / `export PORT=5050` (macOS/Linux),
then `python app.py`.

---

## Configuration

`setup_project.py` writes `linebuilder_config.json`, e.g. `{"project": "LineBuilder"}`.
You can also override the project at run time:

```bash
set LINEBUILDER_PROJECT=MyProject   # Windows
export LINEBUILDER_PROJECT=MyProject # macOS/Linux
```

`ecoinvent-3.12-cutoff` and `biosphere3` names are fixed (the bundled data references
them by name) — keep those exact names.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `setup_project.py` reports **unresolved links** | Your ecoinvent is not **3.12 cutoff** (or is named differently). LineBuilder needs 3.12 cutoff, named `ecoinvent-3.12-cutoff`. |
| `'ecoinvent-3.12-cutoff' is NOT in project …` | Point `--project` at the project that has ecoinvent, or import it with `--ecoinvent PATH`. |
| `ModuleNotFoundError: brightway2` (or flask) | Wrong environment. `conda activate` the right env; re-run the install step. |
| Browser says the site can't be reached | The server isn't running or you closed its terminal. Re-run `python app.py` and keep that window open. |
| Port 5000 already in use | Start on another port (`PORT=5050`). |

---

## How it fits together

- `app.py` — the Flask web app (the UI).
- `linebuilder_core.py` — the engine: loads the template library, links to Brightway,
  assembles a foreground database, computes EF 3.1 GWP100.
- `process_templates.yaml` — the **library**: every step type, its parameters, the flows,
  the material/link catalogs, and the ready-made standard flows. This is where the
  process knowledge lives; edit it to extend the tool (changes reload without a restart).
- `data/input_flows_collection.bw2package` — the bundled custom foreground datasets.
- `setup_project.py` — one-time project builder.

---

## License & data

- **Code and the bundled `Input Flows Collection`**: MIT (see `LICENSE`).
- **ecoinvent**: licensed separately by [ecoinvent](https://ecoinvent.org) and **not**
  included here. You must supply your own ecoinvent 3.12 cutoff.

If you use this in academic work, please cite the repository and ecoinvent 3.12.
