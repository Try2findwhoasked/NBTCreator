"""Public entry point for nbt_composition.large_assembly."""
from nbt_composition.large_assembly import (
    _part_path,
    _workspace_path,
    assembly_manifest,
    assembly_source_matches,
    AssemblyVolume,
    import_assembly,
    is_assembly_source,
    main,
    MAX_AXIS,
    MAX_BLOCKS,
    MAX_MANIFEST_BYTES,
    MAX_PARTITIONS,
    read_assembly,
    require_creative_workspace,
    save_assembly,
    SHA,
    verify_assembly_binding,
    verify_assembly_files,
)


if __name__ == "__main__":
    raise SystemExit(main())
