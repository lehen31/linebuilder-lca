# One-click installer (macOS and Windows)

For users who don't run conda or Brightway themselves. `installer/pack.sh` turns this repository into two zips:

- `installer/dist/LineBuilder-Mac.zip`
- `installer/dist/LineBuilder-Windows.zip`

Each unpacks to a `LineBuilder` folder with **Install LineBuilder**, **Start LineBuilder** and a `README.txt` for
the user (`mac/README.txt`, `windows/README.txt`).

```bash
installer/pack.sh          # from HEAD
installer/pack.sh v1.0     # from a tag, commit or branch
```

## What the installer does

1. Downloads [uv](https://github.com/astral-sh/uv) 0.9.5 from its GitHub release and checks its SHA-256.
2. Puts Python 3.11 and a virtual environment **inside the folder**: no conda, no admin rights, no PATH or
   registry changes.
3. Installs the packages from `common/requirements-lock.txt`, where every file carries a SHA-256 checksum. If those
   exact versions don't fit the machine, it falls back to `common/requirements-app.txt` without checksums.
4. Puts a launcher on the desktop: `LineBuilder.app` on the Mac, a shortcut on Windows.
5. Asks for ecoinvent 3.12 cutoff, in one of three ways:
   - the `.7z` file downloaded from ecoinvent.org (unpacked with py7zr, since macOS can't open `.7z`);
   - the folder it was unpacked to;
   - an existing **Activity Browser 2** project that already has `ecoinvent-3.12-cutoff` and `biosphere3`
     (option A of the main README).

**Start LineBuilder** then runs `app.py` on <http://127.0.0.1:5050> and opens the browser. It uses port 5050
because macOS uses 5000 for AirPlay Receiver.

## Where the Brightway data go

With the ecoinvent download, the project `LineBuilder` is created in the subfolder `brightway/` (set through
`BRIGHTWAY2_DIR`, about 1.7 GB). No other Brightway project on the computer is touched. This matters because
LineBuilder needs the legacy Brightway2 (bw2data 3.6), and that version must never open a Brightway 2.5 project.

With an existing project, its folder is written to `brightway-folder.txt`, and LineBuilder works in that
project. Before anything changes, a dialog says what will happen:
- the databases `Input Flows Collection` and `LineBuilder_web` are added;
- up to 20 elementary flows get their ecoinvent 3.12 names (see below).

Brightway 2.5 projects (Activity Browser 3), recognised by the `"25"` marker in `projects.db`, are never offered.
At every start, `setup_ecoinvent.py --check` makes sure the chosen project is still in the old format.

## Two problems the setup works around

`common/setup_ecoinvent.py` does the ecoinvent part itself, then calls `setup_project.py` for the Input Flows
Collection. Without these two fixes, a fresh pip install did not work:

1. **`setup_project.py --ecoinvent` stops on 3.12.** With pip's bw2io 0.8.12, `bw2setup()` builds `biosphere3`
   from the ecoinvent **3.9** elementary flows. 333 flows of 3.12 then stay unlinked, and the script exits.
   The helper links each unlinked elementary exchange by its flow UUID (the code in `biosphere3`). It adds the
   667 flows that 3.9 doesn't have from the release's own `MasterData/ElementaryExchanges.xml`.
2. **`process_templates.yaml` uses the 3.12 flow names.** Examples are `Isopropanol`, `Argon`, `Trifluoromethane`
   (HFC-23) and `Hexafluoroethane` (PFC-116). In a 3.9-based `biosphere3` these are called `2-Propanol`,
   `Argon-40`, `Methane, trifluoro-, HFC-23` and `Ethane, hexafluoro-, HFC-116`, and the calculation stopped with
   "no activity named 'Isopropanol' in biosphere3". The helper renames those flows to their 3.12 names, matched
   by UUID. The EF v3.1 characterization factors are stored by UUID, so they stay attached (HFC-23 14,600 and
   PFC-116 12,400 kg CO₂-eq/kg). For an existing project, `common/flows_312.json` holds the 3.12 records of every
   flow the library links to.

The legacy stack also needs `numpy<2`, `pandas<2.3`, `scipy<1.14` and `peewee<4`. Without these caps the setup
stops at `np.NaN`.

## Tested

On macOS (Apple Silicon) with ecoinvent 3.12 cutoff, using a fresh install from the zip, the import from the files
and a reused Activity Browser 2 project with 3.9 flow names. In both cases the Input Flows Collection had
0 unresolved links, and the default line gave 16.33 kg CO₂-eq (EF v3.1 GWP100). **The Windows scripts have not
been run yet.**

## Updating

- New package versions: edit `common/requirements-app.txt`, then run `installer/pack.sh --lock` (needs uv).
- New flow names in `process_templates.yaml`: regenerate `common/flows_312.json` from the 3.12 `MasterData`.
  It holds code, name, categories, unit, type and CAS number for every flow the library links to in `biosphere3`.
