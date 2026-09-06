import unittest
import os
import tempfile
from datetime import datetime
from database import Database

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Create a temporary file for the database to keep tests isolated
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.db = Database(self.db_path)

    def tearDown(self):
        self.db.close()
        os.close(self.db_fd)
        os.remove(self.db_path)

    def test_update_game_time_increases_total_seconds(self):
        game_id = self.db.add_game(exe_name="test_game.exe", display_name="Test Game")

        # Initial check
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['total_seconds'], 0)

        # Update time
        self.db.update_game_time(game_id, 3600)

        # Check if time was updated correctly
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['total_seconds'], 3600)

        # Add more time
        self.db.update_game_time(game_id, 1800)
        game = self.db.get_game_by_id(game_id)
        self.assertEqual(game['total_seconds'], 5400)

    def test_update_game_time_updates_last_launched(self):
        game_id = self.db.add_game(exe_name="test_game2.exe", display_name="Test Game 2")

        # Update time
        self.db.update_game_time(game_id, 3600)

        # Check if last_launched was updated
        game = self.db.get_game_by_id(game_id)
        self.assertIsNotNone(game['last_launched'])

        try:
            datetime.fromisoformat(game['last_launched'])
        except ValueError:
            self.fail("last_launched should be a valid ISO format string")

    def test_update_game_time_non_existent_game(self):
        non_existent_id = 9999
        # Ensure it does not raise an exception
        try:
            self.db.update_game_time(non_existent_id, 3600)
        except Exception as e:
            self.fail(f"update_game_time raised an exception for non-existent game: {e}")

if __name__ == '__main__':
    unittest.main()
