import os

os.environ["KIVY_WINDOW"] = "sdl2"

from kivymd.app import MDApp
from kivy.lang import Builder
from kivy.core.window import Window

Window.size = (1024, 600)

screen_helper = """
Screen:
    BoxLayout:
        orientation: 'vertical'
        MDTopAppBar:
            title: "My Toolbar"
            left_action_items: [["menu", lambda x: app.navigation_draw()]]
            right_action_items: [["account-circle", lambda x: app.navigation_draw()]]
        MDLabel:
            text: "Hello, World!"
            halign: "center"
"""

class DemoApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        screen = Builder.load_string(screen_helper)
        return screen
    
    def navigation_draw(self):
        print("Navigation drawer action triggered")
    
DemoApp().run()