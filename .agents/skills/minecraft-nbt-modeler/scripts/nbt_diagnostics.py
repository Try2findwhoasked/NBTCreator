"""Public entry point for nbt_review.diagnostics."""
from nbt_review.diagnostics import (
    bounds,
    candidate,
    CHECKS,
    explain,
    item,
    main,
    protection,
    walk,
)


if __name__ == "__main__":
    raise SystemExit(main())
