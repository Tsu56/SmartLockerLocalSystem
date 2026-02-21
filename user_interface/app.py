from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen

class Gui_manager(ScreenManager):
    pass

class MainMenu(Screen):
    pass

class Dashboard(Screen):
    pass

class Gui_demo(App):
    def build(self):
        return Gui_manager()
    
if __name__ == "__main__":
    Gui_demo().run()