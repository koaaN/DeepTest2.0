import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

if len(sys.argv) >= 3 and sys.argv[1] == "-m" and sys.argv[2] in {"deeptesting.cli", "deeptesting.token_cli"}:
    if sys.argv[2] == "deeptesting.token_cli":
        from deeptesting.token_cli import main
    else:
        from deeptesting.cli import main
    sys.argv = [sys.argv[2], *sys.argv[3:]]
else:
    from deeptesting.gui import main

if __name__ == "__main__":
    raise SystemExit(main())
