# red.py
# Comandos do modo RED (estrutura base)

def register(router):
    router.register("red_test", red_test)

def red_test(*args, **kwargs):
    print("[RED] Comando de teste executado (estrutura base).")

