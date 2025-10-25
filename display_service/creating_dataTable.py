from kivymd.app import MDApp
from kivymd.uix.screen import Screen
from kivymd.uix.datatables import MDDataTable
from kivy.metrics import dp

class DemoApp(MDApp):
    def build(self):
        screen = Screen()
        data_table = MDDataTable(
            size_hint=(0.9, 0.6),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            check=True,
            rows_num=10,
            column_data=[
                ("No.", dp(30)),
                ("Name", dp(30)),
                ("Total", dp(30)),
            ],
            row_data=[
                ("1", "Morphine", "50"),
                ("2", "Codeine", "40"),
                ("3", "Heroin", "30"),
                ("4", "Fentanyl", "20"),
                ("5", "Oxycodone", "10"),
                ("6", "Hydrocodone", "5"),
                ("7", "Methadone", "15"),
                ("8", "Buprenorphine", "25"),
                ("9", "Tramadol", "35"),
                ("10", "Hydromorphone", "45")
            ]
        )
        data_table.bind(on_check_press=self.on_check_press)
        data_table.bind(on_row_press=self.on_row_press)
        screen.add_widget(data_table)
        return screen
    
    def on_check_press(self, instance_table, current_row):
        print(f'checked {current_row}')

    def on_row_press(self, instance_table, current_row):
        print(f'pressed {current_row}')
    
DemoApp().run()