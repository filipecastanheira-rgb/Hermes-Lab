# purple_client.py
# Cliente PURPLE em modo desenvolvimento (não envia pedidos reais)

class PurpleClientDev:
    def __init__(self):
        print("[PurpleClient] (DEV) Cliente inicializado.")

    def prepare_request(self, endpoint: str, payload: dict):
        print(f"[PurpleClient] (DEV) Preparado para enviar: https://localhost/purple/api{endpoint}")
        print(f"[PurpleClient] (DEV) Payload: {payload}")
        print("[PurpleClient] (DEV) Headers: {'Content-Type': 'application/json', 'X-Hermes-Token': 'TOKEN_DEV_AQUI'}")
        print("[PurpleClient] (DEV) HTTPS ativo (Nginx fará TLS).")
        print("[PurpleClient] (DEV) Nenhum pedido real enviado (modo desenvolvimento).")

