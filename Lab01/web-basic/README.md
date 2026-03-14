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
```

## 3. Cập nhật hệ thống

```sh
sudo apt update && sudo apt upgrade -y
```

- Cài git nếu chưa có:

```sh
sudo apt install git -y 
```

- Clone mã nguồn:

```sh
git clone https://github.com/phuocan803/Lab_NT533.git
```

## 4. Cài đặt nginx

```sh
sudo apt install nginx -y
```

- Copy toàn bộ nội dung thư mục Lab_NT533/Lab01/web-basic/public vào /var/www/html/:

```sh
sudo cp -r ~/Lab_NT533/Lab01/web-basic/public/* /var/www/html/
```

- Cấp quyền cho web server:

```sh
sudo chown -R www-data:www-data /var/www/html
```

- Thêm vào file cấu hình nginx (thường là /etc/nginx/sites-available/default):

  ```nginx
  location /server-ip {
      default_type text/plain;
      return 200 "$hostname";
  }
  ```

- Reload nginx:

  ```sh
  sudo systemctl reload nginx
  ```

## 6. Triển khai web tĩnh

- Copy toàn bộ nội dung thư mục Lab_NT533/web-basic/public vào /var/www/html/:

  ```sh
  sudo cp -r ~/Lab_NT533/web-basic/public/* /var/www/html/
  ```

- Cấp quyền cho web server:
  - Ubuntu:

    ```sh
    sudo chown -R www-data:www-data /var/www/html
    ```

  - CentOS:

    ```sh
    sudo chown -R apache:apache /var/www/html
    ```

## 7. Cấu hình nginx trả về hostname/IP server

- Thêm vào file cấu hình nginx (thường là /etc/nginx/sites-available/default):

```nginx

location /server_addr {
            default_type text/plain;
            return 200 "$server_addr";

}

location /http_host {
            default_type text/plain;
            return 200 "$http_host";
}

```

- Reload nginx:

  ```sh
  sudo systemctl reload nginx
  ```

## 8. Truy cập web và xem IP server

- Mở trình duyệt, truy cập http://<IP_VM>
- Trang sẽ tự động hiển thị hostname (hoặc IP nếu bạn thay $hostname bằng IP tĩnh) của server.

- Mở trình duyệt, truy cập http://<IP_VM>
- Trang sẽ tự động hiển thị hostname (hoặc IP nếu bạn thay $hostname bằng IP tĩnh) của server.
- Chọn Flavor (tối thiểu 1 vCPU, 1GB RAM).
- Thiết lập key pair để SSH.
- Gán network (nên chọn network có thể truy cập từ máy thật).
- Mở các cổng cần thiết (22, 80, 443) trong Security Group.
