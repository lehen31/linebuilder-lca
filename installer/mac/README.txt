LineBuilder – installation on the Mac
=====================================

LineBuilder (https://github.com/lehen31/linebuilder-lca, by Lea Ghisalberti, MIT licence) assembles a cleanroom
process line step by step and computes its cradle-to-gate carbon footprint (EF 3.1 climate change) with
Brightway2 against ecoinvent 3.12 cutoff. It runs on this Mac only, nothing is uploaded.

You need your licensed ecoinvent 3.12 cutoff (not included, and it cannot be; exactly 3.12 cutoff), either
- the file "ecoinvent 3.12_cutoff_ecoSpold02.7z" downloaded from ecoinvent.org (or the folder it unpacks to), or
- a project of the Activity Browser 2 that already has the databases "ecoinvent-3.12-cutoff" and "biosphere3".

1. Put this folder "LineBuilder" in a permanent place, best in your home folder (the house icon).
   In Documents, Desktop or Downloads macOS asks for Terminal access at every start.
2. Double-click "Install LineBuilder". macOS blocks it the first time, because the file is not from the
   App Store: System Settings → Privacy & Security → at the bottom "Open Anyway", then double-click again.
   A Terminal window shows the progress. Needs internet, no administrator password.
   At the end it asks for ecoinvent: the .7z file, the unpacked folder (importing takes 10 to 20 minutes),
   or an existing Activity Browser 2 project. "Later" skips this; "Start LineBuilder" then asks again.
3. Start: double-click the app "LineBuilder" on the desktop, or "Start LineBuilder" in this folder.
   The browser opens http://127.0.0.1:5050. Keep the Terminal window open, closing it stops LineBuilder.

With the ecoinvent download, everything stays inside this folder: Python, Brightway2 and the Brightway project
"LineBuilder" (in the subfolder "brightway", about 2 GB). Activity Browser, conda and your other
Brightway projects are not touched.

With an existing Activity Browser 2 project, LineBuilder works in that project: it adds the databases
"Input Flows Collection" and "LineBuilder_web" to it and, after asking, gives up to 20 elementary flows of
biosphere3 their ecoinvent 3.12 names (e.g. "2-Propanol" becomes "Isopropanol", "Methane, trifluoro-, HFC-23"
becomes "Trifluoromethane"); their characterization factors stay. Nothing else changes. Close the Activity
Browser while LineBuilder runs. Projects of the Activity Browser 3 (Brightway 2.5) cannot be used:
LineBuilder's older Brightway2 cannot read them, so they are not offered.
To switch later: delete linebuilder_config.json in this folder and start LineBuilder again.

Remove: move the folder "LineBuilder" and the app "LineBuilder" on the desktop to the Trash.
