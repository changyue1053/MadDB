"""Read-only inventory of one generated Xcode receipt. Never a launch policy."""
import hashlib
import os
import plistlib
import stat
from xml.parsers import expat

LIMIT = 1024 * 1024
TARGET = "MadDBSmokeTests"
HOST = "Debug-iphonesimulator/MadDBSmoke.app"
OVERRIDES = frozenset({
    "CommandLineArguments", "UITargetAppCommandLineArguments",
    "OnlyTestIdentifiers", "SkipTestIdentifiers", "UseDestinationArtifacts",
    "TestBundleDestinationRelativePath", "UITargetAppPath",
    "UITargetAppEnvironmentVariables", "IsUITestBundle", "IsXCTRunnerHostedTestBundle",
})


class Rejected(ValueError):
    pass


# Not ValueError: the binary plist parser would normalize it internally.
class _DuplicateKey(Exception):
    pass


class _UniqueDict(dict):
    def __setitem__(self,key,value):
        if key in self:
            raise _DuplicateKey()
        super().__setitem__(key,value)


_XML_VALUES=frozenset({"array","dict","true","false","integer","real","string","date","data"})
_XML_TEXT=_XML_VALUES-{"array","dict","true","false"}


class _XMLShape(Exception):
    pass


def _xml_envelope(data):
    """Reject XML layouts that plistlib would otherwise silently collapse."""
    parser=expat.ParserCreate()
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    stack=[]

    def invalid(*_):
        raise _XMLShape()

    def doctype(name,system,public,internal):
        # The literal Apple marker is allowed; its external DTD is never read.
        if (name,system,public,internal)!=(
            "plist","http://www.apple.com/DTDs/PropertyList-1.0.dtd",
            "-//Apple//DTD PLIST 1.0//EN",0
        ):
            invalid()

    def start(tag,attrs):
        if not stack:
            if tag!="plist" or attrs!={"version":"1.0"}:
                invalid()
        else:
            if attrs or len(stack)>=64:
                invalid()
            parent,count=stack[-1]
            if parent=="plist":
                good=(count==0 and tag=="dict")
            elif parent=="dict":
                good=(tag=="key" if count%2==0 else tag in _XML_VALUES)
            else:
                good=(parent=="array" and tag in _XML_VALUES)
            if not good:
                invalid()
            stack[-1]=(parent,count+1)
        stack.append((tag,0))

    def end(_):
        tag,count=stack.pop()
        if (tag=="plist" and count!=1) or (tag=="dict" and count%2):
            invalid()

    def character_data(value):
        if (not stack or stack[-1][0] not in _XML_TEXT|{"key"}) and value.strip(" \t\r\n"):
            invalid()

    parser.StartDoctypeDeclHandler=doctype
    parser.ExternalEntityRefHandler=invalid
    parser.EntityDeclHandler=invalid
    parser.ProcessingInstructionHandler=invalid
    parser.StartElementHandler=start
    parser.EndElementHandler=end
    parser.CharacterDataHandler=character_data
    parser.Parse(data,True)


def inventory(root, bundles):
    """Return a private fingerprint and fixed descriptors, never receipt data."""
    if root.resolve(strict=True) != root or not root.is_dir():
        raise Rejected("products-path")
    matches=[]
    for path in root.glob("*.xctestrun"):
        if matches:
            raise Rejected("receipt-count")
        matches.append(path)
    if not matches:
        raise Rejected("receipt-count")
    path=matches[0]
    if not stat.S_ISREG(path.lstat().st_mode) or path.resolve(strict=True)!=path:
        raise Rejected("receipt-path")
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),"rb") as handle:
        meta=os.fstat(handle.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink!=1:
            raise Rejected("receipt-path")
        if not 0<meta.st_size<=LIMIT:
            raise Rejected("receipt-size")
        data=handle.read(LIMIT+1)
    if not 0<len(data)<=LIMIT:
        raise Rejected("receipt-size")
    try:
        if not data.startswith(b"bplist00"):
            _xml_envelope(data)
        doc=plistlib.loads(data,dict_type=_UniqueDict)
    except _XMLShape:
        raise Rejected("receipt-xml-shape") from None
    except _DuplicateKey:
        raise Rejected("receipt-duplicate-key") from None
    except Exception:
        raise Rejected("receipt-read") from None
    return hashlib.sha256(data).digest(), describe(doc, bundles)


def describe(doc,bundles):
    if not isinstance(doc,dict):
        raise Rejected("receipt-shape")
    meta=doc.get("__xctestrun_metadata__",{})
    version=meta.get("FormatVersion",1) if isinstance(meta,dict) else None
    if type(version) is not int or version not in (1,2):
        raise Rejected("receipt-version")
    scopes=[doc]
    if version==2:
        cfg=doc.get("TestConfigurations")
        if not isinstance(cfg,list) or len(cfg)!=1 or not isinstance(cfg[0],dict):
            raise Rejected("receipt-configuration")
        scopes.append(cfg[0])
        targets=cfg[0].get("TestTargets")
        if not isinstance(targets,list) or len(targets)!=1:
            raise Rejected("receipt-target-count")
        target=targets[0]
        default_name=None
    else:
        names=set(doc)-{"__xctestrun_metadata__","CodeCoverageBuildableInfos"}
        if len(names)!=1:
            raise Rejected("receipt-target-count")
        default_name=names.pop()
        target=doc[default_name]
    if not isinstance(target,dict):
        raise Rejected("receipt-target-shape")
    scopes.append(target)
    labels=["format-v1" if version==1 else "format-v2"]
    labels.append("expected-target" if target.get("BlueprintName",default_name)==TARGET else "other-target")
    host=target.get("TestHostPath")
    labels.append("expected-host" if host in ("__TESTROOT__/"+HOST,
                                              "__TESTROOT__/"+HOST+"/MadDBSmoke") else "other-host")
    bundle=target.get("TestBundlePath")
    choices=[]
    for rel in bundles:
        choices.append("__TESTROOT__/"+rel)
        if rel.startswith(HOST+"/"):
            choices.append("__TESTHOST__/"+rel.removeprefix(HOST+"/"))
    labels.append("expected-bundle" if bundle in choices else "other-bundle")
    for key,label in (("EnvironmentVariables","scheme-env"),("TestingEnvironmentVariables","loader-env")):
        if any(key in scope and scope[key]!={} for scope in scopes):
            labels.append(label+"-present")
    if any(key in scope and scope[key] not in (None,False,[],{},"")
           for scope in scopes for key in OVERRIDES):
        labels.append("known-overrides-present")
    return tuple(labels)
