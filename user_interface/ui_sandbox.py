from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.uix.screen import MDScreen
from kivy.core.window import Window  # 🌟 1. อย่าลืม import Window

# 🌟 2. ตั้งค่าจำลองขนาดจอ (ย่อลงครึ่งนึงเพื่อให้พรีวิวบนคอมได้)
# สัดส่วนเดิมคือ 2560x1600 -> ย่อเหลือ 1280x800
Window.size = (1280, 800) 

class MainScreen(MDScreen):
    pass 

class SandboxApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Blue"
        
        Builder.load_file("screen/main_screen.kv")
        return MainScreen()

if __name__ == '__main__':
    SandboxApp().run()