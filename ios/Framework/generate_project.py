"""Generate MadDB's native Xcode framework producer; Python standard library only."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OBJECTS = {}


def ref(number):
    return f"{number:024X}"


def add(number, isa, **fields):
    OBJECTS[ref(number)] = dict(isa=isa, **fields)


add(1, "PBXProject", attributes={"BuildIndependentTargetsInParallel": "YES"},
    buildConfigurationList=ref(30), compatibilityVersion="Xcode 14.0",
    developmentRegion="en", hasScannedForEncodings="0", knownRegions=["en", "Base"],
    mainGroup=ref(2), productRefGroup=ref(3), projectDirPath="", projectRoot="",
    targets=[ref(20)])
add(2, "PBXGroup", children=[ref(4), ref(5), ref(3)], sourceTree="<group>")
add(3, "PBXGroup", name="Products", children=[ref(6)], sourceTree="<group>")
add(4, "PBXFileReference", lastKnownFileType="sourcecode.swift",
    name="MadDatabase.swift", path="../Sources/MadDatabase.swift", sourceTree="SOURCE_ROOT")
# A blue folder reference preserves Notices as a folder in the standard resource phase.
add(5, "PBXFileReference", lastKnownFileType="folder", name="Notices",
    path="../../build/ios/Notices", sourceTree="SOURCE_ROOT")
add(6, "PBXFileReference", explicitFileType="wrapper.framework", includeInIndex="0",
    path="MadDB.framework", sourceTree="BUILT_PRODUCTS_DIR")
add(7, "PBXBuildFile", fileRef=ref(4))
add(8, "PBXBuildFile", fileRef=ref(5))
add(20, "PBXNativeTarget", buildConfigurationList=ref(31),
    buildPhases=[ref(21), ref(22), ref(23)], buildRules=[], dependencies=[],
    name="MadDB", productName="MadDB", productReference=ref(6),
    productType="com.apple.product-type.framework")
for number, isa, files in [
    (21, "PBXSourcesBuildPhase", [ref(7)]),
    (22, "PBXFrameworksBuildPhase", []),
    (23, "PBXResourcesBuildPhase", [ref(8)]),
]:
    add(number, isa, buildActionMask="2147483647", files=files,
        runOnlyForDeploymentPostprocessing="0")
for number, configurations in [(30, [40, 41]), (31, [42, 43])]:
    add(number, "XCConfigurationList", buildConfigurations=list(map(ref, configurations)),
        defaultConfigurationIsVisible="0", defaultConfigurationName="Release")

project_settings = {
    "ARCHS": "arm64",
    "ONLY_ACTIVE_ARCH": "YES",
    "SDKROOT": "iphoneos",
    "SUPPORTED_PLATFORMS": "iphoneos iphonesimulator",
    "IPHONEOS_DEPLOYMENT_TARGET": "15.0",
    "SWIFT_VERSION": "5.0",
    "CLANG_ENABLE_MODULES": "YES",
    "CLANG_ENABLE_OBJC_ARC": "YES",
    "CODE_SIGNING_ALLOWED": "NO",
    "CODE_SIGNING_REQUIRED": "NO",
}
framework_settings = {
    "PRODUCT_NAME": "MadDB",
    "PRODUCT_BUNDLE_IDENTIFIER": "io.maddb.sdk",
    "PRODUCT_MODULE_NAME": "MadDB",
    "MACH_O_TYPE": "mh_dylib",
    "DEFINES_MODULE": "YES",
    "GENERATE_INFOPLIST_FILE": "YES",
    "BUILD_LIBRARY_FOR_DISTRIBUTION": "YES",
    "SKIP_INSTALL": "NO",
    "INSTALL_PATH": "$(LOCAL_LIBRARY_DIR)/Frameworks",
    "MARKETING_VERSION": "0.1.0",
    "CURRENT_PROJECT_VERSION": "1",
    "DYLIB_COMPATIBILITY_VERSION": "1",
    "DYLIB_CURRENT_VERSION": "1",
    "DYLIB_INSTALL_NAME_BASE": "@rpath",
    "TARGETED_DEVICE_FAMILY": "1,2",
    "SUPPORTS_MACCATALYST": "NO",
    "SWIFT_INCLUDE_PATHS": ["$(inherited)", "$(PROJECT_DIR)/../../build/ios/cmodule"],
    "OTHER_LDFLAGS": [
        "$(inherited)",
        "-Wl,-load_hidden,$(MADDB_RUST_STATIC_LIBRARY)",
        "-lresolv",
        "-liconv",
    ],
}
for number, name in [(40, "Debug"), (41, "Release")]:
    settings = dict(project_settings)
    settings["SWIFT_OPTIMIZATION_LEVEL"] = "-Onone" if name == "Debug" else "-O"
    settings["DEBUG_INFORMATION_FORMAT"] = "dwarf" if name == "Debug" else "dwarf-with-dsym"
    if name == "Debug":
        settings["SWIFT_ACTIVE_COMPILATION_CONDITIONS"] = "DEBUG"
    add(number, "XCBuildConfiguration", name=name, buildSettings=settings)
for number, name in [(42, "Debug"), (43, "Release")]:
    add(number, "XCBuildConfiguration", name=name, buildSettings=dict(framework_settings))


def emit(value, level=0):
    if isinstance(value, dict):
        return "{\n" + "".join(
            "\t" * (level + 1) + json.dumps(key) + " = " + emit(item, level + 1) + ";\n"
            for key, item in value.items()
        ) + "\t" * level + "}"
    if isinstance(value, list):
        return "(" + ", ".join(emit(item, level) for item in value) + ")"
    return json.dumps(value)


def write_project():
    project = dict(archiveVersion="1", classes={}, objectVersion="56",
                   objects=OBJECTS, rootObject=ref(1))
    (ROOT / "MadDB.xcodeproj" / "project.pbxproj").write_text(
        "// !$*UTF8*$!\n" + emit(project) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_project()
