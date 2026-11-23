"""Public entry point for nbt_mounting.curved_surface."""
from nbt_mounting.curved_surface import (
    _calculate,
    _calculate_layers,
    _continuity,
    _layered_mask,
    _mask,
    _review_feedback,
    _surface_point,
    main,
    MAX_FACE_SAMPLES,
    MAX_MASK,
    plan_curve,
    record_curve_followup,
    ROLE,
    verify_curve,
    verify_curve_followup,
)


if __name__ == "__main__":
    raise SystemExit(main())
