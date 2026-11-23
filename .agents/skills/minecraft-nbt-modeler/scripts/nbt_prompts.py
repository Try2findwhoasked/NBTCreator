"""Public entry point for nbt_project.prompts."""
from nbt_project.prompts import (
    check_task_index_size,
    completion_evidence,
    digest,
    encode,
    handoff_statuses,
    index_lock,
    inside,
    library_list,
    load_index,
    load_tasks,
    main,
    organize_prompts,
    prompt_group_file,
    publish,
    published_constraint_links,
    read_handoff,
    read_prompt,
    read_prompt_groups,
    read_task,
    relative,
    remove_prompt,
    save,
    scan,
    set_prompt_recycled,
    task_action,
    TASK_ATTACHMENTS,
    task_file,
    task_index,
    TASK_INDEX_BYTES,
    task_status,
    TASK_VIEWS,
    tasks,
)


if __name__ == "__main__":
    raise SystemExit(main())
