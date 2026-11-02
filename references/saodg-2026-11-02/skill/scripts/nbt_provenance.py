"""Optional stable operation IDs and last-writer coordinates for task generators."""
from contextlib import contextmanager
import json
from pathlib import Path


class OperationTrace:
    """Compose with Model.put/WallMask; does not choose a layout or grant refinement."""
    def __init__(self, model):
        self.model, self.operations, self.owners = model, {}, {}
        self.current = None
        self.original = model.put
        def tracked(position, value):
            self.original(position, value)
            self.owners[tuple(position)] = self.current
        self.tracked = tracked
        model.put = tracked

    @contextmanager
    def operation(self, operation_id, purpose):
        if not isinstance(operation_id, str) or not operation_id.strip() or operation_id in self.operations:
            raise ValueError('Use a new, stable, non-empty operation ID')
        if self.current is not None:
            raise ValueError('Operation scopes cannot nest')
        self.operations[operation_id] = dict(purpose=purpose)
        self.current = operation_id
        try:
            yield
        finally:
            self.current = None

    def save(self, path):
        data = dict(geometry_sha256=self.model.fingerprint(), operations=self.operations,
                    owners=[[list(p), op] for p, op in sorted(self.owners.items())],
                    semantics='Last observed put, including air/deletions; null means an unlabelled write. Direct blocks edits are untracked.')
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        return data

    def close(self):
        if self.model.put is not self.tracked:
            raise ValueError('Close newer put wrappers first')
        self.model.put = self.original
