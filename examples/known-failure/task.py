from pathlib import Path

value = Path("input.txt").read_text(encoding="utf-8").strip()
print(value)
print(f"workspace={Path.cwd()}")
raise SystemExit(7)
