import socket
try:
    socket.create_connection(("api.hyperliquid.xyz", 443), timeout=3)
    print("OK")
except:
    exit(1)