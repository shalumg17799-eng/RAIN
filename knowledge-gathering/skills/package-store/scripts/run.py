import posixpath


def run(inp, ctx):
    pkg, store = inp["package"], ctx.get("artifacts")
    ent = pkg.get("enterprise_id") or ctx.get("enterprise") or "platform"
    base = posixpath.join(inp.get("prefix", "packages"), ent, str(pkg["package_version"]))
    manifest = dict(pkg["manifest"])
    write = bool(store) and not ctx.get("dry_run")
    if write and store.exists(posixpath.join(base, "manifest.yaml")) and not inp.get("overwrite"):
        raise ValueError(f"package {ent}/{pkg['package_version']} already exists (immutable); bump package_version")
    files = []
    for f in pkg["files"]:
        path = posixpath.join(base, f["path"])
        uri = store.uri(path) if store else f"file://{path}"
        if write:
            store.put(path, f["content"])
        files.append({k: v for k, v in f.items() if k != "content"} | {"uri": uri})
    manifest["files"] = files
    manifest["uri"] = store.uri(base) if store else f"file://{base}"
    return {"manifest": manifest, "package_version": pkg["package_version"], "written": write, "uri": manifest["uri"],
            "files": [f["uri"] for f in files]}
