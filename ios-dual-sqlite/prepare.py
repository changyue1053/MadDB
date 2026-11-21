"""Narrow overlay on the proven MadDB app-owned hosted test graph."""
from pathlib import Path
import runpy
import shutil

HERE = Path(__file__).resolve().parent


def quote(path):
    path = str(path)
    if not Path(path).is_absolute() or any(c in path for c in ('"', '\\', '$', '\n', '\r')):
        raise ValueError("project input")
    return '"' + path + '"'


def prepare(base, app, db, journal):
    project = app / "MadDBSmoke.xcodeproj"
    project.mkdir(parents=True)
    shutil.copytree(base / "MadDBSmoke.xcodeproj/xcshareddata", project / "xcshareddata")
    generator = app / "generate_project.py"
    shutil.copyfile(base / "generate_project.py", generator)
    state = runpy.run_path(str(generator))
    generator.unlink()
    objects, ref, add = (state[x] for x in ("objects", "ref", "add"))
    objects[ref(6)].update(path=str(db), sourceTree="<absolute>")
    objects[ref(7)]["path"] = "App.swift"
    objects[ref(8)].update(path="Tests.mm", lastKnownFileType="sourcecode.cpp.objcpp")
    objects[ref(35)]["files"] = []
    add(80, "PBXFileReference", path="JournalBridge.mm",
        lastKnownFileType="sourcecode.cpp.objcpp", sourceTree="<group>")
    add(81, "PBXBuildFile", fileRef=ref(80))
    objects[ref(4)]["children"].append(ref(80))
    objects[ref(30)]["files"].append(ref(81))
    for n in (62, 63):
        objects[ref(n)]["buildSettings"].update(
            CLANG_CXX_LANGUAGE_STANDARD="c++17",
            SWIFT_OBJC_BRIDGING_HEADER="$(PROJECT_DIR)/App/JournalBridge.h",
            HEADER_SEARCH_PATHS=["$(inherited)", quote(journal / "include")],
            OTHER_LDFLAGS=["$(inherited)", quote(journal / "lib/libmadmedia_journal_preview.a"),
                           "-lc++", "-lsqlite3"],
        )
    for folder, files in (("App", ("App.swift", "JournalBridge.mm", "JournalBridge.h")),
                          ("Tests", ("Tests.mm",))):
        (app / folder).mkdir()
        for name in files:
            shutil.copyfile(HERE / name, app / folder / name)
    (project / "project.pbxproj").write_text("// !$*UTF8*$!\n" + state["emit"](state["project"]) + "\n")
    return objects
