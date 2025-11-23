# Arquivo: rnp_topo.py
from mininet.topo import Topo

class RNPTopo(Topo):
    """
    Topologia simplificada da RNP com 6 nós, um host por switch.
    Definimos parâmetros de latência e largura de banda (BW).
    """
    def build(self):
        # 1. Adicionar Switches (Representando PoPs - Pontos de Presença)
        sps = []
        for i in range(1, 7):
            sps.append(self.addSwitch(f's{i}', protocols='OpenFlow13'))

        # 2. Adicionar Hosts (Um host por PoP/Switch)
        hosts = []
        for i in range(1, 7):
            # IP inicial 10.0.0.X/24
            hosts.append(self.addHost(f'h{i}', ip=f'10.0.0.{i}/24'))
            # Conexão Switch-Host
            self.addLink(sps[i-1], hosts[i-1])

        # 3. Adicionar Links (Conexões RNP - Exemplo de interconexão e valores)
        # Latência (delay) e Largura de Banda (bw)
        
        # Exemplo de Backbone: São Paulo (s1) -> Rio de Janeiro (s2)
        self.addLink(sps[0], sps[1], bw=1000, delay='5ms') 
        
        # Exemplo: Rio de Janeiro (s2) -> Belo Horizonte (s3)
        self.addLink(sps[1], sps[2], bw=500, delay='8ms')
        
        # Exemplo: Belo Horizonte (s3) -> Brasília (s4)
        self.addLink(sps[2], sps[3], bw=800, delay='10ms')
        
        # Exemplo: São Paulo (s1) -> Curitiba (s5)
        self.addLink(sps[0], sps[4], bw=1000, delay='6ms')
        
        # Exemplo: Brasília (s4) -> Fortaleza (s6)
        self.addLink(sps[3], sps[5], bw=200, delay='20ms') 
        
        # Link de backup/adicional
        self.addLink(sps[4], sps[5], bw=150, delay='25ms')

topos = { 'rnp_topo': RNPTopo }