from datetime import datetime

from kivy.metrics import dp
from kivy.properties import StringProperty, NumericProperty, ObjectProperty
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivymd.app import MDApp
from kivymd.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.datatables import MDDataTable
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField


class MedicineRowWidget(MDBoxLayout):
    med_id = StringProperty("")
    med_name = StringProperty("")
    select_callback = ObjectProperty(None)


class CartItemWidget(MDBoxLayout):
    product_id = StringProperty("")
    product_name = StringProperty("")
    slot = StringProperty("")
    quantity = StringProperty("0")
    delete_callback = ObjectProperty(None)


class SlotSelectCard(MDCard):
    def __init__(self, slot_info, on_select, **kwargs):
        super().__init__(**kwargs)
        self.slot_info = slot_info
        self.on_select = on_select
        self.orientation = "vertical"
        self.padding = dp(12)
        self.spacing = dp(10)
        self.size_hint = (None, None)
        self.size = (dp(210), dp(190))
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

        slot_icon = MDLabel(text="📦", size_hint_x=None, width=dp(24), halign="center")
        header.add_widget(slot_chip)
        header.add_widget(MDLabel())
        header.add_widget(slot_icon)

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
            theme_text_color="Primary",
            bold=True,
        )
        remain_label = MDLabel(
            text=f"คงเหลือ {top_qty} หน่วย",
            halign="center",
            theme_text_color="Secondary",
            font_style="Caption",
            size_hint_y=None,
            height=dp(18),
        )

        bar_bg = MDCard(
            radius=[6],
            size_hint_y=None,
            height=dp(10),
            elevation=0,
            md_bg_color=(0.88, 0.89, 0.91, 1),
        )
        bar_inner = MDCard(
            radius=[6],
            size_hint=(ratio, 1),
            elevation=0,
            md_bg_color=progress_color,
        )
        bar_bg.add_widget(bar_inner)

        bottom_row = MDBoxLayout(size_hint_y=None, height=dp(24))
        bottom_row.add_widget(MDLabel(text="ความจุ", theme_text_color="Secondary", font_style="Caption"))
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
        self.add_widget(bar_bg)
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
        self.slot_button = None
        self.slot_info_label = None

        self.medicines = [
            {"id": "MED001", "name": "พาราเซตามอล 500mg"},
            {"id": "MED002", "name": "แอสไพริน 100mg"},
            {"id": "MED003", "name": "อมอกซีซิลลิน 500mg"},
            {"id": "MED004", "name": "เซทิริซีน 10mg"},
            {"id": "MED005", "name": "โอเมพราโซล 20mg"},
            {"id": "MED006", "name": "เมทฟอร์มิน 500mg"},
            {"id": "MED007", "name": "อะม็อกซีซิลลิน/กรดคลาวูลานิก"},
            {"id": "MED008", "name": "ไอบูโปรเฟน 400mg"},
        ]

        self.slots_data = [
            {"slot": 1, "capacity": 50, "products": [{"id": "MED001", "name": "พาราเซตามอล 500mg", "qty": 30}]},
            {"slot": 2, "capacity": 50, "products": []},
            {"slot": 3, "capacity": 50, "products": [{"id": "MED003", "name": "อมอกซีซิลลิน 500mg", "qty": 45}]},
            {"slot": 4, "capacity": 50, "products": [{"id": "MED004", "name": "เซทิริซีน 10mg", "qty": 10}]},
            {"slot": 5, "capacity": 50, "products": []},
            {"slot": 6, "capacity": 50, "products": [{"id": "MED008", "name": "ไอบูโปรเฟน 400mg", "qty": 50}]},
        ]

    def on_kv_post(self, base_widget):
        self.render_medicine_rows()
        self.refresh_cart_view()

    def render_medicine_rows(self):
        self.ids.medicine_rows.clear_widgets()
        for medicine in self.medicines:
            row = MedicineRowWidget(
                med_id=medicine["id"],
                med_name=medicine["name"],
                select_callback=lambda med=medicine: self.open_add_dialog(med),
            )
            self.ids.medicine_rows.add_widget(row)

    def open_add_dialog(self, medicine):
        self.selected_medicine = medicine
        self.selected_slot = None

        self.quantity_input = MDTextField(
            hint_text="จำนวน",
            text="1",
            input_filter="int",
            mode="rectangle",
            helper_text="กรุณาระบุจำนวนที่ต้องการเติม",
            helper_text_mode="persistent",
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
        detail_card.add_widget(MDLabel(text="รหัสยา", theme_text_color="Secondary", font_style="Caption"))
        detail_card.add_widget(MDLabel(text=medicine["id"], bold=True, font_style="H6", size_hint_y=None, height=dp(36)))
        detail_card.add_widget(MDLabel(text="ชื่อยา", theme_text_color="Secondary", font_style="Caption"))
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
        select_slot_card.add_widget(MDLabel(text="📦", size_hint_x=None, width=dp(24), halign="center"))
        select_slot_card.add_widget(self.slot_button)

        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            size_hint_y=None,
            height=dp(460),
        )
        content.add_widget(MDLabel(text="กรุณาระบุจำนวนและเลือกช่องที่ต้องการเก็บยา", theme_text_color="Secondary", size_hint_y=None, height=dp(22)))
        content.add_widget(detail_card)
        content.add_widget(MDLabel(text="จำนวนที่ต้องการเติม", size_hint_y=None, height=dp(20)))
        content.add_widget(self.quantity_input)
        content.add_widget(MDLabel(text="เลือกช่องที่จะเก็บ", size_hint_y=None, height=dp(20)))
        content.add_widget(select_slot_card)
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

        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(grid)

        legend = MDBoxLayout(size_hint_y=None, height=dp(30), spacing=dp(18), padding=[dp(6), 0, 0, 0])
        legend.add_widget(MDLabel(text="🟢 ช่องว่าง", theme_text_color="Secondary"))
        legend.add_widget(MDLabel(text="🟠 มียาบางส่วน", theme_text_color="Secondary"))
        legend.add_widget(MDLabel(text="🔴 เต็ม", theme_text_color="Secondary"))

        content = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, height=dp(490))
        content.add_widget(MDLabel(text="คลิกที่ช่องเพื่อเลือกตำแหน่งที่ต้องการเติมยา", theme_text_color="Secondary", size_hint_y=None, height=dp(22)))
        content.add_widget(scroll)
        content.add_widget(legend)

        self.slot_dialog = MDDialog(
            title="เลือกช่องเก็บยา",
            type="custom",
            content_cls=content,
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

        self._append_cart_item(self.selected_medicine, self.selected_slot["slot"], quantity)
        self._apply_slot_restock(self.selected_medicine, self.selected_slot, quantity)

        self.refresh_cart_view()
        self.render_medicine_rows()

        if self.add_dialog:
            self.add_dialog.dismiss()

    def _append_cart_item(self, medicine, slot_number, quantity):
        self.cart_items.append(
            {
                "id": medicine["id"],
                "name": medicine["name"],
                "slot": slot_number,
                "quantity": quantity,
                "created_at": datetime.utcnow().isoformat(),
            }
        )

    def _apply_slot_restock(self, medicine, slot_info, quantity):
        for product in slot_info["products"]:
            if product["id"] == medicine["id"]:
                product["qty"] += quantity
                return
        slot_info["products"].append({"id": medicine["id"], "name": medicine["name"], "qty": quantity})

    def remove_cart_item(self, cart_item):
        if cart_item not in self.cart_items:
            return

        self.cart_items.remove(cart_item)
        self._revert_slot_restock(cart_item)

        self.refresh_cart_view()
        self.render_medicine_rows()

    def _revert_slot_restock(self, cart_item):
        for slot in self.slots_data:
            if slot["slot"] != cart_item["slot"]:
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
            widget = CartItemWidget(
                product_name=item["name"],
                product_id=item["id"],
                slot=f"ช่อง {item['slot']}",
                quantity=str(item["quantity"]),
                delete_callback=lambda x=item: self.remove_cart_item(x),
            )
            self.ids.cart_list.add_widget(widget)

        item_count = len(self.cart_items)
        total_units = sum(item["quantity"] for item in self.cart_items)

        self.ids.cart_count_badge.text = f"{item_count} รายการ"
        self.ids.total_units_label.text = f"{total_units} หน่วย"
        self.ids.cart_empty_state.opacity = 1 if item_count == 0 else 0
        self.ids.cart_empty_state.disabled = item_count != 0

    def confirm_selection(self):
        if not self.cart_items:
            toast("ตะกร้าว่างเปล่า")
            return

        self.cart_items.clear()
        self.refresh_cart_view()
        toast("ทำรายการเติมยาเสร็จสิ้น")
