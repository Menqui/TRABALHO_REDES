# Arquivo: run_tests.py
import subprocess
import time
import json
import csv
from datetime import datetime
from pathlib import Path
from mininet.net import Mininet
from mininet.log import info, setLogLevel
from mininet.node import RemoteController, OVSSwitch
from topo_rnp import RNPTopo
from mininet.clean import cleanup



setLogLevel('info')

RYU_CMD = "osken-manager ryu_controller.py"
RYU_IP = '127.0.0.1'
RYU_PORT = 6633

# força o osken-manager a escutar na 6633
RYU_CMD = f"osken-manager --ofp-tcp-listen-port {RYU_PORT} ryu_controller.py"

def salvar_resultados_csv(src, dst, lat, vazao, arquivo='resultados_sdn.csv'):
    """
    Salva resultados de um experimento em um arquivo CSV (append).
    Se o arquivo não existir, cria com cabeçalho.
    """
    caminho = Path(arquivo)
    existe = caminho.exists()

    timestamp = datetime.now().isoformat(timespec='seconds')

    # Converte None pra string legível
    lat_str = '' if lat is None else f'{lat:.4f}'
    vazao_str = '' if vazao is None else f'{vazao:.4f}'

    linha = [timestamp, src, dst, lat_str, vazao_str]

    with open(caminho, 'a', newline='') as f:
        writer = csv.writer(f)
        if not existe:
            writer.writerow(['timestamp', 'host_src', 'host_dst', 'latencia_ms', 'vazao_Mbps'])
        writer.writerow(linha)

    info(f'*** Resultados salvos em {arquivo}\n')


def start_ryu_controller():
    """Inicia o Ryu Controller em segundo plano."""
    info(f'*** Iniciando Ryu Controller: {RYU_CMD}\n')
    # NÃO capturar stdout/stderr, pra ver erros no terminal
    ryu_process = subprocess.Popen(RYU_CMD.split())
    time.sleep(5)
    return ryu_process


def stop_ryu_controller(ryu_process):
    """Encerra o Ryu Controller."""
    info('*** Encerrando Ryu Controller...\n')
    ryu_process.terminate()

def measure_latency(net, host_src_name, host_dst_name, count=5):
    """Mede a latência (RTT) usando ping."""
    h_src = net.get(host_src_name)
    h_dst_ip = net.get(host_dst_name).IP()
    info(f'--- Testando Latência {host_src_name} -> {host_dst_name} ({h_dst_ip}) ---\n')
    ping_cmd = f'ping -c {count} {h_dst_ip}'
    
    output = h_src.cmd(ping_cmd)
    
    try:
        # Extração da latência média da saída do ping
        rtt_line = [line for line in output.split('\n') if 'rtt min/avg/max' in line][0]
        # Exemplo: rtt min/avg/max/mdev = 0.500/1.234/2.500/0.100 ms
        avg_latency = rtt_line.split('=')[1].split('/')[1].strip()
        info(f"Resultado: {avg_latency} ms\n")
        return float(avg_latency)
    except Exception as e:
        info(f"Erro ao medir latência: {e}\n")
        return None

def measure_throughput(net, host_src_name, host_dst_name, duration=10):
    """Mede a vazão (Throughput) usando iperf3."""
    h_src = net.get(host_src_name)
    h_dst = net.get(host_dst_name)
    
    info(f'--- Testando Vazão {host_src_name} -> {host_dst_name} por {duration}s ---\n')
    
    # 1. Inicia o servidor iperf3 em background no host de destino
    h_dst.cmd('iperf3 -s -D') 
    time.sleep(2) 

    # 2. Executa o cliente iperf3 no host de origem, pedindo saída JSON
    client_cmd = f'iperf3 -c {h_dst.IP()} -t {duration} -J'
    output_json = h_src.cmd(client_cmd)
    
    # 3. Mata o servidor iperf3
    h_dst.cmd('pkill iperf3')
    
    try:
        data = json.loads(output_json)
        # Extrai a média de bits por segundo
        avg_throughput_bps = data['end']['sum_sent']['bits_per_second']
        
        # Converte para Mbps
        avg_throughput_mbps = avg_throughput_bps / 10**6
        info(f"Resultado: {avg_throughput_mbps:.2f} Mbps\n")
        return avg_throughput_mbps
    except Exception as e:
        info(f"Erro ao processar iperf3: {e}\n")
        # Mostra o erro para o professor
        info(f"Saída RAW: {output_json[:200]}...\n") 
        return None

def main():
    cleanup()
    # 1. Iniciar o Controlador Ryu
    ryu_process = start_ryu_controller()
    
    # 2. Configurar e Iniciar o Mininet
    info('*** Criando Topologia Mininet...\n')
    # O Controller é remoto (RemoteController), apontando para o Ryu
    net = Mininet(
        topo=RNPTopo(),
        controller=lambda name: RemoteController(name, ip=RYU_IP, port=RYU_PORT),
        switch=OVSSwitch,
        autoSetMacs=True
    )
    
    net.start()

    # Aguardar OVS conectar com o Ryu
    info('*** Aguardando conexão dos Switches (15s)...\n')
    time.sleep(15)

    # Ping de aquecimento entre todos os hosts (ajuda no MAC learning / ARP)
    for i in range(3):
        info(f'*** PingAll de aquecimento (tentativa {i+1}/3) ***\n')
        net.pingAll()
    
    # 3. Realizar Testes de Comunicação e Performance

    # Parâmetros de teste (Exemplo: SP -> Fortaleza)
    src = 'h1'  # São Paulo
    dst = 'h6'  # Fortaleza
    
    # A. Teste de Conectividade (até 30s tentando)
    max_wait = 30  # segundos
    start_ts = time.time()
    connected = False

    while time.time() - start_ts < max_wait:
        info(f'*** Teste de Conectividade {src} -> {dst} ***\n')
        loss = net.ping([net.get(src), net.get(dst)])
        if loss == 0:
            connected = True
            break
        time.sleep(2)

    if not connected:
        info('*** AVISO: não houve conectividade h1->h6 dentro do tempo limite.\n')
        lat = None
        vazao = None
    else:
        # B. Teste de Latência
        lat = measure_latency(net, src, dst, count=10)  # 10 pings para média mais robusta

        # C. Teste de Vazão
        vazao = measure_throughput(net, src, dst, duration=15)  # 15s de transferência
    
    # 4. Apresentação Final
    info('\n======================================================\n')
    info(f'                 RESULTADO FINAL ({src} -> {dst})         \n')
    info('======================================================\n')
    if lat is not None:
        info(f'LATÊNCIA (RTT Média): {lat:.2f} ms\n')
    else:
        info('LATÊNCIA (RTT Média): teste falhou (sem resposta de ping)\n')
    if vazao is not None:
        info(f'VAZÃO (Throughput):   {vazao:.2f} Mbps\n')
    else:
        info('VAZÃO (Throughput):   teste falhou (iperf3 não conectou)\n')
    info('======================================================\n')

    # 4.1 Salvar resultados em CSV (mesmo se der falha)
    salvar_resultados_csv(src, dst, lat, vazao, arquivo='resultados_sdn.csv')

    # 5. Encerrar Mininet e Ryu
    net.stop()
    stop_ryu_controller(ryu_process)



if __name__ == '__main__':
    # Necessário rodar com sudo
    main()