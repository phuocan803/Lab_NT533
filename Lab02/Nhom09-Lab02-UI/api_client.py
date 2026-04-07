import requests
import time
from config import API_ENDPOINTS

class OpenStackAPI:
    def __init__(self):
        self.token = None
        self.project_id = None
        self.username = None

    def get_headers(self):
        """Tạo header chứa Token xác thực cho các request"""
        if not self.token:
            raise Exception("Chưa xác thực (Missing Token). Vui lòng đăng nhập lại!")
        return {
            "X-Auth-Token": self.token, 
            "Content-Type": "application/json"
        }

    # ==========================================
    # 1. IDENTITY (Keystone) - Xác thực
    # ==========================================
    def login(self, username, password, project):
        """Đăng nhập và lấy Token + Project ID"""
        url = f"{API_ENDPOINTS['identity']}/auth/tokens"
        payload = {
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {"name": username, "domain": {"name": "Default"}, "password": password}
                    }
                },
                "scope": {
                    "project": {"name": project, "domain": {"id": "default"}}
                }
            }
        }
        res = requests.post(url, json=payload)
        
        if res.status_code == 201:
            self.token = res.headers.get("X-Subject-Token")
            self.project_id = res.json()["token"]["project"]["id"]
            self.username = username
            return True
        else:
            raise Exception(f"HTTP {res.status_code}: {res.text}")

    def logout(self):
        """Xóa phiên đăng nhập hiện tại"""
        self.token = None
        self.project_id = None
        self.username = None

    # ==========================================
    # 2. COMPUTE (Nova) & IMAGE (Glance)
    # ==========================================
    def get_flavors(self):
        res = requests.get(f"{API_ENDPOINTS['compute']}/{self.project_id}/flavors/detail", headers=self.get_headers())
        res.raise_for_status()
        return res.json().get("flavors", [])

    def get_images(self):
        res = requests.get(f"{API_ENDPOINTS['image']}/v2/images", headers=self.get_headers())
        res.raise_for_status()
        return res.json().get("images", [])

    def get_vms(self):
        res = requests.get(f"{API_ENDPOINTS['compute']}/{self.project_id}/servers/detail", headers=self.get_headers())
        res.raise_for_status()
        return res.json().get("servers", [])

    def create_server(self, name, image_id, flavor_id, net_id, user_data_b64=""):
        """Khởi tạo một máy ảo mới"""
        payload = {
            "server": {
                "name": name,
                "imageRef": image_id,
                "flavorRef": flavor_id,
                "networks": [{"uuid": net_id}],
                "security_groups": [{"name": "default"}]
            }
        }
        if user_data_b64:
            payload["server"]["user_data"] = user_data_b64

        res = requests.post(f"{API_ENDPOINTS['compute']}/{self.project_id}/servers", headers=self.get_headers(), json=payload)
        res.raise_for_status()
        return res.json()["server"]

    def delete_server(self, server_id):
        res = requests.delete(f"{API_ENDPOINTS['compute']}/{self.project_id}/servers/{server_id}?force=true", headers=self.get_headers())
        if res.status_code not in [202, 204]:
            raise Exception(f"Xóa VM thất bại: {res.text}")

    def wait_for_server_active(self, server_id, timeout=120):
        """Hàm đợi máy ảo boot xong (trạng thái ACTIVE)"""
        start = time.time()
        while time.time() - start < timeout:
            res = requests.get(f"{API_ENDPOINTS['compute']}/{self.project_id}/servers/{server_id}", headers=self.get_headers())
            if res.status_code == 200:
                status = res.json()["server"]["status"]
                if status == "ACTIVE": return True
                if status == "ERROR": raise Exception("Trạng thái máy ảo: ERROR")
            time.sleep(5)
        raise Exception("Quá thời gian chờ (Timeout) máy ảo khởi động.")

    # ==========================================
    # 3. NETWORK (Neutron)
    # ==========================================
    def get_networks(self):
        res = requests.get(f"{API_ENDPOINTS['network']}/v2.0/networks", headers=self.get_headers())
        res.raise_for_status()
        return res.json().get("networks", [])

    def create_network(self, name):
        payload = {"network": {"name": name, "admin_state_up": True}}
        res = requests.post(f"{API_ENDPOINTS['network']}/v2.0/networks", headers=self.get_headers(), json=payload)
        res.raise_for_status()
        return res.json()["network"]

    def create_subnet(self, name, network_id, cidr="192.168.10.0/24", dns=["8.8.8.8"]):
        payload = {
            "subnet": {
                "name": name, "network_id": network_id, 
                "ip_version": 4, "cidr": cidr, "dns_nameservers": dns
            }
        }
        res = requests.post(f"{API_ENDPOINTS['network']}/v2.0/subnets", headers=self.get_headers(), json=payload)
        res.raise_for_status()
        return res.json()["subnet"]

    def create_router(self, name, ext_net_id):
        payload = {
            "router": {
                "name": name, "admin_state_up": True, 
                "external_gateway_info": {"network_id": ext_net_id}
            }
        }
        res = requests.post(f"{API_ENDPOINTS['network']}/v2.0/routers", headers=self.get_headers(), json=payload)
        res.raise_for_status()
        return res.json()["router"]

    def add_router_interface(self, router_id, subnet_id):
        res = requests.put(f"{API_ENDPOINTS['network']}/v2.0/routers/{router_id}/add_router_interface", headers=self.get_headers(), json={"subnet_id": subnet_id})
        res.raise_for_status()

    # --- TÍNH NĂNG FLOATING IP ---
    def get_vm_ports(self, device_id):
        res = requests.get(f"{API_ENDPOINTS['network']}/v2.0/ports?device_id={device_id}", headers=self.get_headers())
        res.raise_for_status()
        return res.json().get("ports", [])

    def allocate_floating_ip(self, ext_net_id):
        payload = {"floatingip": {"floating_network_id": ext_net_id}}
        res = requests.post(f"{API_ENDPOINTS['network']}/v2.0/floatingips", headers=self.get_headers(), json=payload)
        res.raise_for_status()
        return res.json()["floatingip"]

    def attach_floating_ip(self, floating_ip_id, port_id):
        payload = {"floatingip": {"port_id": port_id}}
        res = requests.put(f"{API_ENDPOINTS['network']}/v2.0/floatingips/{floating_ip_id}", headers=self.get_headers(), json=payload)
        res.raise_for_status()

    # ==========================================
    # 4. LOAD BALANCER (Octavia)
    # ==========================================
    def wait_for_lb_active(self, lb_id, timeout=180):
        """Chờ Load Balancer chuyển sang trạng thái ACTIVE (Bắt buộc trước mỗi lệnh chỉnh sửa LB)"""
        start = time.time()
        while time.time() - start < timeout:
            res = requests.get(f"{API_ENDPOINTS['loadbalancer']}/v2.0/lbaas/loadbalancers/{lb_id}", headers=self.get_headers())
            if res.status_code == 200:
                status = res.json()["loadbalancer"]["provisioning_status"]
                if status == "ACTIVE": return True
                if status == "ERROR": raise Exception("Load Balancer đang ở trạng thái ERROR")
            time.sleep(5)
        raise Exception("Quá thời gian chờ Load Balancer kích hoạt.")

    def create_load_balancer(self, name, vip_subnet_id):
        payload = {"loadbalancer": {"name": name, "vip_subnet_id": vip_subnet_id}}
        res = requests.post(f"{API_ENDPOINTS['loadbalancer']}/v2.0/lbaas/loadbalancers", headers=self.get_headers(), json=payload)
        res.raise_for_status()
        return res.json()["loadbalancer"]

    def create_listener(self, name, lb_id, port=80):
        payload = {"listener": {"name": name, "protocol": "HTTP", "protocol_port": port, "loadbalancer_id": lb_id}}
        res = requests.post(f"{API_ENDPOINTS['loadbalancer']}/v2.0/lbaas/listeners", headers=self.get_headers(), json=payload)
        res.raise_for_status()
        return res.json()["listener"]

    def create_pool(self, name, listener_id, algo="ROUND_ROBIN"):
        payload = {"pool": {"name": name, "protocol": "HTTP", "lb_algorithm": algo, "listener_id": listener_id}}
        res = requests.post(f"{API_ENDPOINTS['loadbalancer']}/v2.0/lbaas/pools", headers=self.get_headers(), json=payload)
        res.raise_for_status()
        return res.json()["pool"]

    def create_health_monitor(self, pool_id):
        payload = {
            "healthmonitor": {
                "pool_id": pool_id, "type": "HTTP", "delay": 10,
                "timeout": 10, "max_retries": 3, "url_path": "/"
            }
        }
        res = requests.post(f"{API_ENDPOINTS['loadbalancer']}/v2.0/lbaas/healthmonitors", headers=self.get_headers(), json=payload)
        res.raise_for_status()
        return res.json()["healthmonitor"]

    def get_pool_members(self, pool_id):
        res = requests.get(f"{API_ENDPOINTS['loadbalancer']}/v2.0/lbaas/pools/{pool_id}/members", headers=self.get_headers())
        res.raise_for_status()
        return res.json().get("members", [])

    def add_pool_member(self, pool_id, subnet_id, ip_address, port=80):
        payload = {"member": {"address": ip_address, "protocol_port": port, "subnet_id": subnet_id}}
        res = requests.post(f"{API_ENDPOINTS['loadbalancer']}/v2.0/lbaas/pools/{pool_id}/members", headers=self.get_headers(), json=payload)
        res.raise_for_status()
        return res.json()["member"]

    def remove_pool_member(self, pool_id, member_id):
        res = requests.delete(f"{API_ENDPOINTS['loadbalancer']}/v2.0/lbaas/pools/{pool_id}/members/{member_id}", headers=self.get_headers())
        if res.status_code not in [202, 204]:
            raise Exception(f"Xóa Member thất bại: {res.text}")

    # --- CÁC HÀM TỔNG HỢP (SCALE UP / DOWN) ---
    def scale_up_vm_to_lb(self, lb_id, pool_id, subnet_id, vm_name, image_id, flavor_id, net_id, user_data_b64=""):
        """Tạo VM mới, chờ khởi động, sau đó gắn IP vào Load Balancer Pool"""
        # 1. Tạo VM
        new_vm = self.create_server(vm_name, image_id, flavor_id, net_id, user_data_b64)
        
        # 2. Chờ VM ACTIVE
        self.wait_for_server_active(new_vm['id'])
        
        # 3. Lấy IP private của VM vừa tạo
        vm_info = requests.get(f"{API_ENDPOINTS['compute']}/{self.project_id}/servers/{new_vm['id']}", headers=self.get_headers()).json()["server"]
        private_ip = list(vm_info["addresses"].values())[0][0]["addr"]
        
        # 4. Thêm IP vào LB Pool (Bắt buộc chờ LB ACTIVE trước khi thêm)
        self.wait_for_lb_active(lb_id)
        member = self.add_pool_member(pool_id, subnet_id, private_ip)
        self.wait_for_lb_active(lb_id)
        
        return new_vm, member

    def scale_down_vm_from_lb(self, lb_id, pool_id):
        """Xóa Member cuối cùng khỏi Pool và xóa luôn VM tương ứng"""
        # 1. Lấy danh sách members
        members = self.get_pool_members(pool_id)
        if not members:
            raise Exception("Không có thành viên nào trong Pool để Scale Down!")
        
        target_member = members[-1]
        target_ip = target_member["address"]
        
        # 2. Xóa member khỏi LB Pool
        self.wait_for_lb_active(lb_id)
        self.remove_pool_member(pool_id, target_member['id'])
        self.wait_for_lb_active(lb_id)
        
        # 3. Tìm VM dựa trên IP và Xóa VM
        vms = self.get_vms()
        for vm in vms:
            ips = [a["addr"] for net in vm.get("addresses", {}).values() for a in net]
            if target_ip in ips:
                self.delete_server(vm['id'])
                return vm['name'], target_ip
                
        return None, target_ip