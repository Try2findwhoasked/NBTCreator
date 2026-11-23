"""Public entry point for nbt_project.feedback."""
from nbt_project.feedback import (
    archive_evidence,
    collect,
    main,
    read,
    relative,
    resolve_asset,
    scan,
    sha,
    update_index,
    version_source,
)


if __name__ == "__main__":
    raise SystemExit(main())
