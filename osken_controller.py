import eventlet
eventlet.monkey_patch()

import csv
import time
from datetime import datetime

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet
from os_ken.lib import hub


class SimpleSwitch13(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)

        # L2 learning
        self.mac_to_port = {}

        # --- Monitoramento ---
        self.datapaths = {}           # dpid -> datapath
        self.prev_port = {}           # (dpid, port_no) -> (rx_bytes, tx_bytes, t)

        self.csv_file = open("trafego_switch.csv", "w", newline="")
        self.csv = csv.writer(self.csv_file)
        self.csv.writerow([
            "timestamp", "dpid", "port_no",
            "rx_packets", "tx_packets", "rx_bytes", "tx_bytes",
            "rx_mbps", "tx_mbps"
        ])

        self.monitor_thread = hub.spawn(self._monitor)

    # Track switches connect/disconnect
    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        dpid = datapath.id

        if ev.state == MAIN_DISPATCHER:
            self.datapaths[dpid] = datapath
            self.logger.info("Switch conectado: dpid=%s", dpid)
        elif ev.state == DEAD_DISPATCHER:
            if dpid in self.datapaths:
                del self.datapaths[dpid]
            self.logger.info("Switch desconectado: dpid=%s", dpid)

    # Default table-miss -> controller
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst)
        datapath.send_msg(mod)

    # L2 learning switch
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None:
            return

        # Ignorar LLDP
        if eth.ethertype == 35020:
            return

        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        # aprende
        self.mac_to_port[dpid][src] = in_port

        # decide saída
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # instala flow se destino conhecido
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_src=src, eth_dst=dst)
            self.add_flow(datapath, 1, match, actions)

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        )
        datapath.send_msg(out)

    # -------- Monitoramento: polling de PortStats --------
    def _monitor(self):
        while True:
            for dp in list(self.datapaths.values()):
                self._request_port_stats(dp)
            hub.sleep(1)  # intervalo (seg)

    def _request_port_stats(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        dpid = dp.id
        ofproto = dp.ofproto

        now = time.time()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ordena por porta pra ficar legível
        for stat in sorted(msg.body, key=lambda s: s.port_no):
            # ignora portas lógicas especiais
            if stat.port_no > ofproto.OFPP_MAX:
                continue

            rx_bytes = stat.rx_bytes
            tx_bytes = stat.tx_bytes

            key = (dpid, stat.port_no)
            prev = self.prev_port.get(key)

            if prev is None:
                rx_mbps = 0.0
                tx_mbps = 0.0
            else:
                prx, ptx, pt = prev
                dt = max(now - pt, 1e-6)
                rx_mbps = (rx_bytes - prx) * 8.0 / dt / 1e6
                tx_mbps = (tx_bytes - ptx) * 8.0 / dt / 1e6

            self.prev_port[key] = (rx_bytes, tx_bytes, now)

            self.csv.writerow([
                ts, dpid, stat.port_no,
                stat.rx_packets, stat.tx_packets, rx_bytes, tx_bytes,
                round(rx_mbps, 3), round(tx_mbps, 3)
            ])

        self.csv_file.flush()