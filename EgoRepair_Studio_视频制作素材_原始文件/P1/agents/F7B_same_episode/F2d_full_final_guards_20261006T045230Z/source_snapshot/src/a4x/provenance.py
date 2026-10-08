"""Content-addressed immutable references; paths confer no trust by themselves."""
import hashlib
import mimetypes
from pathlib import Path

class IntegrityError(ValueError):
    pass

def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def artifact_ref(path, media_type=None):
    path = Path(path).absolute()
    if not path.is_file():
        raise IntegrityError(f'Not a regular artifact: {path}')
    return dict(path=str(path), sha256=sha256_file(path), bytes=path.stat().st_size,
                media_type=media_type or mimetypes.guess_type(path.name)[0] or 'application/octet-stream')

def verify_artifact(ref, allowed_roots):
    if not allowed_roots:
        raise IntegrityError('An explicit input/run whitelist is required')
    try:
        path = Path(ref['path']).resolve(strict=True)
        roots = [Path(root).resolve(strict=True) for root in allowed_roots]
    except OSError as error:
        raise IntegrityError(f'Missing/unresolvable artifact or whitelist: {error}') from error
    if not any(path == root or path.is_relative_to(root) for root in roots):
        raise IntegrityError(f'Artifact outside whitelist: {path}')
    if not path.is_file() or path.stat().st_size != ref['bytes']:
        raise IntegrityError(f'Artifact size mismatch: {path}')
    if sha256_file(path) != ref['sha256']:
        raise IntegrityError(f'Artifact SHA mismatch: {path}')
    return path
