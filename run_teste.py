import subprocess
import time
import csv
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.log import setLogLevel, info
from mininet.topolib import TreeTopo
from mininet.link import TCLink
from mininet.cli import CLI
from topo_rnp import RNPTopo
from mininet.node import OVSSwitch
from functools import partial




# CONFIGURAÇÕES DO CONTROLADOR OS-KEN
RYU_PORT = 6633
CONTROLLER_FILE = "osken_controller.py"  # <-- SEU CONTROLADOR AQUI
RYU_CMD = f"osken-manager --ofp-tcp-listen-port {RYU_PORT} {CONTROLLER_FILE}"


# ------------------------------------------------------------
# Função para rodar testes de latência (ping)
# ------------------------------------------------------------
def test_latency(net):
    results = []
    hosts = net.hosts

    info("\n=== Teste de Latência (Ping) ===\n")

    for src in hosts:
        for dst in hosts:
            if src != dst:
                result = src.cmd(f"ping -c 4 {dst.IP()}")

                # Extrair latência média
                try:
                    last_line = result.split("\n")[-2]
                    avg_latency = last_line.split("/")[4]
                except Exception:
                    avg_latency = "N/A"

                results.append([src.name, dst.name, avg_latency])
                info(f"{src.name} -> {dst.name}: {avg_latency} ms\n")

    return results


# ------------------------------------------------------------
# Função para medir vazão com iperf3
# ------------------------------------------------------------
def test_throughput(net):
    results = []
    hosts = net.hosts

    info("\n=== Teste de Vazão (iperf3) ===\n")

    for i in range(len(hosts)):
        for j in range(len(hosts)):
            if i != j:
                src = hosts[i]
                dst = hosts[j]

                dst.cmd("iperf3 -s -1 > /tmp/iperf3_server.log 2>&1 &")
                time.sleep(0.2)  # tempo para o servidor levantar
                output = src.cmd(f"iperf3 -c {dst.IP()} -J -t 5")

                # Extrair vazão
                try:
                    import json
                    data = json.loads(output)
                    bitrate = data["end"]["sum_received"]["bits_per_second"] / 1e6
                    bitrate = round(bitrate, 2)
                except Exception:
                    bitrate = "N/A"

                results.append([src.name, dst.name, bitrate])
                info(f"{src.name} -> {dst.name}: {bitrate} Mbps\n")

               

    return results


# ------------------------------------------------------------
# Função principal
# ------------------------------------------------------------
def run():
    setLogLevel('info')

    info("\n=== Iniciando controlador OS-Ken ===\n")
    logf = open("osken.log", "w")
    controller = subprocess.Popen(RYU_CMD.split(), stdout=logf, stderr=logf)

    net = None
    try:
        time.sleep(2)  # Tempo para o controlador subir

        info("\n=== Criando topologia RNP no Mininet ===\n")
        topo = RNPTopo()

        net = Mininet(
            topo=topo,
            controller=None,
            autoSetMacs=True,
            link=TCLink
        )

        net.addController(
            "c0",
            controller=RemoteController,
            ip="127.0.0.1",
            port=RYU_PORT
        )

        net.start()
        # reduzir o tempo de convergência do STP no OVS
        for sw in net.switches:
            sw.cmd(f"ovs-vsctl set Bridge {sw.name} other_config:stp-forward-delay=4")
            sw.cmd(f"ovs-vsctl set Bridge {sw.name} other_config:stp-max-age=6")
        time.sleep(35)  # STP convergir + switches conectarem no controlador

        info(f"Switches: {[s.name for s in net.switches]}\n")
        info(f"Hosts: {[h.name for h in net.hosts]}\n")

        info("\n=== Aquecendo a rede com pingAll ===\n")
        net.pingAll()

        # ---- Testes ----
        latency_results = test_latency(net)
        throughput_results = test_throughput(net)

        # ---- Salvando CSV ----
        info("\n=== Salvando resultados ===\n")

        with open("latencia.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Origem", "Destino", "Latência Média (ms)"])
            writer.writerows(latency_results)

        with open("vazao.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Origem", "Destino", "Vazão TCP (Mbps)"])
            writer.writerows(throughput_results)

        info("\nArquivos gerados: latencia.csv, vazao.csv\n")

        CLI(net)  # Se quiser execução 100% automática, comente esta linha.

    finally:
        if net is not None:
            net.stop()
        controller.terminate()
        logf.close()

# ------------------------------------------------------------
# Execução
# ------------------------------------------------------------
if __name__ == "__main__":
    run()
