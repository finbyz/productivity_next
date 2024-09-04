import re, frappe, os
from frappe.model.document import Document
from PIL import Image, ImageFilter, UnidentifiedImageError

class ScreenScreenshotLog(Document):
    def after_insert(self):
        if not self.blurred_screenshot and self.screenshot and self.project:
            self.blurred_screenshot = self.create_blurred_image()
            
    def validate(self):
        if not self.ip_address:
            self.ip_address = re.search(r"^(.+)", frappe.get_request_header("X-Forwarded-For", str(frappe.request.headers))).group(1)
            
    def create_blurred_image(self, blur_radius=5, max_width=400, max_height=300, quality=20):
        try:
            file_path = frappe.get_site_path() + self.screenshot
            with Image.open(file_path) as img:
                img.thumbnail((max_width, max_height))
                blurred_image = img.filter(ImageFilter.GaussianBlur(blur_radius))
                
                file_name, ext = os.path.splitext(os.path.basename(self.screenshot))
                blurred_file_name = f"{file_name}_blurred.jpg"
                blurred_file_path = os.path.join("public", "files", blurred_file_name)
                full_blurred_path = frappe.get_site_path(blurred_file_path)
                
                # Save with reduced quality and optimize
                blurred_image.save(full_blurred_path, format="JPEG", quality=quality, optimize=True)
                
                file_url = f"/files/{blurred_file_name}"
                frappe.get_doc({
                    'doctype': 'File',
                    'file_name': blurred_file_name,
                    'is_private': 0,
                    'file_url': file_url,
                    'folder': 'Home/Attachments'
                }).insert()
                
                return file_url
        except (UnidentifiedImageError, Exception) as e:
            frappe.log_error(f"Image Processing Error: {str(e)}")
        return None


    def on_update(self):
        if self.screenshot and self.name:
            folder = "Home/private" if self.screenshot.startswith("/private/") else "Home"
            if name := frappe.db.get_value("File", filters={"folder": folder, "file_url": self.screenshot}, fieldname="name"):
                frappe.db.set_value("File", name, {
                    "attached_to_doctype": "Screen Screenshot Log",
                    "attached_to_field": "screenshot",
                    "attached_to_name": self.name
                }, update_modified=False)

def on_doctype_update():
    frappe.db.add_unique("Screen Screenshot Log", ["employee", "time"])
    frappe.db.add_index("Screen Screenshot Log", ["employee", "time"])