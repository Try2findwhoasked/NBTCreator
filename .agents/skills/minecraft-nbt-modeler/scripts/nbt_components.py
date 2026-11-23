"""Public entry point for nbt_assets.components."""
from nbt_assets.components import (
    batch_placement,
    capture,
    component_file,
    content_hash,
    extract,
    library_root,
    listing,
    load,
    main,
    MAX_BLOCKS,
    MAX_BYTES,
    paste_plan,
    placement,
    PlacementBoundsError,
    store,
    thumbnail,
    transform_selection,
    update,
    validate,
    vector,
)


if __name__ == "__main__":
    raise SystemExit(main())
