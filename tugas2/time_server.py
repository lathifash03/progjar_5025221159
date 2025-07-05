# time_server.py
import socket
import threading
from datetime import datetime

def handle_client(conn, addr):
    print(f"[INFO] Koneksi baru dari {addr}")
    done = False
    while not done:
        data = conn.recv(1024)
        if not data:
            print(f"[WARNING] Tidak ada data dari {addr}, koneksi ditutup.")
            break

        message = data.decode('utf-8').strip()
        print(f"[INFO] Perintah dari {addr}: {message}")

        if message == "TIME":
            waktu = datetime.now().strftime("%H:%M:%S")
            reply = f"JAM {waktu}\r\n"
            conn.sendall(reply.encode('utf-8'))
        elif message == "QUIT":
            print(f"[INFO] {addr} mengakhiri koneksi.")
            done = True
        else:
            conn.sendall(b"INVALID COMMAND\r\n")

    conn.close()
    print(f"[INFO] Koneksi dengan {addr} ditutup.")

def run_server(host="0.0.0.0", port=45000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen()
        print(f"[INFO] Time Server berjalan di {host}:{port}")

        while True:
            client_conn, client_addr = s.accept()
            thread = threading.Thread(target=handle_client, args=(client_conn, client_addr))
            thread.daemon = True
            thread.start()
            print(f"[INFO] Thread aktif: {threading.active_count()-1}")

if __name__ == "__main__":
    run_server()
