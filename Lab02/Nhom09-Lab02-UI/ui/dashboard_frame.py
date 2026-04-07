import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading
import requests
import base64
import time
import ipaddress
from datetime import datetime

try:
    from config import API_ENDPOINTS
except ImportError:
    API_ENDPOINTS = {
        "compute": "https://cloud-compute.uitiot.vn/v2.1",
        "network": "https://cloud-network.uitiot.vn",
        "image": "https://cloud-image.uitiot.vn",
        "loadbalancer": "https://cloud-loadbalancer.uitiot.vn",
    }

class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master, api_client, on_logout):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        
        self.api = api_client
        self.on_logout = on_logout

        self.cache_images = {}
        self.cache_flavors = {}
        self.cache_networks = {}
        self.cache_keypairs = {}
        
        self.current_pool_id = None
        self.current_subnet_id = None

        self.setup_ui()
        
        self.switch_tab("overview", self.btn_overview)
        threading.Thread(target=self.preload_data, daemon=True).start()

    # =====================================================================
    # HÀM BỌC API & TIỆN ÍCH
    # =====================================================================
    def get_ep(self, service_name):
        ep = API_ENDPOINTS[service_name].rstrip('/')
        # Tự động làm sạch URL nếu file config.py lỡ ghi thừa đuôi /v2.0/lbaas
        if service_name == 'loadbalancer' and '/v2' in ep:
            ep = ep.split('/v2')[0]
        return ep

    def _api_get(self, url):
        res = requests.get(url, headers=self.api.get_headers())
        if res.status_code >= 400: raise Exception(f"HTTP {res.status_code} tại {url}\nPhản hồi: {res.text[:100]}")
        try: return res.json()
        except ValueError: raise Exception(f"Lỗi JSON tại {url}")

    def _api_post(self, url, payload):
        res = requests.post(url, headers=self.api.get_headers(), json=payload)
        if res.status_code >= 400: raise Exception(f"HTTP {res.status_code} tại {url}\nPhản hồi: {res.text[:100]}")
        try: return res.json()
        except ValueError: return {}

    def _api_put(self, url, payload):
        res = requests.put(url, headers=self.api.get_headers(), json=payload)
        if res.status_code >= 400: raise Exception(f"HTTP {res.status_code} tại {url}\nPhản hồi: {res.text[:100]}")
        try: return res.json()
        except ValueError: return {}

    def _api_delete(self, url):
        res = requests.delete(url, headers=self.api.get_headers())
        if res.status_code >= 400: raise Exception(f"HTTP {res.status_code} tại {url}\nPhản hồi: {res.text[:100]}")
        return True

    def _wait_vm_active(self, server_id, timeout=120):
        start = time.time()
        while time.time() - start < timeout:
            res = requests.get(f"{self.get_ep('compute')}/{self.api.project_id}/servers/{server_id}", headers=self.api.get_headers())
            if res.status_code == 200:
                server_info = res.json()["server"]
                status = server_info["status"]
                if status == "ACTIVE": return True
                if status == "ERROR":
                    fault_msg = server_info.get("fault", {}).get("message", "Lỗi không xác định từ hệ thống OpenStack.")
                    raise Exception(f"Trạng thái máy ảo: ERROR\n📌 Chi tiết lỗi: {fault_msg}")
            time.sleep(5)
        raise Exception("Timeout khi chờ VM ACTIVE")

    # =====================================================================
    # GIAO DIỆN CHÍNH (UI)
    # =====================================================================
    def setup_ui(self):
        # 1. TOPBAR
        self.topbar = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color="#E95420")
        self.topbar.pack(side="top", fill="x")
        header_text = ctk.CTkLabel(self.topbar, text="⨀ OpenStack API", font=ctk.CTkFont(size=18, weight="bold"), text_color="white")
        header_text.pack(side="left", padx=20, pady=10)
        ctk.CTkLabel(self.topbar, text=f"🏢 {self.api.project_id}", font=ctk.CTkFont(size=14), text_color="white").pack(side="left", padx=30)

        ctk.CTkButton(self.topbar, text="Đăng xuất", fg_color="transparent", border_width=1, border_color="white", text_color="white", hover_color="#d6491b", command=self.do_logout).pack(side="right", padx=20, pady=10)
        
        # init_theme_btn = "🌙 Dark Mode" if ctk.get_appearance_mode() == "Light" else "☀️ Light Mode"
        # self.btn_theme = ctk.CTkButton(self.topbar, text=init_theme_btn, width=110, fg_color="transparent", border_width=1, border_color="white", text_color="white", hover_color="#d6491b", command=self.toggle_theme)
        # self.btn_theme.pack(side="right", padx=10, pady=10)
        
        ctk.CTkLabel(self.topbar, text=f"👤 {self.api.username}", text_color="white").pack(side="right", padx=10, pady=10)

        # 2. SIDEBAR
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=("#FFFFFF", "#2A2A2A"))
        self.sidebar.pack(side="left", fill="y")
        
        # ctk.CTkLabel(self.sidebar, text="Project", font=ctk.CTkFont(weight="bold", size=16), text_color=("#333", "white")).pack(anchor="w", padx=15, pady=(20, 5))
        # ctk.CTkLabel(self.sidebar, text="API Access", font=ctk.CTkFont(size=13), text_color="gray").pack(anchor="w", padx=30, pady=2)
        
        ctk.CTkLabel(self.sidebar, text="Compute ˅", font=ctk.CTkFont(weight="bold", size=14), text_color=("#333", "white")).pack(anchor="w", padx=20, pady=(15, 5))
        
        self.btn_overview = ctk.CTkButton(self.sidebar, text="Overview", anchor="w", fg_color="transparent", text_color=("#333", "white"), command=lambda: self.switch_tab("overview", self.btn_overview))
        self.btn_overview.pack(fill="x", padx=25, pady=1)

        self.btn_instances = ctk.CTkButton(self.sidebar, text="Instances", anchor="w", fg_color="transparent", text_color=("#333", "white"), command=lambda: self.switch_tab("instances", self.btn_instances))
        self.btn_instances.pack(fill="x", padx=25, pady=1)

        self.btn_images = ctk.CTkButton(self.sidebar, text="Images", anchor="w", fg_color="transparent", text_color=("#333", "white"), command=lambda: self.switch_tab("images", self.btn_images))
        self.btn_images.pack(fill="x", padx=25, pady=1)

        self.btn_flavors = ctk.CTkButton(self.sidebar, text="Flavors", anchor="w", fg_color="transparent", text_color=("#333", "white"), command=lambda: self.switch_tab("flavors", self.btn_flavors))
        self.btn_flavors.pack(fill="x", padx=25, pady=1)

        self.btn_keypairs = ctk.CTkButton(self.sidebar, text="Key Pairs", anchor="w", fg_color="transparent", text_color=("#333", "white"), command=lambda: self.switch_tab("keypairs", self.btn_keypairs))
        self.btn_keypairs.pack(fill="x", padx=25, pady=1)

        self.btn_servergroups = ctk.CTkButton(self.sidebar, text="Server Groups", anchor="w", fg_color="transparent", text_color=("#333", "white"), command=lambda: self.switch_tab("placeholder", self.btn_servergroups))
        self.btn_servergroups.pack(fill="x", padx=25, pady=1)

        ctk.CTkLabel(self.sidebar, text="Network ˅", font=ctk.CTkFont(weight="bold", size=14), text_color=("#333", "white")).pack(anchor="w", padx=20, pady=(15, 5))

        self.btn_networks = ctk.CTkButton(self.sidebar, text="Networks", anchor="w", fg_color="transparent", text_color=("#333", "white"), command=lambda: self.switch_tab("networks", self.btn_networks))
        self.btn_networks.pack(fill="x", padx=25, pady=1)

        self.btn_routers = ctk.CTkButton(self.sidebar, text="Routers", anchor="w", fg_color="transparent", text_color=("#333", "white"), command=lambda: self.switch_tab("routers", self.btn_routers))
        self.btn_routers.pack(fill="x", padx=25, pady=1)

        # self.btn_sec_groups = ctk.CTkButton(self.sidebar, text="Security Groups", anchor="w", fg_color="transparent", text_color=("#333", "white"), command=lambda: self.switch_tab("placeholder", self.btn_sec_groups))
        # self.btn_sec_groups.pack(fill="x", padx=25, pady=1)

        self.btn_lbs = ctk.CTkButton(self.sidebar, text="Load Balancers", anchor="w", fg_color="transparent", text_color=("#333", "white"), command=lambda: self.switch_tab("lb", self.btn_lbs))
        self.btn_lbs.pack(fill="x", padx=25, pady=1)

        self.btn_fips = ctk.CTkButton(self.sidebar, text="Floating IPs", anchor="w", fg_color="transparent", text_color=("#333", "white"), command=lambda: self.switch_tab("fips", self.btn_fips))
        self.btn_fips.pack(fill="x", padx=25, pady=1)

        self.sidebar_buttons = [
            self.btn_overview, self.btn_instances, self.btn_images, self.btn_flavors,
            self.btn_keypairs, self.btn_networks, self.btn_routers, 
            self.btn_lbs, self.btn_fips
        ]

        # 3. MAIN CONTENT
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.pack(side="right", fill="both", expand=True)

        self.tab_container = ctk.CTkScrollableFrame(self.main_content, fg_color="transparent")
        self.tab_container.pack(side="top", fill="both", expand=True, padx=20, pady=10)

        # 4. LOG CONSOLE
        log_frame = ctk.CTkFrame(self.main_content, height=150, corner_radius=10, fg_color="transparent")
        log_frame.pack(fill="x", side="bottom", padx=20, pady=(0, 20))
        ctk.CTkLabel(log_frame, text=">_ System Logs", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=2)
        self.log_box = ctk.CTkTextbox(log_frame, height=120, font=("Courier", 12), text_color=("#008800", "#00FF00"), fg_color=("#E8E8E8", "#111111"))
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def toggle_theme(self):
        if ctk.get_appearance_mode() == "Dark":
            ctk.set_appearance_mode("Light")
            self.btn_theme.configure(text="🌙 Dark Mode")
        else:
            ctk.set_appearance_mode("Dark")
            self.btn_theme.configure(text="☀️ Light Mode")
        if hasattr(self, 'current_tab') and self.current_tab == "overview":
            self.switch_tab("overview", getattr(self, 'current_btn', None))

    def log(self, msg, is_error=False):
        prefix = "[ERROR] " if is_error else "[INFO] "
        time_str = time.strftime("%H:%M:%S")
        self.log_box.insert("end", f"{time_str} {prefix}{msg}\n")
        self.log_box.see("end")

    def do_logout(self):
        self.api.logout()
        self.on_logout()

    def switch_tab(self, tab_name, active_btn=None):
        self.current_tab = tab_name
        if active_btn is not None:
            self.current_btn = active_btn
            
        for widget in self.tab_container.winfo_children(): widget.destroy()
        
        for btn in getattr(self, 'sidebar_buttons', []):
            btn.configure(fg_color="transparent", text_color=("#333333", "white"), font=ctk.CTkFont(weight="normal"))

        if hasattr(self, 'current_btn') and self.current_btn:
            self.current_btn.configure(fg_color=("#EBEBEB", "#444444"), font=ctk.CTkFont(weight="bold"))

        # Gọi View tương ứng
        if tab_name == "overview": self.render_overview_tab(self.tab_container)
        elif tab_name == "images": self.render_images_tab(self.tab_container)
        elif tab_name == "flavors": self.render_flavors_tab(self.tab_container)
        elif tab_name == "instances": self.render_instances_tab(self.tab_container)
        elif tab_name == "keypairs": self.render_keypairs_tab(self.tab_container)
        elif tab_name == "networks": self.render_networks_tab(self.tab_container)
        elif tab_name == "routers": self.render_routers_tab(self.tab_container)
        elif tab_name == "fips": self.render_fips_tab(self.tab_container)
        elif tab_name == "lb": self.render_lb_tab(self.tab_container)
        elif tab_name == "placeholder":
            ctk.CTkLabel(self.tab_container, text="⚙️ Tính năng này đang được phát triển...", font=ctk.CTkFont(size=20, slant="italic"), text_color="gray").pack(pady=50)

    def preload_data(self):
        try:
            imgs = self._api_get(f"{self.get_ep('image')}/v2/images").get("images", [])
            self.cache_images = {i['id']: i['name'] for i in imgs}
            
            flvs = self._api_get(f"{self.get_ep('compute')}/{self.api.project_id}/flavors/detail").get("flavors", [])
            self.cache_flavors = {f['id']: f"{f['name']} ({f.get('vcpus', 0)} vCPU - {f.get('ram', 0)}MB RAM)" for f in flvs}

            nets = self._api_get(f"{self.get_ep('network')}/v2.0/networks").get("networks", [])
            self.cache_networks = {n['name']: n['id'] for n in nets}
            self.cache_ext_networks = {n['name']: n['id'] for n in nets if n.get("router:external")}

            # CẬP NHẬT: Tải danh sách Subnet để làm Interface cho Router
            subs = self._api_get(f"{self.get_ep('network')}/v2.0/subnets").get("subnets", [])
            self.cache_subnets = {f"{s['name']} ({s['cidr']})": s['id'] for s in subs}

            kps = self._api_get(f"{self.get_ep('compute')}/{self.api.project_id}/os-keypairs").get("keypairs", [])
            self.cache_keypairs = {k['keypair']['name']: k['keypair']['name'] for k in kps}
        except Exception as e:
            self.log(f"Lỗi preload data: {e}", True)

    # =====================================================================
    # HELPER: VẼ BẢNG (TABLE) TỰ ĐỘNG
    # =====================================================================
    def _draw_table_ui(self, container, headers, data, widths, checkable=False, selected_vars=None):
        for widget in container.winfo_children(): widget.destroy()

        header_frame = ctk.CTkFrame(container, fg_color=("#F5F5F5", "#333333"), corner_radius=0)
        header_frame.pack(fill="x")
        
        for col_idx, (head, w) in enumerate(zip(headers, widths)):
            if checkable and col_idx == 0:
                ctk.CTkLabel(header_frame, text="", width=w).grid(row=0, column=col_idx, padx=10, pady=8)
            else:
                ctk.CTkLabel(header_frame, text=head, font=ctk.CTkFont(weight="bold", size=13), width=w, anchor="w").grid(row=0, column=col_idx, padx=10, pady=8)

        if not data:
            ctk.CTkLabel(container, text="Displaying 0 items", text_color="gray", pady=20).pack()
            return

        for row_data in data:
            row_frame = ctk.CTkFrame(container, fg_color="transparent", corner_radius=0)
            row_frame.pack(fill="x")
            
            for col_idx, (cell_val, w) in enumerate(zip(row_data, widths)):
                if checkable and col_idx == 0:
                    var = selected_vars[cell_val]
                    cb = ctk.CTkCheckBox(row_frame, text="", variable=var, onvalue="on", offvalue="off", width=20, checkbox_width=18, checkbox_height=18)
                    cb.grid(row=0, column=col_idx, padx=10, pady=8)
                else:
                    is_name_col = (col_idx == 1 if checkable else col_idx == 0)
                    text_color = "#E95420" if is_name_col else ("#333333", "#CCCCCC")
                    ctk.CTkLabel(row_frame, text=str(cell_val), width=w, anchor="w", font=ctk.CTkFont(size=13), text_color=text_color).grid(row=0, column=col_idx, padx=10, pady=8)
            
            ctk.CTkFrame(container, height=1, fg_color=("#E5E5E5", "#444444")).pack(fill="x")
        
        ctk.CTkLabel(container, text=f"Displaying {len(data)} items", text_color="gray", anchor="w").pack(anchor="w", pady=10, padx=10)

    # =====================================================================
    # TAB 0: OVERVIEW
    # =====================================================================
    def create_pie_chart(self, parent, used, total, unit, label_text):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        bg_color = "#EBEBEB" if ctk.get_appearance_mode() == "Light" else "#242424"
        canvas = tk.Canvas(frame, width=130, height=130, bg=bg_color, highlightthickness=0)
        canvas.pack(pady=(0, 10))
        canvas.create_arc(15, 15, 115, 115, start=0, extent=359.99, outline="#D3D3D3", width=20, style="arc")
        if total > 0:
            percentage = used / total
            extent = -(percentage * 359.99)
            if extent != 0: canvas.create_arc(15, 15, 115, 115, start=90, extent=extent, outline="#E95420", width=20, style="arc")
        
        ctk.CTkLabel(frame, text=label_text, font=ctk.CTkFont(size=14)).pack()
        ctk.CTkLabel(frame, text=f"Used {used}{unit} of {total}{unit}" if unit else f"Used {used} of {total}", font=ctk.CTkFont(size=12), text_color="gray").pack()
        return frame

    def render_overview_tab(self, parent):
        ctk.CTkLabel(parent, text="Project / Compute / Overview", text_color="gray", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(parent, text="Overview", font=ctk.CTkFont(size=32, weight="normal"), text_color=("#333", "white")).pack(anchor="w", pady=(0, 20))
        ctk.CTkLabel(parent, text="Limit Summary", font=ctk.CTkFont(size=22, weight="normal"), text_color=("#333", "white")).pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(parent, text="Compute", font=ctk.CTkFont(size=16), text_color=("#333", "white")).pack(anchor="w", pady=(0, 10))
        self.charts_container = ctk.CTkFrame(parent, fg_color="transparent")
        self.charts_container.pack(fill="x", pady=10)
        
        self.lbl_loading = ctk.CTkLabel(self.charts_container, text="Đang tải dữ liệu...", font=ctk.CTkFont(slant="italic"))
        self.lbl_loading.pack(pady=20)
        
        threading.Thread(target=self._fetch_and_draw_limits, daemon=True).start()

    def _fetch_and_draw_limits(self):
        try:
            res = self._api_get(f"{self.get_ep('compute')}/{self.api.project_id}/limits")
            abs_limits = res.get("limits", {}).get("absolute", {})
            iu, im = abs_limits.get("totalInstancesUsed", 0), abs_limits.get("maxTotalInstances", 10)
            vu, vm = abs_limits.get("totalCoresUsed", 0), abs_limits.get("maxTotalCores", 20)
            ru, rm = abs_limits.get("totalRAMUsed", 0) // 1024, abs_limits.get("maxTotalRAMSize", 51200) // 1024
            self.after(0, lambda: self._draw_charts_ui(iu, im, vu, vm, ru, rm))
        except Exception as e:
            self.after(0, lambda: self.lbl_loading.configure(text=f"Lỗi: {e}"))

    def _draw_charts_ui(self, iu, im, vu, vm, ru, rm):
        for widget in self.charts_container.winfo_children(): widget.destroy()
        self.create_pie_chart(self.charts_container, iu, im, "", "Instances").pack(side="left", padx=(0, 60))
        self.create_pie_chart(self.charts_container, vu, vm, "", "VCPUs").pack(side="left", padx=60)
        self.create_pie_chart(self.charts_container, ru, rm, "GB", "RAM").pack(side="left", padx=60)

    # =====================================================================
    # TAB: NETWORKS (YÊU CẦU 5)
    # =====================================================================
    def render_networks_tab(self, parent):
        ctk.CTkLabel(parent, text="Project / Network / Networks & Subnets", text_color="gray", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(parent, text="Networks & Subnets", font=ctk.CTkFont(size=32, weight="normal")).pack(anchor="w", pady=(0, 15))
        
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.pack(fill="x", pady=5)
        
        def on_auto_setup_click():
            dialog = ctk.CTkInputDialog(text="Nhập tên nhóm (Ví dụ: nhom09):", title="Auto Setup Mạng & Security Group")
            group_name = dialog.get_input()
            if group_name:
                threading.Thread(target=self.action_auto_setup_req5, args=(group_name.strip(),)).start()

        ctk.CTkButton(toolbar, text="⚡ Auto Setup Network", fg_color="#8e44ad", hover_color="#732d91", command=on_auto_setup_click).pack(side="left")
        
        # --- NÚT MỚI: SETUP ĐỘC LẬP SECURITY GROUP ---
        ctk.CTkButton(toolbar, text="🛡️ Config Default SG", fg_color="#f39c12", hover_color="#d68910", command=lambda: threading.Thread(target=self.action_setup_default_sg).start()).pack(side="left", padx=5)
        
        ctk.CTkButton(toolbar, text="Delete Network & Subnet", fg_color="#D9534F", hover_color="#C9302C", command=self.action_delete_selected_networks).pack(side="right", padx=(10, 0))
        ctk.CTkButton(toolbar, text="+ Create Network & Subnet", fg_color="transparent", border_width=1, border_color="#D9534F", text_color="#D9534F", hover_color=("#FDE8E8", "#4A1A1A"), command=lambda: self.form_net.pack(fill="x", pady=10, before=self.table_net_container)).pack(side="right")
        ctk.CTkButton(toolbar, text="Refresh", width=80, fg_color="transparent", border_width=1, text_color=("#333", "white"), command=lambda: threading.Thread(target=self.fetch_networks_data).start()).pack(side="right", padx=10)

        # --- FORM TẠO NETWORK & SUBNET (MỚI) ---
        self.form_net = ctk.CTkFrame(parent, fg_color=("#EBEBEB", "#2A2A2A"), corner_radius=5)
        
        row1 = ctk.CTkFrame(self.form_net, fg_color="transparent")
        row1.pack(fill="x", pady=(10, 5), padx=10)
        ctk.CTkLabel(row1, text="Network Name *", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        self.entry_net_name = ctk.CTkEntry(row1, width=220)
        self.entry_net_name.pack(side="left", padx=5)
        ctk.CTkLabel(row1, text="Subnet Name *", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(20, 5))
        self.entry_sub_name = ctk.CTkEntry(row1, width=220)
        self.entry_sub_name.pack(side="left", padx=5)

        row2 = ctk.CTkFrame(self.form_net, fg_color="transparent")
        row2.pack(fill="x", pady=(5, 5), padx=10)
        ctk.CTkLabel(row2, text="Network Address *", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        self.entry_cidr = ctk.CTkEntry(row2, placeholder_text="VD: 192.168.1.0/24", width=220)
        self.entry_cidr.pack(side="left", padx=5)
        ctk.CTkLabel(row2, text="Gateway IP", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(20, 5))
        self.entry_gateway = ctk.CTkEntry(row2, placeholder_text="Tự động nếu để trống", width=220)
        self.entry_gateway.pack(side="left", padx=5)

        row3 = ctk.CTkFrame(self.form_net, fg_color="transparent")
        row3.pack(fill="x", pady=(5, 10), padx=10)
        
        self.disable_gw_var = ctk.BooleanVar(value=False)
        def toggle_gateway():
            if self.disable_gw_var.get():
                self.entry_gateway.configure(state="disabled")
            else:
                self.entry_gateway.configure(state="normal")
                
        self.cb_disable_gw = ctk.CTkCheckBox(row3, text="Disable Gateway", variable=self.disable_gw_var, command=toggle_gateway, text_color="#E95420")
        self.cb_disable_gw.pack(side="left", padx=5)

        ctk.CTkButton(row3, text="Đóng", fg_color="gray", command=lambda: self.form_net.pack_forget(), width=100).pack(side="right", padx=5)
        ctk.CTkButton(row3, text="Tạo Mới", fg_color="#E95420", command=lambda: threading.Thread(target=self.action_create_network).start(), width=100).pack(side="right", padx=5)

        self.table_net_container = ctk.CTkFrame(parent, fg_color="transparent")
        self.table_net_container.pack(fill="both", expand=True, pady=10)
        threading.Thread(target=self.fetch_networks_data).start()

    def action_setup_default_sg(self):
        """Hàm cài đặt độc lập 5 Rules chuẩn cho Security Group 'default'"""
        try:
            self.log("[Security Group] Đang dò tìm SG 'default' của Project...")
            sgs = self._api_get(f"{self.get_ep('network')}/v2.0/security-groups").get("security_groups", [])
            default_sg = next((sg for sg in sgs if sg["name"] == "default"), None)
            
            if not default_sg:
                self.log("Lỗi: Không tìm thấy Security Group 'default'!", True)
                self.after(0, lambda: messagebox.showwarning("Lỗi", "Không tìm thấy Security Group 'default'!"))
                return

            sg_id = default_sg["id"]
            self.log(f"[Security Group] Đã tìm thấy 'default'. Bắt đầu cấu hình 5 Rules Ingress chuẩn...")

            # Khai báo chính xác 5 Rules như trong yêu cầu hình ảnh
            rules_to_add = [
                {"protocol": "icmp", "port_range_min": None, "port_range_max": None}, # ICMP (Ping)
                {"protocol": "tcp", "port_range_min": 22, "port_range_max": 22},      # SSH
                {"protocol": "tcp", "port_range_min": 80, "port_range_max": 80},      # HTTP
                {"protocol": "tcp", "port_range_min": 3000, "port_range_max": 3000},  # Port 3000
                {"protocol": "tcp", "port_range_min": 9090, "port_range_max": 9090},  # Port 9090
            ]
            
            rule_count = 0
            for rule in rules_to_add:
                payload = {
                    "security_group_rule": {
                        "direction": "ingress",
                        "ethertype": "IPv4",
                        "remote_ip_prefix": "0.0.0.0/0",
                        "security_group_id": sg_id
                    }
                }
                if rule["protocol"]: payload["security_group_rule"]["protocol"] = rule["protocol"]
                if rule["port_range_min"]: payload["security_group_rule"]["port_range_min"] = rule["port_range_min"]
                if rule["port_range_max"]: payload["security_group_rule"]["port_range_max"] = rule["port_range_max"]

                try:
                    self._api_post(f"{self.get_ep('network')}/v2.0/security-group-rules", payload)
                    rule_count += 1
                except Exception:
                    # Nếu OpenStack báo lỗi HTTP 409 Conflict (Nghĩa là Rule này đã được thêm từ trước), ta tự động bỏ qua.
                    pass
            
            self.log(f"🚀 [Thành công] Đã cấu hình xong Tường lửa 'default'! (Thêm mới {rule_count} rules)", False)
            self.after(0, lambda: messagebox.showinfo("Hoàn tất", f"Đã cấu hình chuẩn 9 items cho Security Group 'default'!\n\nĐã đẩy lên {rule_count} rules mới.\n(Các rule có sẵn đã tự động bỏ qua)"))
            
        except Exception as e:
            self.log(f"Lỗi cấu hình Security Group: {e}", True)

    def fetch_networks_data(self):
        try:
            nets = self._api_get(f"{self.get_ep('network')}/v2.0/networks").get("networks", [])
            subs = self._api_get(f"{self.get_ep('network')}/v2.0/subnets").get("subnets", [])
            
            self.cache_networks = {n['name']: n['id'] for n in nets}
            self.cache_ext_networks = {n['name']: n['id'] for n in nets if n.get("router:external")}
            
            # CẬP NHẬT ĐỒNG BỘ: Cập nhật lại danh sách Subnets mới nhất
            self.cache_subnets = {f"{s['name']} ({s['cidr']})": s['id'] for s in subs}
            
            sub_dict = {s['id']: f"{s['name']} {s['cidr']}" for s in subs}
            
            headers = ["", "Name", "Subnets Associated", "Shared", "External", "Status", "Admin State", "Availability Zones"]
            widths = [30, 160, 250, 60, 60, 70, 90, 140]
            
            # Đưa việc tạo Biến giao diện (StringVar) và vẽ bảng về Luồng chính (Main Thread)
            def update_ui():
                self.selected_networks = {}
                data = []
                for n in nets:
                    self.selected_networks[n['id']] = ctk.StringVar(value="off")
                    associated_subs = "\n".join([sub_dict.get(sid, sid) for sid in n.get('subnets', [])])
                    if not associated_subs: associated_subs = "-"
                    shared = "Yes" if n.get("shared") else "No"
                    external = "Yes" if n.get("router:external") else "No"
                    data.append([n['id'], n['name'], associated_subs, shared, external, n.get("status", "Unknown").capitalize(), "True" if n.get("admin_state_up") else "False", ", ".join(n.get("availability_zones", [])) or "-"])
                    
                self._draw_table_ui(self.table_net_container, headers, data, widths, checkable=True, selected_vars=self.selected_networks)
                
            self.after(0, update_ui)
        except Exception as e:
            self.log(f"Lỗi tải Networks: {e}", True)

    def action_delete_selected_networks(self):
        if not hasattr(self, 'selected_networks'): return
        selected_ids = [nid for nid, var in self.selected_networks.items() if var.get() == "on"]
        if not selected_ids: 
            self.after(0, lambda: messagebox.showwarning("Cảnh báo", "Chọn ít nhất 1 Network để xóa!"))
            return
        if messagebox.askyesno("Xác nhận", f"Xóa {len(selected_ids)} Networks?"):
            threading.Thread(target=self._process_delete_networks, args=(selected_ids,)).start()

    def _process_delete_networks(self, selected_ids):
        for nid in selected_ids:
            try:
                self._api_delete(f"{self.get_ep('network')}/v2.0/networks/{nid}?cascade=true")
                self.log(f"Đã xóa Network ID: {nid}", False)
            except Exception as e:
                self.log(f"Lỗi xóa Network {nid}: {e}", True)
        self.fetch_networks_data()
        self.preload_data()

    def action_create_network(self):
        # Lấy dữ liệu và loại bỏ khoảng trắng thừa
        n_name = self.entry_net_name.get().strip()
        s_name = self.entry_sub_name.get().strip()
        cidr = self.entry_cidr.get().strip()
        gw_ip = self.entry_gateway.get().strip()
        disable_gw = self.disable_gw_var.get()
        
        if not n_name or not s_name or not cidr: 
            self.after(0, lambda: messagebox.showwarning("Lỗi", "Vui lòng nhập đủ các trường bắt buộc có dấu * (Name, Subnet, Address)"))
            return
            
        try:
            # Kiểm tra tính hợp lệ của dải IP và Gateway (nếu có)
            ipaddress.IPv4Network(cidr)
            if gw_ip and not disable_gw:
                ipaddress.IPv4Address(gw_ip)
        except ValueError as e:
            self.after(0, lambda err=e: messagebox.showwarning("Lỗi nhập liệu", f"Định dạng dải IP (Network Address) hoặc Gateway không hợp lệ!\nChi tiết: {err}\n\n💡 Gợi ý: Số cuối cùng của dải mạng thường phải là số 0\n(Ví dụ đúng: 192.168.10.0/24)"))
            return

        try:
            self.log(f"Khởi tạo Network '{n_name}'...")
            net_res = self._api_post(f"{self.get_ep('network')}/v2.0/networks", {"network": {"name": n_name, "admin_state_up": True}})
            net_id = net_res["network"]["id"]
            
            # Cấu hình Payload cho Subnet
            sub_payload = {
                "name": s_name, 
                "network_id": net_id, 
                "ip_version": 4, 
                "cidr": cidr
            }
            
            # Xử lý Gateway
            if disable_gw:
                sub_payload["gateway_ip"] = None  # None sẽ disable gateway trên OpenStack
            elif gw_ip:
                sub_payload["gateway_ip"] = gw_ip # Nếu nhập tay thì dùng IP này
            # Nếu để trống (gw_ip=="") và không tick Disable, OpenStack tự lấy IP đầu tiên (VD: .1)

            self._api_post(f"{self.get_ep('network')}/v2.0/subnets", {
                "subnet": sub_payload
            })
            self.log("Đã tạo xong Network và Subnet!", False)
            
            # Đóng form và Reset chữ trên Luồng chính
            self.after(0, self.form_net.pack_forget)
            self.after(0, lambda: self.entry_net_name.delete(0, 'end'))
            self.after(0, lambda: self.entry_sub_name.delete(0, 'end'))
            self.after(0, lambda: self.entry_cidr.delete(0, 'end'))
            self.after(0, lambda: self.entry_gateway.delete(0, 'end'))
            self.after(0, lambda: self.disable_gw_var.set(False))
            self.after(0, lambda: self.entry_gateway.configure(state="normal"))
            
            self.fetch_networks_data()
            self.preload_data()
        except Exception as e:
            self.log(f"Lỗi tạo Network: {e}", True)

    def action_auto_setup_req5(self, group_name):
        try:
            # ================= 1. TẠO MẠNG VÀ ĐỊNH TUYẾN =================
            self.log(f"1. Tạo Network '{group_name}_net'...")
            net_res = self._api_post(f"{self.get_ep('network')}/v2.0/networks", {"network": {"name": f"{group_name}_net", "admin_state_up": True}})
            net_id = net_res["network"]["id"]

            self.log(f"2. Tạo Subnet '{group_name}_subnet' (192.168.10.0/24) kèm Gateway 192.168.10.1...")
            sub_res = self._api_post(f"{self.get_ep('network')}/v2.0/subnets", {
                "subnet": {
                    "name": f"{group_name}_subnet", 
                    "network_id": net_id, 
                    "ip_version": 4, 
                    "cidr": "192.168.10.0/24", 
                    "gateway_ip": "192.168.10.1", 
                    "dns_nameservers": ["8.8.8.8"]
                }
            })
            sub_id = sub_res["subnet"]["id"]
            self.current_subnet_id = sub_id 

            self.log("3. Tìm External Network...")
            nets = self._api_get(f"{self.get_ep('network')}/v2.0/networks").get("networks", [])
            ext_net = next((n for n in nets if n.get("router:external")), None)
            if not ext_net: raise Exception("Không tìm thấy mạng External (Public)!")

            self.log(f"4. Tạo Router '{group_name}_router' và cắm ra External...")
            router_res = self._api_post(f"{self.get_ep('network')}/v2.0/routers", {
                "router": {"name": f"{group_name}_router", "admin_state_up": True, "external_gateway_info": {"network_id": ext_net["id"]}}
            })
            router_id = router_res["router"]["id"]

            self.log(f"5. Nối Router vào mạng nội bộ '{group_name}_subnet'...")
            self._api_put(f"{self.get_ep('network')}/v2.0/routers/{router_id}/add_router_interface", {"subnet_id": sub_id})

            # ================= 2. THIẾT LẬP SECURITY GROUP =================
            self.log("6. Đang cấu hình Security Group 'default'...")
            sgs = self._api_get(f"{self.get_ep('network')}/v2.0/security-groups").get("security_groups", [])
            default_sg = next((sg for sg in sgs if sg["name"] == "default"), None)
            
            if default_sg:
                sg_id = default_sg["id"]
                # Cấu hình 5 Rules như trong ảnh yêu cầu
                rules_to_add = [
                    {"protocol": "icmp", "port_range_min": None, "port_range_max": None}, # Ping
                    {"protocol": "tcp", "port_range_min": 22, "port_range_max": 22},      # SSH
                    {"protocol": "tcp", "port_range_min": 80, "port_range_max": 80},      # HTTP
                    {"protocol": "tcp", "port_range_min": 3000, "port_range_max": 3000},  # Port 3000
                    {"protocol": "tcp", "port_range_min": 9090, "port_range_max": 9090},  # Port 9090
                ]
                
                rule_count = 0
                for rule in rules_to_add:
                    payload = {
                        "security_group_rule": {
                            "direction": "ingress",
                            "ethertype": "IPv4",
                            "remote_ip_prefix": "0.0.0.0/0",
                            "security_group_id": sg_id
                        }
                    }
                    if rule["protocol"]: payload["security_group_rule"]["protocol"] = rule["protocol"]
                    if rule["port_range_min"]: payload["security_group_rule"]["port_range_min"] = rule["port_range_min"]
                    if rule["port_range_max"]: payload["security_group_rule"]["port_range_max"] = rule["port_range_max"]

                    try:
                        self._api_post(f"{self.get_ep('network')}/v2.0/security-group-rules", payload)
                        rule_count += 1
                    except Exception:
                        # Bỏ qua nếu Rule đã tồn tại (Lỗi HTTP 409 Conflict)
                        pass
                
                self.log(f"-> Đã thêm mới {rule_count} rules (Bỏ qua các rules đã tồn tại).", False)
            else:
                self.log("Không tìm thấy SG 'default', bỏ qua bước cấu hình tường lửa.", True)

            self.log("🚀 [Thành công] Yêu cầu 5 đã hoàn tất: Mạng và Tường lửa sẵn sàng!", False)
            self.fetch_networks_data()
            self.preload_data()
        except Exception as e:
            self.log(f"Lỗi Auto Setup: {e}", True)

    # =====================================================================
    # TAB: ROUTERS
    # =====================================================================
    def render_routers_tab(self, parent):
        ctk.CTkLabel(parent, text="Project / Network / Routers", text_color="gray", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(parent, text="Routers", font=ctk.CTkFont(size=28, weight="normal")).pack(anchor="w", pady=(0, 15))
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.pack(fill="x", pady=5)
        ctk.CTkButton(toolbar, text="Delete Routers", fg_color="#D9534F", hover_color="#C9302C", command=self.action_delete_selected_routers).pack(side="right", padx=(10, 0))
        ctk.CTkButton(toolbar, text="+ Create Router", fg_color="transparent", border_width=1, border_color="#D9534F", text_color="#D9534F", hover_color=("#FDE8E8", "#4A1A1A"), command=lambda: self.form_router.pack(fill="x", pady=10, before=self.table_router_container)).pack(side="right")
        ctk.CTkButton(toolbar, text="Refresh", width=80, fg_color="transparent", border_width=1, text_color=("#333", "white"), command=lambda: threading.Thread(target=self.fetch_routers_data).start()).pack(side="right", padx=10)

        # Form tạo Router
        self.form_router = ctk.CTkFrame(parent, fg_color=("#EBEBEB", "#2A2A2A"), corner_radius=5)
        row1 = ctk.CTkFrame(self.form_router, fg_color="transparent")
        row1.pack(fill="x", pady=10, padx=10)
        
        self.entry_router_name = ctk.CTkEntry(row1, placeholder_text="Router Name", width=150)
        self.entry_router_name.pack(side="left", padx=5)
        
        ctk.CTkLabel(row1, text="Ext Gateway:").pack(side="left", padx=2)
        ext_net_values = ["None (Không ra Internet)"] + list(getattr(self, 'cache_ext_networks', {}).keys())
        self.combo_ext_net = ctk.CTkComboBox(row1, values=ext_net_values, width=160)
        self.combo_ext_net.pack(side="left", padx=2)

        ctk.CTkLabel(row1, text="Int Interface:").pack(side="left", padx=2)
        int_sub_values = ["None (Không cắm mạng LAN)"] + list(getattr(self, 'cache_subnets', {}).keys())
        self.combo_int_sub = ctk.CTkComboBox(row1, values=int_sub_values, width=180)
        self.combo_int_sub.pack(side="left", padx=2)

        ctk.CTkButton(row1, text="Tạo Mới", fg_color="#E95420", width=80, command=lambda: threading.Thread(target=self.action_create_router).start()).pack(side="left", padx=5)
        ctk.CTkButton(row1, text="Đóng", fg_color="gray", width=60, command=lambda: self.form_router.pack_forget()).pack(side="left", padx=5)

        self.table_router_container = ctk.CTkFrame(parent, fg_color="transparent")
        self.table_router_container.pack(fill="both", expand=True, pady=10)
        
        threading.Thread(target=self.fetch_routers_data).start()

    def fetch_routers_data(self):
        try:
            rtrs = self._api_get(f"{self.get_ep('network')}/v2.0/routers").get("routers", [])
            self.selected_routers = {}
            headers = ["", "Name", "Status", "State", "Ext Network"]
            widths = [30, 200, 100, 100, 200]
            
            def update_ui():
                data = []
                for r in rtrs:
                    self.selected_routers[r['id']] = ctk.StringVar(value="off")
                    ext_info = r.get("external_gateway_info")
                    ext_net = ext_info.get("network_id") if ext_info else "-"
                    data.append([r['id'], r['name'], r['status'], "UP" if r['admin_state_up'] else "DOWN", ext_net])
                self._draw_table_ui(self.table_router_container, headers, data, widths, checkable=True, selected_vars=self.selected_routers)
                
            self.after(0, update_ui)
        except Exception as e:
            self.log(f"Lỗi tải Routers: {e}", True)

    def action_delete_selected_routers(self):
        selected_ids = [rid for rid, var in getattr(self, 'selected_routers', {}).items() if var.get() == "on"]
        if selected_ids and messagebox.askyesno("Xác nhận", f"Xóa {len(selected_ids)} Routers?"):
            threading.Thread(target=lambda: [self._process_delete_router_safe(rid) for rid in selected_ids] or self.fetch_routers_data()).start()

    def _process_delete_router_safe(self, rid):
        try:
            self.log(f"Đang dọn dẹp cổng Interface của Router {rid}...")
            ports = self._api_get(f"{self.get_ep('network')}/v2.0/ports?device_id={rid}").get("ports", [])
            for p in ports:
                if p.get("device_owner") == "network:router_interface":
                    self._api_put(f"{self.get_ep('network')}/v2.0/routers/{rid}/remove_router_interface", {"port_id": p['id']})
            self._api_delete(f"{self.get_ep('network')}/v2.0/routers/{rid}")
            self.log(f"Đã xóa Router ID: {rid}", False)
        except Exception as e:
            self.log(f"Lỗi xóa Router {rid}: {e}", True)

    def action_create_router(self):
        r_name = self.entry_router_name.get()
        ext_net_name = self.combo_ext_net.get()
        int_sub_name = self.combo_int_sub.get()
        
        if not r_name: 
            self.after(0, lambda: messagebox.showwarning("Lỗi", "Vui lòng nhập Tên Router"))
            return

        try:
            self.log(f"1. Khởi tạo Router '{r_name}'...")
            payload = {"router": {"name": r_name, "admin_state_up": True}}
            
            if ext_net_name != "None (Không ra Internet)":
                ext_net_id = getattr(self, 'cache_ext_networks', {}).get(ext_net_name)
                if ext_net_id:
                    payload["router"]["external_gateway_info"] = {"network_id": ext_net_id}

            res = self._api_post(f"{self.get_ep('network')}/v2.0/routers", payload)
            router_id = res["router"]["id"]
            
            if int_sub_name != "None (Không cắm mạng LAN)":
                sub_id = getattr(self, 'cache_subnets', {}).get(int_sub_name)
                if sub_id:
                    self.log(f"2. Đang gắn Interface vào subnet {int_sub_name}...")
                    self._api_put(f"{self.get_ep('network')}/v2.0/routers/{router_id}/add_router_interface", {"subnet_id": sub_id})
                    self.log("Đã gắn Interface thành công!", False)

            self.log("Hoàn tất tạo Router!", False)
                
            self.after(0, self.form_router.pack_forget)
            self.fetch_routers_data()
        except Exception as e:
            self.log(f"Lỗi tạo Router: {e}", True)

    # =====================================================================
    # TAB: INSTANCES (WIZARD LAUNCH INSTANCE + QUOTA FIX)
    # =====================================================================
    def render_instances_tab(self, parent):
        ctk.CTkLabel(parent, text="Project / Compute / Instances", text_color="gray", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(parent, text="Instances", font=ctk.CTkFont(size=32, weight="normal")).pack(anchor="w", pady=(0, 15))
        
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.pack(fill="x", pady=5)
        
        def on_auto_setup_vm_click():
            dialog = ctk.CTkInputDialog(text="Nhập tên máy ảo:", title="Auto Setup VM")
            group_name = dialog.get_input()
            if group_name:
                threading.Thread(target=self.action_auto_setup_req6, args=(group_name.strip(),)).start()

        ctk.CTkButton(toolbar, text="⚡ Auto Setup VM", fg_color="#2ecc71", hover_color="#27ae60", command=on_auto_setup_vm_click).pack(side="left")

        ctk.CTkButton(toolbar, text="Delete Instances", fg_color="#D9534F", hover_color="#C9302C", command=self.action_delete_selected_vms).pack(side="right", padx=(10, 0))
        ctk.CTkButton(toolbar, text="🚀 Launch Instance", fg_color="transparent", border_width=1, border_color="#D9534F", text_color="#D9534F", hover_color=("#FDE8E8", "#4A1A1A"), command=self.open_launch_instance_wizard).pack(side="right")
        ctk.CTkButton(toolbar, text="Refresh", width=80, fg_color="transparent", border_width=1, text_color=("#333", "white"), command=lambda: threading.Thread(target=self.fetch_instances_data).start()).pack(side="right", padx=10)

        self.table_inst_container = ctk.CTkFrame(parent, fg_color="transparent")
        self.table_inst_container.pack(fill="both", expand=True, pady=10)
        
        threading.Thread(target=self.fetch_instances_data).start()

    def fetch_instances_data(self):
        try:
            vms = self._api_get(f"{self.get_ep('compute')}/{self.api.project_id}/servers/detail").get("servers", [])
            self.selected_instances = {}
            headers = ["", "Instance Name", "Image Name", "IP Address", "Flavor", "Key Pair", "Status", "Availability Zone", "Task", "Power State", "Age"]
            widths = [30, 140, 120, 120, 80, 80, 70, 120, 70, 90, 100]
            
            def update_ui():
                data = []
                for vm in vms:
                    self.selected_instances[vm['id']] = ctk.StringVar(value="off")
                    img_data = vm.get('image')
                    img_id = img_data.get('id') if isinstance(img_data, dict) else None
                    img_name = getattr(self, 'cache_images', {}).get(img_id, "N/A (Volume)") if img_id else "N/A (Volume)"
                    flv_data = vm.get('flavor')
                    flv_id = flv_data.get('id') if isinstance(flv_data, dict) else None
                    flv_name = getattr(self, 'cache_flavors', {}).get(flv_id, "Unknown") if flv_id else "Unknown"
                    ips = [a["addr"] for net in vm.get("addresses", {}).values() for a in net]
                    p_state_map = {0: "No State", 1: "Running", 3: "Paused", 4: "Shut Down"}
                    p_state = p_state_map.get(vm.get('OS-EXT-STS:power_state'), "Unknown")
                    task = str(vm.get('OS-EXT-STS:task_state')).capitalize() if vm.get('OS-EXT-STS:task_state') else "None"
                    created_str = vm.get('created', '')
                    age_str = created_str[:10] if created_str else "Unknown"
                    data.append([
                        vm['id'], vm['name'], img_name, ", ".join(ips) if ips else "-", flv_name, 
                        vm.get('key_name', '-'), vm['status'], vm.get('OS-EXT-AZ:availability_zone', 'nova'),
                        task, p_state, age_str
                    ])
                self._draw_table_ui(self.table_inst_container, headers, data, widths, checkable=True, selected_vars=self.selected_instances)
                
            self.after(0, update_ui)
        except Exception as e:
            self.log(f"Lỗi tải VMs: {e}", True)

    def action_delete_selected_vms(self):
        if not hasattr(self, 'selected_instances'): return
        selected_ids = [vid for vid, var in self.selected_instances.items() if var.get() == "on"]
        if not selected_ids: 
            return messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 máy ảo để xóa!")
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("Xác nhận xóa Máy ảo")
        dialog.geometry("450x250")
        dialog.attributes("-topmost", True)
        dialog.focus_force()

        ctk.CTkLabel(dialog, text=f"Xóa {len(selected_ids)} máy ảo đã chọn?", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 10))

        delete_vol_var = ctk.BooleanVar(value=True)
        cb_vol = ctk.CTkCheckBox(dialog, text="Xóa luôn cả ổ cứng (Volume) đi kèm", variable=delete_vol_var, text_color="#E95420")
        cb_vol.pack(pady=15)

        def on_confirm():
            delete_vols = delete_vol_var.get()
            dialog.destroy()
            threading.Thread(target=self._process_delete_vms, args=(selected_ids, delete_vols)).start()

        footer = ctk.CTkFrame(dialog, fg_color="transparent")
        footer.pack(side="bottom", pady=20)
        ctk.CTkButton(footer, text="Hủy", fg_color="gray", width=100, command=dialog.destroy).pack(side="left", padx=10)
        ctk.CTkButton(footer, text="Xóa Máy Ảo", fg_color="#D9534F", hover_color="#C9302C", width=100, command=on_confirm).pack(side="right", padx=10)

    def _process_delete_vms(self, selected_ids, delete_volumes):
        for vid in selected_ids:
            try:
                attached_volumes = []
                if delete_volumes:
                    try:
                        vm_info = self._api_get(f"{self.get_ep('compute')}/{self.api.project_id}/servers/{vid}")
                        attached_volumes = vm_info.get("server", {}).get("os-extended-volumes:volumes_attached", [])
                    except: pass

                self._api_delete(f"{self.get_ep('compute')}/{self.api.project_id}/servers/{vid}?force=true")
                self.log(f"Đã gửi lệnh xóa máy ảo ID: {vid}", False)

                if delete_volumes and attached_volumes:
                    threading.Thread(target=self._delete_volumes_in_background, args=(attached_volumes,)).start()

            except Exception as e:
                self.log(f"Lỗi xóa máy ảo {vid}: {e}", True)
        self.fetch_instances_data()

    def _delete_volumes_in_background(self, attached_volumes):
        time.sleep(10)
        vol_ep = API_ENDPOINTS.get('volumev3', 'https://cloud-volume.uitiot.vn/v3').rstrip('/')
        for vol in attached_volumes:
            vol_id = vol.get("id")
            if vol_id:
                for attempt in range(6): 
                    try:
                        self.log(f"Đang dọn dẹp Volume phụ {vol_id}...")
                        res = requests.delete(f"{vol_ep}/{self.api.project_id}/volumes/{vol_id}", headers=self.api.get_headers())
                        if res.status_code in [200, 202, 204]:
                            self.log(f"Đã dọn dẹp sạch sẽ Volume {vol_id}!", False)
                            break
                    except: pass
                    time.sleep(5)

    def _show_private_key_popup(self, private_key):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Auto Key Pair Generated")
        dialog.geometry("550x450")
        dialog.attributes("-topmost", True)
        ctk.CTkLabel(dialog, text="⚠️ HỆ THỐNG VỪA TỰ ĐỘNG TẠO KEY PAIR MỚI!\nHãy copy và lưu lại Private Key này thành file .pem để SSH:", text_color="#E95420", font=ctk.CTkFont(weight="bold")).pack(pady=15)
        txt = ctk.CTkTextbox(dialog)
        txt.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        txt.insert("1.0", private_key)
        txt.configure(state="disabled")

    def action_auto_setup_req6(self, group_name):
        try:
            vm_name = f"{group_name.replace(' ', '')}"
            self.log(f"1. Khởi tạo tiến trình Auto Setup VM '{vm_name}'...")

            img_id = next((k for k, v in getattr(self, 'cache_images', {}).items() if "ubuntu" in v.lower()), list(getattr(self, 'cache_images', {}).keys())[0])
            flv_id = next((k for k, v in getattr(self, 'cache_flavors', {}).items() if "d10.xs1" in v), list(getattr(self, 'cache_flavors', {}).keys())[0])

            net_id = None
            int_nets = [nid for name, nid in getattr(self, 'cache_networks', {}).items() if name not in getattr(self, 'cache_ext_networks', {})]
            if not int_nets: raise Exception("Không tìm thấy mạng nội bộ nào! Vui lòng làm Yêu cầu 5 trước.")
            for name, nid in getattr(self, 'cache_networks', {}).items():
                if "nhom" in name.lower() and name not in getattr(self, 'cache_ext_networks', {}):
                    net_id = nid
                    break
            if not net_id: net_id = int_nets[0]

            key_name = None
            if getattr(self, 'cache_keypairs', None):
                key_name = list(self.cache_keypairs.keys())[0]
                self.log(f"Tự động chọn Key Pair có sẵn: '{key_name}'")
            else:
                self.log(f"Chưa có Key Pair. Tự động tạo mới 'Auto_Keypair'...")
                kp_res = self._api_post(f"{self.get_ep('compute')}/{self.api.project_id}/os-keypairs", {"keypair": {"name": "Auto_Keypair"}})
                if "keypair" in kp_res and "private_key" in kp_res["keypair"]:
                    key_name = kp_res["keypair"]["name"]
                    self.cache_keypairs = {key_name: key_name}
                    self.after(0, lambda pk=kp_res["keypair"]["private_key"]: self._show_private_key_popup(pk))

            self.log(f"2. Chuẩn bị User Data (Customization Script) cài đặt Web Server (PHP)...")
            
            # SỬ DỤNG HEREDOC ('EOF') CỦA BASH VÀ F-STRING (""") CỦA PYTHON
            # Lưu ý: Các ngoặc nhọn của CSS và JS đã được nhân đôi thành {{ }}
            script = f"""#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
apt-get update -y && apt-get install -y apache2 php libapache2-mod-php

rm -f /var/www/html/index.nginx-debian.html

cat << 'EOF' > /var/www/html/server_addr.php
<?php echo $_SERVER['SERVER_ADDR']; ?>
EOF

cat << 'EOF' > /var/www/html/http_host.php
<?php echo $_SERVER['HTTP_HOST']; ?>
EOF

cat << 'EOF' > /var/www/html/index.html
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lab 02 - Hệ tính toán phân bố</title>
    <style>
        body {{font-family: Arial, sans-serif; background: #f4f6fa; margin: 0; padding: 0;}}
        .container {{max-width: 600px; margin: 40px auto; background: #fff; border-radius: 10px; box-shadow: 0 2px 8px #0001; padding: 32px;}}
        h1 {{color: #2d6cdf;}}
        h2 {{color: #f50404;}}
    </style>
</head>
<body>
    <div class="container">
        <h1>Lab 02 - Hệ tính toán phân bố</h1>
        <h3>Chào mừng đến với web của Nhóm 9!</h3>
        <h2 class="server_addr">Địa chỉ IP (fixed): <span id="server_addr">Đang tải...</span></h2>
        <h2 class="http_host">Địa chỉ IP (floating): <span id="http_host">Đang tải...</span></h2>
    </div>
    <script>
        fetch('server_addr.php').then(r => r.text()).then(data => {{ document.getElementById('server_addr').innerText = data; }});
        fetch('http_host.php').then(r => r.text()).then(data => {{ document.getElementById('http_host').innerText = data; }});
    </script>
</body>
</html>
EOF

systemctl restart apache2
systemctl enable apache2
"""
            user_data_b64 = base64.b64encode(script.encode('utf-8')).decode('ascii')

            payload = {
                "server": {
                    "name": vm_name, "flavorRef": flv_id, "networks": [{"uuid": net_id}],
                    "user_data": user_data_b64, "security_groups": [{"name": "default"}],
                    "block_device_mapping_v2": [{"uuid": img_id, "source_type": "image", "destination_type": "volume", "boot_index": 0, "volume_size": 10, "delete_on_termination": True}]
                }
            }
            if key_name: payload["server"]["key_name"] = key_name

            self.log(f"3. Gửi lệnh tạo máy ảo (Boot từ Volume 10GB)...")
            srv_res = self._api_post(f"{self.get_ep('compute')}/{self.api.project_id}/servers", payload)
            srv_id = srv_res["server"]["id"]

            self.log("4. Đang chờ máy ảo khởi động (ACTIVE) - Quá trình này có thể mất 1-2 phút...")
            self._wait_vm_active(srv_id)

            self.log("5. Xin cấp và gắn Floating IP để kết nối từ bên ngoài...")
            ext_net_id = list(self.cache_ext_networks.values())[0] if getattr(self, 'cache_ext_networks', None) else None
            if ext_net_id:
                fip_res = self._api_post(f"{self.get_ep('network')}/v2.0/floatingips", {"floatingip": {"floating_network_id": ext_net_id}})
                fip = fip_res["floatingip"]
                ports = self._api_get(f"{self.get_ep('network')}/v2.0/ports?device_id={srv_id}").get("ports", [])
                if ports:
                    self._api_put(f"{self.get_ep('network')}/v2.0/floatingips/{fip['id']}", {"floatingip": {"port_id": ports[0]['id']}})
                    self.log(f"🚀 [Thành công] Auto Setup Yêu cầu 6 hoàn tất! Cổng Web đang chạy tại: http://{fip['floating_ip_address']}", False)
                    if hasattr(self, 'fetch_fips_data'): self.fetch_fips_data()
                else:
                    self.log("Lỗi: Không tìm thấy Port của VM để gắn Floating IP", True)
            else:
                self.log("Cảnh báo: Không tìm thấy mạng External để gắn Floating IP.", True)

            self.fetch_instances_data()
        except Exception as e:
            self.log(f"Lỗi Auto Setup: {e}", True)

    def open_launch_instance_wizard(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Launch Instance")
        dialog.geometry("650x780")
        dialog.attributes("-topmost", True)
        dialog.focus_force()

        container = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(container, text="Khởi tạo Máy ảo (Instance)", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", pady=(0, 20))

        ctk.CTkLabel(container, text="1. Đặt tên VM *", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        entry_name = ctk.CTkEntry(container, width=500, placeholder_text="Nhập tên máy ảo...")
        entry_name.pack(anchor="w", pady=(0, 15))

        ctk.CTkLabel(container, text="2. Chọn Image (HĐH) *", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        img_list = list(getattr(self, 'cache_images', {}).values()) or ["Loading..."]
        combo_img = ctk.CTkComboBox(container, values=img_list, width=500)
        combo_img.pack(anchor="w", pady=(0, 15))
        if img_list: combo_img.set(img_list[0])

        ctk.CTkLabel(container, text="3. Chỉnh sửa Volume (GB) *", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        ctk.CTkLabel(container, text="Lưu ý: Phải >= dung lượng gốc của Image (Thường >= 10GB)", text_color="gray", font=ctk.CTkFont(size=12, slant="italic")).pack(anchor="w")
        entry_vol = ctk.CTkEntry(container, width=500)
        entry_vol.insert(0, "10")
        entry_vol.pack(anchor="w", pady=(0, 15))

        ctk.CTkLabel(container, text="4. Chọn Flavor (Cấu hình) *", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        flv_list = list(getattr(self, 'cache_flavors', {}).values()) or ["Loading..."]
        combo_flv = ctk.CTkComboBox(container, values=flv_list, width=500)
        combo_flv.pack(anchor="w", pady=(0, 15))
        if flv_list: combo_flv.set(flv_list[0])

        ctk.CTkLabel(container, text="5. Chọn Network *", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        net_list = list(getattr(self, 'cache_networks', {}).keys()) or ["Loading..."]
        combo_net = ctk.CTkComboBox(container, values=net_list, width=500)
        combo_net.pack(anchor="w", pady=(0, 10))
        if net_list: combo_net.set(net_list[0])
        
        assign_fip_var = ctk.BooleanVar(value=True)
        cb_fip = ctk.CTkCheckBox(container, text="Tự động xin cấp & gán Floating IP (Public IP)", variable=assign_fip_var, text_color="#E95420")
        cb_fip.pack(anchor="w", pady=(0, 15))

        ctk.CTkLabel(container, text="6. Security Groups", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        ctk.CTkLabel(container, text="✓ Đã tự động gán Security Group: 'default'", text_color="#E95420").pack(anchor="w", pady=(0, 15))

        ctk.CTkLabel(container, text="7. Chọn Key Pair", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        kp_list = ["Select Key Pair..."] + list(getattr(self, 'cache_keypairs', {}).keys())
        combo_kp = ctk.CTkComboBox(container, values=kp_list, width=500)
        combo_kp.pack(anchor="w", pady=(0, 15))
        if len(kp_list)>1: combo_kp.set(kp_list[1])

        ctk.CTkLabel(container, text="8. Customization Script (User Data)", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        txt_script = ctk.CTkTextbox(container, width=500, height=350, font=("Courier", 12))
        txt_script.pack(anchor="w", pady=(0, 15))
        
        # Vì đây là chuỗi raw (không có chữ f đứng trước) nên không cần nhân đôi {{ }}
        default_script = """#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
apt-get update -y && apt-get install -y apache2 php libapache2-mod-php

rm -f /var/www/html/index.nginx-debian.html

cat << 'EOF' > /var/www/html/server_addr.php
<?php echo $_SERVER['SERVER_ADDR']; ?>
EOF

cat << 'EOF' > /var/www/html/http_host.php
<?php echo $_SERVER['HTTP_HOST']; ?>
EOF

cat << 'EOF' > /var/www/html/index.html
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lab 02 - Hệ tính toán phân bố</title>
    <style>
        body {font-family: Arial, sans-serif; background: #f4f6fa; margin: 0; padding: 0;}
        .container {max-width: 600px; margin: 40px auto; background: #fff; border-radius: 10px; box-shadow: 0 2px 8px #0001; padding: 32px;}
        h1 {color: #2d6cdf;}
        h2 {color: #f50404;}
    </style>
</head>
<body>
    <div class="container">
        <h1>Lab 02 - Hệ tính toán phân bố</h1>
        <h3>Chào mừng đến với web của Nhóm 9!</h3>
        <h2 class="server_addr">Địa chỉ IP (fixed): <span id="server_addr">Đang tải...</span></h2>
        <h2 class="http_host">Địa chỉ IP (floating): <span id="http_host">Đang tải...</span></h2>
    </div>
    <script>
        fetch('server_addr.php').then(r => r.text()).then(data => { document.getElementById('server_addr').innerText = data; });
        fetch('http_host.php').then(r => r.text()).then(data => { document.getElementById('http_host').innerText = data; });
    </script>
</body>
</html>
EOF

systemctl restart apache2
systemctl enable apache2
"""
        txt_script.insert("1.0", default_script)

        def action_submit():
            name = entry_name.get()
            img_name = combo_img.get()
            flv_name = combo_flv.get()
            net_name = combo_net.get()
            kp_name = combo_kp.get()
            vol_size = entry_vol.get()
            assign_fip = assign_fip_var.get()
            script = txt_script.get("1.0", "end-1c")

            if not name or not img_name or not flv_name or not net_name or not vol_size:
                dialog.attributes("-topmost", False)
                messagebox.showwarning("Lỗi", "Vui lòng nhập đủ các trường bắt buộc có dấu *")
                dialog.attributes("-topmost", True)
                return

            img_id = next((k for k, v in getattr(self, 'cache_images', {}).items() if v == img_name), None)
            flv_id = next((k for k, v in getattr(self, 'cache_flavors', {}).items() if v == flv_name), None)
            net_id = getattr(self, 'cache_networks', {}).get(net_name)

            if not img_id or not flv_id or not net_id: 
                self.log("Chưa đủ thông số Cache từ OpenStack", True)
                return

            try:
                vol_size_int = int(vol_size)
            except ValueError:
                dialog.attributes("-topmost", False)
                messagebox.showwarning("Lỗi", "Volume Size phải là số nguyên!")
                dialog.attributes("-topmost", True)
                return

            try:
                self.log(f"[Launch] Bắt đầu khởi tạo VM '{name}' (Boot từ Volume {vol_size_int}GB)...")
                user_data_b64 = base64.b64encode(script.encode('utf-8')).decode('ascii')
                
                payload = {
                    "server": {
                        "name": name, "flavorRef": flv_id, "networks": [{"uuid": net_id}],
                        "user_data": user_data_b64, "security_groups": [{"name": "default"}],
                        "block_device_mapping_v2": [{"uuid": img_id, "source_type": "image", "destination_type": "volume", "boot_index": 0, "volume_size": vol_size_int, "delete_on_termination": True}]
                    }
                }
                if kp_name and kp_name != "Select Key Pair...": payload["server"]["key_name"] = kp_name

                dialog.destroy()

                srv_res = self._api_post(f"{self.get_ep('compute')}/{self.api.project_id}/servers", payload)
                srv_id = srv_res["server"]["id"]

                self._post_launch_instance_tasks(srv_id, assign_fip)

            except Exception as e:
                self.log(f"Lỗi tạo VM: {e}", True)

        footer = ctk.CTkFrame(dialog, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=20, pady=10)
        ctk.CTkButton(footer, text="Cancel", fg_color="gray", width=100, command=dialog.destroy).pack(side="right", padx=5)
        ctk.CTkButton(footer, text="Launch Instance", fg_color="#E95420", hover_color="#d6491b", command=lambda: threading.Thread(target=action_submit).start()).pack(side="right", padx=5)

    def _post_launch_instance_tasks(self, srv_id, assign_fip=True):
        try:
            self.log("[Launch] Chờ máy ảo khởi động (ACTIVE)...")
            self._wait_vm_active(srv_id)

            if assign_fip:
                ext_net_id = list(self.cache_ext_networks.values())[0] if getattr(self, 'cache_ext_networks', None) else None
                if ext_net_id:
                    self.log("[Launch] Đang xin cấp và gắn Floating IP...")
                    fip_res = self._api_post(f"{self.get_ep('network')}/v2.0/floatingips", {"floatingip": {"floating_network_id": ext_net_id}})
                    fip = fip_res["floatingip"]

                    ports = self._api_get(f"{self.get_ep('network')}/v2.0/ports?device_id={srv_id}").get("ports", [])
                    if ports:
                        self._api_put(f"{self.get_ep('network')}/v2.0/floatingips/{fip['id']}", {"floatingip": {"port_id": ports[0]['id']}})
                        self.log(f"🚀 [Thành công] VM đã hoàn tất cài đặt Web Server. Cổng Web tại: http://{fip['floating_ip_address']}", False)
                        if hasattr(self, 'fetch_fips_data'): self.fetch_fips_data()
                    else:
                        self.log("Lỗi: Không tìm thấy Port của VM để gắn IP", True)
                else:
                    self.log("Cảnh báo: Không tìm thấy mạng External. Bỏ qua bước gắn Floating IP.", True)
            else:
                self.log("🚀 [Thành công] Máy ảo đã ACTIVE (Không gán Floating IP theo tùy chọn).", False)
            
            self.fetch_instances_data()
        except Exception as e:
            self.log(f"Lỗi tiến trình ngầm (Launch VM): {e}", True)

    # =====================================================================
    # TAB: IMAGES, FLAVORS, KEY PAIRS
    # =====================================================================
    def render_images_tab(self, parent):
        ctk.CTkLabel(parent, text="Project / Compute / Images", text_color="gray", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(parent, text="Images", font=ctk.CTkFont(size=28, weight="normal")).pack(anchor="w", pady=(0, 15))
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.pack(fill="x", pady=5)
        ctk.CTkButton(toolbar, text="Delete Images", fg_color="#D9534F", hover_color="#C9302C", command=self.action_delete_selected_images).pack(side="right", padx=(10, 0))
        ctk.CTkButton(toolbar, text="Refresh", width=80, fg_color="transparent", border_width=1, text_color=("#333", "white"), command=lambda: threading.Thread(target=self.fetch_images_data).start()).pack(side="right", padx=10)
        self.table_images_container = ctk.CTkFrame(parent, fg_color="transparent")
        self.table_images_container.pack(fill="both", expand=True, pady=10)
        threading.Thread(target=self.fetch_images_data).start()

    def fetch_images_data(self):
        try:
            imgs = self._api_get(f"{self.get_ep('image')}/v2/images").get("images", [])
            self.selected_images = {}
            headers = ["", "Name", "Type", "Status", "Visibility", "Protected", "Disk Format", "Size"]
            widths = [30, 200, 80, 80, 80, 80, 100, 100]
            
            def update_ui():
                data = []
                for i in imgs:
                    self.selected_images[i['id']] = ctk.StringVar(value="off")
                    size_mb = f"{i.get('size', 0) / (1024*1024):.2f} MB"
                    data.append([i['id'], i['name'], "Image", i['status'].capitalize(), i.get('visibility', 'Public').capitalize(), "Yes" if i.get('protected') else "No", i.get('disk_format', '').upper(), size_mb])
                self._draw_table_ui(self.table_images_container, headers, data, widths, checkable=True, selected_vars=self.selected_images)
            self.after(0, update_ui)
        except Exception as e:
            self.log(f"Lỗi tải Images: {e}", True)

    def action_delete_selected_images(self):
        selected_ids = [iid for iid, var in getattr(self, 'selected_images', {}).items() if var.get() == "on"]
        if selected_ids and messagebox.askyesno("Xác nhận", f"Xóa {len(selected_ids)} Images?"):
            threading.Thread(target=lambda: [self._api_delete(f"{self.get_ep('image')}/v2/images/{iid}") for iid in selected_ids] or self.fetch_images_data()).start()

    def render_flavors_tab(self, parent):
        ctk.CTkLabel(parent, text="Project / Compute / Flavors", text_color="gray", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(parent, text="Flavors", font=ctk.CTkFont(size=28, weight="normal")).pack(anchor="w", pady=(0, 15))
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.pack(fill="x", pady=5)
        ctk.CTkButton(toolbar, text="Refresh", width=80, fg_color="transparent", border_width=1, text_color=("#333", "white"), command=lambda: threading.Thread(target=self.fetch_flavors_data).start()).pack(side="right", padx=10)
        self.table_flavors_container = ctk.CTkFrame(parent, fg_color="transparent")
        self.table_flavors_container.pack(fill="both", expand=True, pady=10)
        threading.Thread(target=self.fetch_flavors_data).start()

    def fetch_flavors_data(self):
        try:
            flvs = self._api_get(f"{self.get_ep('compute')}/{self.api.project_id}/flavors/detail").get("flavors", [])
            headers = ["Name", "VCPUs", "RAM", "Total Disk", "Root Disk", "Ephemeral Disk", "Public"]
            widths = [200, 80, 100, 100, 100, 120, 80]
            
            def update_ui():
                data = []
                for f in flvs:
                    ram_str = f"{f['ram']} MB"
                    disk_str = f"{f['disk']} GB"
                    root_str = f"{f.get('root_gb', f['disk'])} GB"
                    ephemeral_str = f"{f.get('ephemeral_gb', 0)} GB"
                    is_public = "Yes" if f.get('os-flavor-access:is_public') else "No"
                    data.append([f['name'], f['vcpus'], ram_str, disk_str, root_str, ephemeral_str, is_public])
                self._draw_table_ui(self.table_flavors_container, headers, data, widths, checkable=False)
            self.after(0, update_ui)
        except Exception as e:
            self.log(f"Lỗi tải Flavors: {e}", True)

    def render_keypairs_tab(self, parent):
        ctk.CTkLabel(parent, text="Project / Compute / Key Pairs", text_color="gray", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(parent, text="Key Pairs", font=ctk.CTkFont(size=28, weight="normal")).pack(anchor="w", pady=(0, 15))
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.pack(fill="x", pady=5)
        ctk.CTkButton(toolbar, text="Delete Key Pairs", fg_color="#D9534F", hover_color="#C9302C", command=self.action_delete_selected_keypairs).pack(side="right", padx=(10, 0))
        ctk.CTkButton(toolbar, text="+ Create Key Pair", fg_color="transparent", border_width=1, text_color=("#333", "white"), command=lambda: self.form_kp.pack(fill="x", pady=10, before=self.table_kp_container)).pack(side="right")
        ctk.CTkButton(toolbar, text="Refresh", width=80, fg_color="transparent", border_width=1, text_color=("#333", "white"), command=lambda: threading.Thread(target=self.fetch_keypairs_data).start()).pack(side="right", padx=10)
        
        self.form_kp = ctk.CTkFrame(parent, fg_color=("#EBEBEB", "#2A2A2A"), corner_radius=5)
        row1 = ctk.CTkFrame(self.form_kp, fg_color="transparent")
        row1.pack(fill="x", pady=10, padx=10)
        self.entry_kp_name = ctk.CTkEntry(row1, placeholder_text="Tên Key Pair...", width=200)
        self.entry_kp_name.pack(side="left", padx=5)
        ctk.CTkButton(row1, text="Tạo Mới", fg_color="#E95420", command=lambda: threading.Thread(target=self.action_create_keypair).start()).pack(side="left", padx=5)
        ctk.CTkButton(row1, text="Đóng", fg_color="gray", command=lambda: self.form_kp.pack_forget()).pack(side="left", padx=5)
        
        self.table_kp_container = ctk.CTkFrame(parent, fg_color="transparent")
        self.table_kp_container.pack(fill="both", expand=True, pady=10)
        threading.Thread(target=self.fetch_keypairs_data).start()

    def fetch_keypairs_data(self):
        try:
            kps = self._api_get(f"{self.get_ep('compute')}/{self.api.project_id}/os-keypairs").get("keypairs", [])
            self.cache_keypairs = {k['keypair']['name']: k['keypair']['name'] for k in kps}
            
            self.selected_keypairs = {}
            headers = ["", "Name", "Type", "Fingerprint"]
            widths = [30, 200, 100, 400]
            
            def update_ui():
                data = []
                for k in kps:
                    name = k['keypair']['name']
                    self.selected_keypairs[name] = ctk.StringVar(value="off")
                    data.append([name, name, k['keypair'].get('type', 'ssh'), k['keypair'].get('fingerprint', 'N/A')])
                self._draw_table_ui(self.table_kp_container, headers, data, widths, checkable=True, selected_vars=self.selected_keypairs)
            self.after(0, update_ui)
        except Exception as e:
            self.log(f"Lỗi tải Key Pairs: {e}", True)

    def action_delete_selected_keypairs(self):
        selected_names = [name for name, var in getattr(self, 'selected_keypairs', {}).items() if var.get() == "on"]
        if selected_names and messagebox.askyesno("Xác nhận", f"Xóa {len(selected_names)} Key Pairs?"):
            threading.Thread(target=lambda: [self._api_delete(f"{self.get_ep('compute')}/{self.api.project_id}/os-keypairs/{name}") for name in selected_names] or self.fetch_keypairs_data()).start()

    def action_create_keypair(self):
        name = self.entry_kp_name.get()
        if name:
            try:
                res = self._api_post(f"{self.get_ep('compute')}/{self.api.project_id}/os-keypairs", {"keypair": {"name": name}})
                if "keypair" in res and "private_key" in res["keypair"]:
                    self.after(0, lambda pk=res["keypair"]["private_key"]: self._show_private_key_popup(pk))
                self.fetch_keypairs_data()
                self.after(0, self.form_kp.pack_forget)
            except Exception as e: self.log(f"Lỗi tạo Key: {e}", True)

    # =====================================================================
    # TAB: LOAD BALANCER & AUTO SCALING (YÊU CẦU 7, 8)
    # =====================================================================
    def render_lb_tab(self, parent):
        ctk.CTkLabel(parent, text="Project / Network / Load Balancers", text_color="gray", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(parent, text="Load Balancers & Auto Scaling", font=ctk.CTkFont(size=32, weight="normal")).pack(anchor="w", pady=(0, 15))
        
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.pack(fill="x", pady=5)
        
        # Nút tạo LB thông qua Wizard (Yêu cầu 7)
        ctk.CTkButton(toolbar, text="🚀 Create Load Balancer", fg_color="transparent", border_width=1, border_color="#8e44ad", text_color="#8e44ad", hover_color=("#F5E8FA", "#3E1C47"), command=self.open_create_lb_wizard).pack(side="left", padx=(0, 5))
        
        # Nút Scale Up/Down (Yêu cầu 8) - Đã bỏ Thread wrapper trên nút để gọi Popup nhập liệu trước
        ctk.CTkButton(toolbar, text="Scale Up (+VM)", fg_color="#2ecc71", hover_color="#27ae60", command=self.action_scale_up_req8).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Scale Down (-VM)", fg_color="#D9534F", hover_color="#C9302C", command=self.action_scale_down_req8).pack(side="left", padx=5)

        ctk.CTkButton(toolbar, text="Delete LB", fg_color="#D9534F", hover_color="#C9302C", command=self.action_delete_selected_lbs).pack(side="right", padx=(10, 0))
        ctk.CTkButton(toolbar, text="Refresh", width=80, fg_color="transparent", border_width=1, text_color=("#333", "white"), command=lambda: threading.Thread(target=self.fetch_lbs_data).start()).pack(side="right", padx=10)

        self.table_lb_container = ctk.CTkFrame(parent, fg_color="transparent")
        self.table_lb_container.pack(fill="both", expand=True, pady=10)
        
        threading.Thread(target=self.fetch_lbs_data).start()

    def fetch_lbs_data(self):
        try:
            # Lọc theo project_id để tránh lỗi 403 Policy Forbidden
            lbs = self._api_get(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/loadbalancers?project_id={self.api.project_id}").get("loadbalancers", [])
            self.selected_lbs = {}
            headers = ["", "Name", "VIP Address", "Prov. Status", "Operating Status", "Provider"]
            widths = [30, 200, 150, 120, 120, 100]
            
            # Đưa việc vẽ bảng về Luồng chính (Main Thread)
            def update_ui():
                data = []
                for lb in lbs:
                    self.selected_lbs[lb['id']] = ctk.StringVar(value="off")
                    data.append([
                        lb['id'], lb['name'], lb.get('vip_address', 'N/A'), 
                        lb.get('provisioning_status', 'UNKNOWN'), lb.get('operating_status', 'UNKNOWN'),
                        lb.get('provider', 'octavia')
                    ])
                self._draw_table_ui(self.table_lb_container, headers, data, widths, checkable=True, selected_vars=self.selected_lbs)
            
            self.after(0, update_ui)
        except Exception as e:
            self.log(f"Lỗi tải Load Balancers: {e}", True)

    def action_delete_selected_lbs(self):
        selected_ids = [lbid for lbid, var in getattr(self, 'selected_lbs', {}).items() if var.get() == "on"]
        if not selected_ids:
            self.after(0, lambda: messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 Load Balancer để xóa!"))
            return
            
        if messagebox.askyesno("Xác nhận", f"Xóa {len(selected_ids)} Load Balancers?\n\n(Lưu ý: Quá trình xóa (Cascade) sẽ tự động gỡ bỏ toàn bộ Listener, Pool và Monitor đi kèm. Sẽ mất khoảng 1-2 phút để dọn dẹp hoàn toàn)"):
            threading.Thread(target=self._process_delete_lbs, args=(selected_ids,)).start()

    def _process_delete_lbs(self, selected_ids):
        for lbid in selected_ids:
            try:
                self.log(f"[LB] Đang gửi lệnh xóa Load Balancer ID: {lbid} (Cascade)...")
                # Tham số cascade=true giúp xóa rễ mọi thứ bên trong LB
                self._api_delete(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/loadbalancers/{lbid}?cascade=true")
                self.log(f"-> Đang chờ OpenStack dọn dẹp (PENDING_DELETE). Vui lòng đợi...", False)
                
                # Chạy vòng lặp kiểm tra liên tục cho đến khi LB thực sự biến mất (trả về lỗi 404)
                start_time = time.time()
                is_deleted = False
                while time.time() - start_time < 300: # Đợi tối đa 5 phút
                    try:
                        # Gọi API xem LB còn tồn tại không
                        self._api_get(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/loadbalancers/{lbid}")
                        # Tải lại bảng để cập nhật trạng thái PENDING_DELETE lên giao diện
                        self.fetch_lbs_data()
                        time.sleep(5) # Nghỉ 5s rồi check lại
                    except Exception:
                        # Nếu gọi API văng lỗi (Thường là HTTP 404 Not Found) => Đã xóa xong!
                        is_deleted = True
                        break
                        
                if is_deleted:
                    self.log(f"🚀 [Thành công] Load Balancer {lbid} đã bị xóa sạch sẽ khỏi hệ thống!", False)
                else:
                    self.log(f"Cảnh báo: Đã quá thời gian chờ nhưng Load Balancer vẫn chưa bị xóa hẳn.", True)
                    
            except Exception as e:
                self.log(f"Lỗi xóa Load Balancer {lbid}: {e}", True)
        
        # Tải lại bảng sau khi hoàn tất tiến trình
        self.fetch_lbs_data()

    def _wait_lb_active(self, lb_id, timeout=180):
        start = time.time()
        while time.time() - start < timeout:
            res = self._api_get(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/loadbalancers/{lb_id}")
            if res["loadbalancer"]["provisioning_status"] == "ACTIVE": return True
            time.sleep(5)
        raise Exception("Timeout khi chờ LB ACTIVE")

    # --- WIZARD TẠO LOAD BALANCER (YÊU CẦU 7) ---
    def open_create_lb_wizard(self):
        self.lb_wizard = ctk.CTkToplevel(self)
        self.lb_wizard.title("Create Load Balancer")
        self.lb_wizard.geometry("1000x700")
        self.lb_wizard.attributes("-topmost", True)
        self.lb_wizard.focus_force()

        # Dữ liệu form lưu tạm (Mô phỏng chi tiết Horizon)
        self.lb_wizard_data = {
            # LB Details
            "lb_name": ctk.StringVar(), "lb_desc": ctk.StringVar(), "lb_ip": ctk.StringVar(), "subnet": ctk.StringVar(),
            # Listener Details
            "create_lis": ctk.StringVar(value="Yes"), "lis_name": ctk.StringVar(value="listener_80"), 
            "lis_desc": ctk.StringVar(), "lis_proto": ctk.StringVar(value="HTTP"), 
            "lis_port": ctk.StringVar(value="80"), "lis_conn_limit": ctk.StringVar(value="-1"),
            # Pool Details
            "create_pool": ctk.StringVar(value="Yes"), "pool_name": ctk.StringVar(value="pool_web"),
            "pool_desc": ctk.StringVar(), "pool_algo": ctk.StringVar(value="ROUND_ROBIN"),
            "pool_session": ctk.StringVar(value="None"),
            # Monitor Details
            "create_mon": ctk.StringVar(value="Yes"), "mon_name": ctk.StringVar(), 
            "mon_type": ctk.StringVar(value="HTTP"), "mon_delay": ctk.StringVar(value="5"), 
            "mon_timeout": ctk.StringVar(value="5"), "mon_retries": ctk.StringVar(value="3"),
            "mon_retries_down": ctk.StringVar(value="3")
        }
        self.selected_lb_members = {}

        main_container = ctk.CTkFrame(self.lb_wizard, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Thanh Menu Dọc
        sidebar = ctk.CTkFrame(main_container, width=240, fg_color=("#F0F0F0", "#2A2A2A"))
        sidebar.pack(side="left", fill="y", padx=(0, 10))

        self.lb_wizard_content = ctk.CTkFrame(main_container, fg_color=("#FFFFFF", "#333333"))
        self.lb_wizard_content.pack(side="right", fill="both", expand=True)

        tabs = ["Load Balancer Details *", "Listener Details *", "Pool Details *", "Pool Members", "Monitor Details *"]
        self.lb_wizard_btns = {}
        for tab in tabs:
            btn = ctk.CTkButton(sidebar, text=tab, anchor="w", fg_color="transparent", text_color=("#333", "white"), 
                                command=lambda t=tab: self.switch_lb_wizard_tab(t))
            btn.pack(fill="x", padx=5, pady=2)
            self.lb_wizard_btns[tab] = btn

        # Footer Actions
        footer = ctk.CTkFrame(self.lb_wizard, height=50, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=10, pady=10)
        ctk.CTkButton(footer, text="Cancel", fg_color="gray", width=100, command=self.lb_wizard.destroy).pack(side="right", padx=5)
        ctk.CTkButton(footer, text="Create Load Balancer", fg_color="#E95420", hover_color="#d6491b", 
                      command=lambda: threading.Thread(target=self.action_submit_lb_wizard).start()).pack(side="right", padx=5)

        # Lấy danh sách máy ảo cho Pool Members
        threading.Thread(target=self._fetch_vms_for_lb_wizard).start()
        
        self.switch_lb_wizard_tab("Load Balancer Details *")

    def _fetch_vms_for_lb_wizard(self):
        try:
            self.lb_vms_cache = self._api_get(f"{self.get_ep('compute')}/{self.api.project_id}/servers/detail").get("servers", [])
            for vm in self.lb_vms_cache:
                self.selected_lb_members[vm['id']] = ctk.StringVar(value="off")
        except:
            self.lb_vms_cache = []

    def switch_lb_wizard_tab(self, tab_name):
        for widget in self.lb_wizard_content.winfo_children(): widget.destroy()
        for btn in self.lb_wizard_btns.values(): btn.configure(fg_color="transparent", font=ctk.CTkFont(weight="normal"))
        self.lb_wizard_btns[tab_name].configure(fg_color=("#E0E0E0", "#444444"), font=ctk.CTkFont(weight="bold"))

        # Tiêu đề Tab
        clean_name = tab_name.replace(" *", "")
        header_frame = ctk.CTkFrame(self.lb_wizard_content, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header_frame, text=f"Provide the details for the {clean_name.lower()}.", text_color="gray", font=ctk.CTkFont(size=14)).pack(anchor="w")

        # Khung chứa nội dung (Grid Layout)
        grid_frame = ctk.CTkFrame(self.lb_wizard_content, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=15, pady=5)
        grid_frame.columnconfigure((0, 1), weight=1)

        def create_field(parent, label, var, row, col, req=False, widget_type="entry", values=None, colspan=1):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.grid(row=row, column=col, columnspan=colspan, sticky="ew", padx=10, pady=10)
            lbl_color = "#E95420" if req else ("#333", "white")
            ctk.CTkLabel(f, text=f"{label} *" if req else label, text_color=lbl_color, font=ctk.CTkFont(weight="bold")).pack(anchor="w")
            
            if widget_type == "entry":
                ctk.CTkEntry(f, textvariable=var).pack(fill="x", pady=(5, 0))
            elif widget_type == "combo":
                cb = ctk.CTkComboBox(f, values=values, variable=var)
                cb.pack(fill="x", pady=(5, 0))
                if values and not var.get(): cb.set(values[0])
            elif widget_type == "seg":
                ctk.CTkSegmentedButton(f, values=values, variable=var, selected_color="#E95420", selected_hover_color="#d6491b").pack(anchor="w", pady=(5, 0))

        if tab_name == "Load Balancer Details *":
            create_field(grid_frame, "Name", self.lb_wizard_data["lb_name"], 0, 0)
            create_field(grid_frame, "IP address", self.lb_wizard_data["lb_ip"], 0, 1)
            create_field(grid_frame, "Description", self.lb_wizard_data["lb_desc"], 1, 0, colspan=2)
            
            sub_list = list(getattr(self, 'cache_subnets', {}).keys()) or ["Loading..."]
            create_field(grid_frame, "Subnet", self.lb_wizard_data["subnet"], 2, 0, req=True, widget_type="combo", values=sub_list, colspan=2)
            create_field(grid_frame, "Admin State Up", ctk.StringVar(value="Yes"), 3, 0, widget_type="seg", values=["Yes", "No"])

        elif tab_name == "Listener Details *":
            create_field(grid_frame, "Create Listener", self.lb_wizard_data["create_lis"], 0, 0, widget_type="seg", values=["Yes", "No"], colspan=2)
            create_field(grid_frame, "Name", self.lb_wizard_data["lis_name"], 1, 0)
            create_field(grid_frame, "Description", self.lb_wizard_data["lis_desc"], 1, 1)
            create_field(grid_frame, "Protocol", self.lb_wizard_data["lis_proto"], 2, 0, req=True, widget_type="combo", values=["HTTP", "HTTPS", "TCP", "UDP"])
            create_field(grid_frame, "Port", self.lb_wizard_data["lis_port"], 2, 1, req=True)
            create_field(grid_frame, "Connection Limit", self.lb_wizard_data["lis_conn_limit"], 3, 0, req=True)
            create_field(grid_frame, "Admin State Up", ctk.StringVar(value="Yes"), 4, 0, widget_type="seg", values=["Yes", "No"])

        elif tab_name == "Pool Details *":
            create_field(grid_frame, "Create Pool", self.lb_wizard_data["create_pool"], 0, 0, widget_type="seg", values=["Yes", "No"], colspan=2)
            create_field(grid_frame, "Name", self.lb_wizard_data["pool_name"], 1, 0)
            create_field(grid_frame, "Description", self.lb_wizard_data["pool_desc"], 1, 1)
            create_field(grid_frame, "Algorithm", self.lb_wizard_data["pool_algo"], 2, 0, req=True, widget_type="combo", values=["ROUND_ROBIN", "LEAST_CONNECTIONS", "SOURCE_IP"])
            create_field(grid_frame, "Session Persistence", self.lb_wizard_data["pool_session"], 2, 1, widget_type="combo", values=["None", "SOURCE_IP", "HTTP_COOKIE", "APP_COOKIE"])
            create_field(grid_frame, "Admin State Up", ctk.StringVar(value="Yes"), 3, 0, widget_type="seg", values=["Yes", "No"])

        elif tab_name == "Pool Members":
            ctk.CTkLabel(grid_frame, text="Add members to the load balancer pool.", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10))
            frame_members = ctk.CTkScrollableFrame(grid_frame, height=350, fg_color=("gray90", "gray15"))
            frame_members.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10)
            
            vms = getattr(self, 'lb_vms_cache', [])
            if not vms:
                ctk.CTkLabel(frame_members, text="No available instances", font=ctk.CTkFont(slant="italic")).pack(pady=20)
            else:
                for vm in vms:
                    ips = [a["addr"] for net in vm.get("addresses", {}).values() for a in net]
                    ip_str = ips[0] if ips else "No IP"
                    row = ctk.CTkFrame(frame_members, fg_color="transparent")
                    row.pack(fill="x", pady=2)
                    cb = ctk.CTkCheckBox(row, text=f"{vm['name']}  ({ip_str})", variable=self.selected_lb_members[vm['id']], onvalue="on", offvalue="off", text_color="#E95420")
                    cb.pack(side="left", padx=10, pady=5)
                    ctk.CTkLabel(row, text="Port: 80 | Weight: 1").pack(side="right", padx=20)

        elif tab_name == "Monitor Details *":
            create_field(grid_frame, "Create Health Monitor", self.lb_wizard_data["create_mon"], 0, 0, widget_type="seg", values=["Yes", "No"], colspan=2)
            create_field(grid_frame, "Name", self.lb_wizard_data["mon_name"], 1, 0)
            create_field(grid_frame, "Type", self.lb_wizard_data["mon_type"], 1, 1, req=True, widget_type="combo", values=["HTTP", "PING", "TCP", "HTTPS", "TLS-HELLO"])
            create_field(grid_frame, "Delay (sec)", self.lb_wizard_data["mon_delay"], 2, 0, req=True)
            create_field(grid_frame, "Timeout (sec)", self.lb_wizard_data["mon_timeout"], 2, 1, req=True)
            create_field(grid_frame, "Max Retries", self.lb_wizard_data["mon_retries"], 3, 0, req=True)
            create_field(grid_frame, "Max Retries Down", self.lb_wizard_data["mon_retries_down"], 3, 1, req=True)
            create_field(grid_frame, "Admin State Up", ctk.StringVar(value="Yes"), 4, 0, widget_type="seg", values=["Yes", "No"])

    def action_submit_lb_wizard(self):
        d = self.lb_wizard_data
        lb_name = d["lb_name"].get()
        subnet_name = d["subnet"].get()
        
        if not subnet_name or subnet_name == "Loading...":
            self.lb_wizard.attributes("-topmost", False)
            messagebox.showwarning("Lỗi", "Vui lòng chọn Subnet ở tab Load Balancer Details!")
            self.lb_wizard.attributes("-topmost", True)
            return

        subnet_id = getattr(self, 'cache_subnets', {}).get(subnet_name)
        if not subnet_id: return self.log("Không lấy được ID của Subnet!", True)

        self.lb_wizard.destroy() # Tắt form

        try:
            self.log("================= BẮT ĐẦU TẠO LOAD BALANCER =================")
            # 1. Tạo LB
            self.log(f"[LB] 1. Khởi tạo Load Balancer '{lb_name}'...")
            lb_payload = {"loadbalancer": {"name": lb_name, "vip_subnet_id": subnet_id}}
            if d["lb_desc"].get(): lb_payload["loadbalancer"]["description"] = d["lb_desc"].get()
            if d["lb_ip"].get(): lb_payload["loadbalancer"]["vip_address"] = d["lb_ip"].get()

            lb_res = self._api_post(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/loadbalancers", lb_payload)
            lb_id = lb_res["loadbalancer"]["id"]
            self._wait_lb_active(lb_id)

            # 2. Tạo Listener (Nếu được chọn)
            lis_id = None
            if d["create_lis"].get() == "Yes":
                lis_port = int(d["lis_port"].get() or 80)
                self.log(f"[LB] 2. Tạo Listener '{d['lis_name'].get()}' (Port {lis_port})...")
                lis_payload = {
                    "listener": {
                        "name": d["lis_name"].get(), "protocol": d["lis_proto"].get(), 
                        "protocol_port": lis_port, "loadbalancer_id": lb_id,
                        "connection_limit": int(d["lis_conn_limit"].get() or -1)
                    }
                }
                if d["lis_desc"].get(): lis_payload["listener"]["description"] = d["lis_desc"].get()
                lis_res = self._api_post(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/listeners", lis_payload)
                lis_id = lis_res["listener"]["id"]
                self._wait_lb_active(lb_id)

            # 3. Tạo Pool (Nếu có Listener và được chọn)
            pool_id = None
            if lis_id and d["create_pool"].get() == "Yes":
                self.log(f"[LB] 3. Tạo Pool '{d['pool_name'].get()}' (Thuật toán: {d['pool_algo'].get()})...")
                pool_payload = {
                    "pool": {
                        "name": d["pool_name"].get(), "protocol": d["lis_proto"].get(), 
                        "lb_algorithm": d["pool_algo"].get(), "listener_id": lis_id
                    }
                }
                if d["pool_desc"].get(): pool_payload["pool"]["description"] = d["pool_desc"].get()
                if d["pool_session"].get() != "None": 
                    pool_payload["pool"]["session_persistence"] = {"type": d["pool_session"].get()}

                pool_res = self._api_post(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/pools", pool_payload)
                pool_id = pool_res["pool"]["id"]
                self.current_pool_id = pool_id
                self._wait_lb_active(lb_id)

            # 4. Thêm Members
            if pool_id:
                selected_vms = [vid for vid, var in self.selected_lb_members.items() if var.get() == "on"]
                if selected_vms:
                    self.log(f"[LB] 4. Thêm {len(selected_vms)} VMs vào Pool Members...")
                    vms = getattr(self, 'lb_vms_cache', [])
                    for vid in selected_vms:
                        vm = next((v for v in vms if v['id'] == vid), None)
                        if vm:
                            ips = [a["addr"] for net in vm.get("addresses", {}).values() for a in net]
                            if ips:
                                self._api_post(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/pools/{pool_id}/members", {
                                    "member": {"address": ips[0], "protocol_port": lis_port, "subnet_id": subnet_id}
                                })
                                self._wait_lb_active(lb_id)

            # 5. Tạo Monitor
            if pool_id and d["create_mon"].get() == "Yes":
                self.log(f"[LB] 5. Tạo Health Monitor ({d['mon_type'].get()})...")
                mon_payload = {
                    "healthmonitor": {
                        "pool_id": pool_id, "type": d["mon_type"].get(), 
                        "delay": int(d["mon_delay"].get()), "timeout": int(d["mon_timeout"].get()), 
                        "max_retries": int(d["mon_retries"].get()), "max_retries_down": int(d["mon_retries_down"].get())
                    }
                }
                if d["mon_name"].get(): mon_payload["healthmonitor"]["name"] = d["mon_name"].get()
                if d["mon_type"].get() == "HTTP": mon_payload["healthmonitor"]["url_path"] = "/"
                
                self._api_post(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/healthmonitors", mon_payload)
                self._wait_lb_active(lb_id)

            self.log(f"🚀 [Thành công] Load Balancer đã thiết lập xong! VIP: {lb_res['loadbalancer'].get('vip_address')}", False)
            self.fetch_lbs_data()
        except Exception as e:
            self.log(f"Lỗi khởi tạo LB: {e}", True)

    # --- AUTO SCALE UP / DOWN (YÊU CẦU 8) ---
    def action_scale_up_req8(self):
        selected_ids = [lbid for lbid, var in getattr(self, 'selected_lbs', {}).items() if var.get() == "on"]
        if len(selected_ids) != 1:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ĐÚNG 1 Load Balancer trong bảng để Scale Up!")
            return
        
        lb_id = selected_ids[0]
        
        dialog = ctk.CTkInputDialog(text="Nhập số lượng VM muốn thêm vào Load Balancer này:", title="Auto Scale Up")
        count_str = dialog.get_input()
        
        if not count_str: return
        
        try:
            count = int(count_str)
            if count <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Số lượng phải là số nguyên dương!")
            return
            
        threading.Thread(target=self._process_scale_up, args=(lb_id, count)).start()

    def _process_scale_up(self, lb_id, count):
        try:
            lb_details = self._api_get(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/loadbalancers/{lb_id}")
            subnet_id = lb_details["loadbalancer"]["vip_subnet_id"]
            pools = lb_details["loadbalancer"].get("pools", [])
            
            if not pools:
                return self.log("Lỗi: Load Balancer này chưa có Pool nào! Vui lòng tạo Listener và Pool trước.", True)
            pool_id = pools[0]["id"]

            # --- KIỂM TRA GIỚI HẠN TỐI ĐA (MAX 5 VMs) ---
            members = self._api_get(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/pools/{pool_id}/members").get("members", [])
            current_count = len(members)
            if current_count + count > 5:
                self.log(f"Cảnh báo: Hệ thống cho phép tối đa 5 VMs. (Hiện có {current_count}, muốn thêm {count})", True)
                self.after(0, lambda: messagebox.showwarning("Giới hạn Auto Scale", f"Không thể Scale Up!\nHệ thống cho phép tối đa 5 máy ảo trong cụm Load Balancer.\n\nHiện tại đang có: {current_count} máy ảo."))
                return

            self.log(f"Bắt đầu Scale Up: Clone {count} VM mới...")

            # Lấy thông số (Lấy Image Ubuntu và Flavor d10.xs1 tự động)
            img_id = next((k for k, v in self.cache_images.items() if "ubuntu" in v.lower()), list(self.cache_images.keys())[0])
            flv_id = next((k for k, v in self.cache_flavors.items() if "d10.xs1" in v), list(self.cache_flavors.keys())[0])
            
            # Map subnet_id ngược ra net_id để tạo VM
            net_id = None
            for n_name, n_id in self.cache_networks.items():
                ports = self._api_get(f"{self.get_ep('network')}/v2.0/subnets?network_id={n_id}").get("subnets", [])
                if any(s["id"] == subnet_id for s in ports):
                    net_id = n_id
                    break
            if not net_id: net_id = list(self.cache_networks.values())[0] # Fallback

            # --- XỬ LÝ KEY PAIR TỰ ĐỘNG ---
            key_name = None
            if getattr(self, 'cache_keypairs', None):
                key_name = list(self.cache_keypairs.keys())[0]
            else:
                try:
                    kp_res = self._api_post(f"{self.get_ep('compute')}/{self.api.project_id}/os-keypairs", {"keypair": {"name": "Auto_Scale_Keypair"}})
                    if "keypair" in kp_res and "private_key" in kp_res["keypair"]:
                        key_name = kp_res["keypair"]["name"]
                        self.cache_keypairs[key_name] = key_name
                        self.after(0, lambda pk=kp_res["keypair"]["private_key"]: self._show_private_key_popup(pk))
                except: pass

            for i in range(count):
                vm_name = f"scale_vm_{str(time.time()).split('.')[0][-4:]}"
                self.log(f"  -> [{i+1}/{count}] Khởi tạo VM '{vm_name}' (Volume 10GB)...")

                script = f"""#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
apt-get update -y && apt-get install -y apache2 php libapache2-mod-php

rm -f /var/www/html/index.nginx-debian.html

cat << 'EOF' > /var/www/html/server_addr.php
<?php echo $_SERVER['SERVER_ADDR']; ?>
EOF

cat << 'EOF' > /var/www/html/http_host.php
<?php echo $_SERVER['HTTP_HOST']; ?>
EOF

cat << 'EOF' > /var/www/html/index.html
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lab 02 - Hệ tính toán phân bố</title>
    <style>
        body {{font-family: Arial, sans-serif; background: #f4f6fa; margin: 0; padding: 0;}}
        .container {{max-width: 600px; margin: 40px auto; background: #fff; border-radius: 10px; box-shadow: 0 2px 8px #0001; padding: 32px;}}
        h1 {{color: #2d6cdf;}}
        h2 {{color: #f50404;}}
    </style>
</head>
<body>
    <div class="container">
        <h1>Lab 02 - Hệ tính toán phân bố</h1>
        <h3>Chào mừng đến với web của Nhóm 9!</h3>
        <h2 class="server_addr">Địa chỉ IP (fixed): <span id="server_addr">Đang tải...</span></h2>
        <h2 class="http_host">Địa chỉ IP (floating): <span id="http_host">Đang tải...</span></h2>
    </div>
    <script>
        fetch('server_addr.php').then(r => r.text()).then(data => {{ document.getElementById('server_addr').innerText = data; }});
        fetch('http_host.php').then(r => r.text()).then(data => {{ document.getElementById('http_host').innerText = data; }});
    </script>
</body>
</html>
EOF

systemctl restart apache2
systemctl enable apache2
"""
                
                payload = {
                    "server": {
                        "name": vm_name, "flavorRef": flv_id, "networks": [{"uuid": net_id}], 
                        "user_data": base64.b64encode(script.encode()).decode(), "security_groups": [{"name": "default"}],
                        "block_device_mapping_v2": [{
                            "uuid": img_id, "source_type": "image", "destination_type": "volume",
                            "boot_index": 0, "volume_size": 10, "delete_on_termination": True
                        }]
                    }
                }
                
                # Gắn Key Pair
                if key_name:
                    payload["server"]["key_name"] = key_name
                
                srv_res = self._api_post(f"{self.get_ep('compute')}/{self.api.project_id}/servers", payload)
                srv_id = srv_res["server"]["id"]
                
                self.log(f"  -> Chờ VM {vm_name} khởi động (ACTIVE)...")
                self._wait_vm_active(srv_id)

                vm_info = self._api_get(f"{self.get_ep('compute')}/{self.api.project_id}/servers/{srv_id}")["server"]
                private_ip = list(vm_info["addresses"].values())[0][0]["addr"]

                # --- XỬ LÝ CẤP & GÁN FLOATING IP TỰ ĐỘNG CHO NODE SCALE UP ---
                ext_net_id = list(self.cache_ext_networks.values())[0] if getattr(self, 'cache_ext_networks', None) else None
                if ext_net_id:
                    try:
                        self.log(f"  -> Đang xin cấp và gán Floating IP cho {vm_name}...")
                        fip_res = self._api_post(f"{self.get_ep('network')}/v2.0/floatingips", {"floatingip": {"floating_network_id": ext_net_id}})
                        fip = fip_res["floatingip"]

                        ports = self._api_get(f"{self.get_ep('network')}/v2.0/ports?device_id={srv_id}").get("ports", [])
                        if ports:
                            self._api_put(f"{self.get_ep('network')}/v2.0/floatingips/{fip['id']}", {"floatingip": {"port_id": ports[0]['id']}})
                            self.log(f"     => Đã gán Public IP: {fip['floating_ip_address']}", False)
                            if hasattr(self, 'fetch_fips_data'):
                                self.fetch_fips_data() # Làm mới bảng Floating IP
                        else:
                            self.log(f"     => Lỗi: Không tìm thấy Port của VM để gán IP", True)
                    except Exception as e:
                        self.log(f"     => Lỗi xin cấp FIP: {e}", True)

                self.log(f"  -> Thêm VM IP ({private_ip}) vào Load Balancer Pool...")
                self._wait_lb_active(lb_id)
                self._api_post(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/pools/{pool_id}/members", {
                    "member": {"address": private_ip, "protocol_port": 80, "subnet_id": subnet_id}
                })
                self._wait_lb_active(lb_id)

            self.log(f"🚀 [Thành công] Đã Auto Scale Up và nhét {count} Node mới vào LB!", False)
            self.fetch_instances_data()
        except Exception as e:
            self.log(f"Lỗi Scale Up: {e}", True)

    def action_scale_down_req8(self):
        selected_ids = [lbid for lbid, var in getattr(self, 'selected_lbs', {}).items() if var.get() == "on"]
        if len(selected_ids) != 1:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ĐÚNG 1 Load Balancer trong bảng để Scale Down!")
            return
        
        lb_id = selected_ids[0]
        
        dialog = ctk.CTkInputDialog(text="Nhập số lượng VM muốn GỠ khỏi Load Balancer này:", title="Auto Scale Down")
        count_str = dialog.get_input()
        
        if not count_str: return
        
        try:
            count = int(count_str)
            if count <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Số lượng phải là số nguyên dương!")
            return
            
        threading.Thread(target=self._process_scale_down, args=(lb_id, count)).start()

    def _process_scale_down(self, lb_id, count):
        try:
            lb_details = self._api_get(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/loadbalancers/{lb_id}")
            pools = lb_details["loadbalancer"].get("pools", [])
            
            if not pools:
                return self.log("Lỗi: Load Balancer này chưa có Pool nào!", True)
            pool_id = pools[0]["id"]

            self.log(f"Bắt đầu Scale Down: Lấy danh sách Member...")
            members = self._api_get(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/pools/{pool_id}/members").get("members", [])
            current_count = len(members)
            
            if current_count == 0: 
                return self.log("Không có máy ảo nào trong Pool để Scale Down.")

            # --- KIỂM TRA GIỚI HẠN TỐI THIỂU (MIN 1 VM) ---
            if current_count - count < 1:
                max_can_delete = current_count - 1
                if max_can_delete <= 0:
                    self.log("Cảnh báo: Không thể Scale Down! Phải giữ lại ít nhất 1 máy ảo.", True)
                    self.after(0, lambda: messagebox.showwarning("Giới hạn Auto Scale", "Không thể Scale Down!\nPhải giữ lại ít nhất 1 máy ảo trong hệ thống để duy trì dịch vụ Web."))
                    return
                else:
                    self.log(f"Cảnh báo: Phải giữ lại ít nhất 1 máy ảo. Tự động giảm số lượng xóa xuống còn {max_can_delete}...", True)
                    count = max_can_delete

            for i in range(count):
                target_member = members[-(i+1)] # Lấy từ cuối danh sách lên
                target_ip = target_member["address"]
                
                self.log(f"  -> [{i+1}/{count}] Gỡ IP {target_ip} khỏi Load Balancer Pool...")
                self._wait_lb_active(lb_id)
                self._api_delete(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/pools/{pool_id}/members/{target_member['id']}")
                self._wait_lb_active(lb_id)

                self.log(f"  -> [{i+1}/{count}] Xóa Instance có IP {target_ip} khỏi OpenStack...")
                vms = self._api_get(f"{self.get_ep('compute')}/{self.api.project_id}/servers/detail").get("servers", [])
                for vm in vms:
                    ips = [a["addr"] for net in vm.get("addresses", {}).values() for a in net]
                    if target_ip in ips:
                        self._api_delete(f"{self.get_ep('compute')}/{self.api.project_id}/servers/{vm['id']}?force=true")
                        self.log(f"     => Đã xóa Instance '{vm['name']}' thành công!", False)
                        break
            
            self.log(f"🚀 [Thành công] Đã hoàn tất Scale Down {count} Nodes!", False)
            self.fetch_instances_data()
        except Exception as e:
            self.log(f"Lỗi Scale Down: {e}", True)

    # =====================================================================
    # TAB CÒN LẠI (IMAGES, FLAVORS, KEY PAIRS, ROUTERS, FIPS) VẪN GIỮ NGUYÊN
    # =====================================================================
    # TAB: FLOATING IPS (CẤP PHÁT & GÁN IP PUBLIC)
    # =====================================================================
    def render_fips_tab(self, parent):
        ctk.CTkLabel(parent, text="Project / Network / Floating IPs", text_color="gray", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(parent, text="Floating IPs", font=ctk.CTkFont(size=32, weight="normal")).pack(anchor="w", pady=(0, 15))
        
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.pack(fill="x", pady=5)
        
        # Nhóm nút hành động
        ctk.CTkButton(toolbar, text="+ Allocate IP to Project", fg_color="transparent", border_width=1, border_color="#E95420", text_color="#E95420", hover_color=("#FDE8E8", "#4A1A1A"), command=lambda: threading.Thread(target=self.action_allocate_fip).start()).pack(side="left", padx=(0, 5))
        ctk.CTkButton(toolbar, text="Associate (Gán IP)", fg_color="#2ecc71", hover_color="#27ae60", command=self.open_associate_fip_dialog).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Disassociate (Gỡ IP)", fg_color="#f39c12", hover_color="#d68910", command=lambda: threading.Thread(target=self.action_disassociate_fips).start()).pack(side="left", padx=5)

        ctk.CTkButton(toolbar, text="Release IPs (Xóa)", fg_color="#D9534F", hover_color="#C9302C", command=self.action_release_fips).pack(side="right", padx=(10, 0))
        ctk.CTkButton(toolbar, text="Refresh", width=80, fg_color="transparent", border_width=1, text_color=("#333", "white"), command=lambda: threading.Thread(target=self.fetch_fips_data).start()).pack(side="right", padx=10)

        self.table_fips_container = ctk.CTkFrame(parent, fg_color="transparent")
        self.table_fips_container.pack(fill="both", expand=True, pady=10)
        
        threading.Thread(target=self.fetch_fips_data).start()

    def fetch_fips_data(self):
        try:
            fips = self._api_get(f"{self.get_ep('network')}/v2.0/floatingips").get("floatingips", [])
            self.selected_fips = {}
            headers = ["", "IP Address", "Mapped Fixed IP", "Status", "Port ID"]
            widths = [30, 150, 200, 100, 300]
            
            def update_ui():
                data = []
                for f in fips:
                    self.selected_fips[f['id']] = ctk.StringVar(value="off")
                    status_color = "ACTIVE" if f['status'] == "ACTIVE" else "DOWN"
                    mapped_ip = f.get('fixed_ip_address') or "-"
                    port_id = f.get('port_id') or "-"
                    data.append([f['id'], f['floating_ip_address'], mapped_ip, status_color, port_id])
                
                self._draw_table_ui(self.table_fips_container, headers, data, widths, checkable=True, selected_vars=self.selected_fips)
            
            self.after(0, update_ui)
        except Exception as e:
            self.log(f"Lỗi tải FIPs: {e}", True)

    def action_allocate_fip(self):
        """Xin cấp IP mới từ mạng External đầu tiên tìm thấy"""
        try:
            if not getattr(self, 'cache_ext_networks', None):
                self.log("Lỗi: Không tìm thấy mạng External/Public nào để xin cấp IP.", True)
                self.after(0, lambda: messagebox.showwarning("Lỗi", "Không tìm thấy mạng External (Public_Net) để cấp phát IP!"))
                return
                
            ext_net_id = list(self.cache_ext_networks.values())[0]
            self.log(f"Đang xin cấp Floating IP mới từ mạng External...")
            
            self._api_post(f"{self.get_ep('network')}/v2.0/floatingips", {"floatingip": {"floating_network_id": ext_net_id}})
            
            self.log("-> Cấp phát Floating IP thành công!", False)
            self.fetch_fips_data()
        except Exception as e:
            self.log(f"Lỗi cấp FIP: {e}", True)

    def action_release_fips(self):
        """Xóa hẳn IP khỏi Project"""
        selected_ids = [fid for fid, var in getattr(self, 'selected_fips', {}).items() if var.get() == "on"]
        if not selected_ids:
            self.after(0, lambda: messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 IP để Release (Xóa)!"))
            return
            
        if messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn trả {len(selected_ids)} Floating IP này về cho hệ thống (Release)?"):
            def process():
                for fid in selected_ids:
                    try:
                        self.log(f"Đang trả Floating IP {fid} về pool chung...")
                        self._api_delete(f"{self.get_ep('network')}/v2.0/floatingips/{fid}")
                    except Exception as e:
                        self.log(f"Lỗi Release IP {fid}: {e}", True)
                self.log("-> Đã xóa Floating IPs thành công!")
                self.fetch_fips_data()
            threading.Thread(target=process).start()

    def action_disassociate_fips(self):
        """Gỡ IP khỏi thiết bị hiện tại (Chuyển port_id thành null)"""
        selected_ids = [fid for fid, var in getattr(self, 'selected_fips', {}).items() if var.get() == "on"]
        if not selected_ids:
            self.after(0, lambda: messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 IP để gỡ (Disassociate)!"))
            return

        def process():
            for fid in selected_ids:
                try:
                    self.log(f"Đang gỡ Floating IP {fid} khỏi thiết bị hiện tại...")
                    self._api_put(f"{self.get_ep('network')}/v2.0/floatingips/{fid}", {"floatingip": {"port_id": None}})
                except Exception as e:
                    self.log(f"Lỗi Disassociate IP {fid}: {e}", True)
            self.log("-> Đã gỡ thành công! IP đã trở về trạng thái rảnh rỗi.")
            self.fetch_fips_data()
            
        threading.Thread(target=process).start()

    # --- WIZARD GÁN IP (ASSOCIATE) ---
    def open_associate_fip_dialog(self):
        selected_ids = [fid for fid, var in getattr(self, 'selected_fips', {}).items() if var.get() == "on"]
        if len(selected_ids) != 1:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn CHÍNH XÁC 1 Floating IP để gán!")
            return
            
        fip_id = selected_ids[0]

        dialog = ctk.CTkToplevel(self)
        dialog.title("Manage Floating IP Associations")
        dialog.geometry("600x300")
        dialog.attributes("-topmost", True)
        dialog.focus_force()

        ctk.CTkLabel(dialog, text="Associate Floating IP", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", padx=20, pady=(20, 10))
        ctk.CTkLabel(dialog, text="Chọn Cổng (Port) thuộc máy ảo hoặc Load Balancer để gán IP:", text_color="gray").pack(anchor="w", padx=20)

        combo_ports = ctk.CTkComboBox(dialog, values=["Đang quét hệ thống để tìm thiết bị..."], width=500)
        combo_ports.pack(padx=20, pady=20)

        port_map = {} # Lưu trữ { "Tên hiển thị": "port_id" }

        def load_ports():
            try:
                # 1. Quét Máy Ảo (VMs)
                vms = self._api_get(f"{self.get_ep('compute')}/{self.api.project_id}/servers/detail").get("servers", [])
                for vm in vms:
                    # Lấy port mạng của từng VM
                    ports = self._api_get(f"{self.get_ep('network')}/v2.0/ports?device_id={vm['id']}").get("ports", [])
                    for p in ports:
                        ip_addr = p.get('fixed_ips', [{}])[0].get('ip_address', 'No IP')
                        display_name = f"🖥️ [Máy ảo] {vm['name']}  ({ip_addr})"
                        port_map[display_name] = p['id']

                # 2. Quét Load Balancers (LBs)
                lbs = self._api_get(f"{self.get_ep('loadbalancer')}/v2.0/lbaas/loadbalancers?project_id={self.api.project_id}").get("loadbalancers", [])
                for lb in lbs:
                    if lb.get('vip_port_id'):
                        display_name = f"⚖️ [Load Balancer] {lb['name']}  ({lb['vip_address']})"
                        port_map[display_name] = lb['vip_port_id']

                # Cập nhật danh sách thả xuống
                choices = list(port_map.keys())
                if choices:
                    combo_ports.configure(values=choices)
                    combo_ports.set(choices[0])
                else:
                    combo_ports.configure(values=["Không tìm thấy Máy ảo / Load Balancer nào có cổng mạng."])
            except Exception as e:
                self.log(f"Lỗi quét thiết bị: {e}", True)

        threading.Thread(target=load_ports).start()

        def do_associate():
            selected_str = combo_ports.get()
            port_id = port_map.get(selected_str)
            if not port_id:
                dialog.attributes("-topmost", False)
                messagebox.showwarning("Lỗi", "Cổng không hợp lệ hoặc đang tải!")
                dialog.attributes("-topmost", True)
                return
                
            dialog.destroy()
            
            def process():
                try:
                    self.log(f"Đang gán Floating IP vào thiết bị: {selected_str}...")
                    self._api_put(f"{self.get_ep('network')}/v2.0/floatingips/{fip_id}", {"floatingip": {"port_id": port_id}})
                    self.log("-> Gán Floating IP thành công!", False)
                    self.fetch_fips_data()
                except Exception as e:
                    self.log(f"Lỗi khi gán IP: {e}", True)
            
            threading.Thread(target=process).start()

        footer = ctk.CTkFrame(dialog, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=20, pady=20)
        ctk.CTkButton(footer, text="Cancel", fg_color="gray", width=100, command=dialog.destroy).pack(side="right", padx=5)
        ctk.CTkButton(footer, text="Associate", fg_color="#E95420", hover_color="#d6491b", command=do_associate).pack(side="right", padx=5)