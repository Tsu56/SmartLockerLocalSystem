from datetime import datetime

from kivy.metrics import dp
from kivy.properties import StringProperty, NumericProperty, ObjectProperty
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivymd.app import MDApp
from kivymd.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.relativelayout import MDRelativeLayout
from kivymd.uix.button import MDFlatButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.datatables import MDDataTable
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel, MDIcon
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField
from kivymd.uix.pickers import MDDatePicker
import requests

# URL ของ API Gateway
API_BASE_URL = "http://localhost:5000/api/product/locker"


class RestockMedicineRowWidget(MDBoxLayout):
    med_id = StringProperty("")
    med_name = StringProperty("")
    select_callback = ObjectProperty(None)


class RestockCartItemWidget(MDBoxLayout):
    product_id = StringProperty("")
    product_name = StringProperty("")
    slot = StringProperty("")
    quantity = StringProperty("0")
    lot_id = StringProperty("")
    expired_at = StringProperty("")
    delete_callback = ObjectProperty(None)

    def __init__(self, **kwargs):
        self.delete_callback = kwargs.pop("delete_callback", None)
        super().__init__(**kwargs)

    def on_delete_press(self):
        if callable(self.delete_callback):
            self.delete_callback()


class SlotSelectCard(MDCard):
    def __init__(self, slot_info, on_select, **kwargs):
        super().__init__(**kwargs)
        self.slot_info = slot_info
        self.on_select = on_select
        self.orientation = "vertical"
        self.padding = dp(12)
        self.spacing = dp(10)
        self.size_hint = (None, None)
        self.size = (dp(180), dp(205))
        self.radius = [12]
        self.ripple_behavior = True

        current_qty = sum(p["qty"] for p in slot_info["products"])
        capacity = slot_info["capacity"]
        ratio = current_qty / capacity if capacity else 0

        if current_qty == 0:
            border_color = (0.11, 0.77, 0.36, 1)
            card_bg = (0.93, 0.99, 0.95, 1)
            progress_color = (0.11, 0.77, 0.36, 1)
            status_text = "ว่าง"
            can_select = True
        elif current_qty >= capacity:
            border_color = (0.95, 0.24, 0.24, 1)
            card_bg = (1, 0.95, 0.95, 1)
            progress_color = (0.95, 0.24, 0.24, 1)
            status_text = "เต็ม"
            can_select = False
        else:
            border_color = (0.94, 0.66, 0.05, 1)
            card_bg = (1, 0.98, 0.90, 1)
            progress_color = (0.94, 0.66, 0.05, 1)
            status_text = "มียาบางส่วน"
            can_select = True

        self.line_color = border_color
        self.line_width = 1.2
        self.md_bg_color = card_bg

        header = MDBoxLayout(size_hint_y=None, height=dp(32), spacing=dp(6))
        slot_chip = MDCard(
            size_hint=(None, None),
            size=(dp(34), dp(34)),
            radius=[10],
            elevation=0,
            md_bg_color=(0.95, 0.96, 0.98, 1),
        )
        slot_chip.add_widget(
            MDLabel(
                text=str(slot_info["slot"]),
                halign="center",
                valign="middle",
                theme_text_color="Primary",
                bold=True,
            )
        )

        header.add_widget(slot_chip)
        header.add_widget(MDLabel())

        if slot_info["products"]:
            top_product = slot_info["products"][0]
            top_name = top_product["name"]
            top_qty = top_product["qty"]
        else:
            top_name = "ว่าง"
            top_qty = 0

        name_label = MDLabel(
            text=top_name,
            halign="center",
            valign="middle",
            theme_text_color="Primary",
            bold=True,
            size_hint_y=None,
            height=dp(50),
            text_size=(dp(156), None),
            max_lines=2,
            shorten=True,
            shorten_from="right",
        )
        remain_label = MDLabel(
            text=f"คงเหลือ {top_qty} หน่วย",
            halign="center",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(18),
        )

        bottom_row = MDBoxLayout(size_hint_y=None, height=dp(24))
        bottom_row.add_widget(MDLabel(text="ความจุ", theme_text_color="Secondary"))
        bottom_row.add_widget(
            MDLabel(
                text=f"{current_qty}/{capacity}",
                halign="right",
                bold=True,
                theme_text_color="Primary",
            )
        )

        status_badge = MDLabel(
            text=status_text,
            halign="right",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(18),
        )

        self.add_widget(header)
        self.add_widget(name_label)
        self.add_widget(remain_label)
        self.add_widget(bottom_row)
        self.add_widget(status_badge)

        if can_select:
            self.bind(on_release=lambda *_: self.on_select(slot_info))
        else:
            self.disabled = True


class RestockScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cart_items = []
        self.selected_medicine = None
        self.selected_slot = None

        self.add_dialog = None
        self.slot_dialog = None
        self.quantity_input = None
        self.lot_id_input = None
        self.expired_at_input = None
        self.slot_button = None
        self.slot_info_label = None

        # เริ่มต้นเป็น list ว่าง จะดึงจาก API ทีหลัง
        self.medicines = []
        self.slots_data = []

    def on_kv_post(self, base_widget):
        # โหลดข้อมูลจาก API
        self.load_data_from_api()
        self.render_medicine_rows()
        self.refresh_cart_view()

    def on_pre_enter(self, *args):
        """รีเฟรชข้อมูลทุกครั้งก่อนเข้าหน้า restock"""
        self.load_data_from_api()
        self.render_medicine_rows()
        return super().on_pre_enter(*args)

    def go_home(self):
        app = MDApp.get_running_app()
        if app and hasattr(app, "change_screen"):
            app.change_screen("home_screen")

    def load_qr_task(self, task_payload):
        """เติมตะกร้าอัตโนมัติจาก QR task"""
        self.cart_items.clear()
        self.load_data_from_api()

        items = task_payload.get("items", []) if isinstance(task_payload, dict) else []
        if not isinstance(items, list):
            items = []

        medicine_by_id = {m["id"]: m for m in self.medicines}
        slot_by_server_id = {s.get("slot_id_from_server"): s for s in self.slots_data}

        for item in items:
            try:
                product_id = item.get("product_id")
                slot_id = int(item.get("slot_id"))
                qty = int(item.get("amount") or 0)
            except Exception:
                continue

            if qty <= 0:
                continue

            medicine = medicine_by_id.get(product_id) or {
                "id": product_id,
                "name": item.get("product_name") or product_id,
            }
            slot_info = slot_by_server_id.get(slot_id)
            if not slot_info:
                continue

            lot_id = item.get("lot_id") or ""
            expired_at = item.get("expired_at") or ""

            self._append_cart_item(
                medicine,
                slot_id,
                slot_info.get("slot"),
                qty,
                lot_id,
                expired_at,
            )
            self._apply_slot_restock(medicine, slot_info, qty)

        self.refresh_cart_view()
        self.render_medicine_rows()

    def load_data_from_api(self):
        """ดึงข้อมูลยาและช่องจาก API"""
        try:
            # ดึงข้อมูลยา (products)
            products_response = requests.get(f"{API_BASE_URL}/products", timeout=5)
            if products_response.status_code == 200:
                products_data = products_response.json()
                self.medicines = [
                    {
                        "id": product["product_id"],
                        "name": product["product_name"] or "ไม่ระบุชื่อ"
                    }
                    for product in products_data
                ]
            else:
                toast(f"ไม่สามารถดึงข้อมูลยาได้: {products_response.status_code}")
                
            # ดึงข้อมูลช่อง (slots with stocks)
            slots_response = requests.get(f"{API_BASE_URL}/slots", timeout=5)
            if slots_response.status_code == 200:
                slots_data = slots_response.json()
                self.slots_data = []
                
                for slot in slots_data:
                    # แปลงข้อมูล stocks ให้อยู่ในรูปแบบที่ UI ใช้
                    products_in_slot = []
                    for stock in slot.get("stocks", []):
                        product = stock.get("product", {})
                        products_in_slot.append({
                            "id": product.get("product_id", ""),
                            "name": product.get("product_name", "ไม่ระบุชื่อ"),
                            "qty": stock.get("amount", 0)
                        })
                    
                    self.slots_data.append({
                        "slot": slot["slot_id"],
                        "slot_id_from_server": slot.get("slot_id_from_server"),
                        "capacity": slot.get("capacity", 50),
                        "products": products_in_slot
                    })
                
            else:
                toast(f"ไม่สามารถดึงข้อมูลช่องได้: {slots_response.status_code}")
                
        except requests.RequestException as e:
            toast(f"ข้อผิดพลาดในการเชื่อมต่อ API: {str(e)}")
            print(f"API Error: {e}")
            
            # ใช้ข้อมูล fallback หาก API ไม่ทำงาน
            self.medicines = [
                {"id": "MED001", "name": "พาราเซตามอล 500mg"},
                {"id": "MED002", "name": "แอสไพริน 100mg"},
            ]
            self.slots_data = [
                {"slot": 1, "slot_id_from_server": 1, "capacity": 50, "products": []},
                {"slot": 2, "slot_id_from_server": 3, "capacity": 50, "products": []},
            ]

    def render_medicine_rows(self):
        self.ids.medicine_rows.clear_widgets()
        for medicine in self.medicines:
            row = RestockMedicineRowWidget(
                med_id=medicine["id"],
                med_name=medicine["name"],
                select_callback=lambda med=medicine: self.open_add_dialog(med),
            )
            self.ids.medicine_rows.add_widget(row)

    def _apply_thai_to_theme(self):
        """
        บังคับให้ทุก Font Style ของ KivyMD (H1-H6, Body, Button, etc.)
        เปลี่ยนมาใช้ Font 'Thai' ที่เราลงทะเบียนไว้
        """
        app = MDApp.get_running_app()
        # รายชื่อสไตล์ทั้งหมดที่ KivyMD ใช้งาน
        font_styles = [
            "H1", "H2", "H3", "H4", "H5", "H6", 
            "Subtitle1", "Subtitle2", "Body1", "Body2", 
            "Button", "Caption", "Overline"
        ]
        
        for style in font_styles:
            # เปลี่ยนชื่อ Font ใน List ของแต่ละ Style (ตำแหน่งที่ 0 คือชื่อ Font)
            if style in app.theme_cls.font_styles:
                app.theme_cls.font_styles[style][0] = "Thai"

    def open_add_dialog(self, medicine):
        self.selected_medicine = medicine
        self.selected_slot = None

        self._apply_thai_to_theme()

        self.quantity_input = MDTextField(
            hint_text="จำนวน",
            text="1",
            input_filter="int",
            mode="fill",
            fill_color_normal=(1, 1, 1, 1),
            line_color_normal=(0.5, 0.5, 0.5, 0.5),
            helper_text_mode="on_error",
        )

        self.lot_id_input = MDTextField(
            hint_text="LOT ID",
            mode="fill",
            fill_color_normal=(1, 1, 1, 1),
            line_color_normal=(0.5, 0.5, 0.5, 0.5),
            helper_text_mode="on_error",
            multiline=False,
        )

        self.expired_at_input = MDTextField(
            hint_text="(YYYY-MM-DD)",
            mode="fill",
            fill_color_normal=(1, 1, 1, 1),
            line_color_normal=(0.5, 0.5, 0.5, 0.5),
            helper_text_mode="on_error",
            multiline=False,
            readonly=True,
        )
        
        # ปุ่มเปิด date picker
        date_picker_btn = MDIconButton(
            icon="calendar",
            size_hint=(None, None),
            size=(dp(48), dp(48)),
            on_release=lambda *_: self.open_date_picker(),
        )

        self.slot_button = MDFlatButton(
            text="คลิกเพื่อเลือกช่อง",
            on_release=lambda *_: self.open_slot_picker_dialog(),
        )

        self.slot_info_label = MDLabel(
            text="",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(22),
        )

        detail_card = MDCard(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(8),
            radius=[12],
            elevation=1,
            md_bg_color=(0.93, 0.96, 1, 1),
            size_hint_y=None,
            height=dp(160),
        )
        detail_card.add_widget(MDLabel(text="รหัสยา", theme_text_color="Secondary"))
        detail_card.add_widget(MDLabel(text=medicine["id"], bold=True, size_hint_y=None, height=dp(36)))
        detail_card.add_widget(MDLabel(text="ชื่อยา", theme_text_color="Secondary"))
        detail_card.add_widget(MDLabel(text=medicine["name"], bold=True))

        select_slot_card = MDCard(
            orientation="horizontal",
            padding=[dp(12), dp(8), dp(12), dp(8)],
            radius=[10],
            size_hint_y=None,
            height=dp(56),
            elevation=0,
            line_color=(0.82, 0.84, 0.88, 1),
            line_width=1,
        )
        
        icon_container = MDCard(
            size_hint=(None, None),
            size=(dp(40), dp(40)),
            radius=[8],
            elevation=0,
            md_bg_color=(0.93, 0.94, 0.95, 1),
        )
        
        icon_layout = MDRelativeLayout()
        icon_layout.add_widget(
            MDIcon(
                icon="package-variant-closed",
                halign="center",
                valign="middle",
                theme_text_color="Secondary",
                pos_hint={"center_x": 0.5, "center_y": 0.5},
            )
        )
        
        icon_container.add_widget(icon_layout)
        
        select_slot_card.add_widget(icon_container)
        select_slot_card.add_widget(self.slot_button)

        row1 = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(12),
            size_hint_y=None,
            height=dp(78),
        )
        row1_left = MDBoxLayout(
            orientation="vertical",
            spacing=dp(6),
        )
        row1_left.add_widget(MDLabel(text="จำนวนที่ต้องการเติม", size_hint_y=None, height=dp(20)))
        row1_left.add_widget(self.quantity_input)
        row1_right = MDBoxLayout(
            orientation="vertical",
            spacing=dp(6),
        )
        row1_right.add_widget(MDLabel(text="LOT ID", size_hint_y=None, height=dp(20)))
        row1_right.add_widget(self.lot_id_input)
        row1.add_widget(row1_left)
        row1.add_widget(row1_right)

        row2 = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(12),
            size_hint_y=None,
            height=dp(92),
        )
        row2_left = MDBoxLayout(
            orientation="vertical",
            spacing=dp(6),
        )
        row2_left.add_widget(MDLabel(text="วันหมดอายุ", size_hint_y=None, height=dp(20)))
        
        # Container สำหรับ TextField + ปุ่มปฏิทิน
        date_input_container = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(8),
        )
        date_input_container.add_widget(self.expired_at_input)
        date_input_container.add_widget(date_picker_btn)
        
        row2_left.add_widget(date_input_container)
        row2_right = MDBoxLayout(
            orientation="vertical",
            spacing=dp(6),
        )
        row2_right.add_widget(MDLabel(text="เลือกช่องที่จะเก็บ", size_hint_y=None, height=dp(20)))
        row2_right.add_widget(select_slot_card)
        row2.add_widget(row2_left)
        row2.add_widget(row2_right)

        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(20),
            size_hint_y=None,
        )
        content.bind(minimum_height=content.setter("height"))
        content.add_widget(MDLabel(text="กรุณาระบุจำนวนและเลือกช่องที่ต้องการเก็บยา", theme_text_color="Secondary", font_style="Subtitle2"))
        content.add_widget(detail_card)
        content.add_widget(MDBoxLayout(size_hint_y=None, height=dp(4)))
        content.add_widget(row1)
        content.add_widget(row2)
        content.add_widget(self.slot_info_label)

        self.add_dialog = MDDialog(
            title="เพิ่มยาเข้าตู้เก็บ",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="ยกเลิก", on_release=lambda *_: self.add_dialog.dismiss()),
                MDFlatButton(text="เพิ่มเข้าตะกร้า", on_release=lambda *_: self.add_to_cart_from_dialog()),
            ],
        )
        self.add_dialog.open()

    def open_slot_picker_dialog(self):
        grid = GridLayout(cols=3, spacing=dp(12), padding=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        for slot in self.slots_data:
            card = SlotSelectCard(slot, on_select=self.on_slot_chosen)
            grid.add_widget(card)

        scroll = ScrollView(
            do_scroll_x=False,
            size_hint_y=1,
        )
        scroll.add_widget(grid)

        # Inner legend box with fixed width for compact grouping
        legend_inner = MDBoxLayout(
            size_hint=(None, None),
            size=(dp(450), dp(30)),
            spacing=dp(16),
        )
        
        # ช่องว่าง (สีเขียว)
        empty_box = MDBoxLayout(spacing=dp(8), size_hint_x=None, width=dp(120))
        empty_indicator = MDCard(
            size_hint=(None, None),
            size=(dp(20), dp(20)),
            radius=[dp(10)],
            md_bg_color=(0.11, 0.77, 0.36, 1),
            elevation=0,
        )
        empty_box.add_widget(empty_indicator)
        empty_box.add_widget(MDLabel(text="ช่องว่าง", theme_text_color="Secondary", size_hint_y=None, height=dp(20), valign="middle"))
        
        # มียาบางส่วน (สีส้ม)
        partial_box = MDBoxLayout(spacing=dp(8), size_hint_x=None, width=dp(140))
        partial_indicator = MDCard(
            size_hint=(None, None),
            size=(dp(20), dp(20)),
            radius=[dp(10)],
            md_bg_color=(0.94, 0.66, 0.05, 1),
            elevation=0,
        )
        partial_box.add_widget(partial_indicator)
        partial_box.add_widget(MDLabel(text="มียาบางส่วน", theme_text_color="Secondary", size_hint_y=None, height=dp(20), valign="middle"))
        
        # เต็ม (สีแดง)
        full_box = MDBoxLayout(spacing=dp(8), size_hint_x=None, width=dp(80))
        full_indicator = MDCard(
            size_hint=(None, None),
            size=(dp(20), dp(20)),
            radius=[dp(10)],
            md_bg_color=(0.95, 0.24, 0.24, 1),
            elevation=0,
        )
        full_box.add_widget(full_indicator)
        full_box.add_widget(MDLabel(text="เต็ม", theme_text_color="Secondary", size_hint_y=None, height=dp(20), valign="middle"))
        
        legend_inner.add_widget(empty_box)
        legend_inner.add_widget(partial_box)
        legend_inner.add_widget(full_box)
        
        # Outer wrapper to center the legend group
        legend = MDBoxLayout(
            size_hint_y=None,
            height=dp(30),
        )
        legend.add_widget(MDLabel())  # Left spacer
        legend.add_widget(legend_inner)
        legend.add_widget(MDLabel())  # Right spacer

        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            size_hint=(None, None),
            size=(dp(640), dp(440)),
        )
        content.add_widget(MDLabel(text="คลิกที่ช่องเพื่อเลือกตำแหน่งที่ต้องการเติมยา", theme_text_color="Secondary", size_hint_y=None, height=dp(22)))
        content.add_widget(scroll)
        content.add_widget(legend)

        self.slot_dialog = MDDialog(
            title="เลือกช่องเก็บยา",
            type="custom",
            content_cls=content,
            size_hint=(None, None),
            width=dp(640),
            buttons=[MDFlatButton(text="ปิด", on_release=lambda *_: self.slot_dialog.dismiss())],
        )
        self.slot_dialog.open()

    def on_slot_chosen(self, slot_info):
        self.selected_slot = slot_info
        if self.slot_dialog:
            self.slot_dialog.dismiss()

        current_qty = sum(p["qty"] for p in slot_info["products"])
        capacity = slot_info["capacity"]
        self.slot_button.text = f"ช่องที่ {slot_info['slot']}  ({current_qty}/{capacity} หน่วย)"

        if slot_info["products"]:
            product_text = ", ".join([f"{p['name']} {p['qty']}mg" if "mg" not in p['name'] else p['name'] for p in slot_info["products"]])
            self.slot_info_label.text = f"ยาที่มีอยู่: {product_text}"
            self.slot_info_label.theme_text_color = "Custom"
            self.slot_info_label.text_color = (0.75, 0.45, 0.05, 1)
        else:
            self.slot_info_label.text = ""

    def open_date_picker(self):
        """เปิด date picker สำหรับเลือกวันหมดอายุ"""
        date_dialog = MDDatePicker()
        date_dialog.bind(on_save=self.on_date_selected, on_cancel=self.on_date_cancel)
        date_dialog.open()

    def on_date_selected(self, instance, value, date_range):
        """เมื่อเลือกวันที่แล้ว นำมาใส่ใน TextField"""
        self.expired_at_input.text = value.strftime("%Y-%m-%d")
        self.expired_at_input.error = False
        self.expired_at_input.helper_text = ""

    def on_date_cancel(self, instance, value):
        """เมื่อยกเลิกการเลือกวันที่"""
        pass

    def add_to_cart_from_dialog(self):
        if not self.selected_medicine:
            return

        if not self.selected_slot:
            toast("กรุณาเลือกช่องที่จะเก็บ")
            return

        try:
            quantity = int(self.quantity_input.text.strip())
        except ValueError:
            self.quantity_input.error = True
            self.quantity_input.helper_text = "จำนวนไม่ถูกต้อง"
            return

        lot_id = self.lot_id_input.text.strip()
        if not lot_id:
            self.lot_id_input.error = True
            self.lot_id_input.helper_text = "กรุณากรอก LOT ID"
            return
        self.lot_id_input.error = False
        self.lot_id_input.helper_text = ""

        expired_at_text = self.expired_at_input.text.strip()
        if not expired_at_text:
            self.expired_at_input.error = True
            self.expired_at_input.helper_text = "กรุณากรอกวันหมดอายุ"
            return

        try:
            datetime.strptime(expired_at_text, "%Y-%m-%d")
        except ValueError:
            self.expired_at_input.error = True
            self.expired_at_input.helper_text = "รูปแบบวันที่ต้องเป็น YYYY-MM-DD"
            return

        self.expired_at_input.error = False
        self.expired_at_input.helper_text = ""

        if quantity <= 0:
            self.quantity_input.error = True
            self.quantity_input.helper_text = "จำนวนต้องมากกว่า 0"
            return

        used = sum(p["qty"] for p in self.selected_slot["products"])
        available = self.selected_slot["capacity"] - used
        if quantity > available:
            self.quantity_input.error = True
            self.quantity_input.helper_text = f"เกินพื้นที่ว่าง (เติมได้สูงสุด {available})"
            return

        slot_id = self.selected_slot.get("slot_id_from_server")
        slot_label = self.selected_slot.get("slot")

        print(f"slot_id: {slot_id}")

        self._append_cart_item(
            self.selected_medicine,
            slot_id,
            slot_label,
            quantity,
            lot_id,
            expired_at_text,
        )
        self._apply_slot_restock(self.selected_medicine, self.selected_slot, quantity)

        self.refresh_cart_view()

        if self.add_dialog:
            self.add_dialog.dismiss()

    def _append_cart_item(self, medicine, slot_id, slot_label, quantity, lot_id, expired_at):
        self.cart_items.append(
            {
                "id": medicine["id"],
                "name": medicine["name"],
                "slot_id": slot_id,
                "slot_label": slot_label,
                "quantity": quantity,
                "lot_id": lot_id,
                "expired_at": expired_at,
                "created_at": datetime.utcnow().isoformat(),
            }
        )

    def _apply_slot_restock(self, medicine, slot_info, quantity):
        for product in slot_info["products"]:
            if product["id"] == medicine["id"]:
                product["qty"] += quantity
                return
        slot_info["products"].append({"id": medicine["id"], "name": medicine["name"], "qty": quantity})

    def remove_cart_item(self, cart_item, cart_widget=None):
        """ลบรายการออกจากตะกร้า"""
        if not isinstance(cart_item, dict):
            print(f"Warning: Invalid cart item payload: {cart_item}")
            return

        removed_item = None

        # จับคู่ด้วย created_at ก่อน (แม่นยำที่สุด)
        created_at = cart_item.get("created_at")
        if created_at:
            for i, item in enumerate(self.cart_items):
                if item.get("created_at") == created_at:
                    removed_item = self.cart_items.pop(i)
                    break

        # fallback: จับคู่ด้วยข้อมูลหลัก
        if removed_item is None:
            for i, item in enumerate(self.cart_items):
                if (
                    item.get("id") == cart_item.get("id")
                    and item.get("slot_id") == cart_item.get("slot_id")
                    and item.get("quantity") == cart_item.get("quantity")
                ):
                    removed_item = self.cart_items.pop(i)
                    break

        if removed_item is None:
            print(f"Warning: Item not found in cart: {cart_item}")
            return

        self._revert_slot_restock(removed_item)

        if cart_widget is not None and getattr(cart_widget, "parent", None):
            self.ids.cart_list.remove_widget(cart_widget)
            self._update_cart_summary_ui()
        else:
            self.refresh_cart_view()

    def _revert_slot_restock(self, cart_item):
        for slot in self.slots_data:
            if slot["slot"] != cart_item["slot_label"]:
                continue
            for product in slot["products"]:
                if product["id"] == cart_item["id"]:
                    product["qty"] -= cart_item["quantity"]
                    if product["qty"] <= 0:
                        slot["products"].remove(product)
                    return

    def refresh_cart_view(self):
        self.ids.cart_list.clear_widgets()

        for item in self.cart_items:
            widget = RestockCartItemWidget(
                product_name=item["name"],
                product_id=item["id"],
                slot=f"ช่อง {item['slot_label']}",
                quantity=str(item["quantity"]),
                lot_id=item.get("lot_id", ""),
                expired_at=item.get("expired_at", ""),
                delete_callback=None,
            )
            widget.delete_callback = lambda selected_item=item, selected_widget=widget: self.remove_cart_item(selected_item, selected_widget)
            self.ids.cart_list.add_widget(widget)

        self._update_cart_summary_ui()

    def _update_cart_summary_ui(self):
        item_count = len(self.cart_items)
        total_units = sum(item["quantity"] for item in self.cart_items)

        self.ids.cart_count_badge.text = f"{item_count} รายการ"
        self.ids.total_units_label.text = f"{total_units} หน่วย"
        
        # สลับการแสดงผลระหว่าง empty state และรายการยา
        if item_count > 0:
            self.ids.cart_empty_state.opacity = 0
            self.ids.cart_empty_state.size_hint = (None, None)
            self.ids.cart_empty_state.size = (0, 0)
            self.ids.cart_scroll.opacity = 1
        else:
            self.ids.cart_empty_state.opacity = 1
            self.ids.cart_empty_state.size_hint = (1, 1)
            self.ids.cart_scroll.opacity = 0
        
        # อัปเดตสถานะปุ่มยืนยัน
        btn_confirm = self.ids.btn_confirm_restock
        if item_count > 0:
            btn_confirm.disabled = False
            btn_confirm.md_bg_color = (0.12, 0.16, 0.23, 1)
        else:
            btn_confirm.disabled = True
            btn_confirm.md_bg_color = (0.7, 0.7, 0.7, 1)

    def confirm_selection(self):
        """ยืนยันการเติมยาและบันทึกข้อมูล"""
        if not self.cart_items:
            toast("ตะกร้าว่างเปล่า")
            return

        # ตรวจสอบว่าทุกรายการมีข้อมูลครบถ้วน
        for item in self.cart_items:
            if not item.get("lot_id"):
                toast(f"รายการ {item['name']} ยังไม่มี LOT ID")
                return
            if not item.get("expired_at"):
                toast(f"รายการ {item['name']} ยังไม่มีวันหมดอายุ")
                return

        # แสดง dialog ยืนยันก่อนทำรายการ
        total_items = len(self.cart_items)
        total_units = sum(item["quantity"] for item in self.cart_items)
        
        confirm_dialog = MDDialog(
            title="ยืนยันการเติมยา",
            text=f"คุณต้องการเติมยาจำนวน {total_items} รายการ ({total_units} หน่วย) ใช่หรือไม่?",
            buttons=[
                MDFlatButton(
                    text="ยกเลิก",
                    on_release=lambda *_: confirm_dialog.dismiss()
                ),
                MDFlatButton(
                    text="ยืนยัน",
                    on_release=lambda *_: self.process_restock(confirm_dialog)
                ),
            ],
        )
        confirm_dialog.open()

    def process_restock(self, dialog):
        """ดำเนินการเติมยาจริง"""
        dialog.dismiss()

        app = MDApp.get_running_app()
        user_id = getattr(app, "user_id", "").strip() if app else ""

        if not user_id:
            toast("ไม่พบข้อมูลผู้ใช้ กรุณาเข้าสู่ระบบใหม่")
            return

        payload = {
            "user_id": user_id,
            "items": [
                {
                    "product_id": item["id"],
                    "slot_id": item["slot_id"],
                    "amount": item["quantity"],
                    "lot_id": item["lot_id"],
                    "expired_at": item["expired_at"],
                }
                for item in self.cart_items
            ],
        }

        try:
            restock_response = requests.post(
                f"{API_BASE_URL}/restock",
                json=payload,
                timeout=10,
            )

            if restock_response.status_code != 200:
                detail_message = ""
                try:
                    detail_message = restock_response.json().get("detail", "")
                except ValueError:
                    detail_message = restock_response.text
                toast(f"เกิดข้อผิดพลาด: {detail_message or restock_response.status_code}")
                return

        except requests.RequestException as e:
            toast(f"ข้อผิดพลาด: {str(e)}")
            return

        # ล้างตะกร้าและโหลดข้อมูลใหม่
        self.cart_items.clear()
        self.load_data_from_api()  # รีโหลดข้อมูลจาก API
        self.refresh_cart_view()
        self.render_medicine_rows()
        if app and hasattr(app, "complete_active_qr_task"):
            app.complete_active_qr_task()
        toast("บันทึกการเติมยาสำเร็จ")