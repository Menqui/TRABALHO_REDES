from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet, arp
from os_ken.lib import hub
import time

class SDNMonitorRNP(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SDNMonitorRNP, self).__init__(*args, **kwargs)
        self.datapaths = {}    # {dpid: datapath_obj}
        self.port_stats = {}   # Para armazenar estatísticas de porta
        self.monitor_thread = hub.spawn(self._monitor)

    def add_flow(self, datapath, priority, match, actions, idle_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst,
                                idle_timeout=idle_timeout)
        datapath.send_msg(mod)

    # ======= AQUI É A PARTE IMPORTANTE =========
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # guarda datapath para o monitor
        self.datapaths[datapath.id] = datapath

        # Regra única: manda tudo para o pipeline NORMAL do OVS
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_NORMAL)]
        self.add_flow(datapath, 0, match, actions)
    # ===========================================

    # PODE comentar completamente o packet_in_handler,
    # ele não é mais necessário. Ex.:
    #
    # @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    # def _packet_in_handler(self, ev):
    #     pass
    #
    # (ou simplesmente apaga o método inteiro)

    def _monitor(self):
        while True:
            for dp_id, dp in self.datapaths.items():
                self._request_stats(dp)
            hub.sleep(5)

    def _request_stats(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
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
            self.logger.info('%4x %10d %10d %10d %10d',
                             stat.port_no, stat.rx_packets, stat.tx_packets,
                             stat.rx_bytes, stat.tx_bytes)

            self.port_stats[dpid][stat.port_no] = {
                'rx_bytes': stat.rx_bytes,
                'tx_bytes': stat.tx_bytes,
                'timestamp': time.time()
            }
