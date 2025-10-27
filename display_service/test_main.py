import unittest
from unittest.mock import MagicMock
from main import SmartLockerApp

class TestSmartLockerApp(unittest.TestCase):
    def setUp(self):
        self.app = SmartLockerApp()
        self.app.build()
        self.app.show_toast = MagicMock()
        self.app.change_screen = MagicMock()
    
    def test_card_insert_and_read(self):
        self.app.reader.card_present = MagicMock(return_value=True)
        self.app.reader.read_all = MagicMock(return_value={
            "citizenID": "1234567890123",
            "firstname": "John",
            "lastname": "Doe"
        })

        self.app.current_screen_name = "id_card_login"

        self.app.check_card_status(0)

        self.assertTrue(self.app.card_present_status)
        
        self.app.read_card_thread()

        self.app.show_toast.assert_called_with("Welcome, John Doe")
        self.app.change_screen.assert_called_with("main_screen")

    def test_no_card_present(self):
        self.app.reader.card_presesnt = MagicMock(return_value=False)
        self.app.current_screen_name = "id_card_login"

        self.app.check_card_status(0)
        self.assertFalse(self.app.card_present_status)
        self.assertFalse(self.app.is_reading_card)

    def test_reader_error(self):
        self.app.reader.card_present = MagicMock(side_effect=Exception("Reader not connected"))
        self.app.current_screen_name = "id_card_login"

        self.app.check_card_status(0)
        
        self.app.show_toast.assert_called_with("Reader error: Reader not connected")
        self.assertFalse(self.app.card_present_status)
        self.assertFalse(self.app.is_reading_card)

if __name__ == '__main__':
    unittest.main()