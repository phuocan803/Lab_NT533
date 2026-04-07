import customtkinter as ctk
from tkinter import messagebox

class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, api_client, on_login_success):
        # Khởi tạo một khung chữ nhật kích thước 400x500
        super().__init__(master, width=400, height=500, corner_radius=15)
        
        self.api_client = api_client
        self.on_login_success = on_login_success

        self.setup_ui()

    def setup_ui(self):
        """Hàm dùng để vẽ các thành phần giao diện lên khung"""
        
        # Tiêu đề Form
        ctk.CTkLabel(self, text="Đăng nhập vào OpenStack", font=ctk.CTkFont(size=24, weight="bold")).place(relx=0.5, rely=0.1, anchor=ctk.CENTER)

        # 1. Khu vực Username
        ctk.CTkLabel(self, text="Username", font=ctk.CTkFont(size=14), text_color="#000000").place(relx=0.5, x=-150, rely=0.3, anchor="w")
        self.entry_user = ctk.CTkEntry(self, width=300)
        self.entry_user.place(relx=0.5, rely=0.36, anchor=ctk.CENTER)
        
        # 2. Khu vực Password
        ctk.CTkLabel(self, text="Password", font=ctk.CTkFont(size=14), text_color="#000000").place(relx=0.5, x=-150, rely=0.46, anchor="w")
        self.entry_pass = ctk.CTkEntry(self, width=300, show="*")
        self.entry_pass.place(relx=0.5, rely=0.52, anchor=ctk.CENTER)

        # Hàm xử lý ẩn/hiện mật khẩu
        def toggle_password():
            if self.entry_pass.cget('show') == '*':
                self.entry_pass.configure(show='')
                self.btn_show_pass.configure(text='Ẩn')
            else:
                self.entry_pass.configure(show='*')
                self.btn_show_pass.configure(text='Hiện')

        # Nút Ẩn/Hiện đặt đè lên góc phải của ô nhập mật khẩu
        self.btn_show_pass = ctk.CTkButton(self, text="Hiện", width=40, height=20, 
                                           fg_color="#FFFFFF", text_color="#E95420", 
                                           hover_color="#444444", command=toggle_password)
        self.btn_show_pass.place(relx=0.5, x=125, rely=0.52, anchor=ctk.CENTER)

        # 3. Khu vực Project
        ctk.CTkLabel(self, text="Project Name", font=ctk.CTkFont(size=14), text_color="#000000").place(relx=0.5, x=-150, rely=0.62, anchor="w")
        self.entry_proj = ctk.CTkEntry(self, width=300)
        self.entry_proj.place(relx=0.5, rely=0.68, anchor=ctk.CENTER)

        # Giá trị điền sẵn (hỗ trợ test)
        self.entry_proj.insert(0, "NT533.Q21.G9")

        # Nút Đăng nhập
        self.btn_login = ctk.CTkButton(self, text="Đăng nhập", width=300, height=40, fg_color="#E95420", hover_color="#d6491b", command=self.do_login)
        self.btn_login.place(relx=0.5, rely=0.82, anchor=ctk.CENTER)

    def do_login(self):
        """Hàm lấy dữ liệu và gọi API xác thực"""
        user = self.entry_user.get()
        pwd = self.entry_pass.get()
        proj = self.entry_proj.get()

        if not user or not pwd or not proj:
            messagebox.showerror("Lỗi", "Vui lòng nhập đủ thông tin!")
            return

        # Vô hiệu hóa nút và đổi chữ trong khi đợi mạng
        self.btn_login.configure(state="disabled", text="Đang kết nối...")
        self.update()

        try:
            # Gọi hàm login từ lớp api_client (Không còn dùng requests ở đây nữa)
            self.api_client.login(user, pwd, proj)
            
            # Nếu chạy thành công mà không có lỗi (Exception), chuyển sang Dashboard
            self.on_login_success()
            
        except Exception as e:
            # Nếu API báo lỗi (Sai pass, CORS...), báo lỗi và mở khóa nút
            messagebox.showerror("Lỗi Đăng nhập", str(e))
            self.btn_login.configure(state="normal", text="Sign In")