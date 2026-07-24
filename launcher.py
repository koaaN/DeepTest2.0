import sys

if len(sys.argv) >= 3 and sys.argv[1:3] == ["-m", "deeptesting.cli"]:
    from deeptesting.cli import main
    sys.argv = ["deeptesting.cli", *sys.argv[3:]]
else:
    from deeptesting.gui import main

if __name__ == "__main__":
    raise SystemExit(main())
