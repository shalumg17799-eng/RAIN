import json
import re
from collections import Counter

from dif.config import settings

PASCAL = re.compile(r"^[A-Z][A-Za-z0-9]*$")
CAMEL = re.compile(r"^[a-z][A-Za-z0-9]*$")


def load_upper_ontology(spec=None):
    if isinstance(spec, dict) and spec.get("concepts"):
        return spec
    return json.loads((settings.platform_dir / "ontology" / "upper-ontology.v1.json").read_text())


def _issue(issues, severity, message, subject=None):
    issues.append({"severity": severity, "message": message, "subject": subject})


def validate(ontology, domain_model=None, extraction=None, alignment=None, upper_ontology=None):
    classes = ontology.get("classes") or []
    ids = [c.get("id") for c in classes]
    class_ids = set(ids)
    checks, issues = [], []

    def check(name, errors, detail=None, severity="error"):
        for subject, msg in errors:
            _issue(issues, severity, msg, subject)
        checks.append({"name": name, "passed": not errors or severity != "error",
                       "detail": detail or (f"{len(errors)} issue(s)" if errors else "ok")})

    dup_ids = [i for i, n in Counter(ids).items() if n > 1]
    dup_names = [i for i, n in Counter(c.get("name") for c in classes).items() if n > 1]
    check("unique_classes", [(d, f"duplicate class id '{d}'") for d in dup_ids] +
          [(d, f"duplicate class name '{d}'") for d in dup_names])

    check("class_provenance", [(c["id"], f"class '{c['id']}' traces to neither an entity nor a table")
                               for c in classes if not ((c.get("source") or {}).get("entity") or (c.get("source") or {}).get("table"))])

    errs = []
    for p in ontology.get("object_properties") or []:
        for end in ("domain", "range"):
            if p.get(end) not in class_ids:
                errs.append((p.get("id"), f"object property '{p.get('id')}' has unknown {end} '{p.get(end)}'"))
    check("object_property_refs", errs)
    check("data_property_refs", [(p.get("id"), f"data property '{p.get('id')}' has unknown domain '{p.get('domain')}'")
                                 for p in ontology.get("data_properties") or [] if p.get("domain") not in class_ids])

    errs = [(c["id"], f"class id '{c['id']}' is not PascalCase") for c in classes if not PASCAL.match(str(c.get("id")))]
    for p in (ontology.get("object_properties") or []) + (ontology.get("data_properties") or []):
        if not CAMEL.match(str(p.get("name"))):
            errs.append((p.get("id"), f"property name '{p.get('name')}' is not camelCase"))
    check("naming", errs)

    if domain_model:
        covered = {(c.get("source") or {}).get("entity") for c in classes}
        missing = [e for e in domain_model.get("entities") or [] if e.get("id") not in covered and e.get("name") not in covered]
        total = len(domain_model.get("entities") or [])
        check("entity_coverage", [(e.get("id"), f"entity '{e.get('id')}' has no class") for e in missing],
              f"{total - len(missing)}/{total} entities covered")

    if extraction and isinstance(extraction.get("tables"), list):
        tables = set(extraction["tables"])
        check("table_refs", [(c["id"], f"class '{c['id']}' references unknown table '{c['source']['table']}'")
                             for c in classes if (c.get("source") or {}).get("table") and c["source"]["table"] not in tables],
              severity="warning")

    if alignment:
        upper = load_upper_ontology(upper_ontology)
        concepts = {c["id"] for c in upper.get("concepts", [])} | {c.get("name") for c in upper.get("concepts", [])}
        aligned = {m.get("class") for m in alignment.get("mappings") or []}
        proposed = {c for e in alignment.get("extensions_proposed") or [] for c in e.get("classes") or []}
        unaligned = set(alignment.get("unaligned") or [])
        check("alignment_coverage", [(i, f"class '{i}' is neither aligned, proposed as an extension nor listed as unaligned")
                                     for i in ids if i not in aligned | proposed | unaligned])
        errs = [(m.get("class"), f"mapping of '{m.get('class')}' targets unknown upper concept '{m.get('upper_concept')}'")
                for m in alignment.get("mappings") or [] if m.get("upper_concept") not in concepts]
        errs += [(e.get("name"), f"extension '{e.get('name')}' has unknown parent '{e.get('parent')}'")
                 for e in alignment.get("extensions_proposed") or [] if e.get("parent") not in concepts]
        check("alignment_concepts", errs)

    failed = [c for c in checks if not c["passed"]]
    return {"passed": not failed, "issues": issues, "checks": checks,
            "score": round((len(checks) - len(failed)) / len(checks), 2) if checks else 1.0}


def run(inp, ctx):
    onto = inp["ontology"]
    if not isinstance(onto, dict) or not isinstance(onto.get("classes"), list):
        raise ValueError("ontology must be an ontology.v1 object (needs 'classes')")
    return validate(onto, inp.get("domain_model"), inp.get("extraction"), inp.get("alignment"), inp.get("upper_ontology"))
