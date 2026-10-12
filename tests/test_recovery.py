import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from operations import lab


class RecoveryTests(unittest.TestCase):
    def test_rto_rpo_and_missing_records(self):
        rows = [{'id': 1, 'payload': 'a', 'committed_at': '2026-10-12T10:00:00+00:00'},
                {'id': 2, 'payload': 'b', 'committed_at': '2026-10-12T10:00:05+00:00'}]
        result = lab.metrics(rows, rows[:1], 12.12345)
        self.assertEqual(result['rto_seconds'], 12.123)
        self.assertEqual(result['rpo_seconds'], 5)
        self.assertEqual(result['missing_ids'], [2])

    def test_recovered_corruption_fails_validation(self):
        row = {'id': 1, 'payload': 'a', 'committed_at': '2026-10-12T10:00:00+00:00'}
        with self.assertRaises(ValueError):
            lab.metrics([row], [dict(row, payload='corrupt')], 1)

    def test_fencing_failure_prevents_restore_and_routing(self):
        with patch.object(lab, 'active_site', return_value='primary'), \
             patch.object(lab, 'verified_archive'), \
             patch.object(lab, 'ready', return_value=True), \
             patch.object(lab, 'fence_primary', side_effect=RuntimeError('cannot fence')), \
             patch.object(lab, 'restore_dr') as restore, patch.object(lab, 'save_state') as save:
            with self.assertRaises(RuntimeError):
                lab.failover(Path('backup.dump'))
            restore.assert_not_called()
            save.assert_not_called()

    def test_unready_dr_does_not_get_promoted(self):
        with patch.object(lab, 'active_site', return_value='primary'), \
             patch.object(lab, 'verified_archive'), patch.object(lab, 'fence_primary'), \
             patch.object(lab, 'restore_dr', return_value=[]), \
             patch.object(lab, 'ready', side_effect=[True, False]), patch.object(lab, 'save_state') as save:
            with self.assertRaises(RuntimeError):
                lab.failover(Path('backup.dump'))
            save.assert_not_called()

    def test_probe_success_resets_failure_count(self):
        with patch.object(lab, 'primary_service_ready', side_effect=[False, False, True, False, False, False]) as ready, \
             patch.object(lab.time, 'sleep'), patch.object(lab, 'failover', return_value=['ok']) as failover:
            self.assertEqual(lab.wait_and_failover(Path('x')), ['ok'])
            self.assertEqual(ready.call_count, 6)
            failover.assert_called_once()

    def test_backup_integrity_and_path_boundary(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(lab, 'ROOT', Path(directory)):
            backups = Path(directory) / 'backups'
            backups.mkdir()
            archive = backups / 'sample.dump'
            archive.write_bytes(b'PGDMPtest')
            archive.with_suffix('.json').write_text(json.dumps({'sha256': hashlib.sha256(b'PGDMPtest').hexdigest()}))
            self.assertEqual(lab.verified_archive(archive), b'PGDMPtest')
            archive.write_bytes(b'PGDMPtampered')
            with self.assertRaises(ValueError):
                lab.verified_archive(archive)
            with self.assertRaises(ValueError):
                lab.verified_archive(Path(directory) / 'outside.dump')

    def test_foreign_namespace_rejected(self):
        with self.assertRaises(ValueError):
            lab.namespace('production')


if __name__ == '__main__':
    unittest.main()
