#!/usr/bin/env python3
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

                # Iniciar servidor TCP
                dst.cmd("iperf3 -s -D")  # Daemon

                # Cliente envia tráfego por 5 segundos
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

                dst.cmd("killall iperf3")

    return results


# ------------------------------------------------------------
# Função principal
# ------------------------------------------------------------
def run():
    setLogLevel('info')

    info("\n=== Iniciando controlador OS-Ken ===\n")
    controller = subprocess.Popen(RYU_CMD.split(),
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)

    time.sleep(2)  # Tempo para o controlador subir

    info("\n=== Criando topologia RNP no Mininet ===\n")
    topo = RNPTopo()
    net = Mininet(topo=topo,
                  controller=None,
                  autoSetMacs=True,
                  link=TCLink)

    net.addController("c0", controller=RemoteController,
                      ip="127.0.0.1", port=RYU_PORT)

    net.start()

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

    CLI(net)
    net.stop()
    controller.terminate()
def gerar_notebook():
    import json

    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# 📊 Análise de Resultados – SDN\n",
                    "Notebook gerado automaticamente pelo script."
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "source": [
                    "import pandas as pd\n",
                    "import matplotlib.pyplot as plt\n",
                    "\n",
                    "lat = pd.read_csv('latencia.csv')\n",
                    "vaz = pd.read_csv('vazao.csv')\n",
                    "\n",
                    "# Criar coluna 'host_pair'\n",
                    "lat['host_pair'] = lat['Origem'] + '-' + lat['Destino']\n",
                    "vaz['host_pair'] = vaz['Origem'] + '-' + vaz['Destino']\n",
                    "\n",
                    "# Converter valores numéricos (N/A vira NaN)\n",
                    "lat['Latência Média (ms)'] = pd.to_numeric(lat['Latência Média (ms)'], errors='coerce')\n",
                    "vaz['Vazão TCP (Mbps)'] = pd.to_numeric(vaz['Vazão TCP (Mbps)'], errors='coerce')\n",
                    "\n",
                    "lat.head(), vaz.head()"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "source": [
                    "# 📈 Gráfico de Latência\n",
                    "plt.figure()\n",
                    "plt.plot(lat['host_pair'], lat['Latência Média (ms)'])\n",
                    "plt.xlabel('Par de Hosts')\n",
                    "plt.ylabel('Latência (ms)')\n",
                    "plt.title('Latência por Par de Hosts')\n",
                    "plt.xticks(rotation=90)\n",
                    "plt.tight_layout()\n",
                    "plt.show()"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "source": [
                    "# 📈 Gráfico de Vazão\n",
                    "plt.figure()\n",
                    "plt.plot(vaz['host_pair'], vaz['Vazão TCP (Mbps)'])\n",
                    "plt.xlabel('Par de Hosts')\n",
                    "plt.ylabel('Vazão TCP (Mbps)')\n",
                    "plt.title('Vazão TCP por Par de Hosts')\n",
                    "plt.xticks(rotation=90)\n",
                    "plt.tight_layout()\n",
                    "plt.show()"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "source": [
                    "# 📉 Comparação Latência x Vazão\n",
                    "plt.figure()\n",
                    "plt.plot(lat['host_pair'], lat['Latência Média (ms)'], label='Latência (ms)')\n",
                    "plt.plot(vaz['host_pair'], vaz['Vazão TCP (Mbps)'], label='Vazão TCP (Mbps)')\n",
                    "plt.legend()\n",
                    "plt.title('Comparativo Latência x Vazão')\n",
                    "plt.xticks(rotation=90)\n",
                    "plt.tight_layout()\n",
                    "plt.show()"
                ]
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.x"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }

    with open("analise_resultados.ipynb", "w") as f:
        json.dump(notebook, f, indent=2)

    print("*** Notebook analise_resultados.ipynb criado com sucesso! ***")
# ------------------------------------------------------------
# Execução
# ------------------------------------------------------------
if __name__ == "__main__":
    run()
    gerar_notebook()
