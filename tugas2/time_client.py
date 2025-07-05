# time_client.py
import socket

def main():
    host = '172.16.16.101'  # Ganti sesuai IP servermu
    port = 45000

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.connect((host, port))
            print(f"Tersambung ke {host}:{port}")

            while True:
                command = input("Ketik TIME atau QUIT: ").strip().upper()
                if command not in ["TIME", "QUIT"]:
                    print("Perintah tidak dikenali.")
                    continue

                full_cmd = f"{command}\r\n"
                sock.sendall(full_cmd.encode('utf-8'))

                if command == "QUIT":
                    print("Mengakhiri koneksi...")
                    break

                data = sock.recv(1024)
                if not data:
                    print("Server memutus koneksi.")
                    break

                print(f"Respon server: {data.decode('utf-8').strip()}")

        except Exception as e:
            print(f"Koneksi gagal: {e}")

if __name__ == "__main__":
    main()
