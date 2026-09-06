import unittest
import os
from database import Database

class TestDatabaseGetGameById(unittest.TestCase):
    def setUp(self):
        """Инициализируем in-memory базу данных перед каждым тестом"""
        self.db = Database(":memory:")

    def tearDown(self):
        """Закрываем соединение с базой данных после каждого теста"""
        self.db.close()

    def test_get_existing_game_by_id(self):
        """Тест успешного получения существующей игры по ID"""
        # Добавляем игру в базу
        exe_name = "test_game.exe"
        display_name = "Test Game"
        exe_path = "C:\\Games\\test_game.exe"
        game_id = self.db.add_game(exe_name, display_name, exe_path)

        # Получаем игру по ID
        game = self.db.get_game_by_id(game_id)

        # Проверяем, что игра найдена и данные совпадают
        self.assertIsNotNone(game)
        self.assertEqual(game["id"], game_id)
        self.assertEqual(game["exe_name"], exe_name.lower())
        self.assertEqual(game["display_name"], display_name)
        self.assertEqual(game["exe_path"], exe_path)

    def test_get_non_existent_game_by_id(self):
        """Тест получения игры по несуществующему ID"""
        # Пытаемся получить игру с ID, которого точно нет в пустой базе
        game = self.db.get_game_by_id(999)

        # Проверяем, что возвращается None
        self.assertIsNone(game)

    def test_get_game_by_id_invalid_type(self):
        """Тест получения игры с передачей некорректного типа ID"""
        # SQLite часто может обработать строку как число, если она конвертируется,
        # но передача чего-то вроде "invalid" должна вернуть None, а не упасть с ошибкой,
        # так как sqlite3 не найдет совпадения.
        game = self.db.get_game_by_id("invalid")
        self.assertIsNone(game)

        # Проверим с числом в виде строки
        game_id = self.db.add_game("test2.exe", "Test 2", None)
        game_str = self.db.get_game_by_id(str(game_id))
        self.assertIsNotNone(game_str)
        self.assertEqual(game_str["id"], game_id)

if __name__ == '__main__':
    unittest.main()
