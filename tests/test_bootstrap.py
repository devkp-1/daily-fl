import tempfile
import unittest
from pathlib import Path

from app import create_app


class BootstrapTests(unittest.TestCase):
    def test_root_route_and_database_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            app = create_app({"TESTING": True, "DATABASE": str(db_path)})
            client = app.test_client()

            response = client.get("/")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_data(as_text=True), "Personal Productivity Loop")
            self.assertTrue(db_path.exists())


if __name__ == "__main__":
    unittest.main()
