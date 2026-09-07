# -*- coding: utf-8 -*-
"""Shared LineBuilder engine: load the template library, resolve links to
Brightway activities, assemble a run into a foreground database, and compute
EF 3.1 climate change. Used by both the CLI assembler and the Flask web app."""
import os, json, math, yaml
import brightway2 as bw

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_config():
    """Portable settings. Only the Brightway PROJECT name is configurable (people name
    their project differently). The background database names are FIXED: the bundled
    'Input Flows Collection' package and the template links both store references to
    'ecoinvent-3.12-cutoff' and 'biosphere3' by name, so those must exist under exactly
    those names -- see setup_project.py / README. setup_project.py writes
    linebuilder_config.json; the LINEBUILDER_PROJECT env var overrides it."""
    cfg = {"project": "LineBuilder"}
    path = os.path.join(HERE, "linebuilder_config.json")
    if os.path.exists(path):
        try:
            cfg.update(json.load(open(path, encoding="utf-8")))
        except Exception:
            pass
    cfg["project"] = os.environ.get("LINEBUILDER_PROJECT", cfg["project"])
    return cfg


PROJECT = _load_config()["project"]
DBNAME = "LineBuilder_web"
BG_DBS = ["ecoinvent-3.12-cutoff", "biosphere3", "Input Flows Collection"]
LOC_PREF = ["CH", "RER", "GLO", "RoW", "Europe without Switzerland"]

_lib = None
_lib_mtime = None
_index = None
_link_cache = {}


def load_lib():
    """Reload the YAML if it changed on disk, so library edits show up without a restart."""
    global _lib, _lib_mtime, _link_cache
    path = os.path.join(HERE, "process_templates.yaml")
    mt = os.path.getmtime(path)
    if _lib is None or mt != _lib_mtime:
        _lib = yaml.safe_load(open(path, encoding="utf-8"))
        _lib_mtime = mt
        _link_cache = {}   # links may have changed
    return _lib


def _ensure_index():
    global _index
    bw.projects.set_current(PROJECT)
    if _index is None:
        _index = {db: {} for db in BG_DBS}
        for db in BG_DBS:
            for a in bw.Database(db):
                _index[db].setdefault(a["name"], []).append(a)


def resolve_link(key):
    if key in _link_cache:
        return _link_cache[key]
    spec = load_lib()["links"].get(key)
    if spec is None:
        raise ValueError(f"link '{key}' is a null placeholder — add a proxy before using it")
    cands = list(_index[spec["database"]].get(spec["name"], []))
    if not cands:
        raise ValueError(f"no activity named '{spec['name']}' in {spec['database']} (link '{key}')")
    if spec.get("location"):
        cands = [a for a in cands if a.get("location") == spec["location"]] or cands
    if spec.get("reference_product"):
        cands = [a for a in cands if a.get("reference product") == spec["reference_product"]] or cands
    if spec["database"] == "biosphere3":
        air = [a for a in cands if a.get("categories") and a["categories"][0] == "air"]
        if air:
            # Deterministically prefer the unspecified ('air',) sub-compartment, which
            # LCIA methods (EF v3.1, IPCC) reliably characterise. Without this the pick
            # was whatever the DB returned first and could land on
            # ('air','low population density, long-term') -- UNCHARACTERISED in GWP100 --
            # silently zeroing strong GHGs (CO2, N2O) and making the result irreproducible.
            _SUBPRIO = {("air",): 0,
                        ("air", "urban air close to ground"): 1,
                        ("air", "non-urban air or from high stacks"): 2,
                        ("air", "lower stratosphere + upper troposphere"): 3,
                        ("air", "low population density, long-term"): 8}
            air.sort(key=lambda a: _SUBPRIO.get(tuple(a.get("categories")), 5))
            cands = air
    cands.sort(key=lambda a: LOC_PREF.index(a.get("location")) if a.get("location") in LOC_PREF else 99)
    _link_cache[key] = cands[0]
    return cands[0]


def get_schema():
    """Describe every step type and its parameters, for the web form to render."""
    lib = load_lib()
    steps = []
    for t in lib["templates"]:
        params = []
        for p in t["parameters"]:
            if p.get("type") == "choice":
                params.append({"name": p["name"], "kind": "choice", "choices": p["choices"],
                               "default": p.get("default"), "about": p.get("about", ""),
                               "advanced": p.get("advanced", False)})
            else:
                params.append({"name": p["name"], "kind": "number", "default": p.get("default"),
                               "unit": p.get("unit", ""), "about": p.get("about", ""),
                               "advanced": p.get("advanced", False)})
        steps.append({"id": t["id"], "label": t["label"], "family": t.get("family", "Other"),
                      "note": t.get("note", ""), "batchable": t.get("batchable", False),
                      "params": params,
                      # {choice_param: {choice: {dependent_param: value}}} -- the form fills
                      # the dependent fields when the choice changes (user can still override)
                      "choice_defaults": t.get("choice_defaults", {})})
    flows = [{"id": f["id"], "label": f["label"], "about": f.get("about", ""),
              "steps": f["steps"]} for f in lib.get("process_flows", [])]
    return {"steps": steps, "flows": flows,
            "substrate_formats": lib["materials"].get("substrate_formats", {})}


def _build_flow_exchanges(template, params, opts=None):
    opts = opts or {}
    lib = load_lib()
    ns = dict(params)
    # every catalog under `materials:` is available to to_expr (resists, developers,
    # substrates, etchants, metals, ...) -- adding a catalog needs no code change
    ns.update(lib["materials"])
    # densities (kg/L) so amount expressions can convert lab VOLUME input -> mass,
    # e.g. "ipa_mL * rho['ipa'] / 1000". Water/aqueous = 1.0 so mL <-> g is 1:1.
    ns["rho"] = lib.get("densities", {})
    # run-level wafer size -> area scaling factor for flows that scale with wafer AREA
    # (resist dispense, blanket metal). Bath volumes and tool times must NOT use it.
    dia = float(opts.get("wafer_diameter_mm") or 150.0)
    ns["area_factor"] = (dia / 150.0) ** 2
    grid = opts.get("grid")
    catalog = "grids_hv" if str(opts.get("voltage", "MV")).upper() == "HV" else "grids"
    out = []
    for f in template["flows"]:
        linkkey = f["to"] if "to" in f else eval(f["to_expr"], {"__builtins__": {}}, ns)
        # run-level grid + voltage: every electricity flow follows them, no template edits needed
        if linkkey == "elec" and grid:
            linkkey = lib["materials"][catalog].get(grid, "elec")
        try:
            amt = float(eval(f["amount"], {"__builtins__": {}}, ns))
        except TypeError as exc:
            blank = [k for k, v in params.items() if v is None]
            raise ValueError(
                f"template '{template['id']}': cannot evaluate '{f['amount']}' -- "
                f"parameter(s) {blank} have no value. Auto-filled parameters (e.g. "
                f"cleanroom_overhead.n_steps) are resolved by assemble_db(); call that "
                f"instead of _build_flow_exchanges() directly."
            ) from exc
        # ---- per-flow scaling semantics (declared once, applied by the engine) ----
        #   per_wafer (default) : fixed per wafer  (N2 gun, IPA dispense, resist, tool time)
        #   per_run             : shared by every wafer in one chamber/tool run
        #   per_bath            : shared over the life of a bath / consumable fill
        # Templates declare WHAT a flow is; the engine does the arithmetic, so no template
        # ever hand-divides by batch_size again.
        mode = f.get("scaling", "per_wafer")
        if mode == "per_run":
            amt /= max(float(params.get("wafers_per_run", 1) or 1), 1e-9)
        elif mode == "per_bath":
            amt /= max(float(params.get("wafers_per_bath", 1) or 1), 1e-9)
        elif mode != "per_wafer":
            raise ValueError(f"template '{template['id']}': unknown scaling '{mode}'")
        if amt == 0:
            continue
        act = resolve_link(linkkey)
        scale = load_lib()["uncertainty_presets"][f["unc"]]["scale"]
        ex = {"input": act.key, "amount": amt, "type": f["role"],
              "uncertainty type": 2, "loc": math.log(abs(amt)), "scale": scale}
        if amt < 0:
            ex["negative"] = True
        out.append(ex)
    return out


def _pick_method():
    cc = [m for m in bw.methods if m[0].startswith("EF v3.1") and "climate change" in m[1].lower()
          and "GWP100" in m[2]]
    cc = [m for m in cc if "no LT" in m[0]] or cc
    return cc[0]


def _coerce(v):
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return v
    return v


def assemble_db(rows, opts=None):
    """Build the foreground Brightway database from the run and return (templates, order)."""
    _ensure_index()
    lib = load_lib()
    templates = {t["id"]: t for t in lib["templates"]}
    if DBNAME in bw.databases:
        del bw.databases[DBNAME]
    # steps the cleanroom overhead should be spread over = everything that is not
    # itself an overhead or a substrate input
    n_process_steps = sum(1 for r in rows
                          if r["step_type"] not in ("cleanroom_overhead", "substrate"))
    data = {}
    for i, row in enumerate(rows, 1):
        tpl = templates[row["step_type"]]
        params = {p["name"]: p.get("default") for p in tpl["parameters"]}
        params.update({k: _coerce(v) for k, v in (row.get("params") or {}).items() if v not in (None, "")})
        # leave n_steps blank -> overhead automatically matches THIS run's length
        if tpl["id"] == "cleanroom_overhead" and params.get("n_steps") in (None, ""):
            params["n_steps"] = max(n_process_steps, 1)
        code = f"step_{i}"
        name = f"{i}. {tpl['label']}"
        # Each step is INDEPENDENT: only its own direct flows (no predecessor link),
        # so an activity carries just its own burden. Total = sum of steps.
        exch = [{"input": (DBNAME, code), "amount": 1, "type": "production", "uncertainty type": 0}]
        exch += _build_flow_exchanges(tpl, params, opts)
        data[(DBNAME, code)] = {"name": name, "reference product": name, "unit": "unit",
                                "location": "CH", "exchanges": exch}
    bw.Database(DBNAME).write(data)
    return templates


def export_excel(rows, path, opts=None):
    """Assemble the run and export the resulting foreground Brightway database in the
    NATIVE Brightway/bw2io Excel format (Database / Activity / Exchanges blocks) — the
    same layout bw2io.ExcelImporter reads back."""
    import shutil, xlsxwriter
    assemble_db(rows, opts)
    # safety net: tolerate any NaN/Inf in uncertainty fields during write
    _orig = xlsxwriter.Workbook
    def _wb(filename=None, options=None):
        opts = dict(options or {}); opts["nan_inf_to_errors"] = True
        return _orig(filename, opts)
    xlsxwriter.Workbook = _wb
    try:
        from bw2io.export.excel import write_lci_excel
        fp = write_lci_excel(DBNAME)          # writes lci-<db>.xlsx to the project output dir
    finally:
        xlsxwriter.Workbook = _orig
    shutil.copy(fp, path)
    return path


def compute(rows, opts=None):
    """rows: [{'step_type': str, 'params': {name: value}}]  ->  total GWP + per-step hotspot."""
    templates = assemble_db(rows, opts)
    method = _pick_method()
    per = []
    for i in range(1, len(rows) + 1):
        act = bw.get_activity((DBNAME, f"step_{i}"))
        l = bw.LCA({act: 1}, method); l.lci(); l.lcia()
        per.append(l.score)                      # each step standalone
    total = sum(per)
    steps = [{"n": i + 1, "label": templates[rows[i]["step_type"]]["label"],
              "gwp": per[i], "share": (100 * per[i] / total if total else 0)}
             for i in range(len(rows))]
    steps_sorted = sorted(steps, key=lambda s: -s["gwp"])
    return {"total": total, "method": " / ".join(method), "steps": steps_sorted}
