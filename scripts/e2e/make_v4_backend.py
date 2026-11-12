"""Create the v4 backend modules from the v3 ones (renames only); v4-specific edits are made afterwards."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "rain-api"
COMMON = [("rain_v3", "rain_v4"), ("ui_v3", "ui_v4"), ("PG_DB_V3", "PG_DB_V4"), ("/api/v3/", "/api/v4/"),
          ("v0.3", "v0.4"), ("RAIN_v3", "RAIN_v4")]
FILES = {
    "ui_data_v3.py": ("ui_data_v4.py", [("ui-data-v3", "ui-data-v4")]),
    "persona_queries_v3.py": ("persona_queries_v4.py", [("persona-queries-v3", "persona-queries-v4"),
                                                        ("rain_v4_persona_queries", "rain_v4_persona_queries")]),
    "chat_v3.py": ("chat_v4.py", [("chat_v3", "chat_v4"), ("test_chat_v4_build", "test_chat_v4_build")]),
    "ultra_v3_api.py": ("ultra_v4_api.py", [("import chat_v3", "import chat_v4"), ("chat_v3.", "chat_v4."),
                                             ("persona_queries_v3 as pq", "persona_queries_v4 as pq"),
                                             ("import ui_data_v3", "import ui_data_v4"), ("ui_data_v3.", "ui_data_v4."),
                                             ('tags=["ultra-v3"]', 'tags=["ultra-v4"]')]),
}
for src, (dst, extra) in FILES.items():
    text = (API / src).read_text(encoding="utf-8")
    for a, b in extra + COMMON:
        text = text.replace(a, b)
    text = text.replace("rain_v4_persona_queries.sql", "rain_v4_persona_queries.sql")
    (API / dst).write_text(text, encoding="utf-8", newline="\n")
    print("wrote", dst)
src = (ROOT / "deploy/scripts/load_ui_data.py").read_text(encoding="utf-8")
for a, b in [("rain_v3_ui_data.json", "rain_v4_ui_data.json"), ("v3_ui", "v4_ui")] + COMMON:
    src = src.replace(a, b)
(ROOT / "deploy/scripts/load_ui_data_v4.py").write_text(src, encoding="utf-8", newline="\n")
print("wrote deploy/scripts/load_ui_data_v4.py")
