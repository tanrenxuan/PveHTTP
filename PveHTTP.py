from typing import Optional
from NetworkType import NetworkType
import requests
import sys
import urllib3

urllib3.disable_warnings()


class PveHTTP:
    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self.base_url = 'https://' + host + ':8006'

        login_data = self.ticket()
        if not login_data:  # 登陆失败，退出程序
            sys.exit(1)
        self.ticket = login_data.get('ticket')
        self.csrf_token = login_data.get('CSRFPreventionToken')
        self.verify_header = {
            'Cookie': 'PVEAuthCookie={}'.format(self.ticket),
            'CSRFPreventionToken': self.csrf_token,
        }

    def req(self, api_url, data_only: bool = True, **kwargs):
        """
        封装url
        :param data_only: 若为true，返回只返回数据；若为false，返回整个response
        :param api_url: api接口
        :param kwargs: 参数
        :return: data字段
        """
        url = self.base_url + api_url
        try:
            kwargs = {
                **kwargs,
                'verify': False}
            response = requests.request(url=url, **kwargs)
            if data_only:
                return response.json().get('data')
            return response
        except Exception as e:
            print(e)

    def ticket(self):
        """
        Create or verify authentication ticket
        HTTP: POST /api2/json/access/ticket
        :return:
        """
        api_url = '/api2/json/access/ticket'
        payload = {
            'username': self.username,
            'password': self.password,
            'realm': 'pam'
        }
        response = self.req(api_url, method='post', json=payload)
        if not response:
            print("login fail!")
            return
        return response

    def get_cluster_status(self):
        """
        List recent tasks (cluster wide).
        HTTP: GET /api2/json/cluster/status
        :return:
        """
        api_url = "/api2/json/cluster/status"
        response = self.req(api_url, method='get', headers=self.verify_header)
        if not response:
            print("get cluster status fail!")
        return response

    def get_cluster_tasks(self):
        """
        List recent tasks (cluster wide)
        HTTP: GET /api2/json/cluster/tasks
        :return:
        """
        api_url = "/api2/json/cluster/tasks"
        response = self.req(api_url, method='get', headers=self.verify_header)
        if not response:
            print("get cluster tasks fail!")
        return response

    def vm_start(self, node: str, vmid: int) -> bool:
        """
        Start virtual machine
        HTTP: POST /api2/json/nodes/{node}/qemu/{vmid}/status/start
        :param node: node
        :param vmid: vm id
        :return:
        """
        api_url = f'/api2/json/nodes/{node}/qemu/{vmid}/status/start'
        response = self.req(api_url, method='post', headers=self.verify_header, data_only=False)
        if not response or response.status_code != 200:
            print(f'开启节点{node}的虚拟机{vmid}失败，状态码为{response.status_code}，状态信息为{response.reason}')
            return False
        return True

    def vm_stop(self, node: str, vmid: int) -> bool:
        """
        Stop virtual machine. The qemu process will exit immediately.
        Thisis akin to pulling the power plug of a running computer and may damage the VM data.
        不推荐使用
        HTTP: POST /api2/json/nodes/{node}/qemu/{vmid}/status/stop
        :param node: node
        :param vmid: vm id
        :return:
        """
        api_url = f'/api2/json/nodes/{node}/qemu/{vmid}/status/stop'
        response = self.req(api_url, method='post', headers=self.verify_header, data_only=False)
        if not response or response.status_code != 200:
            print(f'强制停止节点{node}的虚拟机{vmid}失败，状态码为{response.status_code}，状态信息为{response.reason}')
            return False
        return True

    def vm_shutdown(self, vmid: int, node: str = 'pve') -> bool:
        """
        Shutdown virtual machine. This is similar to pressing the power button on a physical machine.
        This will send an ACPI event for the guest OS, which should then proceed to a clean shutdown.
        一般情况使用这种方式关闭虚拟机
        HTTP: POST /api2/json/nodes/{node}/qemu/{vmid}/status/shutdown
        :param node: node
        :param vmid: vm id
        :return:
        """
        api_url = f'/api2/json/nodes/{node}/qemu/{vmid}/status/shutdown'
        response = self.req(api_url, method='post', headers=self.verify_header, data_only=False)
        if not response or response.status_code != 200:
            print(f'关闭节点{node}的虚拟机{vmid}失败，状态码为{response.status_code}，状态信息为{response.reason}')
            return False
        return True

    def get_available_networks(self, node: str = 'pve', network_type: Optional[NetworkType] = None):
        """
        List available networks
        HTTP: GET /api2/json/nodes/{node}/network
        :param node: 结点
        :param network_type: 默认返回所有network设备，若含有此参数，则只返回对应类型的network设备
        :return:
        """
        api_url = f'/api2/json/nodes/{node}/network'
        params = None
        if network_type is not None:
            params = {
                'type': network_type.value
            }
        response = self.req(api_url, method='get', headers=self.verify_header, params=params)
        if not response:
            print("no certain networks!")
        return response

    def create_network_bridge(self, iface: str, node: str = 'pve', cidr: Optional[str] = None,
                              gateway: Optional[str] = None, autostart: Optional[bool] = True,
                              bridge_ports: Optional[str] = None, ):
        """
        创建网络设备linux bridge（不同的网络设备，请求体设置的参数有所区别，由于只需要bridge类型device，type硬编码为NetworkType。bridge）
        :param iface: 名称，最好起类似名称vmbr0、vmbr1等
        :param node: 节点
        :param cidr: cidr参数，形式x.x.x.x/d，如192.168.247.131/24
        :param gateway: 网关 形式x.x.x.x
        :param autostart: 是否自动启动
        :param bridge_ports: 端口从属，如ens33
        :return:
        """
        api_url = f'/api2/json/nodes/{node}/network'
        payload = {
            "iface": iface,
            "type": NetworkType.bridge.value, # 硬编码为bridge类型
            "autostart": autostart,
        }
        if cidr is not None:
            pass

        response = self.req(api_url, method='post', headers=self.verify_header, json=payload)

    def __str__(self):
        dict_str = ''
        for attr, value in self.__dict__.items():
            dict_str += '\n{}: {}'.format(attr, value)
        return '<class PveHTTP>: {}'.format(dict_str)


if __name__ == '__main__':
    data = {
        'username': 'root',
        'password': '123456',
        'host': '192.168.247.131'
    }
    p = PveHTTP(**data)
    print(p.get_available_networks(network_type=NetworkType.bridge))

