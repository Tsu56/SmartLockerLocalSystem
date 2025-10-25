from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.uix.list import ThreeLineListItem

list_helper = """
Screen:
    ScrollView:
        MDList:
            id: md_list
"""

class DemoApp(MDApp):
    def build(self):
        screen = Builder.load_string(list_helper)

        return screen
    
    def on_start(self):
        for i in range(20):
            self.root.ids.md_list.add_widget(
                ThreeLineListItem(
                    text=f"Item {i+1}",
                    secondary_text="This is a secondary text",
                    tertiary_text="This is a tertiary text",
                )
            )
    
DemoApp().run()