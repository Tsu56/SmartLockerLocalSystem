#restock_controller.py
from kivymd.uix.screen import MDScreen
from kivymd.uix.datatables import MDDataTable
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivy.metrics import dp
from kivy.properties import StringProperty, NumericProperty, ListProperty
from kivy.uix.gridlayout import GridLayout


class CartItemWidget(MDBoxLayout):
    product_name = StringProperty()
    product_id = StringProperty()
    slot = StringProperty()
    quantity = StringProperty()
    
    def __init__(self, **kwargs):
        self.edit_callback = kwargs.pop('edit_callback', None)
        self.delete_callback = kwargs.pop('delete_callback', None)
        super().__init__(**kwargs)


class SlotCard(MDCard):
    """Card widget สำหรับแสดงช่องเก็บยา - แสดงรายการยาทั้งหมด"""
    slot_number = StringProperty()
    products_list = ListProperty([])  # [{name: "", quantity: 0}, ...]
    max_qty = NumericProperty()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = dp(10)
        self.spacing = dp(6)
        self.size_hint = (None, None)
        self.size = (dp(180), dp(200))  # ขยายขนาดให้แสดงได้หลายรายการ
        self.radius = [12]
        self.elevation = 2
        
        # คำนวณข้อมูล
        total_qty = sum(p["quantity"] for p in self.products_list)
        available_space = self.max_qty - total_qty
        has_product = len(self.products_list) > 0
        
        # เปลี่ยนสีตามพื้นที่ว่าง
        if available_space > 20:
            self.md_bg_color = (0.95, 1, 0.95, 1)  # สีเขียวอ่อน (พื้นที่เยอะ)
        elif available_space > 0:
            self.md_bg_color = (1, 1, 0.9, 1)  # สีเหลืองอ่อน (พื้นที่น้อย)
        else:
            self.md_bg_color = (1, 0.9, 0.9, 1)  # สีแดงอ่อน (เต็ม)
        
        # Slot number
        slot_label = MDLabel(
            text=f"Slot {self.slot_number}",
            font_style="H6",
            bold=True,
            size_hint_y=None,
            height=dp(28)
        )
        self.add_widget(slot_label)
        
        # แสดงรายการยา
        if self.products_list:
            # สร้าง ScrollView สำหรับรายการยา
            from kivy.uix.scrollview import ScrollView
            scroll = ScrollView(
                size_hint_y=None,
                height=dp(110),
                do_scroll_x=False
            )
            
            products_box = MDBoxLayout(
                orientation="vertical",
                spacing=dp(3),
                size_hint_y=None,
                padding=[0, dp(4), 0, 0]
            )
            products_box.bind(minimum_height=products_box.setter('height'))
            
            for product in self.products_list:
                # แสดงชื่อยาและจำนวน
                product_item = MDLabel(
                    text=f"• {product['name']}: {product['quantity']}",
                    font_style="Caption",
                    theme_text_color="Custom",
                    text_color=(0.2, 0.2, 0.2, 1),
                    size_hint_y=None,
                    height=dp(18)
                )
                products_box.add_widget(product_item)
            
            scroll.add_widget(products_box)
            self.add_widget(scroll)
        else:
            empty_label = MDLabel(
                text="Empty Slot",
                font_style="Caption",
                theme_text_color="Custom",
                text_color=(0.6, 0.6, 0.6, 1),
                size_hint_y=None,
                height=dp(110),
                halign="center",
                valign="middle",
                italic=True
            )
            self.add_widget(empty_label)
        
        # Space indicator + Total
        space_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(2),
            size_hint_y=None,
            height=dp(34)
        )
        
        # Available space
        if available_space > 0:
            space_text = f"Space: {available_space}"
            space_color = (0.15, 0.68, 0.38, 1) if available_space > 20 else (0.9, 0.6, 0.2, 1)
        else:
            space_text = "Full"
            space_color = (0.9, 0.3, 0.3, 1)
        
        space_label = MDLabel(
            text=space_text,
            font_style="Caption",
            theme_text_color="Custom",
            text_color=space_color,
            halign="center",
            size_hint_y=None,
            height=dp(16),
            bold=True
        )
        
        # Total Quantity
        qty_label = MDLabel(
            text=f"Total: {total_qty}/{self.max_qty}",
            font_style="Caption",
            halign="center",
            size_hint_y=None,
            height=dp(16),
            theme_text_color="Custom",
            text_color=(0.3, 0.5, 0.8, 1),
            bold=True
        )
        
        space_box.add_widget(space_label)
        space_box.add_widget(qty_label)
        self.add_widget(space_box)


class RestockScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dialog = None
        self.quantity_dialog = None
        self.cart_items = []  # เก็บรายการในตะกร้า
        self.selected_medicine = None
        self.selected_slot = None
        
        # Mock data สำหรับช่องเก็บยา - 1 ช่องมีหลายชนิดยา
        # โครงสร้าง: products แต่ละตัวมี expired_at
        # ทุกช่องมี capacity = 50
        self.slots_data = [
            {
                "slot": "A1",
                "products": [
                    {"id": "MED001", "name": "Paracetamol 500mg", "quantity": 30, "expired_at": "2025-12-31"},
                    {"id": "MED008", "name": "Ibuprofen 400mg", "quantity": 15, "expired_at": "2025-11-30"}
                ],
                "max": 50  # capacity = 50 (total: 45/50, available: 5)
            },
            {
                "slot": "A2",
                "products": [],
                "max": 50  # capacity = 50 (empty)
            },
            {
                "slot": "B1",
                "products": [
                    {"id": "MED003", "name": "Amoxicillin 500mg", "quantity": 25, "expired_at": "2026-01-15"},
                    {"id": "MED007", "name": "Amoxicillin/Clavulanate", "quantity": 20, "expired_at": "2025-10-20"}
                ],
                "max": 50  # capacity = 50 (total: 45/50, available: 5)
            },
            {
                "slot": "B2",
                "products": [
                    {"id": "MED004", "name": "Cetirizine 10mg", "quantity": 10, "expired_at": "2026-03-10"}
                ],
                "max": 50  # capacity = 50 (total: 10/50, available: 40)
            },
            {
                "slot": "C1",
                "products": [],
                "max": 50  # capacity = 50 (empty)
            },
            {
                "slot": "C2",
                "products": [
                    {"id": "MED002", "name": "Aspirin 100mg", "quantity": 35, "expired_at": "2025-09-15"},
                    {"id": "MED005", "name": "Omeprazole 20mg", "quantity": 15, "expired_at": "2026-02-28"}
                ],
                "max": 50  # capacity = 50 (total: 50/50, FULL!)
            },
        ]
    
    def on_kv_post(self, base_widget):
        # สร้าง DataTable
        self.table = MDDataTable(
            use_pagination=True,
            size_hint = (1,1),
            check=False,
            column_data=[
                ("ID", dp(30)),
                ("Name", dp(40)),
                ("Action", dp(30))
            ],
            row_data=[
                ("MED001", "Paracetamol 500mg", ""),
                ("MED002", "Aspirin 100mg", ""),
                ("MED003", "Amoxicillin 500mg", ""),
                ("MED004", "Cetirizine 10mg",""),
                ("MED005", "Omeprazole 20mg", ""),
                ("MED006", "Metformin 500mg", ""),
                ("MED007", "Amoxicillin/Clavulanate", ""),
                ("MED008", "Ibuprofen 400mg", ""),
            ],
        )
        
        # Bind event เมื่อกดแถวในตาราง
        self.table.bind(on_row_press=self.on_row_press)
        
        if 'table_container' in self.ids:
            self.ids.table_container.add_widget(self.table)
    
    def on_row_press(self, instance_table, instance_row):
        """เมื่อกดแถวในตาราง"""
        # ดึงข้อมูลจากแถวที่กด
        start_index = instance_row.index
        row_data = instance_table.row_data[start_index // len(instance_table.column_data)]
        
        med_id = row_data[0]
        med_name = row_data[1]
        
        self.selected_medicine = {
            "id": med_id,
            "name": med_name
        }
        
        # เปิด Dialog เลือกช่อง
        self.show_slot_selection_dialog()
    
    def show_slot_selection_dialog(self):
        """แสดง Dialog เลือกช่องเก็บยา"""
        if not self.dialog:
            # สร้าง ScrollView สำหรับ Grid
            from kivy.uix.scrollview import ScrollView
            
            scroll = ScrollView(
                size_hint_y=None,
                height=dp(450),
                do_scroll_x=False
            )
            
            # สร้าง Grid Layout สำหรับแสดงช่อง 3x2
            grid = GridLayout(
                cols=3,
                spacing=dp(12),
                padding=dp(16),
                size_hint_y=1,
                size_hint_x=1
            )
            
            # คำนวณความสูงตาม rows
            rows = (len(self.slots_data) + 2) // 3
            grid.height = rows * (dp(200) + dp(12))
            
            # สร้าง Slot Cards
            for slot_info in self.slots_data:
                # เตรียมข้อมูล products_list
                products_list = [
                    {"name": p["name"], "quantity": p["quantity"]} 
                    for p in slot_info["products"]
                ]
                
                slot_card = SlotCard(
                    slot_number=slot_info["slot"],
                    products_list=products_list,
                    max_qty=slot_info["max"]
                )
                
                # เพิ่ม event เมื่อกดเลือกช่อง
                slot_card.bind(on_release=lambda x, s=slot_info: self.on_slot_selected(s))
                grid.add_widget(slot_card)
            
            scroll.add_widget(grid)
            
            # สร้าง Content Box
            content_box = MDBoxLayout(
                orientation="vertical",
                spacing=dp(12),
                size_hint_y=None,
                height=dp(500)
            )
            
            # Header
            header_label = MDLabel(
                text=f"Select slot for: {self.selected_medicine['name']}",
                font_style="Subtitle1",
                bold=True,
                size_hint_y=None,
                height=dp(30)
            )
            
            content_box.add_widget(header_label)
            content_box.add_widget(scroll)
            
            self.dialog = MDDialog(
                title="Select Storage Slot",
                type="custom",
                content_cls=content_box,
                buttons=[
                    MDFlatButton(
                        text="CANCEL",
                        theme_text_color="Custom",
                        text_color=(0.9, 0.3, 0.3, 1),
                        on_release=lambda x: self.dialog.dismiss()
                    ),
                ],
            )
        
        # อัพเดท Grid ทุกครั้งที่เปิด Dialog (เพื่อแสดงข้อมูลล่าสุด)
        self.update_slot_grid()
        self.dialog.open()
    
    def update_slot_grid(self):
        """อัพเดท Slot Grid ให้แสดงข้อมูลล่าสุด"""
        if not self.dialog:
            return
        
        # หา ScrollView ใน dialog content
        content_box = self.dialog.content_cls
        if len(content_box.children) >= 1:
            scroll = content_box.children[0]  # ScrollView อยู่ตำแหน่งที่ 0
            
            # หา Grid ใน ScrollView
            if hasattr(scroll, 'children') and len(scroll.children) > 0:
                grid = scroll.children[0]
                grid.clear_widgets()
                
                # สร้าง Slot Cards ใหม่
                for slot_info in self.slots_data:
                    # เตรียมข้อมูล products_list
                    products_list = [
                        {"name": p["name"], "quantity": p["quantity"]} 
                        for p in slot_info["products"]
                    ]
                    
                    slot_card = SlotCard(
                        slot_number=slot_info["slot"],
                        products_list=products_list,
                        max_qty=slot_info["max"]
                    )
                    
                    slot_card.bind(on_release=lambda x, s=slot_info: self.on_slot_selected(s))
                    grid.add_widget(slot_card)
    
    def on_slot_selected(self, slot_info):
        """เมื่อเลือกช่องเก็บยา"""
        # คำนวณพื้นที่ว่าง
        total_qty = sum(p["quantity"] for p in slot_info["products"])
        available_space = slot_info["max"] - total_qty
        
        # ตรวจสอบว่ามีพื้นที่ว่างหรือไม่ (แก้ไขเป็น < แทน <=)
        if available_space < 1:
            print(f"Slot {slot_info['slot']} is full! No space available.")
            # TODO: แสดง Snackbar หรือ Toast แจ้งเตือนผู้ใช้
            return
        
        # เก็บข้อมูลช่องที่เลือก
        self.selected_slot = slot_info
        
        # ปิด Dialog เลือกช่อง
        self.dialog.dismiss()
        
        # เปิด Dialog ใส่จำนวนยา
        self.show_quantity_input_dialog()
    
    def show_quantity_input_dialog(self):
        """แสดง Dialog สำหรับใส่จำนวนยาและวันหมดอายุ"""
        from kivymd.uix.textfield import MDTextField
        
        # คำนวณจำนวนที่เติมได้สูงสุด
        total_qty = sum(p["quantity"] for p in self.selected_slot["products"])
        max_can_add = self.selected_slot["max"] - total_qty
        
        # สร้าง TextField สำหรับใส่จำนวน
        self.quantity_input = MDTextField(
            hint_text="Enter quantity",
            helper_text=f"Available space: {max_can_add} units (Current: {total_qty}/{self.selected_slot['max']})",
            helper_text_mode="persistent",
            mode="rectangle",
            size_hint_x=1,
            input_filter="int",
            multiline=False,
        )
        
        # สร้าง TextField สำหรับใส่วันหมดอายุ
        self.expired_input = MDTextField(
            hint_text="Expiration date (YYYY-MM-DD)",
            helper_text="Format: YYYY-MM-DD (e.g., 2026-12-31)",
            helper_text_mode="persistent",
            mode="rectangle",
            size_hint_x=1,
            multiline=False,
        )
        
        # สร้าง Content Box
        content_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(16),
            size_hint_y=None,
            height=dp(240)
        )
        
        # Header
        header_label = MDLabel(
            text=f"{self.selected_medicine['name']} → Slot {self.selected_slot['slot']}",
            font_style="Subtitle1",
            bold=True,
            size_hint_y=None,
            height=dp(30)
        )
        
        # ID label
        id_label = MDLabel(
            text=f"ID: {self.selected_medicine['id']}",
            font_style="Caption",
            theme_text_color="Hint",
            size_hint_y=None,
            height=dp(20)
        )
        
        content_box.add_widget(header_label)
        content_box.add_widget(id_label)
        content_box.add_widget(self.quantity_input)
        content_box.add_widget(self.expired_input)
        
        self.quantity_dialog = MDDialog(
            title="Enter Quantity & Expiration",
            type="custom",
            content_cls=content_box,
            buttons=[
                MDFlatButton(
                    text="CANCEL",
                    theme_text_color="Custom",
                    text_color=(0.9, 0.3, 0.3, 1),
                    on_release=lambda x: self.quantity_dialog.dismiss()
                ),
                MDFlatButton(
                    text="ADD TO CART",
                    theme_text_color="Custom",
                    text_color=(0.15, 0.68, 0.38, 1),
                    on_release=lambda x: self.validate_and_add_to_cart()
                ),
            ],
        )
        
        self.quantity_dialog.open()
    
    def validate_and_add_to_cart(self):
        """ตรวจสอบจำนวน วันหมดอายุ และเพิ่มเข้าตะกร้า"""
        import re
        from datetime import datetime
        
        try:
            quantity = int(self.quantity_input.text)
            expired_at = self.expired_input.text.strip()
            
            # ตรวจสอบจำนวน
            total_qty = sum(p["quantity"] for p in self.selected_slot["products"])
            max_can_add = self.selected_slot["max"] - total_qty
            
            if quantity <= 0:
                self.quantity_input.error = True
                self.quantity_input.helper_text = "Quantity must be greater than 0"
                return
            
            if quantity > max_can_add:
                self.quantity_input.error = True
                self.quantity_input.helper_text = f"Exceeds available space! Maximum: {max_can_add}"
                return
            
            # ตรวจสอบรูปแบบวันหมดอายุ (YYYY-MM-DD)
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', expired_at):
                self.expired_input.error = True
                self.expired_input.helper_text = "Invalid format! Use YYYY-MM-DD"
                return
            
            # ตรวจสอบว่าเป็นวันที่ที่ถูกต้อง
            try:
                datetime.strptime(expired_at, '%Y-%m-%d')
            except ValueError:
                self.expired_input.error = True
                self.expired_input.helper_text = "Invalid date! Please check day/month"
                return
            
            # เพิ่มรายการเข้าตะกร้า
            self.add_to_cart(
                product_id=self.selected_medicine["id"],
                product_name=self.selected_medicine["name"],
                slot=self.selected_slot["slot"],
                quantity=quantity,
                expired_at=expired_at
            )
            
            # ปิด Dialog
            self.quantity_dialog.dismiss()
            
        except ValueError:
            self.quantity_input.error = True
            self.quantity_input.helper_text = "Please enter a valid number"
    
    def add_to_cart(self, product_id, product_name, slot, quantity, expired_at):
        """เพิ่มรายการเข้าตะกร้า"""
        # ตรวจสอบว่ามีรายการซ้ำไหม (product_id + slot + expired_at เดียวกัน)
        for item in self.cart_items:
            if item["id"] == product_id and item["slot"] == slot and item["expired_at"] == expired_at:
                print("Item with same product, slot, and expiration already in cart!")
                return
        
        # เพิ่มรายการใหม่
        cart_item = {
            "id": product_id,
            "name": product_name,
            "slot": slot,
            "quantity": quantity,
            "expired_at": expired_at
        }
        self.cart_items.append(cart_item)
        
        # อัพเดทข้อมูล slot ชั่วคราว (สำหรับแสดงใน dialog)
        self.update_slot_data_temp(slot, product_id, product_name, quantity, expired_at)
        
        # สร้าง Widget สำหรับแสดงในตะกร้า
        item_widget = CartItemWidget(
            product_id=product_id,
            product_name=product_name,
            slot=slot,
            quantity=str(quantity),
            edit_callback=lambda: self.edit_cart_item(cart_item, item_widget),
            delete_callback=lambda: self.remove_from_cart(item_widget, cart_item)
        )
        
        self.ids.cart_list.add_widget(item_widget)
        
        # อัพเดทจำนวนในตะกร้า
        self.update_cart_summary()
        
        print(f"Added {quantity} units of {product_name} (ID: {product_id}, Exp: {expired_at}) to cart in slot {slot}")
    
    def update_slot_data_temp(self, slot_number, product_id, product_name, quantity, expired_at):
        """อัพเดทข้อมูลในช่องเก็บยาชั่วคราว (สำหรับแสดงใน Dialog)
        - ถ้ายาชนิดเดียวกัน + expired_at เหมือนกัน → รวมเข้าด้วยกัน (merge)
        - ถ้ายาชนิดเดียวกัน + expired_at ต่างกัน → เพิ่มเป็นรายการใหม่ (insert)
        """
        for slot in self.slots_data:
            if slot["slot"] == slot_number:
                # หาว่ามียานี้อยู่ในช่องแล้วหรือไม่ (product_id + expired_at ตรงกัน)
                found = False
                for product in slot["products"]:
                    if product["id"] == product_id and product["expired_at"] == expired_at:
                        # ยาชนิดเดียวกัน + วันหมดอายุเดียวกัน → รวมเข้าด้วยกัน
                        product["quantity"] += quantity
                        found = True
                        break
                
                # ถ้ายังไม่มี หรือมีแต่ expired_at ต่างกัน ให้เพิ่มใหม่
                if not found:
                    slot["products"].append({
                        "id": product_id,
                        "name": product_name,
                        "quantity": quantity,
                        "expired_at": expired_at
                    })
                break
    
    def remove_from_cart(self, widget, cart_item):
        """ลบรายการออกจากตะกร้า"""
        self.ids.cart_list.remove_widget(widget)
        self.cart_items.remove(cart_item)
        
        # คืนจำนวนให้ slot (ต้องระบุ expired_at ด้วย)
        self.revert_slot_data_temp(cart_item["slot"], cart_item["id"], -cart_item["quantity"], cart_item["expired_at"])
        
        self.update_cart_summary()
        print(f"Removed {cart_item['name']} from cart")
    
    def revert_slot_data_temp(self, slot_number, product_id, quantity_change, expired_at):
        """คืนจำนวนให้ slot เมื่อลบออกจากตะกร้า"""
        for slot in self.slots_data:
            if slot["slot"] == slot_number:
                for product in slot["products"]:
                    if product["id"] == product_id and product["expired_at"] == expired_at:
                        product["quantity"] += quantity_change
                        # ถ้าจำนวนเป็น 0 ให้ลบรายการออก
                        if product["quantity"] <= 0:
                            slot["products"].remove(product)
                        break
                break
    
    def edit_cart_item(self, cart_item, widget):
        """แก้ไขรายการในตะกร้า"""
        from kivymd.uix.textfield import MDTextField
        
        # คืนจำนวนเดิมให้ slot ก่อน
        self.update_slot_data_temp(cart_item["slot"], cart_item["id"], cart_item["name"], -cart_item["quantity"])
        
        # หาข้อมูล slot
        slot_info = None
        for slot in self.slots_data:
            if slot["slot"] == cart_item["slot"]:
                slot_info = slot
                break
        
        if not slot_info:
            return
        
        total_qty = sum(p["quantity"] for p in slot_info["products"])
        max_can_add = slot_info["max"] - total_qty
        
        # สร้าง TextField พร้อมค่าเดิม
        self.edit_quantity_input = MDTextField(
            hint_text="Enter new quantity",
            text=str(cart_item["quantity"]),
            helper_text=f"Available space: {max_can_add} units (Current: {total_qty}/{slot_info['max']})",
            helper_text_mode="persistent",
            mode="rectangle",
            size_hint_x=1,
            input_filter="int",
            multiline=False,
        )
        
        # สร้าง Content Box
        content_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(16),
            padding=dp(16),
            size_hint_y=None,
            height=dp(180)
        )
        
        header_label = MDLabel(
            text=f"Edit: {cart_item['name']} → Slot {cart_item['slot']}",
            font_style="Subtitle1",
            bold=True,
            size_hint_y=None,
            height=dp(30)
        )
        
        id_label = MDLabel(
            text=f"ID: {cart_item['id']}",
            font_style="Caption",
            theme_text_color="Hint",
            size_hint_y=None,
            height=dp(20)
        )
        
        content_box.add_widget(header_label)
        content_box.add_widget(id_label)
        content_box.add_widget(self.edit_quantity_input)
        
        edit_dialog = MDDialog(
            title="Edit Quantity",
            type="custom",
            content_cls=content_box,
            buttons=[
                MDFlatButton(
                    text="CANCEL",
                    theme_text_color="Custom",
                    text_color=(0.9, 0.3, 0.3, 1),
                    on_release=lambda x: self.cancel_edit(edit_dialog, cart_item, slot_info)
                ),
                MDFlatButton(
                    text="SAVE",
                    theme_text_color="Custom",
                    text_color=(0.15, 0.68, 0.38, 1),
                    on_release=lambda x: self.save_edit(edit_dialog, cart_item, widget, slot_info)
                ),
            ],
        )
        
        edit_dialog.open()
    
    def cancel_edit(self, dialog, cart_item, slot_info):
        """ยกเลิกการแก้ไข - คืนค่าเดิม"""
        self.update_slot_data_temp(cart_item["slot"], cart_item["id"], cart_item["name"], cart_item["quantity"])
        dialog.dismiss()
    
    def save_edit(self, dialog, cart_item, widget, slot_info):
        """บันทึกการแก้ไข"""
        try:
            new_quantity = int(self.edit_quantity_input.text)
            total_qty = sum(p["quantity"] for p in slot_info["products"])
            max_can_add = slot_info["max"] - total_qty
            
            if new_quantity <= 0:
                self.edit_quantity_input.error = True
                self.edit_quantity_input.helper_text = "Quantity must be greater than 0"
                return
            
            if new_quantity > max_can_add:
                self.edit_quantity_input.error = True
                self.edit_quantity_input.helper_text = f"Exceeds available space! Maximum: {max_can_add}"
                return
            
            # อัพเดทข้อมูลใน cart_item
            cart_item["quantity"] = new_quantity
            
            # อัพเดท slot data
            self.update_slot_data_temp(cart_item["slot"], cart_item["id"], cart_item["name"], new_quantity)
            
            # อัพเดท widget
            widget.quantity = str(new_quantity)
            
            dialog.dismiss()
            print(f"Updated {cart_item['name']} quantity to {new_quantity}")
            
        except ValueError:
            self.edit_quantity_input.error = True
            self.edit_quantity_input.helper_text = "Please enter a valid number"
    
    def update_cart_summary(self):
        """อัพเดทข้อมูลสรุปในตะกร้า"""
        total_items = len(self.cart_items)
        self.ids.cart_count_badge.text = f"{total_items} list{'s' if total_items != 1 else ''}"
        self.ids.total_items_label.text = f"{total_items} total"
    
    def confirm_selection(self):
        """ยืนยันการเติมยา"""
        if not self.cart_items:
            print("Cart is empty!")
            return
        
        print("=== Restock Confirmation ===")
        for item in self.cart_items:
            print(f"ID: {item['id']}, Name: {item['name']}, Slot: {item['slot']}, Quantity: {item['quantity']}")
        print("===========================")
        
        # TODO: ส่งข้อมูลไปยัง backend หรือ database
        # ข้อมูลถูกอัพเดทใน slots_data แล้ว (ผ่าน update_slot_data_temp)
        
        # Clear cart
        self.ids.cart_list.clear_widgets()
        self.cart_items.clear()
        self.update_cart_summary()
        
        print("Restock completed successfully!")