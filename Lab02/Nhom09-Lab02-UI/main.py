import customtkinter as ctk
from api_client import OpenStackAPI
from ui import LoginFrame, DashboardFrame

ctk.set_appearance_mode("Light")  # Chuyển mặc định sang nền Sáng
ctk.set_default_color_theme("blue")

class OpenStackApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("NT533.Q21 - Nhóm 09 - Lab 02: OpenStack API")
        
        # Khởi tạo đối tượng API (Chỉ tạo 1 lần và truyền đi khắp nơi)
        self.api = OpenStackAPI()

        # Bắt đầu ứng dụng bằng màn hình Login
        self.show_login()

    def set_window_size(self, width, height):
        """Hàm hỗ trợ: Tự động đổi kích thước và canh giữa cửa sổ trên màn hình"""
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        x_pos = int((screen_width / 2) - (width / 2))
        y_pos = int((screen_height / 2) - (height / 2))
        
        self.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

    def show_login(self):
        """Hiển thị màn hình Đăng nhập"""
        # 1. Dọn dẹp màn hình cũ (nếu có)
        for widget in self.winfo_children():
            widget.destroy()
            
        # 2. Đổi kích thước cửa sổ cho nhỏ gọn vừa form đăng nhập
        self.set_window_size(450, 600)

        # 3. Gọi LoginFrame và truyền các thông số cần thiết
        self.login_view = LoginFrame(
            master=self, 
            api_client=self.api, 
            on_login_success=self.show_dashboard  # Kích hoạt show_dashboard khi đăng nhập xong
        )
        self.login_view.place(relx=0.5, rely=0.5, anchor=ctk.CENTER)

    def show_dashboard(self):
        """Hiển thị màn hình Dashboard chính"""
        # 1. Dọn dẹp màn hình Đăng nhập
        for widget in self.winfo_children():
            widget.destroy()
            
        # 2. Mở rộng kích thước cửa sổ để chứa bảng điều khiển
        self.set_window_size(1200, 800)

        # 3. Gọi DashboardFrame
        self.dashboard_view = DashboardFrame(
            master=self, 
            api_client=self.api, 
            on_logout=self.show_login  # Kích hoạt show_login khi bấm Sign Out
        )
        self.dashboard_view.pack(fill="both", expand=True)

# Lệnh khởi chạy ứng dụng
if __name__ == "__main__":
    app = OpenStackApp()
    app.mainloop()