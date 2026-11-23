"""Public entry point for nbt_composition.working_model."""
from nbt_composition.working_model import (
    constraint_context,
    digest,
    empty_volume,
    file_hash,
    head_file,
    main,
    managed_manifest,
    model_hash,
    ModelConflict,
    point,
    publication_lock,
    publish_head,
    value_at,
    verify_version,
    WorkingModel,
    world_objects,
    world_policy,
    world_position,
    write_json,
)


if __name__ == "__main__":
    raise SystemExit(main())
