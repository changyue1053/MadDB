"""Use unchanged project generator in a disposable consumer, then edit typed objects."""
import runpy
import shutil
from pathlib import Path


def create(root, destination, package, db_headers, obs_prefix):
    source = root/'ios/Smoke'
    shutil.copytree(source, destination)
    state = runpy.run_path(str(destination/'generate_project.py'))
    objects = state['objects']
    ref = state['ref']
    objects[ref(6)]['path'] = str(package)
    objects[ref(6)]['sourceTree'] = '<absolute>'
    objects[ref(8)]['path'] = 'Tests.swift'
    objects[ref(8)]['lastKnownFileType'] = 'sourcecode.swift'
    state['add'](80, 'PBXFileReference', lastKnownFileType='sourcecode.cpp.cpp', path='Bridge.cpp', sourceTree='<group>')
    state['add'](81, 'PBXBuildFile', fileRef=ref(80))
    objects[ref(5)]['children'].append(ref(80))
    objects[ref(34)]['files'].append(ref(81))
    for n in (64, 65):
        settings = objects[ref(n)]['buildSettings']
        settings.update(CLANG_CXX_LANGUAGE_STANDARD='c++17',
                        SWIFT_OBJC_BRIDGING_HEADER='$(PROJECT_DIR)/Tests/Bridge.h',
                        HEADER_SEARCH_PATHS=['$(inherited)', '"'+str(db_headers)+'"', '"'+str(obs_prefix/'$(PLATFORM_NAME)/include')+'"'],
                        OTHER_LDFLAGS=['$(inherited)', '"'+str(obs_prefix/'$(PLATFORM_NAME)/lib/libmadobs_runtime.a')+'"', '-lz', '-lc++'])
    for name in ('Tests.swift', 'Bridge.cpp', 'Bridge.h'):
        shutil.copyfile(root/'ios-obs-composition'/name, destination/'Tests'/name)
    (destination/'MadDBSmoke.xcodeproj/project.pbxproj').write_text('// !$*UTF8*$!\n'+state['emit'](state['project'])+'\n')
    return objects
