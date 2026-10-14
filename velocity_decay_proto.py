"""Deprecated entry point from the first sketch.

The sketch priced an endpoint slope and paid an uncapped multiple. Settlement
now lives in the vdc package. Running this file prints the same desk demo.
"""

from vdc.demo import main

if __name__ == "__main__":
    main()
