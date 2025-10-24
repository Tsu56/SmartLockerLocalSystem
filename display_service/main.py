from kivymd.app import MDApp
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import Screen
from kivymd.uix.button import MDRectangleFlatButton


class SmartLockerApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        screen = Screen()
        Header = MDLabel(text='Welcome to Smart Locker',
                         halign='center',
                         pos_hint={'center_x': 0.5, 'center_y': 0.9},
                         font_style='H3')
        SubHeader = MDLabel(text='Please select your login method.',
                            halign='center',
                            pos_hint={'center_x': 0.5, 'center_y': 0.8},
                            font_style='Subtitle1')
        btn_flat = MDRectangleFlatButton(text='ID Card',
                                        pos_hint={'center_x': 0.5, 'center_y': 0.5})
        screen.add_widget(Header)
        screen.add_widget(SubHeader)
        screen.add_widget(btn_flat)
        return screen
    
SmartLockerApp().run()