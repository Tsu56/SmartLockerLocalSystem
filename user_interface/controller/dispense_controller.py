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
from kivymd.uix.menu import MDDropdownMenu
import requests

# URL ของ API Gateway
API_BASE_URL = "http://localhost:5000/api/product/locker"


class DispenseMedicineRowWidget(MDBoxLayout):
    med_id = StringProperty("")
    med_name = StringProperty("")
    select_callback = ObjectProperty(None)


class DispenseCartItemWidget(MDBoxLayout):
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
    def __init__(self, slot_info, on_select, filter_product_id=None, **kwargs):
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

        # 👉 1. กรองหา active_products เพื่อดูว่า "ปัจจุบันช่องนี้มียาอะไรวางอยู่จริงๆ"
        active_products = [p for p in slot_info["products"] if p["qty"] > 0]
        if active_products:
            default_top_name = active_products[0]["name"]
            default_top_qty = active_products[0]["qty"]
        else:
            default_top_name = "ว่าง"
            default_top_qty = 0

        # ถ้าระบุ filter_product_id → เช็คว่าช่องนี้มียาที่ต้องการเบิกหรือไม่
        if filter_product_id is not None:
            product_in_slot = next(
                (p for p in slot_info["products"] if p["id"] == filter_product_id),
                None
            )
            if product_in_slot and product_in_slot["qty"] > 0:
                border_color = (0.11, 0.77, 0.36, 1)
                card_bg = (0.93, 0.99, 0.95, 1)
                status_text = f"พร้อมเบิก"
                can_select = True
                top_name = product_in_slot["name"]
                top_qty = product_in_slot["qty"]
            else:
                border_color = (0.8, 0.8, 0.8, 1)
                card_bg = (0.93, 0.93, 0.93, 1)
                status_text = "ไม่มียานี้"
                can_select = False
                # 👉 2. แสดงชื่อและจำนวนยาตัวอื่น ที่กำลังยึดพื้นที่ช่องนี้อยู่แทน
                top_name = default_top_name
                top_qty = default_top_qty
        else:
            if current_qty == 0:
                border_color = (0.11, 0.77, 0.36, 1)
                card_bg = (0.93, 0.99, 0.95, 1)
                status_text = "ว่าง"
                can_select = True
            elif current_qty >= capacity:
                border_color = (0.95, 0.24, 0.24, 1)
                card_bg = (1, 0.95, 0.95, 1)
                status_text = "เต็ม"
                can_select = False
            else:
                border_color = (0.94, 0.66, 0.05, 1)
                card_bg = (1, 0.98, 0.90, 1)
                status_text = "มียาบางส่วน"
                can_select = True

            top_name = default_top_name
            top_qty = default_top_qty

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


class DispenseScreen(MDScreen):
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
        self.selected_lot = None
        self._lot_expired_label = None
        self._lot_menu = None

        # เริ่มต้นเป็น list ว่าง จะดึงจาก API ทีหลัง
        self.medicines = []
        self.slots_data = []

    def on_kv_post(self, base_widget):
        # โหลดข้อมูลจาก API
        self.load_data_from_api()
        self.render_medicine_rows()
        self.refresh_cart_view()

    def on_pre_enter(self, *args):
        """รีเฟรชข้อมูลทุกครั้งก่อนเข้าหน้า dispense"""
        self.load_data_from_api()
        self.render_medicine_rows()
        return super().on_pre_enter(*args)

    def go_home(self):
        app = MDApp.get_running_app()
        if app and hasattr(app, "change_screen"):
            app.change_screen("home_screen")

    def _resolve_slot_stock_id(self, slot_info, product_id, lot_id, fallback_slot_stock_id=None):
        """หา slot_stock_id ของ local จาก lot_id ภายใน slot เดียวกัน"""
        if fallback_slot_stock_id not in (None, ""):
            return fallback_slot_stock_id

        if not isinstance(slot_info, dict):
            return None

        for product in slot_info.get("products", []):
            if product.get("id") != product_id:
                continue
            for lot in product.get("lots", []):
                if str(lot.get("lot_id") or "") == str(lot_id or ""):
                    return lot.get("slot_stock_id")

        return None

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
            slot_stock_id = self._resolve_slot_stock_id(
                slot_info,
                product_id,
                lot_id,
                None,
            )

            self._append_cart_item(
                medicine,
                slot_id,
                slot_info.get("slot"),
                qty,
                lot_id,
                expired_at,
                slot_stock_id,
            )
            self._apply_slot_dispense(medicine, slot_info, qty)

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
                    # จัดกลุ่มตาม product_id เพื่อให้รู้ lot ทั้งหมดต่อยา
                    products_by_id = {}
                    for stock in slot.get("stocks", []):
                        product = stock.get("product", {})
                        pid = product.get("product_id", "")
                        lot_entry = {
                            "slot_stock_id": stock.get("slot_stock_id"),
                            "lot_id": stock.get("lot_id", ""),
                            "qty": stock.get("amount", 0),
                            "expired_at": stock.get("expired_at", ""),
                        }
                        if pid not in products_by_id:
                            products_by_id[pid] = {
                                "id": pid,
                                "name": product.get("product_name", "ไม่ระบุชื่อ"),
                                "qty": 0,
                                "lots": [],
                            }
                        products_by_id[pid]["qty"] += lot_entry["qty"]
                        products_by_id[pid]["lots"].append(lot_entry)

                    self.slots_data.append({
                        "slot": slot["slot_id"],
                        "slot_id_from_server": slot.get("slot_id_from_server"),
                        "capacity": slot.get("capacity", 50),
                        "products": list(products_by_id.values()),
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
            row = DispenseMedicineRowWidget(
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
        """กดเลือกยา → เปิด dialog เลือกช่องทันที"""
        self.selected_medicine = medicine
        self.selected_slot = None
        self._apply_thai_to_theme()
        self.open_slot_picker_dialog()

    def _open_add_detail_dialog(self):
        """เปิด dialog กรอกรายละเอียด หลังจากเลือกช่องแล้ว"""
        medicine = self.selected_medicine
        slot_info = self.selected_slot
        self.selected_lot = None
        self._lot_expired_label = None
        self._lot_menu = None

        # หา lots ของยาตัวนี้ในช่องที่เลือก (qty > 0 เท่านั้น)
        product_in_slot = next(
            (p for p in slot_info["products"] if p["id"] == medicine["id"]), None
        )
        lots = [lot for lot in (product_in_slot.get("lots", []) if product_in_slot else []) if lot["qty"] > 0]
        available_qty = product_in_slot["qty"] if product_in_slot else 0

        # --- Quantity input (fixed width) ---
        self.quantity_input = MDTextField(
            text="1",
            input_filter="int",
            mode="fill",
            fill_color_normal=(1, 1, 1, 1),
            line_color_normal=(0.5, 0.5, 0.5, 0.5),
            helper_text_mode="on_error",
            size_hint_x=None,
            width=dp(140),
        )

        # --- Medicine info card (with mutable expiry label) ---
        self._lot_expired_label = MDLabel(
            text="วันหมดอายุ: —",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(24),
        )
        detail_card = MDCard(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(6),
            radius=[12],
            elevation=1,
            md_bg_color=(0.93, 0.96, 1, 1),
            size_hint_y=None,
            height=dp(120),
        )
        detail_card.add_widget(MDLabel(text=medicine["id"], bold=True, size_hint_y=None, height=dp(24)))
        detail_card.add_widget(MDLabel(text=medicine["name"], size_hint_y=None, height=dp(24)))
        detail_card.add_widget(self._lot_expired_label)

        # --- Slot info card ---
        current_qty = sum(p["qty"] for p in slot_info["products"])
        slot_card = MDCard(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(4),
            radius=[12],
            elevation=1,
            md_bg_color=(0.93, 0.99, 0.95, 1),
            size_hint_y=None,
            height=dp(56),
        )
        slot_card.add_widget(MDLabel(
            text=f"ช่องที่ {slot_info['slot']}  —  มียานี้: {available_qty} หน่วย",
            bold=True,
            theme_text_color="Primary",
            size_hint_y=None,
            height=dp(28),
        ))

        # --- Lot selector card (looks like a filled TextField) ---
        lot_btn_label = MDLabel(
            text="เลือก LOT",
            theme_text_color="Hint",
            valign="middle",
            halign="left",
        )
        lot_btn = MDCard(
            orientation="horizontal",
            padding=[dp(12), 0, dp(8), 0],
            spacing=dp(4),
            radius=[dp(4)],
            elevation=0,
            md_bg_color=(0.95, 0.95, 0.95, 1),
            size_hint=(None, None),
            width=dp(220),
            height=dp(52),
            ripple_behavior=True,
        )
        lot_btn.add_widget(lot_btn_label)
        icon_wrap = MDBoxLayout(
            size_hint=(None, 1),
            width=dp(24),
        )
        icon_wrap.add_widget(MDIcon(
            icon="chevron-down",
            theme_text_color="Secondary",
            halign="center",
            valign="middle",
            pos_hint={"center_y": 0.5},
        ))
        lot_btn.add_widget(icon_wrap)

        def open_lot_menu(*_):
            if not lots:
                toast("ไม่พบ LOT ของยานี้ในช่องที่เลือก")
                return
            menu_items = [
                {
                    "text": f"LOT: {lot['lot_id']}  ({lot['qty']} หน่วย)",
                    "viewclass": "OneLineListItem",
                    "on_release": (lambda l=lot: _pick_lot(l)),
                }
                for lot in lots
            ]
            self._lot_menu = MDDropdownMenu(
                caller=lot_btn,
                items=menu_items,
                width_mult=4,
            )
            self._lot_menu.open()

        def _pick_lot(lot):
            self.selected_lot = lot
            lot_btn_label.text = f"LOT: {lot['lot_id']}  ({lot['qty']} หน่วย)"
            lot_btn_label.theme_text_color = "Primary"
            exp = lot.get("expired_at") or "—"
            self._lot_expired_label.text = f"วันหมดอายุ: {exp}"
            if self._lot_menu:
                self._lot_menu.dismiss()

        lot_btn.bind(on_release=open_lot_menu)

        # --- Layout rows ---
        label_row = MDBoxLayout(orientation="horizontal", spacing=dp(12), size_hint_y=None, height=dp(20))
        label_row.add_widget(MDLabel(text="จำนวนที่ต้องการเบิก", size_hint_x=None, width=dp(140)))
        label_row.add_widget(MDLabel(text="LOT ID", size_hint_x=None, width=dp(220)))

        input_row = MDBoxLayout(orientation="horizontal", spacing=dp(12), size_hint_y=None, height=dp(52))
        input_row.add_widget(self.quantity_input)
        input_row.add_widget(lot_btn)
        input_row.add_widget(MDLabel())

        row1 = MDBoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None, height=dp(78))
        row1.add_widget(label_row)
        row1.add_widget(input_row)

        content = MDBoxLayout(orientation="vertical", spacing=dp(14), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        content.add_widget(MDLabel(
            text="กรุณาระบุรายละเอียดการเบิกยา",
            theme_text_color="Secondary",
            font_style="Subtitle2",
            size_hint_y=None,
            height=dp(24),
        ))
        content.add_widget(detail_card)
        content.add_widget(slot_card)
        content.add_widget(MDBoxLayout(size_hint_y=None, height=dp(4)))
        content.add_widget(row1)

        self.add_dialog = MDDialog(
            title="รายละเอียดยาที่ต้องการเบิก",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="ย้อนกลับ", on_release=lambda *_: (self.add_dialog.dismiss(), self.open_slot_picker_dialog())),
                MDFlatButton(text="เพิ่มเข้าตะกร้า", on_release=lambda *_: self.add_to_cart_from_dialog()),
            ],
        )
        self.add_dialog.open()

    def open_slot_picker_dialog(self):
        filter_product_id = self.selected_medicine["id"] if self.selected_medicine else None

        grid = GridLayout(cols=3, spacing=dp(12), padding=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        for slot in self.slots_data:
            card = SlotSelectCard(slot, on_select=self.on_slot_chosen, filter_product_id=filter_product_id)
            grid.add_widget(card)

        scroll = ScrollView(do_scroll_x=False, size_hint_y=1)
        scroll.add_widget(grid)

        # Legend
        legend_inner = MDBoxLayout(size_hint=(None, None), size=(dp(340), dp(30)), spacing=dp(16))

        ready_box = MDBoxLayout(spacing=dp(8), size_hint_x=None, width=dp(140))
        ready_indicator = MDCard(size_hint=(None, None), size=(dp(20), dp(20)), radius=[dp(10)], md_bg_color=(0.11, 0.77, 0.36, 1), elevation=0)
        ready_box.add_widget(ready_indicator)
        ready_box.add_widget(MDLabel(text="พร้อมเบิก", theme_text_color="Secondary", size_hint_y=None, height=dp(20), valign="middle"))

        no_med_box = MDBoxLayout(spacing=dp(8), size_hint_x=None, width=dp(140))
        no_med_indicator = MDCard(size_hint=(None, None), size=(dp(20), dp(20)), radius=[dp(10)], md_bg_color=(0.8, 0.8, 0.8, 1), elevation=0)
        no_med_box.add_widget(no_med_indicator)
        no_med_box.add_widget(MDLabel(text="ไม่มียานี้", theme_text_color="Secondary", size_hint_y=None, height=dp(20), valign="middle"))

        legend_inner.add_widget(ready_box)
        legend_inner.add_widget(no_med_box)

        legend = MDBoxLayout(size_hint_y=None, height=dp(30))
        legend.add_widget(MDLabel())
        legend.add_widget(legend_inner)
        legend.add_widget(MDLabel())

        med_name = self.selected_medicine["name"] if self.selected_medicine else ""
        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            size_hint=(None, None),
            size=(dp(640), dp(440)),
        )
        content.add_widget(MDLabel(
            text=f"เลือกช่องที่มียา: {med_name}",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(22),
        ))
        content.add_widget(scroll)
        content.add_widget(legend)

        self.slot_dialog = MDDialog(
            title="เลือกช่องเบิกยา",
            type="custom",
            content_cls=content,
            size_hint=(None, None),
            width=dp(640),
            buttons=[MDFlatButton(text="ยกเลิก", on_release=lambda *_: self.slot_dialog.dismiss())],
        )
        self.slot_dialog.open()

    def on_slot_chosen(self, slot_info):
        self.selected_slot = slot_info
        if self.slot_dialog:
            self.slot_dialog.dismiss()
            
        # ในหน้าเบิกยา พอเลือกช่องเสร็จ ให้เปิดหน้าต่างกรอกรายละเอียด (Detail Dialog) ทันที
        self._open_add_detail_dialog()

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
            toast("กรุณาเลือกช่องที่จะเบิก")
            return

        if not self.selected_lot:
            toast("กรุณาเลือก LOT")
            return

        try:
            quantity = int(self.quantity_input.text.strip())
        except ValueError:
            self.quantity_input.error = True
            self.quantity_input.helper_text = "จำนวนไม่ถูกต้อง"
            return

        if quantity <= 0:
            self.quantity_input.error = True
            self.quantity_input.helper_text = "จำนวนต้องมากกว่า 0"
            return

        lot_qty = self.selected_lot["qty"]
        if quantity > lot_qty:
            self.quantity_input.error = True
            self.quantity_input.helper_text = f"LOT นี้มีแค่ {lot_qty} หน่วย"
            return
        self.quantity_input.error = False
        self.quantity_input.helper_text = ""

        lot_id = self.selected_lot["lot_id"]
        expired_at = str(self.selected_lot.get("expired_at") or "")
        slot_stock_id = self.selected_lot.get("slot_stock_id")
        slot_id = self.selected_slot.get("slot_id_from_server")
        slot_label = self.selected_slot.get("slot")

        self._append_cart_item(
            self.selected_medicine,
            slot_id,
            slot_label,
            quantity,
            lot_id,
            expired_at,
            slot_stock_id,
        )
        self._apply_slot_dispense(self.selected_medicine, self.selected_slot, quantity)
        self.refresh_cart_view()

        if self.add_dialog:
            self.add_dialog.dismiss()

    def _append_cart_item(self, medicine, slot_id, slot_label, quantity, lot_id, expired_at, slot_stock_id=None):
        self.cart_items.append(
            {
                "id": medicine["id"],
                "name": medicine["name"],
                "slot_id": slot_id,
                "slot_label": slot_label,
                "quantity": quantity,
                "lot_id": lot_id,
                "expired_at": expired_at,
                "slot_stock_id": slot_stock_id,
                "created_at": datetime.utcnow().isoformat(),
            }
        )

    def _apply_slot_dispense(self, medicine, slot_info, quantity):
        """ลดจำนวนสต็อกในช่องเมื่อเบิก"""
        for product in slot_info["products"]:
            if product["id"] == medicine["id"]:
                product["qty"] -= quantity
                if product["qty"] <= 0:
                    slot_info["products"].remove(product)
                return

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

        self._revert_slot_dispense(removed_item)

        if cart_widget is not None and getattr(cart_widget, "parent", None):
            self.ids.cart_list.remove_widget(cart_widget)
            self._update_cart_summary_ui()
        else:
            self.refresh_cart_view()

    def _revert_slot_dispense(self, cart_item):
        """คืนจำนวนเมื่อลบรายการออกจากตะกร้า"""
        for slot in self.slots_data:
            if slot["slot"] != cart_item["slot_label"]:
                continue
            for product in slot["products"]:
                if product["id"] == cart_item["id"]:
                    product["qty"] += cart_item["quantity"]
                    return
            # ถ้าไม่เจอ product ให้เพิ่มกลับเข้าไป
            slot["products"].append({
                "id": cart_item["id"],
                "name": cart_item["name"],
                "qty": cart_item["quantity"]
            })

    def refresh_cart_view(self):
        self.ids.cart_list.clear_widgets()

        for item in self.cart_items:
            widget = DispenseCartItemWidget(
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
        btn_confirm = self.ids.btn_confirm_dispense
        if item_count > 0:
            btn_confirm.disabled = False
            btn_confirm.md_bg_color = (0.12, 0.16, 0.23, 1)
        else:
            btn_confirm.disabled = True
            btn_confirm.md_bg_color = (0.7, 0.7, 0.7, 1)

    def confirm_selection(self):
        """ยืนยันการเบิกยาและบันทึกข้อมูล"""
        if not self.cart_items:
            toast("ตะกร้าว่างเปล่า")
            return

        # บังคับใช้ฟอนต์ Thai ก่อนสร้าง MDDialog เพื่อให้ title ภาษาไทยแสดงผลถูกต้อง
        self._apply_thai_to_theme()

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
            title="ยืนยันการเบิกยา",
            text=f"คุณต้องการเบิกยาจำนวน {total_items} รายการ ({total_units} หน่วย) ใช่หรือไม่?",
            buttons=[
                MDFlatButton(
                    text="ยกเลิก",
                    on_release=lambda *_: confirm_dialog.dismiss()
                ),
                MDFlatButton(
                    text="ยืนยัน",
                    on_release=lambda *_: self.process_dispense(confirm_dialog)
                ),
            ],
        )
        confirm_dialog.open()

    def process_dispense(self, dialog):
        """ดำเนินการเบิกยาจริง"""
        dialog.dismiss()

        app = MDApp.get_running_app()
        user_id = getattr(app, "user_id", "").strip() if app else ""

        if not user_id:
            toast("ไม่พบข้อมูลผู้ใช้ กรุณาเข้าสู่ระบบใหม่")
            return

        # 👉 1. สั่งบันทึกข้อมูลเข้า DB ก่อนเปิดตู้ เพื่อเอารหัส Transaction!
        success, result = self._save_transaction_to_api()
        if not success:
            toast(result) # ถ้าพังให้โชว์ error แล้วหยุดเลย
            return
            
        transaction_id = result # ดึงรหัสที่เพิ่งสร้างเสร็จมาเก็บไว้

        slots_to_open = list(set([f"S{item['slot_label']}" for item in self.cart_items]))
        slots_to_open.sort() 
        # 👉 2. โยน transaction_id ส่งต่อให้ระบบฮาร์ดแวร์
        self.start_hardware_queue(slots_to_open, transaction_id)

    def _save_transaction_to_api(self):
        """ยิง API เพื่อตัดสต็อก จะถูกเรียกจาก Background Thread (ไม่ทำให้จอค้าง)"""
        import requests
        app = MDApp.get_running_app()
        user_id = getattr(app, "user_id", "").strip() if app else ""

        transaction_payload = {
            "user_id": user_id,
            "activity": "dispense",
            "status": "success"
        }

        try:
            # 1. สร้าง Transaction
            transaction_response = requests.post(f"{API_BASE_URL}/transactions", json=transaction_payload, timeout=10)
            if transaction_response.status_code != 200:
                return False, "เกิดข้อผิดพลาดในการสร้าง Transaction"

            transaction_id = transaction_response.json().get("transaction_id")

            # 2. สร้าง Transaction Details (ตัดสต็อก)
            for item in self.cart_items:
                slot_info = next((s for s in self.slots_data if s.get("slot_id_from_server") == item.get("slot_id")), None)
                slot_stock_id = self._resolve_slot_stock_id(slot_info, item.get("id"), item.get("lot_id"), item.get("slot_stock_id"))

                if slot_stock_id in (None, ""): continue

                detail_payload = {
                    "transaction_id": transaction_id,
                    "product_id": item["id"],
                    "slot_id": item["slot_id"],
                    "slot_stock_id": slot_stock_id,
                    "amount": item["quantity"]
                }
                requests.post(f"{API_BASE_URL}/transactions/{transaction_id}/details", json=detail_payload, timeout=10)
            
            requests.post(f"{API_BASE_URL}/transactions/{transaction_id}/complete-sync", timeout=5)

            return True, transaction_id
        except Exception as e:
            return False, f"ข้อผิดพลาดจากเซิร์ฟเวอร์: {str(e)}"

    def start_hardware_queue(self, slots_queue, transaction_id):
        import threading
        
        # 1. สร้าง Dialog แจ้งสถานะผู้ใช้ (ห้ามกดปิดเอง)
        self.hw_dialog_label = MDLabel(
            text="กำลังเตรียมระบบฮาร์ดแวร์...", 
            halign="center", 
            theme_text_color="Primary",
            font_style="H6"
        )
        self.hw_dialog = MDDialog(
            title="กรุณาเปิดตู้และหยิบยาตามลำดับ",
            type="custom",
            content_cls=self.hw_dialog_label,
            auto_dismiss=False, 
        )
        self.hw_dialog.open()
        
        # 2. สั่ง Thread เบื้องหลังไปไล่เปิดทีละบาน
        threading.Thread(target=self._run_hardware_sequence, args=(slots_queue, transaction_id), daemon=True).start()

    def _run_hardware_sequence(self, slots_queue, transaction_id):
        import time
        import requests
        from kivy.clock import Clock
        from kivymd.app import MDApp
        
        HARDWARE_API = "http://localhost:8003/api/device/door"
        
        for slot in slots_queue:
            Clock.schedule_once(lambda dt, s=slot: setattr(
                self.hw_dialog_label, 
                'text', 
                f"⏳ กำลังเตรียมระบบตู้ {s}...\n(โปรดรอจนกว่าไฟสถานะสีเขียวจะสว่าง)"
            ), 0)
            
            try:
                requests.post(f"{HARDWARE_API}/open", json={"address": slot, "transaction_id": str(transaction_id)}, timeout=15)
            except Exception as e:
                print(f"⚠️ Error opening slot {slot}: {e}")
                
            # --- วนลูปรอจนกว่าตู้จะ "เปิด" ---
            door_opened = False
            wait_time = 0
            # ⏳ ให้เวลาผู้ใช้เดินไปเปิดตู้สูงสุด 60 วินาที
            while wait_time < 60.0:  
                try:
                    res = requests.get(f"{HARDWARE_API}/status/{slot}", timeout=2).json()
                    if res.get("status") == "OPEN":
                        door_opened = True
                        Clock.schedule_once(lambda dt, s=slot: setattr(self.hw_dialog_label, 'text', f"🔓 ตู้ {s} เปิดแล้ว!\nหยิบยาให้ครบแล้ว กรุณาปิดให้สนิทครับ"), 0)
                        try:
                            # สั่งตัดไฟกลอนแม่เหล็ก เพื่อให้ตอนดันประตูปิดมันล็อกได้เลย
                            requests.post(f"{HARDWARE_API}/close", json={"address": slot, "transaction_id": str(transaction_id)}, timeout=2)
                        except:
                            pass
                        break
                except:
                    pass
                time.sleep(0.5)
                wait_time += 0.5
                
            # ถ้าครบ 60 วินาทีแล้วประตูยังไม่ถูกเปิด
            if not door_opened:
                try:
                    requests.post(f"{HARDWARE_API}/close", json={"address": slot, "transaction_id": str(transaction_id)}, timeout=2) 
                    requests.post(f"{HARDWARE_API}/status-light/off", json={"address": slot, "transaction_id": str(transaction_id)}, timeout=2) 
                except:
                    pass
                print(f"⚠️ หมดเวลารอ! ประตู {slot} ไม่ถูกเปิดออก")
                continue # ข้ามไปคิวของตู้ถัดไป
                
            # --- วนลูปรอปิดประตู ---
            while door_opened:
                try:
                    res = requests.get(f"{HARDWARE_API}/status/{slot}", timeout=2).json()
                    if res.get("status") == "CLOSED":
                        Clock.schedule_once(lambda dt, s=slot: setattr(self.hw_dialog_label, 'text', f"✅ ตู้ {s} ปิดเรียบร้อย\nกำลังบันทึกภาพ..."), 0)
                        break
                except:
                    pass
                time.sleep(0.5)
                
            # ปิดไฟสถานะหน้าตู้
            try:
                requests.post(f"{HARDWARE_API}/status-light/off", json={"address": slot, "transaction_id": str(transaction_id)}, timeout=3)
            except:
                pass
            
            # ⏳ รอ 4 วินาที ให้ Camera Service ถ่ายรูป After และส่งคำสั่งตัด Relay กล้องให้เสร็จสมบูรณ์ ก่อนเริ่มตู้ถัดไป
            print(f"⏳ รอระบบกล้องตู้ {slot} เคลียร์ตัวเอง 4 วินาที...")
            time.sleep(4) 
            
        Clock.schedule_once(lambda dt: setattr(self.hw_dialog_label, 'text', "ปิดตู้ครบถ้วน..."), 0)
        Clock.schedule_once(lambda dt: self._on_hardware_sequence_complete("ทำรายการเบิกยาสำเร็จและปิดตู้ครบถ้วน!"), 0)

    def _on_hardware_sequence_complete(self, msg):
        # เคลียร์หน้าจอ และโหลดหน้าตะกร้าใหม่
        self.hw_dialog.dismiss()
        self.cart_items.clear()
        self.load_data_from_api()  
        self.refresh_cart_view()
        self.render_medicine_rows()
        
        app = MDApp.get_running_app()
        if app and hasattr(app, "complete_active_qr_task"):
            app.complete_active_qr_task()
            
        toast(msg)