## 11. Tạo repository mới và đẩy code lên GitHub

Nếu bạn muốn tạo repository mới và đẩy code lên GitHub, làm như sau:

```sh
echo "# Lab_NT533" >> README.md
git init
git add README.md
git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/phuocan803/Lab_NT533.git
git push -u origin main
```

Lưu ý: Bạn cần đăng nhập GitHub và có quyền push lên repository.
# Hướng dẫn triển khai Web với Compute trên OpenStack

- Đăng nhập dashboard OpenStack (Horizon).
- Vào Project → Compute → Instances → Launch Instance.
- Chọn Image: Ubuntu 20.04/22.04.
- Chọn Flavor (tối thiểu 1 vCPU, 1GB RAM).
- Thiết lập key pair để SSH.
- Gán network (nên chọn network có thể truy cập từ máy thật).
- Mở các cổng cần thiết (22, 80, 443) trong Security Group.

## 1. Kết nối SSH vào máy ảo

# Hướng dẫn triển khai Web tĩnh trên OpenStack (Ubuntu/CentOS)

## 1. Tạo máy ảo trên OpenStack

- Đăng nhập dashboard OpenStack (Horizon).
- Vào Project → Compute → Instances → Launch Instance.
- Chọn Image: Ubuntu 20.04/22.04 hoặc CentOS 7/8.
- Chọn Flavor (tối thiểu 1 vCPU, 1GB RAM).
- Thiết lập key pair để SSH.
- Gán network (nên chọn network có thể truy cập từ máy thật).
- Mở các cổng cần thiết (22, 80, 443) trong Security Group.

## 2. Kết nối SSH vào máy ảo

```sh
ssh -i <file-key.pem> ubuntu@<Floating-IP hoặc IP nội bộ>
# hoặc với CentOS:
ssh -i <file-key.pem> centos@<Floating-IP hoặc IP nội bộ>
```

## 3. Cập nhật hệ thống

```sh
# Ubuntu
sudo apt update && sudo apt upgrade -y
# CentOS
sudo yum update -y
```

## 4. Cài đặt Web Server

### Ubuntu

```sh
sudo apt install nginx apache2 -y
```

### CentOS

```sh
sudo yum install nginx httpd -y
```

## 5. Khởi động và enable dịch vụ

### Ubuntu

```sh
sudo systemctl start nginx
sudo systemctl enable nginx
sudo systemctl start apache2
sudo systemctl enable apache2
```

### CentOS

```sh
sudo systemctl start nginx
sudo systemctl enable nginx
sudo systemctl start httpd
sudo systemctl enable httpd
```

## 6. Lấy mã nguồn web tĩnh

- Cài git nếu chưa có:

  ```sh
  sudo apt install git -y   # Ubuntu
  sudo yum install git -y   # CentOS
  ```

- Clone mã nguồn:

  ```sh
  git clone https://github.com/phuocan803/Lab_NT533.git
  ```

- Thư mục web nằm ở: Lab_NT533/web-basic/public

## 7. Copy code vào thư mục web server

```sh
sudo cp -r ~/Lab_NT533/web-basic/public/* /var/www/html/
```

## 8. Cấp quyền cho thư mục web

```sh
# Ubuntu (nginx/apache2)
sudo chown -R www-data:www-data /var/www/html

# CentOS (nginx/httpd)
sudo chown -R apache:apache /var/www/html
```

## 9. Mở firewall (nếu cần)

```sh
# Ubuntu
sudo ufw allow OpenSSH
sudo ufw allow 80,443/tcp
sudo ufw enable

# CentOS
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## 10. Truy cập web từ máy thật

- Truy cập: http://<Floating-IP hoặc IP_VM> trên trình duyệt máy thật.

---

Nếu cần triển khai với nginx, apache2, httpd thì chỉ cần copy code vào /var/www/html/ và đảm bảo dịch vụ đã khởi động, cấp quyền đúng như trên. Không cần scp nếu đã clone mã nguồn trực tiếp trên máy ảo.

- Đảm bảo Security Group đã mở các cổng cần thiết.
- Nếu dùng IP nội bộ, máy thật phải cùng mạng với VM hoặc có VPN.

---

Nếu cần hướng dẫn cấu hình nâng cao hoặc gặp lỗi, hãy liên hệ để được hỗ trợ thêm!
