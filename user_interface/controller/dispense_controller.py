#dispense_controller.py
from kivymd.uix.screen import MDScreen
from kivymd.uix.datatables import MDDataTable
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.list import OneLineListItem, TwoLineListItem
from kivy.metrics import dp
from kivy.properties import StringProperty, NumericProperty, ListProperty
from kivy.uix.gridlayout import GridLayout


class DispenseCartItemWidget(MDBoxLayout):
    """Widget สำหรับแสดงรายการในตะกร้าเบิก"""
    slot_number = StringProperty()
    product_id = StringProperty()
    product_name = StringProperty()
    quantity = StringProperty()
    
    def __init__(self, **kwargs):
        self.edit_callback = kwargs.pop('edit_callback', None)
        self.delete_callback = kwargs.pop('delete_callback', None)
        super().__init__(**kwargs)


class SlotDispenseCard(MDCard):
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
        
        # คำนวณจำนวนรวม
        total_qty = sum(p["quantity"] for p in self.products_list)
        has_product = len(self.products_list) > 0
        
        # เปลี่ยนสีตามสถานะ
        if has_product and total_qty > 0:
            self.md_bg_color = (0.95, 1, 0.95, 1)  # สีเขียวอ่อน (มียา)
        elif has_product and total_qty == 0:
            self.md_bg_color = (1, 0.95, 0.95, 1)  # สีแดงอ่อน (ยาหมด)
        else:
            self.md_bg_color = (0.95, 0.95, 0.95, 1)  # สีเทาอ่อน (ไม่มียา)
        
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
            # สร้าง Box สำหรับรายการยา (ไม่ใช้ ScrollView เพื่อไม่ให้ block touch)
            products_box = MDBoxLayout(
                orientation="vertical",
                spacing=dp(3),
                size_hint_y=None,
                padding=[0, dp(4), 0, 0],
                height=dp(120)
            )
            
            # จำกัดจำนวนที่แสดงไม่เกิน 6 รายการ
            display_products = self.products_list[:6]
            for product in display_products:
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
            
            # ถ้ามีเกิน 6 รายการ แสดง "..."
            if len(self.products_list) > 6:
                more_label = MDLabel(
                    text=f"... +{len(self.products_list) - 6} more",
                    font_style="Caption",
                    theme_text_color="Custom",
                    text_color=(0.5, 0.5, 0.5, 1),
                    size_hint_y=None,
                    height=dp(18),
                    italic=True
                )
                products_box.add_widget(more_label)
            
            self.add_widget(products_box)
        else:
            empty_label = MDLabel(
                text="Empty Slot",
                font_style="Caption",
                theme_text_color="Custom",
                text_color=(0.6, 0.6, 0.6, 1),
                size_hint_y=None,
                height=dp(120),
                halign="center",
                valign="middle",
                italic=True
            )
            self.add_widget(empty_label)
        
        # Total Quantity
        qty_label = MDLabel(
            text=f"Total: {total_qty}/{self.max_qty}",
            font_style="Caption",
            halign="center",
            size_hint_y=None,
            height=dp(24),
            theme_text_color="Custom",
            text_color=(0.3, 0.5, 0.8, 1),
            bold=True
        )
        self.add_widget(qty_label)


class DispenseScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dialog = None
        self.product_selection_dialog = None
        self.quantity_dialog = None
        self.dispense_cart_items = []  # เก็บรายการในตะกร้าเบิก
        self.selected_slot = None
        self.selected_product = None
        
        # Mock data สำหรับช่องเก็บยา - 1 ช่องมีหลายชนิดยา
        # โครงสร้าง: {"slot": "A1", "products": [{"id": "MED001", "name": "...", "quantity": 30}, ...], "max": 50}
        self.slots_data = [
            {
                "slot": "A1",
                "products": [
                    {"id": "MED001", "name": "Paracetamol 500mg", "quantity": 30},
                    {"id": "MED008", "name": "Ibuprofen 400mg", "quantity": 15}
                ],
                "max": 50
            },
            {
                "slot": "A2",
                "products": [],
                "max": 50
            },
            {
                "slot": "B1",
                "products": [
                    {"id": "MED003", "name": "Amoxicillin 500mg", "quantity": 25},
                    {"id": "MED007", "name": "Amoxicillin/Clavulanate", "quantity": 20}
                ],
                "max": 50
            },
            {
                "slot": "B2",
                "products": [
                    {"id": "MED004", "name": "Cetirizine 10mg", "quantity": 10}
                ],
                "max": 50
            },
            {
                "slot": "C1",
                "products": [],
                "max": 50
            },
            {
                "slot": "C2",
                "products": [
                    {"id": "MED002", "name": "Aspirin 100mg", "quantity": 35},
                    {"id": "MED005", "name": "Omeprazole 20mg", "quantity": 15}
                ],
                "max": 50
            },
        ]
    
    def on_kv_post(self, base_widget):
        """สร้าง Grid ของช่องเก็บยาหลังจาก KV โหลดเสร็จ"""
        self.build_slots_grid()
    
    def build_slots_grid(self):
        """สร้าง Grid Layout สำหรับแสดงช่องเก็บยา"""
        if 'slots_grid_container' not in self.ids:
            return
        
        # Clear existing widgets
        self.ids.slots_grid_container.clear_widgets()
        
        # สร้าง Grid Layout 3x2
        grid = GridLayout(
            cols=3,
            spacing=dp(12),
            padding=dp(16),
            size_hint_y=None
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
            
            slot_card = SlotDispenseCard(
                slot_number=slot_info["slot"],
                products_list=products_list,
                max_qty=slot_info["max"]
            )
            
            # เพิ่ม event เมื่อกดเลือกช่อง
            slot_card.bind(on_release=lambda x, s=slot_info: self.on_slot_selected(s))
            grid.add_widget(slot_card)
        
        self.ids.slots_grid_container.add_widget(grid)
    
    def on_slot_selected(self, slot_info):
        """เมื่อเลือกช่อง - แสดงรายการยาในช่องให้เลือก"""
        # ตรวจสอบว่าช่องมียาหรือไม่
        if not slot_info["products"]:
            print(f"Slot {slot_info['slot']} has no products!")
            return
        
        # เก็บข้อมูลช่องที่เลือก
        self.selected_slot = slot_info
        
        # แสดง Dialog เลือกยาในช่อง
        self.show_product_selection_dialog()
    
    def show_product_selection_dialog(self):
        """แสดง Dialog เลือกยาจากช่องที่เลือก"""
        # สร้าง List ของยาในช่อง
        products_list = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=dp(8)
        )
        
        # คำนวณความสูง
        products_list.height = len(self.selected_slot["products"]) * dp(60) + dp(16)
        
        for product in self.selected_slot["products"]:
            if product["quantity"] > 0:  # แสดงเฉพาะยาที่มีจำนวนเหลือ
                item = TwoLineListItem(
                    text=product["name"],
                    secondary_text=f"Available: {product['quantity']} units",
                    on_release=lambda x, p=product: self.on_product_selected(p)
                )
                products_list.add_widget(item)
        
        # สร้าง ScrollView
        scroll = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=min(dp(300), products_list.height)
        )
        
        from kivy.uix.scrollview import ScrollView
        scroll_view = ScrollView(
            size_hint_y=None,
            height=min(dp(300), products_list.height)
        )
        scroll_view.add_widget(products_list)
        
        # สร้าง Content Box
        content_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(12),
            size_hint_y=None,
            height=min(dp(350), products_list.height + dp(50))
        )
        
        # Header
        header_label = MDLabel(
            text=f"Select medicine from Slot {self.selected_slot['slot']}",
            font_style="Subtitle1",
            bold=True,
            size_hint_y=None,
            height=dp(30)
        )
        
        content_box.add_widget(header_label)
        content_box.add_widget(scroll_view)
        
        self.product_selection_dialog = MDDialog(
            title="Select Medicine",
            type="custom",
            content_cls=content_box,
            buttons=[
                MDFlatButton(
                    text="CANCEL",
                    theme_text_color="Custom",
                    text_color=(0.9, 0.3, 0.3, 1),
                    on_release=lambda x: self.product_selection_dialog.dismiss()
                ),
            ],
        )
        
        self.product_selection_dialog.open()
    
    def on_product_selected(self, product):
        """เมื่อเลือกยาจากช่อง"""
        self.selected_product = product
        
        # ปิด Dialog เลือกยา
        if self.product_selection_dialog:
            self.product_selection_dialog.dismiss()
        
        # เปิด Dialog ใส่จำนวน
        self.show_quantity_dialog()
    
    def show_quantity_dialog(self):
        """แสดง Dialog สำหรับใส่จำนวนยาที่ต้องการเบิก"""
        from kivymd.uix.textfield import MDTextField
        
        max_can_dispense = self.selected_product["quantity"]
        
        # สร้าง TextField สำหรับใส่จำนวน
        self.quantity_input = MDTextField(
            hint_text="Enter quantity to dispense",
            helper_text=f"Available: {max_can_dispense} units",
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
            height=dp(200)
        )
        
        # Header
        header_label = MDLabel(
            text=f"Dispense from Slot {self.selected_slot['slot']}",
            font_style="Subtitle1",
            bold=True,
            size_hint_y=None,
            height=dp(30)
        )
        
        # Product info
        product_label = MDLabel(
            text=f"Product: {self.selected_product['name']}",
            font_style="Body2",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(25)
        )
        
        # Product ID
        id_label = MDLabel(
            text=f"ID: {self.selected_product['id']}",
            font_style="Caption",
            theme_text_color="Hint",
            size_hint_y=None,
            height=dp(20)
        )
        
        content_box.add_widget(header_label)
        content_box.add_widget(product_label)
        content_box.add_widget(id_label)
        content_box.add_widget(self.quantity_input)
        
        self.quantity_dialog = MDDialog(
            title="Dispense Medicine",
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
                    text_color=(0.52, 0.6, 0.85, 1),
                    on_release=lambda x: self.validate_and_add_to_cart()
                ),
            ],
        )
        
        self.quantity_dialog.open()
    
    def validate_and_add_to_cart(self):
        """ตรวจสอบจำนวนและเพิ่มเข้าตะกร้า"""
        try:
            quantity = int(self.quantity_input.text)
            max_can_dispense = self.selected_product["quantity"]
            
            if quantity <= 0:
                self.quantity_input.error = True
                self.quantity_input.helper_text = "Quantity must be greater than 0"
                return
            
            if quantity > max_can_dispense:
                self.quantity_input.error = True
                self.quantity_input.helper_text = f"Insufficient stock! Available: {max_can_dispense}"
                return
            
            # เพิ่มรายการเข้าตะกร้า
            self.add_to_cart(
                slot=self.selected_slot["slot"],
                product_id=self.selected_product["id"],
                product_name=self.selected_product["name"],
                quantity=quantity
            )
            
            # ปิด Dialog
            self.quantity_dialog.dismiss()
            
        except ValueError:
            self.quantity_input.error = True
            self.quantity_input.helper_text = "Please enter a valid number"
    
    def add_to_cart(self, slot, product_id, product_name, quantity):
        """เพิ่มรายการเข้าตะกร้าเบิก"""
        # ตรวจสอบว่ามีรายการซ้ำไหม (slot + product_id เดียวกัน)
        for item in self.dispense_cart_items:
            if item["slot"] == slot and item["product_id"] == product_id:
                print("Item already in cart!")
                return
        
        # เพิ่มรายการใหม่
        cart_item = {
            "slot": slot,
            "product_id": product_id,
            "product_name": product_name,
            "quantity": quantity
        }
        self.dispense_cart_items.append(cart_item)
        
        # สร้าง Widget สำหรับแสดงในตะกร้า
        item_widget = DispenseCartItemWidget(
            slot_number=slot,
            product_id=product_id,
            product_name=product_name,
            quantity=str(quantity),
            edit_callback=lambda: self.edit_cart_item(cart_item, item_widget),
            delete_callback=lambda: self.remove_from_cart(item_widget, cart_item)
        )
        
        self.ids.dispense_cart_list.add_widget(item_widget)
        
        # อัพเดทจำนวนในตะกร้า
        self.update_cart_summary()
        
        print(f"Added {quantity} units of {product_name} (ID: {product_id}) from slot {slot} to cart")
    
    def remove_from_cart(self, widget, cart_item):
        """ลบรายการออกจากตะกร้า"""
        self.ids.dispense_cart_list.remove_widget(widget)
        self.dispense_cart_items.remove(cart_item)
        
        self.update_cart_summary()
        print(f"Removed {cart_item['product_name']} from cart")
    
    def edit_cart_item(self, cart_item, widget):
        """แก้ไขรายการในตะกร้า"""
        from kivymd.uix.textfield import MDTextField
        
        # หา product ในช่อง
        slot_info = None
        product_info = None
        
        for slot in self.slots_data:
            if slot["slot"] == cart_item["slot"]:
                slot_info = slot
                for product in slot["products"]:
                    if product["id"] == cart_item["product_id"]:
                        product_info = product
                        break
                break
        
        if not slot_info or not product_info:
            return
        
        max_can_dispense = product_info["quantity"]
        
        # สร้าง TextField พร้อมค่าเดิม
        self.edit_quantity_input = MDTextField(
            hint_text="Enter new quantity",
            text=str(cart_item["quantity"]),
            helper_text=f"Available: {max_can_dispense} units",
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
            height=dp(200)
        )
        
        header_label = MDLabel(
            text=f"Edit: Slot {cart_item['slot']}",
            font_style="Subtitle1",
            bold=True,
            size_hint_y=None,
            height=dp(30)
        )
        
        product_label = MDLabel(
            text=f"Product: {cart_item['product_name']}",
            font_style="Body2",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(25)
        )
        
        id_label = MDLabel(
            text=f"ID: {cart_item['product_id']}",
            font_style="Caption",
            theme_text_color="Hint",
            size_hint_y=None,
            height=dp(20)
        )
        
        content_box.add_widget(header_label)
        content_box.add_widget(product_label)
        content_box.add_widget(id_label)
        content_box.add_widget(self.edit_quantity_input)
        
        edit_dialog = MDDialog(
            title="Edit Dispense Quantity",
            type="custom",
            content_cls=content_box,
            buttons=[
                MDFlatButton(
                    text="CANCEL",
                    theme_text_color="Custom",
                    text_color=(0.9, 0.3, 0.3, 1),
                    on_release=lambda x: edit_dialog.dismiss()
                ),
                MDFlatButton(
                    text="SAVE",
                    theme_text_color="Custom",
                    text_color=(0.52, 0.6, 0.85, 1),
                    on_release=lambda x: self.save_edit(edit_dialog, cart_item, widget, product_info)
                ),
            ],
        )
        
        edit_dialog.open()
    
    def save_edit(self, dialog, cart_item, widget, product_info):
        """บันทึกการแก้ไข"""
        try:
            new_quantity = int(self.edit_quantity_input.text)
            max_can_dispense = product_info["quantity"]
            
            if new_quantity <= 0:
                self.edit_quantity_input.error = True
                self.edit_quantity_input.helper_text = "Quantity must be greater than 0"
                return
            
            if new_quantity > max_can_dispense:
                self.edit_quantity_input.error = True
                self.edit_quantity_input.helper_text = f"Insufficient stock! Available: {max_can_dispense}"
                return
            
            # อัพเดทข้อมูลใน cart_item
            cart_item["quantity"] = new_quantity
            
            # อัพเดท widget
            widget.quantity = str(new_quantity)
            
            dialog.dismiss()
            print(f"Updated {cart_item['product_name']} quantity to {new_quantity}")
            
        except ValueError:
            self.edit_quantity_input.error = True
            self.edit_quantity_input.helper_text = "Please enter a valid number"
    
    def update_cart_summary(self):
        """อัพเดทข้อมูลสรุปในตะกร้า"""
        total_items = len(self.dispense_cart_items)
        self.ids.dispense_cart_count_badge.text = f"{total_items} list{'s' if total_items != 1 else ''}"
        self.ids.dispense_total_items_label.text = f"{total_items} total"
    
    def confirm_dispense(self):
        """ยืนยันการเบิกยา"""
        if not self.dispense_cart_items:
            print("Dispense cart is empty!")
            return
        
        print("=== Dispense Confirmation ===")
        for item in self.dispense_cart_items:
            print(f"Slot: {item['slot']}, Product ID: {item['product_id']}, Name: {item['product_name']}, Quantity: {item['quantity']}")
        print("============================")
        
        # อัพเดทข้อมูลในช่องเก็บยาหลังจากเบิก
        for item in self.dispense_cart_items:
            for slot in self.slots_data:
                if slot["slot"] == item["slot"]:
                    for product in slot["products"]:
                        if product["id"] == item["product_id"]:
                            product["quantity"] -= item["quantity"]
                            if product["quantity"] < 0:
                                product["quantity"] = 0
                            break
                    break
        
        # TODO: ส่งข้อมูลไปยัง backend หรือ database
        
        # Rebuild slots grid เพื่อแสดงข้อมูลใหม่
        self.build_slots_grid()
        
        # Clear cart
        self.ids.dispense_cart_list.clear_widgets()
        self.dispense_cart_items.clear()
        self.update_cart_summary()
        
        print("Dispense completed successfully!")