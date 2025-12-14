# Arquivo: rnp_topo.py
from mininet.topo import Topo

class RNPTopo(Topo):
    """
    Topologia baseada na rede da RNP, com 6 PoPs (switches)
    e um host conectado a cada PoP.
    """

    def build(self):

        # === 1. Criar switches (PoPs) ===
        sps = []
        for i in range(1, 7):
            s = self.addSwitch(
                f's{i}', 
                protocols='OpenFlow13'  # garante compatibilidade com OS-Ken
            )
            sps.append(s)

        # === 2. Criar hosts e conectá-los aos switches ===
        for i in range(1, 7):
            h = self.addHost(f'h{i}', ip=f'10.0.0.{i}/24')
            self.addLink(sps[i-1], h)

        # === 3. Criar enlaces representando conexões RNP ===

        # São Paulo (s1) -> Rio de Janeiro (s2)
        self.addLink(sps[0], sps[1], bw=1000, delay='5ms')

        # Rio -> Belo Horizonte
        self.addLink(sps[1], sps[2], bw=500, delay='8ms')

        # BH -> Brasília
        self.addLink(sps[2], sps[3], bw=800, delay='10ms')

        # São Paulo -> Curitiba
        self.addLink(sps[0], sps[4], bw=1000, delay='6ms')

        # Brasília -> Fortaleza
        self.addLink(sps[3], sps[5], bw=200, delay='20ms')


     

# Registrar topologia
topos = { 'rnp_topo': RNPTopo }
