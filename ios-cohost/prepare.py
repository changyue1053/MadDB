"""Generate a separate app-owned consumer from the pinned MadDB Xcode generator."""
from pathlib import Path
import runpy
import shutil

HERE = Path(__file__).resolve().parent


def quote(path):
    path = str(path)
    if not Path(path).is_absolute() or any(c in path for c in ('"', '\\', '$', '\n', '\r')):
        raise ValueError("unrepresentable input")
    return '"' + path + '"'


def prepare(base_project, dest, db, link_archive, obs, *, api_headers=None):
    if obs is not None and api_headers is not None:
        raise ValueError("ambiguous observation mode")
    project = dest / "MadDBSmoke.xcodeproj"
    project.mkdir(parents=True)
    shutil.copytree(base_project / "MadDBSmoke.xcodeproj/xcshareddata", project / "xcshareddata")
    generator = dest / "generate_project.py"
    shutil.copyfile(base_project / "generate_project.py", generator)
    state = runpy.run_path(str(generator))
    objects, ref, add = (state[k] for k in ("objects","ref","add"))
    objects[ref(6)].update(path=str(db),sourceTree="<absolute>")
    objects[ref(7)]["path"]="App.swift"
    objects[ref(8)].update(path="CohostTests.mm",lastKnownFileType="sourcecode.cpp.objcpp")
    objects[ref(35)]["files"]=[] # Tests resolve only the fixture ingress via BUNDLE_LOADER.
    add(80,"PBXFileReference",path="Bridge.mm",lastKnownFileType="sourcecode.cpp.objcpp",sourceTree="<group>")
    add(81,"PBXBuildFile",fileRef=ref(80))
    objects[ref(4)]["children"].append(ref(80))
    objects[ref(30)]["files"].append(ref(81))
    for config in (62,63):
        settings=objects[ref(config)]["buildSettings"]
        settings.update(CLANG_CXX_LANGUAGE_STANDARD="c++17",
                        SWIFT_OBJC_BRIDGING_HEADER="$(PROJECT_DIR)/App/Bridge.h",
                        GCC_PREPROCESSOR_DEFINITIONS=["$(inherited)","COHOST_OBS="+str(int(obs is not None))],
                        FRAMEWORK_SEARCH_PATHS=["$(inherited)",quote(link_archive.parent.parent)],
                        OTHER_LDFLAGS=["$(inherited)",quote(link_archive),"-lc++"])
        if api_headers is not None:
            settings["SWIFT_ACTIVE_COMPILATION_CONDITIONS"]="$(inherited) COHOST_OBS_API"
            settings["GCC_PREPROCESSOR_DEFINITIONS"].append("COHOST_OBS_API=1")
            settings["HEADER_SEARCH_PATHS"]=["$(inherited)",quote(api_headers)]
        if obs:
            archive, headers=obs
            settings["SWIFT_ACTIVE_COMPILATION_CONDITIONS"]="$(inherited) COHOST_OBS"
            settings["HEADER_SEARCH_PATHS"]=["$(inherited)",quote(headers)]
            settings["OTHER_LDFLAGS"] += [quote(archive),"-lz"]
    for name in ("App","Tests"):
        (dest/name).mkdir()
    for f in ("App.swift","Bridge.h","Bridge.mm"):
        shutil.copyfile(HERE/f,dest/"App"/f)
    if api_headers is not None:
        shutil.copyfile(HERE/"ApiCollector.hpp",dest/"App/ApiCollector.hpp")
    shutil.copyfile(HERE/"CohostTests.mm",dest/"Tests/CohostTests.mm")
    generator.unlink()
    (project/"project.pbxproj").write_text("// !$*UTF8*$!\n"+state["emit"](state["project"])+"\n")
    return objects
