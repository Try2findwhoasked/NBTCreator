"""Public entry point for nbt_assets.batches."""
from nbt_assets.batches import (
    base,
    bounded_json,
    dispatch,
    KIND,
    LIMIT,
    local,
    main,
    manifest,
    MAX_BYTES,
    new_list,
    organize,
    register_components,
    relative,
    sha,
)


if __name__ == "__main__":
    raise SystemExit(main())
