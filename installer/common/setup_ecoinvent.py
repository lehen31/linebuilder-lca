# -*- coding: utf-8 -*-
"""Sets up the Brightway project of LineBuilder (called by the installer and the start script).

Two ways, chosen in a dialog (or on the command line):

1. From the ecoinvent 3.12 cutoff ecoSpold02 download (the .7z file, the folder it unpacks to, or its "datasets"
   folder): a new project "LineBuilder" in the subfolder "brightway" of this folder, so no other Brightway project
   of this computer is touched.
       python setup_ecoinvent.py PATH

2. An existing project of the Activity Browser 2 (Brightway2) that already has "ecoinvent-3.12-cutoff" and
   "biosphere3", as option A of the README. LineBuilder adds the databases "Input Flows Collection" (now)
   and "LineBuilder_web" (at each calculation) to it, and, after asking, gives the few elementary flows it needs
   their ecoinvent 3.12 names (flows_312.json). Projects in the Brightway 2.5 format (Activity Browser 3) are
   never opened: the legacy Brightway2 of LineBuilder cannot read them and could damage them.
       python setup_ecoinvent.py --project NAME [--brightway-dir DIR]

    python setup_ecoinvent.py --check     (start script: is the chosen project still usable?)

The Brightway folder in use is written to brightway-folder.txt when it is not the own subfolder "brightway".
"""
import argparse
import hashlib
import json
import os
import pickle
import shutil
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OWN_DIR = os.path.join(HERE, "brightway")
FOLDER_FILE = os.path.join(HERE, "brightway-folder.txt")
CONFIG = os.path.join(HERE, "linebuilder_config.json")
UNPACKED = os.path.join(HERE, ".tools", "ecoinvent-unpacked")
ECO = "ecoinvent-3.12-cutoff"   # the names the bundled Input Flows Collection refers to
BIO = "biosphere3"
FIELDS = ("name", "categories", "unit", "CAS number", "type")

ASK = "LineBuilder needs ecoinvent 3.12 cutoff (licensed from ecoinvent.org). Where is it?"
CHOICES = ["The .7z file downloaded from ecoinvent.org …",
           "The folder it was unpacked to …",
           "An existing Activity Browser 2 project with ecoinvent 3.12 …"]


# --- dialogs: osascript on the Mac, tkinter on Windows, the terminal otherwise -----------------------------------

def _osa(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def _q(text):
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


def _tk():
    import tkinter
    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return root


def ui_choose(prompt, items):
    """One of items, or None."""
    if sys.platform == "darwin":
        r = _osa('choose from list {%s} with title "LineBuilder" with prompt %s OK button name "Choose" '
                 'cancel button name "Later"' % (", ".join(_q(i) for i in items), _q(prompt)))
        return r if r in items else None
    if os.name == "nt":
        import tkinter
        root = _tk()
        win = tkinter.Toplevel(root)
        win.title("LineBuilder")
        win.attributes("-topmost", True)
        tkinter.Label(win, text=prompt, justify="left", wraplength=520).pack(padx=16, pady=(16, 8), anchor="w")
        box = tkinter.Listbox(win, width=80, height=min(len(items), 12))
        for i in items:
            box.insert("end", i)
        box.selection_set(0)
        box.pack(padx=16)
        out = {}

        def ok(_=None):
            sel = box.curselection()
            out["v"] = items[sel[0]] if sel else None
            win.destroy()
        box.bind("<Double-Button-1>", ok)
        bar = tkinter.Frame(win)
        bar.pack(pady=12)
        tkinter.Button(bar, text="Choose", width=12, command=ok).pack(side="left", padx=6)
        tkinter.Button(bar, text="Later", width=12, command=win.destroy).pack(side="left", padx=6)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        root.wait_window(win)
        root.destroy()
        return out.get("v")
    print(prompt)
    for n, i in enumerate(items, 1):
        print("  %d  %s" % (n, i))
    a = input("Number (empty: later): ").strip()
    return items[int(a) - 1] if a.isdigit() and 0 < int(a) <= len(items) else None


def ui_confirm(text, ok="OK"):
    if sys.platform == "darwin":
        return _osa('button returned of (display dialog %s buttons {"Cancel", %s} default button 2 '
                    'with title "LineBuilder")' % (_q(text), _q(ok))) == ok
    if os.name == "nt":
        from tkinter import messagebox
        root = _tk()
        r = messagebox.askokcancel("LineBuilder", text, parent=root)
        root.destroy()
        return bool(r)
    return input(text + "\n[y/N] ").strip().lower() in ("y", "yes")


def ui_info(text):
    print(text)
    if sys.platform == "darwin":
        _osa('display dialog %s buttons {"OK"} default button 1 with title "LineBuilder"' % _q(text))
    elif os.name == "nt":
        from tkinter import messagebox
        root = _tk()
        messagebox.showinfo("LineBuilder", text, parent=root)
        root.destroy()


def ui_file():
    if sys.platform == "darwin":
        return _osa('POSIX path of (choose file with prompt "ecoinvent 3.12 cutoff ecoSpold02 (.7z)")')
    if os.name == "nt":
        from tkinter import filedialog
        root = _tk()
        p = filedialog.askopenfilename(parent=root, title="ecoinvent 3.12 cutoff ecoSpold02 (.7z)",
                                       filetypes=[("7-Zip", "*.7z"), ("All files", "*.*")])
        root.destroy()
        return p or ""
    return input("Path to the .7z file: ").strip()


def ui_folder(title):
    if sys.platform == "darwin":
        return _osa('POSIX path of (choose folder with prompt %s)' % _q(title))
    if os.name == "nt":
        from tkinter import filedialog
        root = _tk()
        p = filedialog.askdirectory(parent=root, title=title)
        root.destroy()
        return p or ""
    return input(title + ": ").strip()


# --- existing Brightway2 projects --------------------------------------------------------------------------------

def default_bw_dir():
    """Where the Activity Browser keeps its Brightway projects (appdirs "Brightway3", "pylca")."""
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Brightway3")
    if os.name == "nt":
        return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")),
                            "pylca", "Brightway3")
    return os.path.expanduser("~/.local/share/Brightway3")


def scan_projects(bw_dir):
    """[(name, is_bw25, databases)] of a Brightway data folder, read without opening anything for writing."""
    db = os.path.join(bw_dir, "projects.db")
    if not os.path.isfile(db):
        return []
    con = sqlite3.connect("file:%s?mode=ro" % db.replace("?", "%3f"), uri=True)
    try:
        rows = con.execute("SELECT name, data FROM projectdataset").fetchall()
    finally:
        con.close()
    out = []
    for name, blob in rows:
        try:
            data = pickle.loads(blob) if blob else None
        except Exception:
            data = None
        # Brightway 2.5 marks a project it has migrated with "25" (bw2data 4 sets it when it migrates a project)
        is25 = bool(isinstance(data, dict) and data.get("25"))
        suffix = "." + hashlib.md5(name.encode("utf-8")).hexdigest()
        dirs = [d for d in os.listdir(bw_dir) if d.endswith(suffix)]
        dbs = []
        if dirs:
            try:
                with open(os.path.join(bw_dir, dirs[0], "databases.json"), encoding="utf-8") as f:
                    dbs = list(json.load(f))
            except (OSError, ValueError):
                pass
        out.append((name, is25, dbs))
    return out


def pick_project():
    """(bw_dir, project name) of an Activity Browser 2 project with ecoinvent 3.12 cutoff, or None."""
    bw_dir = default_bw_dir()
    while True:
        projects = scan_projects(bw_dir)
        usable = sorted(n for n, is25, dbs in projects if not is25 and ECO in dbs)
        newer = sorted(n for n, is25, dbs in projects if is25 and ECO in dbs)
        if usable:
            name = ui_choose("Activity Browser 2 projects with %s in\n%s" % (ECO, bw_dir), usable)
            return (bw_dir, name) if name else None
        text = "No Activity Browser 2 project with a database named \"%s\" in\n%s" % (ECO, bw_dir)
        if newer:
            text += ("\n\nThese have it, but in the newer Brightway 2.5 format (Activity Browser 3), "
                     "which LineBuilder's Brightway2 cannot open: " + ", ".join(newer))
        if not ui_confirm(text + "\n\nChoose another Brightway data folder?", "Choose folder …"):
            return None
        bw_dir = ui_folder("Brightway data folder (the one with projects.db)")
        if not bw_dir:
            return None


def use_project(bw_dir, name, ask=True):
    """Prepares an existing Activity Browser 2 project and lets setup_project.py add the Input Flows Collection."""
    bw_dir = os.path.abspath(bw_dir)
    found = {n: (is25, dbs) for n, is25, dbs in scan_projects(bw_dir)}
    if name not in found:
        sys.exit("No project \"%s\" in %s" % (name, bw_dir))
    if found[name][0]:
        sys.exit("\"%s\" is in the Brightway 2.5 format (Activity Browser 3). LineBuilder's Brightway2 "
                 "cannot open it. Use an Activity Browser 2 project, or import ecoinvent from its files." % name)

    os.environ["BRIGHTWAY2_DIR"] = bw_dir
    import warnings
    warnings.filterwarnings("ignore")
    import bw2data as bd
    bd.projects.set_current(name)
    missing = [d for d in (ECO, BIO) if d not in bd.databases]
    if missing:
        sys.exit("The project \"%s\" has no database %s (it has: %s).\nThe bundled Input Flows Collection refers to "
                 "exactly \"%s\" and \"%s\"." % (name, " and ".join('"%s"' % m for m in missing),
                                                 ", ".join(bd.databases) or "none", ECO, BIO))
    if not any(m[0].startswith("EF v3.1") and "climate change" in m[1].lower() and "GWP100" in m[2]
               for m in bd.methods):
        sys.exit("The project \"%s\" has no LCIA method EF v3.1 climate change (GWP100)." % name)

    with open(os.path.join(HERE, "flows_312.json"), encoding="utf-8") as f:
        wanted = json.load(f)
    rename, add = [], []
    for d in wanted:
        try:
            act = bd.get_activity((BIO, d["code"]))
        except Exception:
            add.append(d)
            continue
        if act.get("name") != d["name"]:
            rename.append((act, d))

    if ask:
        text = ("LineBuilder will use the project \"%s\" (%s).\n\nIt adds the databases \"Input Flows Collection\" "
                "and \"LineBuilder_web\" to it." % (name, bw_dir))
        if rename:
            olds = sorted({"%s → %s" % (a["name"], d["name"]) for a, d in rename})
            text += ("\n\nIt gives %d elementary flows of biosphere3 their ecoinvent 3.12 names (%s); "
                     "their characterization factors stay." % (len(rename), "; ".join(olds)))
        if add:
            text += "\n\nIt adds %d elementary flows of ecoinvent 3.12 to biosphere3." % len(add)
        text += "\n\nNothing else changes. Close the Activity Browser first."
        if not ui_confirm(text, "Use this project"):
            print("Cancelled.")
            sys.exit(2)

    for act, d in rename:
        for k, v in flow_fields(d).items():
            act[k] = v
        act.save()
    for d in add:
        bd.Database(BIO).new_activity(**flow_fields(d, code=True)).save()
    if rename or add:
        print("biosphere3: %d flows renamed, %d added (ecoinvent 3.12 names)" % (len(rename), len(add)))

    code = run_setup_project(name)
    if code == 0:
        with open(FOLDER_FILE, "w", encoding="utf-8") as f:
            f.write(bw_dir)
    return code


def check():
    """For the start script: when an outside project is used, is it still there and still Brightway2?"""
    if not os.path.isfile(FOLDER_FILE):
        return 0
    with open(FOLDER_FILE, encoding="utf-8") as f:
        bw_dir = f.read().strip()
    try:
        with open(CONFIG, encoding="utf-8") as f:
            name = json.load(f)["project"]
    except (OSError, ValueError, KeyError):
        return 0
    found = {n: is25 for n, is25, _ in scan_projects(bw_dir)}
    if name not in found:
        print("The project \"%s\" is no longer in %s." % (name, bw_dir))
    elif found[name]:
        print("The project \"%s\" has been converted to Brightway 2.5 (the Activity Browser 3 opened it). "
              "LineBuilder's Brightway2 cannot read it any more." % name)
    else:
        return 0
    print("Choose ecoinvent again.")
    os.remove(CONFIG)
    os.remove(FOLDER_FILE)
    return 1


# --- import from the ecoinvent files -----------------------------------------------------------------------------

def find_datasets(path):
    """The folder with the .spold files: PATH itself, PATH/datasets, or one level deeper."""
    def has_spold(d):
        try:
            return any(n.lower().endswith(".spold") for n in os.listdir(d))
        except OSError:
            return False

    for cand in (path, os.path.join(path, "datasets")):
        if has_spold(cand):
            return cand
    for root, dirs, _ in os.walk(path):
        if root[len(path):].count(os.sep) > 2:
            dirs[:] = []
            continue
        for d in dirs:
            if d.lower() == "datasets" and has_spold(os.path.join(root, d)):
                return os.path.join(root, d)
    return None


def flow_fields(d, code=False):
    """The fields of an elementary flow as biosphere3 keeps them ("unspecified" subcategory dropped)."""
    out = {k: d[k] for k in FIELDS + ("synonyms",) if k in d}
    out["categories"] = tuple(c for c in d["categories"] if c and c != "unspecified")
    if code:
        out["code"] = d["code"]
    return out


def align_biosphere(flows):
    """Gives the flows of biosphere3 (ecoinvent 3.9) their ecoinvent 3.12 names, matched by UUID.

    The process library of LineBuilder names elementary flows as ecoinvent 3.12 does, e.g. "Isopropanol",
    "Trifluoromethane" (HFC-23) and "Hexafluoroethane" (PFC-116), which 3.9 calls "2-Propanol",
    "Methane, trifluoro-, HFC-23" and "Ethane, hexafluoro-, HFC-116". The characterization factors of the LCIA
    methods point to the UUID (the code), so they stay with the renamed flow.
    """
    import bw2data as bd
    changed = 0
    for act in bd.Database(BIO):
        new = flows.get(act["code"])
        if not new:
            continue
        fields = flow_fields(new)
        if any(act.get(k) != v for k, v in fields.items()):
            for k, v in fields.items():
                act[k] = v
            act.save()
            changed += 1
    if changed:
        print("      %d elementary flows of biosphere3 now carry their ecoinvent 3.12 names" % changed)


def import_ecoinvent(datasets):
    """biosphere3 and ecoinvent-3.12-cutoff in the project LineBuilder.

    setup_project.py on its own cannot import ecoinvent 3.12 into a new project: legacy bw2io builds biosphere3
    from the ecoinvent 3.9 elementary flows, so 333 flows of 3.12 stay unlinked and it stops. Here every unlinked
    elementary exchange is linked by its flow UUID (the code in biosphere3); flows that 3.9 does not have yet are
    added to biosphere3 from the release's own MasterData/ElementaryExchanges.xml. The LCIA methods (EF v3.1 among
    them) stay those of bw2setup.
    """
    import warnings
    warnings.filterwarnings("ignore")
    import bw2data as bd
    import bw2io as bi
    from bw2io.importers.ecospold2_biosphere import Ecospold2BiosphereImporter

    bd.projects.set_current("LineBuilder")
    if BIO not in bd.databases:
        print("[1/3] biosphere3 and LCIA methods (bw2setup) …")
        bi.bw2setup()
    if ECO in bd.databases:
        print("[2/3] %s is already there." % ECO)
        return

    master = os.path.join(os.path.dirname(datasets), "MasterData", "ElementaryExchanges.xml")
    if not os.path.isfile(master):
        sys.exit("MasterData/ElementaryExchanges.xml is missing next to %s.\n"
                 "Choose the whole ecoinvent 3.12 cutoff ecoSpold02 download (.7z or its unpacked folder)." % datasets)

    flows = {d["code"]: d for d in Ecospold2BiosphereImporter(BIO, filepath=master).data}
    align_biosphere(flows)

    print("[2/3] Importing %s …" % ECO)
    imp = bi.SingleOutputEcospold2Importer(datasets, ECO)
    imp.apply_strategies()

    bio = bd.Database(BIO)
    codes = {a["code"] for a in bio}
    missing = {exc["flow"] for ds in imp.data for exc in ds["exchanges"]
               if exc.get("type") == "biosphere" and not exc.get("input") and exc.get("flow") not in codes}
    unknown = [f for f in missing if f not in flows]
    if unknown:
        sys.exit("%d elementary flows are not in the release's MasterData, e.g. %s. Is this ecoinvent 3.12 cutoff?"
                 % (len(unknown), unknown[0]))
    if missing:
        print("      adding %d elementary flows of ecoinvent 3.12 to biosphere3" % len(missing))
        for code in sorted(missing):
            bio.new_activity(**flow_fields(flows[code], code=True)).save()
        codes |= missing
    for ds in imp.data:
        for exc in ds["exchanges"]:
            if exc.get("type") == "biosphere" and not exc.get("input") and exc.get("flow") in codes:
                exc["input"] = (BIO, exc["flow"])

    unlinked = imp.statistics(print_stats=False)[2]
    if unlinked:
        imp.statistics()
        sys.exit("ecoinvent still has %d unlinked exchanges. Is this ecoinvent 3.12 cutoff?" % unlinked)
    imp.write_database()
    print("      %s: %d activities" % (ECO, len(bd.Database(ECO))))


def from_files(given):
    os.makedirs(OWN_DIR, exist_ok=True)
    os.environ["BRIGHTWAY2_DIR"] = OWN_DIR
    path = os.path.abspath(os.path.expanduser(given.strip().strip('"').strip("'")))
    if not os.path.exists(path):
        sys.exit("Not found: %s" % path)

    if os.path.isfile(path):
        if not path.lower().endswith(".7z"):
            sys.exit("This is neither a folder nor a .7z file: %s" % path)
        import py7zr
        print("Unpacking %s …" % os.path.basename(path))
        shutil.rmtree(UNPACKED, ignore_errors=True)
        os.makedirs(UNPACKED)
        with py7zr.SevenZipFile(path, "r") as z:
            z.extractall(UNPACKED)
        path = UNPACKED

    name = os.path.basename(given.rstrip("/\\"))
    if "3.12" not in name and any(v in name for v in ("3.9", "3.10", "3.11", "3.13")):
        print("NOTE: the name \"%s\" looks like another ecoinvent version. LineBuilder needs 3.12 cutoff." % name)
    if "conseq" in name.lower() or "apos" in name.lower():
        print("NOTE: the name \"%s\" looks like another system model. LineBuilder needs cutoff." % name)

    datasets = find_datasets(path)
    if not datasets:
        shutil.rmtree(UNPACKED, ignore_errors=True)
        sys.exit("No ecoinvent datasets (.spold files) found in %s" % path)
    print("ecoinvent datasets: %s" % datasets)
    print("Importing takes 5 to 15 minutes …")
    print()
    try:
        import_ecoinvent(datasets)
    finally:
        shutil.rmtree(UNPACKED, ignore_errors=True)
    code = run_setup_project("LineBuilder")
    if code == 0 and os.path.isfile(FOLDER_FILE):
        os.remove(FOLDER_FILE)   # back to the own subfolder
    return code


def run_setup_project(project):
    """biosphere3 and ecoinvent are there: setup_project.py adds the Input Flows Collection, checks its links
    and writes linebuilder_config.json (BRIGHTWAY2_DIR is passed on)."""
    print()
    env = dict(os.environ, PYTHONWARNINGS="ignore")
    if os.path.isfile(CONFIG):
        os.remove(CONFIG)
    code = subprocess.call([sys.executable, os.path.join(HERE, "setup_project.py"), "--project", project],
                           cwd=HERE, env=env)
    return code if code else (0 if os.path.isfile(CONFIG) else 1)


def main():
    sys.stdout.reconfigure(line_buffering=True)   # keeps its lines in order with those of setup_project.py
    ap = argparse.ArgumentParser(description="Sets up the Brightway project of LineBuilder.")
    ap.add_argument("path", nargs="?", help="ecoinvent 3.12 cutoff ecoSpold02: .7z file or folder")
    ap.add_argument("--project", help="use this existing Activity Browser 2 project instead")
    ap.add_argument("--brightway-dir", default=None, help="its Brightway data folder (default: the Activity Browser's)")
    ap.add_argument("--yes", action="store_true", help="do not ask before changing the existing project")
    ap.add_argument("--check", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.check:
        sys.exit(check())
    if args.project:
        sys.exit(use_project(args.brightway_dir or default_bw_dir(), args.project, ask=not args.yes))
    if args.path:
        sys.exit(from_files(args.path))

    try:
        kind = ui_choose(ASK, CHOICES)
        if kind == CHOICES[0]:
            given = ui_file()
        elif kind == CHOICES[1]:
            given = ui_folder("ecoinvent 3.12 cutoff ecoSpold02 folder")
        elif kind == CHOICES[2]:
            chosen = pick_project()
            if chosen:
                sys.exit(use_project(*chosen))
            given = ""
        else:
            given = ""
    except SystemExit:
        raise
    except Exception as e:  # no window possible: ask in the terminal
        print("(no dialog: %s)" % e)
        given = input("Path to the ecoinvent 3.12 cutoff .7z file or folder (empty: later): ")
    if not given.strip():
        print("Skipped: no ecoinvent chosen.")
        sys.exit(2)
    sys.exit(from_files(given))


if __name__ == "__main__":
    main()
