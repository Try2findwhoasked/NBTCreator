"""Public entry point for nbt_project.batches."""
from nbt_project.batches import (
    add_artifact,
    add_model,
    current,
    details,
    discover,
    dispatch,
    index,
    local,
    main,
    now,
    persist,
    read,
    rel,
    ROLES,
    sha,
    SHAPES,
    STATUSES,
    summary,
    task_document,
    workspace_root,
    write_index,
)


if __name__ == "__main__":
    raise SystemExit(main())
