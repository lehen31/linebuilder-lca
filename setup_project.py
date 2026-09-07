# -*- coding: utf-8 -*-
"""
LineBuilder one-time setup.

Creates (or reuses) a Brightway2 project and makes sure it contains the three
background databases LineBuilder needs:

    1. biosphere3               -- created automatically (bw2setup)
    2. ecoinvent-3.12-cutoff    -- YOU provide this (licensed; not shipped here)
    3. Input Flows Collection   -- bundled in data/, imported for you

Run it once:

    python setup_project.py                         # ecoinvent already in this project
    python setup_project.py --ecoinvent  PATH_TO_ECOSPOLD_DATASETS_FOLDER
    python setup_project.py --project  MyProjectName

The ecoinvent database MUST end up named exactly 'ecoinvent-3.12-cutoff'
(the bundled datasets reference it by that name). See README.
"""
import os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ECO = "ecoinvent-3.12-cutoff"
IFC = "Input Flows Collection"
PKG = os.path.join(HERE, "data", "input_flows_collection.bw2package")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=os.environ.get("LINEBUILDER_PROJECT", "LineBuilder"),
                    help="Brightway project name to set up (default: LineBuilder)")
    ap.add_argument("--ecoinvent", default=None,
                    help="path to the ecoinvent 3.12 cutoff ecoSpold ('datasets') folder, "
                         "to import it if this project does not already have it")
    args = ap.parse_args()

    try:
        import brightway2 as bw
        import bw2io
    except ImportError:
        sys.exit("Brightway2 is not installed in this environment.\n"
                 "  conda env create -f environment.yml   (then: conda activate linebuilder)\n"
                 "  or:  pip install -r requirements.txt")

    print("=" * 64)
    print("LineBuilder setup  ->  project '%s'" % args.project)
    print("=" * 64)
    bw.projects.set_current(args.project)

    # 1) biosphere3 + LCIA methods -------------------------------------------
    if "biosphere3" in bw.databases:
        print("[1/3] biosphere3            already present -- ok")
    else:
        print("[1/3] biosphere3            creating (bw2setup)...")
        bw.bw2setup()

    # 2) ecoinvent ------------------------------------------------------------
    if ECO in bw.databases:
        print("[2/3] %-24s already present (%d activities) -- ok"
              % (ECO, len(bw.Database(ECO))))
    elif args.ecoinvent:
        p = args.ecoinvent
        if not os.path.isdir(p):
            sys.exit("  ecoinvent path not found: %s" % p)
        print("[2/3] importing ecoinvent from %s ..." % p)
        imp = bw.SingleOutputEcospold2Importer(p, ECO)
        imp.apply_strategies()
        imp.statistics()
        if imp.statistics()[2]:      # unlinked exchanges
            sys.exit("  ecoinvent import has unlinked exchanges -- check the version/path.")
        imp.write_database()
        print("      ecoinvent imported as '%s'." % ECO)
    else:
        sys.exit(
            "\n  '%s' is NOT in project '%s'.\n"
            "  Provide your licensed ecoinvent 3.12 cutoff, one of:\n"
            "    * run this in the project that already has it, or\n"
            "    * python setup_project.py --ecoinvent  C:\\path\\to\\ecoinvent\\datasets\n"
            "  It must be named exactly '%s'." % (ECO, args.project, ECO))

    # 3) Input Flows Collection ----------------------------------------------
    if IFC in bw.databases:
        print("[3/3] %-24s already present -- replacing with bundled copy" % IFC)
        del bw.databases[IFC]
    print("[3/3] importing '%s' from data/ ..." % IFC)
    bw2io.BW2Package.import_file(PKG)

    # verify every foreground link resolves ----------------------------------
    ifc = bw.Database(IFC)
    unlinked = 0
    for a in ifc:
        for e in a.exchanges():
            try:
                e.input
            except Exception:
                unlinked += 1
    print("      '%s' imported: %d activities, %d unresolved links." % (IFC, len(ifc), unlinked))

    # write config so app.py knows the project -------------------------------
    json.dump({"project": args.project},
              open(os.path.join(HERE, "linebuilder_config.json"), "w", encoding="utf-8"), indent=2)

    print("-" * 64)
    if unlinked:
        print("WARNING: %d links did not resolve. Your ecoinvent is probably not 3.12 cutoff,\n"
              "         or is named differently. LineBuilder needs ecoinvent 3.12 cutoff." % unlinked)
    else:
        print("All set. Start the tool with:   python app.py   ->  http://127.0.0.1:5000")


if __name__ == "__main__":
    main()
