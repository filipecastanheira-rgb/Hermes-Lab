class ModeProfile:
    def __init__(self, mode):
        self.mode = mode.lower()
        self.profile = {}

        self._definir_perfil()

    def _definir_perfil(self):
        """
        Define o comportamento interno de cada modo.
        """

        if self.mode == "blue":
            self.profile = {
                "nome": "BLUE",
                "descricao": "Modo defensivo. Monitorização, scanner, alertas, logs.",
                "modulos_ativos": ["scanner", "alert_engine", "log_manager"],
                "permissoes": {
                    "scan_rede": True,
                    "ataque": False,
                    "exploit": False,
                    "monitorizacao": True
                },
                "nivel_risco": "baixo"
            }

        elif self.mode == "red":
            self.profile = {
                "nome": "RED",
                "descricao": "Modo ofensivo. Recon agressivo, exploits, ataques controlados.",
                "modulos_ativos": ["recon_engine", "exploit_engine"],
                "permissoes": {
                    "scan_rede": True,
                    "ataque": True,
                    "exploit": True,
                    "monitorizacao": False
                },
                "nivel_risco": "alto"
            }

        elif self.mode == "purple":
            self.profile = {
                "nome": "PURPLE",
                "descricao": "Modo híbrido. Combina defesa e ataque com regras específicas.",
                "modulos_ativos": ["scanner", "alert_engine", "recon_engine"],
                "permissoes": {
                    "scan_rede": True,
                    "ataque": True,
                    "exploit": False,  # exploits desativados para segurança
                    "monitorizacao": True
                },
                "nivel_risco": "médio"
            }

        else:
            # fallback
            self.profile = {
                "nome": "SAFE",
                "descricao": "Modo seguro. Apenas operações básicas.",
                "modulos_ativos": [],
                "permissoes": {
                    "scan_rede": False,
                    "ataque": False,
                    "exploit": False,
                    "monitorizacao": False
                },
                "nivel_risco": "mínimo"
            }

    def obter_perfil(self):
        """
        Devolve o perfil completo do modo atual.
        """
        return self.profile

