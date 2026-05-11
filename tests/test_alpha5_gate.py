import unittest

from alpha5_gate import evaluate


class Alpha5GateTests(unittest.TestCase):
    def test_gate_pass(self):
        records = [
            {"ended_at": "2099-01-01T00:00:00", "success": True, "restart_count": 0, "elapsed_seconds": 300},
            {"ended_at": "2099-01-01T01:00:00", "success": True, "restart_count": 1, "elapsed_seconds": 240},
            {"ended_at": "2099-01-01T02:00:00", "success": True, "restart_count": 0, "elapsed_seconds": 500},
        ]
        result = evaluate(records, days=36500, min_records=3, min_success_rate=0.9, max_avg_restarts=1.2)
        self.assertTrue(result["is_pass"])

    def test_gate_fail_on_success_rate(self):
        records = [
            {"ended_at": "2099-01-01T00:00:00", "success": False, "restart_count": 0, "elapsed_seconds": 300},
            {"ended_at": "2099-01-01T01:00:00", "success": True, "restart_count": 0, "elapsed_seconds": 300},
        ]
        result = evaluate(records, days=36500, min_records=2, min_success_rate=0.9, max_avg_restarts=1.2)
        self.assertFalse(result["is_pass"])
        self.assertFalse(result["pass_success"])


if __name__ == "__main__":
    unittest.main()
