from kivymd.app import MDApp
from kivymd.uix.screen import Screen
from kivymd.uix.button import MDRectangleFlatButton, MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivy.lang import Builder
from helpers import username_helper


class DemoApp(MDApp):
    def build(self):
        screen = Screen()
        self.theme_cls.primary_palette = "Blue"
        button = MDRectangleFlatButton(text='Show',
                                       pos_hint={'center_x': 0.5, 'center_y': 0.4},
                                       on_release=self.show_data)
        self.username = Builder.load_string(username_helper)
        screen.add_widget(self.username)
        screen.add_widget(button)
        return screen
    
    def show_data(self, obj):
        if self.username.text is "":
            check_string = 'Please enter your username.'
        else:
            check_string = f'Hello, {self.username.text}!'
        close_button = MDFlatButton(text='Close',
                                     on_release=lambda x: self.dialog.dismiss())
        self.dialog = MDDialog(title='Input Data',
                          text=check_string,
                          size_hint=(0.8, None),
                          height='200dp',
                          buttons=[close_button])
        self.dialog.open()
        print(f'Username: {self.username.text}')
    
DemoApp().run()