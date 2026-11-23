"""Public entry point for nbt_project.history."""
from nbt_project.history import (
    digest,
    dispatch,
    encode,
    ENGINE,
    EXTENSIONS,
    file_hash,
    History,
    history_source,
    IDENTIFIER,
    main,
    MAX_FILE,
    MAX_LEGACY_STATE,
    MAX_PREVIEW_TOTAL,
    MAX_STATE,
    model_file,
    now,
    owned,
    PRIVATE,
    record_produced_version,
    relative,
    resolve_git,
    safe_name,
    SHA,
    SKIP,
    source_workspace,
    write_git_binding,
)


if __name__ == "__main__":
    raise SystemExit(main())
