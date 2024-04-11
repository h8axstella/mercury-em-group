#!.env/bin/python3.9
# -*- coding: utf-8 -*-
#
# Mercury Energy Meter
#
# receive data from electricity meter MERCURY
#
# 2019 <eugene@skorlov.name>
#
import os
import argparse
import socket
import json
import mercury.mercury206 as mercury206
import mercury.mercury236 as mercury236


def parse_cmd_line_args():
    config_path = 'config.json'
    config = {}
    
    
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
    
  
    parser = argparse.ArgumentParser(description="Mercury energy meter data receiver")

  
    parser.add_argument("--proto", default=config.get('proto', 'm206'), help='Mercury protocol (M206/M236)')
    parser.add_argument("--serial", type=str, default=config.get('serial'), help='Device serial number')
    parser.add_argument("--host", default=config.get('host', '0'), help='RS485-TCP/IP Converter IP.')
    parser.add_argument("--port", type=int, default=config.get('port', 50), help='RS485-TCP/IP Converter port')
    parser.add_argument("--user", default=config.get('user', 'user'), help='Device user (for m236 protocol)')
    parser.add_argument("--pass", dest="passwd", default=config.get('pass', ''), help='Device password (for m236 protocol)')
    parser.add_argument("--format", default=config.get('format', 'json'), help='Output format')
    parser.add_argument("--array-number", type=int, default=config.get('array_number', 0x00), help='Array number')

    args = parser.parse_args()

    
    if not args.serial:
        raise ValueError("The --serial argument is required but not provided in command line or config.json")

    return args

def print_output_text(arr, prefix=""):
    for key, value in arr.items():
        if isinstance(value, dict):
            print_output_text(value, prefix + "." + key)
        else:
            print(f"{prefix}.{key}={value}")


def print_output(arr, output_format):
    if output_format == "text":
        print_output_text(arr)

    elif output_format == "json":
        print(json.dumps(arr))


if __name__ == "__main__":
    args = parse_cmd_line_args()
    serial_numbers = [int(serial) for serial in args.serial.split(',')]

    for serial in serial_numbers:  # Добавлено двоеточие
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((args.host, args.port))
            result = {}

            if args.proto == "m206":
                result['info'] = {}
                try:
                    result['info']['V'], result['info']['A'], result['info']['P'] = mercury206.read_vap(sock, serial)
                    result['info']['freq'] = mercury206.read_freq(sock, serial)

                    result['energy'] = mercury206.read_energy(sock, serial)
                except TimeoutError:
                    result['error'] = "Timeout while reading data from socket"
                except ValueError:
                    result['error'] = "Wrong data"

            elif args.proto == "m236":
                serial_mod = serial % 1000  

                if serial_mod == 0:
                    serial_mod = 1
                elif serial_mod > 240:
                    serial_mod = serial_mod % 100

                user_level = 0x02 if args.user == "admin" else 0x01
                passwd = args.passwd or ("222222" if user_level == 0x02 else "111111")

                try:
                    mercury236.check_connect(sock, serial_mod)
                    mercury236.open_channel(sock, serial_mod, user_level, passwd)

                    result[f'energy_phases_{args.array_number}'] = mercury236.read_energy_sum_act_react(sock, serial_mod, param=0x0B)
                    result[f'energy_tarif_{args.array_number}'] = mercury236.read_energy_tarif_act_react(sock, serial_mod, param=0x0B)
                    result['energy_phases'] = mercury236.read_energy_sum_by_phases(sock, serial_mod)
                    result['energy_tarif'] = mercury236.read_energy_tarif_by_phases(sock, serial_mod)

                    result['info'] = mercury236.read_vap(sock, serial_mod)
                    result['info']['freq'] = mercury236.read_freq(sock, serial_mod)

                    mercury236.close_channel(sock, serial_mod)
                except TimeoutError:
                    result['error'] = "Timeout while reading data from socket"
                except ValueError:
                    result['error'] = "Wrong data"

            print_output(result, args.format)
        except Exception as e:
            print(f"Ошибка: {e}")
        finally:
            sock.close()  
    with open('results.json', 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
