import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('verify_artifact_identity', Path(__file__).parents[1] / 'scripts' / 'verify_artifact_identity.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class IdentityTests(unittest.TestCase):
    def test_match_changed_and_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'asset.glb').write_bytes(b'model A')
            manifest = {'artifacts': [{'path': 'asset.glb', 'sha256': hashlib.sha256(b'model A').hexdigest()}]}
            self.assertTrue(module.verify(root, manifest)['match'])
            (root / 'asset.glb').write_bytes(b'model B')
            self.assertFalse(module.verify(root, manifest)['match'])
            (root / 'asset.glb').unlink()
            self.assertIsNone(module.verify(root, manifest)['artifacts'][0]['actual_sha256'])
    def test_rejects_escape_and_empty_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError): module.verify(Path(directory), {'artifacts': []})
            with self.assertRaises(ValueError): module.verify(Path(directory), {'artifacts': [{'path': '../outside', 'sha256': 'a' * 64}]})

if __name__ == '__main__': unittest.main()
