#!.env/bin/python3.9
# -*- coding: utf-8 -*-
#
# Mercury Energy Meter
#
# receive data from electricity meter MERCURY
#
# 2019 <eugene@skorlov.name>
#

import argparse
import sys
import socket
import json
import mercury.mercury206 as mercury206
import mercury.mercury236 as mercury236


def parse_cmd_line_args():
    parser = argparse.ArgumentParser(description="Mercury energy meter data receiver")

    parser.add_argument("--proto", choices=["m206", "m236"], nargs='?', default="m206",
                        help='Mercury protocol (M206/M236)')
    parser.add_argument('--serial', type=int, nargs='?', default=0, help='Device serial number', required=True)

    parser.add_argument('--host', type=str, nargs='?', default=0, help='RS485-TCP/IP Convertor IP.')
    parser.add_argument('--port', type=int, nargs='?', default="50", help='RS485-TCP/IP Convertor (default: 50)')

    parser.add_argument('--user', choices=["user", "admin"], default="user", nargs='?',
                        help='Device user (for m236 proto)')
    parser.add_argument('--pass', dest="passwd", type=str, nargs='?', help='Device password (for m236 proto)')

    parser.add_argument('--format', choices=["text", "json", "human"], nargs='?', default="json", help='Output format')

    return parser.parse_args()


def print_output_text(arr, prefix=""):
    for key, value in arr.items():
        if isinstance(value, dict):
            print_output_text(value, prefix + "." + key)
        else:
            print(f"{prefix}.{key}={value}")


def print_output(arr, format):
    if format == "text":
        print_output_text(arr)

    elif format == "json":
        print(json.dumps(arr))


if __name__ == "__main__":
    args = parse_cmd_line_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((args.host, args.port))

    result = {}

    if args.proto == "m206":
        ''' Сетевой адрес счетчика - серийный номер 
        '''
        result['info'] = {}
        try:
            result['info']['V'], result['info']['A'], result['info']['P'] = mercury206.read_vap(sock, args.serial)
            result['info']['freq'] = mercury206.read_freq(sock, args.serial)

            result['energy'] = mercury206.read_energy(sock, args.serial)
        except TimeoutError:
            result['error'] = "Timeout while read data from socket"
        except ValueError:
            result['error'] = "Wrong data"

        finally:
            sock.close()

    elif args.proto == "m236":

        ''' Сетевым адресом счетчика по умолчанию являются три последние цифры заводского номера или две
            последние цифры в случае, если три последние цифры образуют число более 240.
            Если три последние цифры – нули, то сетевой адрес "1". 
        '''
        args.serial = args.serial % 1000

        if args.serial == 0:
            args.serial = 1
        elif args.serial > 240:
            args.serial = args.serial % 100

        ''' уровень доступа "User"  - 0x01 default passwd = 111111
            уровень доступа "Admin" - 0x02 default passwd = 222222
        '''

        args.user = 0x02 if args.user == "admin" else 0x01
        if not args.passwd:
            args.passwd = "222222" if args.user == 2 else "111111"

        try:
            mercury236.check_connect(sock, args.serial)
            mercury236.open_channel(sock, args.serial, args.user, args.passwd)

            result['energy_phases_AR'] = mercury236.read_energy_sum_act_react(sock, args.serial)
            result['energy_tarif_AR'] = mercury236.read_energy_tarif_act_react(sock, args.serial)
            result['energy_phases'] = mercury236.read_energy_sum_by_phases(sock, args.serial)
            result['energy_tarif'] = mercury236.read_energy_tarif_by_phases(sock, args.serial)

            result['info'] = mercury236.read_vap(sock, args.serial)
            result['info']['freq'] = mercury236.read_freq(sock, args.serial)

            mercury236.close_channel(sock, args.serial)
        except TimeoutError:
            result['error'] = "Timeout while read data from socket"
        except ValueError:
            result['error'] = "Wrong data"

        finally:
            sock.close()

    print_output(result, args.format)
