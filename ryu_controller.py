# Arquivo: ryu_controller.py
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp
from ryu.lib import hub
import time

class SDNMonitorRNP(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SDNMonitorRNP, self).__init__(*args, **kwargs)
        self.mac_to_port = {}  # {dpid: {mac: port}}
        self.datapaths = {}    # {dpid: datapath_obj}
        
        # Variáveis para monitoramento
        self.port_stats = {}   # Para armazenar estatísticas de porta
        self.monitor_thread = hub.spawn(self._monitor)

    def add_flow(self, datapath, priority, match, actions, idle_timeout=0):
        # Auxiliar para instalar regras de fluxo
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst,
                                idle_timeout=idle_timeout)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Salva o datapath e instala a regra "Table-miss" (Flood e vai para o Controller)
        self.datapaths[datapath.id] = datapath
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions) # Prioridade 0 (default)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        self.mac_to_port.setdefault(dpid, {})

        # 1. MAC Learning: Aprende a localização do host de origem
        self.mac_to_port[dpid][src] = in_port

        out_port = ofproto.OFPP_FLOOD
        
        # 2. Reactive Forwarding: Verifica se o destino é conhecido
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
            
            # Se for conhecido, instala a regra de fluxo no switch (evita PacketIn futuro)
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            # Regra para pacotes TCP/IP não precisa de timeout, mas aqui usaremos 10s
            self.add_flow(datapath, 1, match, [parser.OFPActionOutput(out_port)], idle_timeout=10)
        
        # 3. Encaminha o pacote (Output)
        actions = [parser.OFPActionOutput(out_port)]
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def _monitor(self):
        # Thread para coleta periódica de estatísticas
        while True:
            for dp_id, dp in self.datapaths.items():
                self._request_stats(dp)
            hub.sleep(5) # Coleta a cada 5 segundos

    def _request_stats(self, datapath):
        # Solicita estatísticas de Portas (para vazão) e Fluxos (opcional)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # Solicita estatísticas de Portas
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        
        self.port_stats.setdefault(dpid, {})

        self.logger.info('--- Monitoramento de Tráfego (Switch %s) ---', dpid)
        self.logger.info('Porta        Rx Pkts    Tx Pkts    Rx Bytes   Tx Bytes')
        self.logger.info('-------------------------------------------------------')

        for stat in body:
            # Cálculo de Vazão (Bytes por segundo) exige comparação com o valor anterior
            
            # --- Lógica simplificada de Logging para o Professor ---
            self.logger.info('%4x %10d %10d %10d %10d',
                             stat.port_no, stat.rx_packets, stat.tx_packets,
                             stat.rx_bytes, stat.tx_bytes)
            
            # Armazenamento de dados (para análise mais complexa no run_tests.py se necessário)
            self.port_stats[dpid][stat.port_no] = {
                'rx_bytes': stat.rx_bytes,
                'tx_bytes': stat.tx_bytes,
                'timestamp': time.time()
            }