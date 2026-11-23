"""Public entry point for nbt_review.reference_views."""
from nbt_review.reference_views import (
    _hash,
    _image_bytes,
    fit_profile,
    IDENTIFIER,
    load_reference,
    main,
    MAX_IMAGE,
    MAX_MANIFEST,
    register_reference,
    save_fit,
    SHA,
    verify_fit,
    VIEW_AXES,
)


if __name__ == "__main__":
    raise SystemExit(main())
