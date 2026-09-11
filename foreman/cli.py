"""Headless run: python -m foreman.cli "work order" [--ledger out.json]"""
import asyncio, sys, json
from foreman.pipeline import Foreman


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    order = args[0] if args else "Prepare the Q3 vendor comparison for procurement: pricing, SLA and support for the three storage vendors, a 3-year total cost table, and a one-page recommendation memo under 350 words."
    fm = Foreman(order)
    summary = asyncio.run(fm.run())
    if "--ledger" in sys.argv:
        out = sys.argv[sys.argv.index("--ledger") + 1]
        open(out, "w").write(fm.ledger.to_json())
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
