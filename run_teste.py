# Arquivo: run_tests.py
import subprocess
import time
import json
from mininet.net import Mininet
from mininet.log import info, setLogLevel
from mininet.node import RemoteController
from rnp_topo import RNPTopo # Importa a topologia

setLogLevel('info')

RYU_CMD = "ryu-manager ryu_controller.py"
RYU_IP = '127.0.0.1'

def start_ryu_controller():
    """Inicia o Ryu Controller em segundo plano."""
    info(f'*** Iniciando Ryu Controller: {RYU_CMD}\n')
    # Use subprocess.Popen para não bloquear o script
    ryu_process = subprocess.Popen(RYU_CMD.split(), 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.STDOUT)
    time.sleep(5) # Dá tempo para o Ryu iniciar
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
    time.sleep(1) 

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
    # 1. Iniciar o Controlador Ryu
    ryu_process = start_ryu_controller()
    
    # 2. Configurar e Iniciar o Mininet
    info('*** Criando Topologia Mininet...\n')
    # O Controller é remoto (RemoteController), apontando para o Ryu
    net = Mininet(topo=RNPTopo(), 
                  controller=lambda name: RemoteController(name, ip=RYU_IP), 
                  switch='ovs', 
                  autoSetMacs=True)
    
    net.start()
    
    # Aguardar o OVS conectar com o Ryu
    info('*** Aguardando conexão dos Switches (5s)...\n')
    time.sleep(5) 
    
    # 3. Realizar Testes de Comunicação e Performance

    # Parâmetros de teste (Exemplo: SP -> Fortaleza)
    src = 'h1' # São Paulo
    dst = 'h6' # Fortaleza
    
    # A. Teste de Conectividade (Ping inicial para forçar o MAC Learning e instalação de fluxos)
    info(f'*** Teste Inicial de Conectividade {src} -> {dst} ***\n')
    net.ping([net.get(src), net.get(dst)])
    
    # B. Teste de Latência
    lat = measure_latency(net, src, dst, count=10) # 10 pings para média mais robusta
    
    # C. Teste de Vazão
    vazao = measure_throughput(net, src, dst, duration=15) # 15s de transferência
    
    # 4. Apresentação Final
    info('\n======================================================\n')
    info(f'                 RESULTADO FINAL ({src} -> {dst})         \n')
    info('======================================================\n')
    info(f'LATÊNCIA (RTT Média): {lat:.2f} ms\n')
    info(f'VAZÃO (Throughput):   {vazao:.2f} Mbps\n')
    info('======================================================\n')

    # Para permitir interação manual após os testes:
    # CLI(net) 
    
    # 5. Encerrar Mininet e Ryu
    net.stop()
    stop_ryu_controller(ryu_process)

if __name__ == '__main__':
    # Necessário rodar com sudo
    main()