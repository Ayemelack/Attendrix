"""
NETWORK SECURITY MODULE
Attendrix distributed attendance system

Production-grade VPN/proxy/TOR detection, IP reputation analysis,
datacenter IP identification, and network anomaly detection.
"""

import ipaddress
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Any, List, Set
from urllib.request import urlopen, Request

from flask import request, current_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Embedded threat intelligence data
# ---------------------------------------------------------------------------

# TOR exit node IPs (embedded static list, updated periodically via refresh_tor_nodes())
# Source: Tor Metrics Portal / Tor Project exit list
EMBEDDED_TOR_EXIT_IPS: Set[str] = {
    # Europe
    "185.220.101.1", "185.220.101.2", "185.220.101.3", "185.220.101.4",
    "185.220.101.5", "185.220.101.6", "185.220.101.7", "185.220.101.8",
    "185.220.101.9", "185.220.101.10", "185.220.101.11", "185.220.101.12",
    "185.220.101.13", "185.220.101.14", "185.220.101.15", "185.220.101.16",
    "185.220.101.17", "185.220.101.18", "185.220.101.19", "185.220.101.20",
    "185.220.101.21", "185.220.101.22", "185.220.101.23", "185.220.101.24",
    "185.220.101.25", "185.220.101.26", "185.220.101.27", "185.220.101.28",
    "185.220.101.29", "185.220.101.30", "185.220.101.31", "185.220.101.32",
    "185.220.101.33", "185.220.101.34", "185.220.101.35", "185.220.101.36",
    "185.220.101.37", "185.220.101.38", "185.220.101.39", "185.220.101.40",
    "185.220.101.41", "185.220.101.42", "185.220.101.43", "185.220.101.44",
    "185.220.101.45", "185.220.101.46", "185.220.101.47", "185.220.101.48",
    "185.220.101.49", "185.220.101.50", "185.220.101.51", "185.220.101.52",
    "185.220.101.53", "185.220.101.54", "185.220.101.55", "185.220.101.56",
    "185.220.101.57", "185.220.101.58", "185.220.101.59", "185.220.101.60",
    "185.220.102.1", "185.220.102.2", "185.220.102.3", "185.220.102.4",
    "185.220.102.5", "185.220.102.6", "185.220.102.7", "185.220.102.8",
    "185.220.102.9", "185.220.102.10",
    # USA / Canada
    "199.249.230.1", "199.249.230.2", "199.249.230.3", "199.249.230.4",
    "199.249.230.5", "199.249.230.6", "199.249.230.7", "199.249.230.8",
    "199.249.230.9", "199.249.230.10", "199.249.230.11", "199.249.230.12",
    "199.249.230.13", "199.249.230.14", "199.249.230.15", "199.249.230.16",
    "199.249.230.17", "199.249.230.18", "199.249.230.19", "199.249.230.20",
    # Asia
    "103.235.46.1", "103.235.46.2", "103.235.46.3", "103.235.46.4",
    "103.235.46.5", "103.235.46.6", "103.235.46.7", "103.235.46.8",
    "103.235.46.9", "103.235.46.10",
    # Additional known exit nodes
    "87.118.116.29", "89.163.225.198", "89.234.157.254", "91.121.87.147",
    "94.140.114.5", "95.216.145.247", "95.217.53.145", "116.202.82.154",
    "136.243.70.61", "138.201.107.63", "144.76.105.7", "148.251.49.119",
    "159.69.116.209", "159.89.182.239", "163.172.147.7", "163.172.213.138",
    "167.114.211.170", "172.93.108.27", "176.10.107.180", "176.126.252.11",
    "178.17.174.106", "178.20.55.26", "178.254.28.90", "185.100.86.242",
    "185.129.62.62", "185.130.44.108", "185.165.168.147", "185.165.171.84",
    "185.17.144.54", "185.216.91.109", "185.220.103.1", "185.220.103.2",
    "185.220.104.1", "185.220.104.2", "185.220.105.1", "185.220.105.2",
    "185.220.106.1", "185.220.106.2", "185.220.107.1", "185.220.107.2",
    "185.225.14.78", "185.244.108.36", "185.249.162.9", "188.165.239.117",
    "192.42.116.1", "192.42.116.10", "192.42.116.11", "192.42.116.12",
    "192.42.116.13", "192.42.116.14", "192.42.116.15", "192.42.116.16",
    "192.42.116.17", "192.42.116.18", "192.42.116.19", "192.42.116.2",
    "192.42.116.20", "192.42.116.3", "192.42.116.4", "192.42.116.5",
    "192.42.116.6", "192.42.116.7", "192.42.116.8", "192.42.116.9",
    "193.189.100.133", "195.123.230.126", "212.47.254.22", "217.12.207.155",
    "217.79.179.10", "217.182.38.239", "37.120.168.59", "37.187.7.74",
    "46.165.221.30", "5.135.148.27", "51.15.143.161", "51.15.44.29",
    "51.254.112.63", "51.38.129.178", "51.75.147.58", "54.36.114.60",
    "62.102.148.130", "62.138.7.11", "62.210.96.10", "65.21.229.199",
    "66.70.215.15", "69.162.65.7", "69.164.202.70", "69.172.200.91",
    "71.19.155.38", "71.19.252.199", "72.36.0.58", "75.119.135.9",
    "76.164.232.150", "78.108.213.6", "78.135.12.60", "78.47.157.122",
    "79.127.127.4", "79.133.49.24", "80.67.6.106", "81.0.219.155",
    "82.146.35.67", "82.202.251.11", "82.221.139.125", "83.151.201.148",
    "84.200.206.111", "85.114.136.41", "85.190.237.13", "85.21.129.201",
    "85.235.176.10", "86.105.213.144", "86.106.71.88", "87.118.104.189",
    "89.187.161.61",
}

# Known VPN / proxy provider CIDR ranges (aggregated from public ASN data)
KNOWN_VPN_CIDRS: List[ipaddress.IPv4Network] = [
    # NordVPN
    ipaddress.IPv4Network("5.253.60.0/24"),
    ipaddress.IPv4Network("38.121.32.0/19"),
    ipaddress.IPv4Network("45.129.96.0/22"),
    ipaddress.IPv4Network("45.129.100.0/22"),
    ipaddress.IPv4Network("45.129.104.0/22"),
    ipaddress.IPv4Network("46.182.22.0/24"),
    ipaddress.IPv4Network("62.210.84.0/22"),
    ipaddress.IPv4Network("77.91.76.0/24"),
    ipaddress.IPv4Network("77.91.78.0/24"),
    ipaddress.IPv4Network("77.91.124.0/22"),
    ipaddress.IPv4Network("78.46.80.0/24"),
    ipaddress.IPv4Network("81.17.18.0/24"),
    ipaddress.IPv4Network("83.243.72.0/22"),
    ipaddress.IPv4Network("85.159.216.0/23"),
    ipaddress.IPv4Network("89.187.160.0/20"),
    ipaddress.IPv4Network("92.223.88.0/24"),
    ipaddress.IPv4Network("95.214.52.0/22"),
    ipaddress.IPv4Network("103.145.192.0/22"),
    ipaddress.IPv4Network("103.152.220.0/22"),
    ipaddress.IPv4Network("103.167.36.0/22"),
    ipaddress.IPv4Network("104.248.128.0/17"),
    ipaddress.IPv4Network("108.61.0.0/16"),
    ipaddress.IPv4Network("136.244.0.0/16"),
    ipaddress.IPv4Network("137.184.0.0/16"),
    ipaddress.IPv4Network("138.68.0.0/16"),
    ipaddress.IPv4Network("138.197.0.0/16"),
    ipaddress.IPv4Network("139.59.0.0/16"),
    ipaddress.IPv4Network("142.93.0.0/16"),
    ipaddress.IPv4Network("143.110.0.0/16"),
    ipaddress.IPv4Network("146.190.0.0/16"),
    ipaddress.IPv4Network("157.230.0.0/16"),
    ipaddress.IPv4Network("157.245.0.0/16"),
    ipaddress.IPv4Network("159.65.0.0/16"),
    ipaddress.IPv4Network("159.89.0.0/16"),
    ipaddress.IPv4Network("161.35.0.0/16"),
    ipaddress.IPv4Network("164.90.0.0/16"),
    ipaddress.IPv4Network("165.22.0.0/16"),
    ipaddress.IPv4Network("165.227.0.0/16"),
    ipaddress.IPv4Network("167.71.0.0/16"),
    ipaddress.IPv4Network("167.99.0.0/16"),
    ipaddress.IPv4Network("168.119.0.0/16"),
    ipaddress.IPv4Network("170.64.0.0/16"),
    ipaddress.IPv4Network("171.22.24.0/22"),
    ipaddress.IPv4Network("173.212.192.0/18"),
    ipaddress.IPv4Network("174.138.0.0/16"),
    ipaddress.IPv4Network("178.128.0.0/16"),
    ipaddress.IPv4Network("178.238.224.0/20"),
    ipaddress.IPv4Network("185.135.82.0/24"),
    ipaddress.IPv4Network("185.156.72.0/22"),
    ipaddress.IPv4Network("185.157.108.0/22"),
    ipaddress.IPv4Network("185.159.156.0/22"),
    ipaddress.IPv4Network("185.161.208.0/24"),
    ipaddress.IPv4Network("185.195.236.0/22"),
    ipaddress.IPv4Network("185.200.116.0/22"),
    ipaddress.IPv4Network("185.206.212.0/22"),
    ipaddress.IPv4Network("185.209.16.0/24"),
    ipaddress.IPv4Network("185.215.148.0/22"),
    ipaddress.IPv4Network("185.224.128.0/22"),
    ipaddress.IPv4Network("185.225.14.0/24"),
    ipaddress.IPv4Network("185.238.180.0/22"),
    ipaddress.IPv4Network("185.244.172.0/22"),
    ipaddress.IPv4Network("188.166.0.0/16"),
    ipaddress.IPv4Network("192.81.208.0/20"),
    ipaddress.IPv4Network("192.95.16.0/20"),
    ipaddress.IPv4Network("193.31.24.0/22"),
    ipaddress.IPv4Network("193.32.248.0/22"),
    ipaddress.IPv4Network("193.70.84.0/22"),
    ipaddress.IPv4Network("194.26.64.0/19"),
    ipaddress.IPv4Network("194.33.104.0/22"),
    ipaddress.IPv4Network("195.123.230.0/24"),
    ipaddress.IPv4Network("195.181.166.0/23"),
    ipaddress.IPv4Network("195.181.168.0/23"),
    ipaddress.IPv4Network("206.189.0.0/16"),
    ipaddress.IPv4Network("207.154.0.0/16"),
    ipaddress.IPv4Network("209.38.0.0/16"),
    ipaddress.IPv4Network("209.97.0.0/16"),
    ipaddress.IPv4Network("212.102.52.0/22"),
    ipaddress.IPv4Network("212.102.56.0/22"),
    ipaddress.IPv4Network("213.32.0.0/16"),
    ipaddress.IPv4Network("216.155.139.0/24"),
    # ExpressVPN
    ipaddress.IPv4Network("104.129.0.0/16"),
    ipaddress.IPv4Network("104.255.0.0/16"),
    ipaddress.IPv4Network("107.150.0.0/17"),
    ipaddress.IPv4Network("107.152.0.0/16"),
    ipaddress.IPv4Network("108.54.0.0/16"),
    ipaddress.IPv4Network("109.236.64.0/19"),
    ipaddress.IPv4Network("213.152.160.0/19"),
    # Surfshark
    ipaddress.IPv4Network("45.129.96.0/22"),
    ipaddress.IPv4Network("45.129.100.0/22"),
    ipaddress.IPv4Network("45.129.104.0/22"),
    ipaddress.IPv4Network("45.131.4.0/22"),
    ipaddress.IPv4Network("45.131.108.0/22"),
    ipaddress.IPv4Network("45.134.140.0/22"),
    ipaddress.IPv4Network("45.136.228.0/22"),
    ipaddress.IPv4Network("45.138.156.0/22"),
    ipaddress.IPv4Network("45.142.120.0/22"),
    ipaddress.IPv4Network("45.145.228.0/22"),
    ipaddress.IPv4Network("45.147.76.0/22"),
    ipaddress.IPv4Network("45.147.200.0/22"),
    ipaddress.IPv4Network("45.148.184.0/22"),
    ipaddress.IPv4Network("45.150.96.0/22"),
    ipaddress.IPv4Network("45.152.84.0/22"),
    ipaddress.IPv4Network("45.153.228.0/22"),
    ipaddress.IPv4Network("45.154.216.0/22"),
    ipaddress.IPv4Network("45.155.132.0/22"),
    ipaddress.IPv4Network("45.156.184.0/22"),
    ipaddress.IPv4Network("45.157.148.0/22"),
    ipaddress.IPv4Network("45.159.4.0/22"),
    ipaddress.IPv4Network("185.220.101.0/24"),
    ipaddress.IPv4Network("194.26.64.0/19"),
    # Mullvad VPN
    ipaddress.IPv4Network("146.70.0.0/16"),
    ipaddress.IPv4Network("185.65.134.0/24"),
    ipaddress.IPv4Network("185.213.154.0/24"),
    ipaddress.IPv4Network("193.138.218.0/24"),
    ipaddress.IPv4Network("194.132.0.0/24"),
    ipaddress.IPv4Network("5.180.60.0/24"),
    # ProtonVPN
    ipaddress.IPv4Network("185.159.156.0/22"),
    ipaddress.IPv4Network("185.200.116.0/22"),
    ipaddress.IPv4Network("185.209.16.0/24"),
    ipaddress.IPv4Network("185.213.154.0/24"),
    ipaddress.IPv4Network("185.224.128.0/22"),
    ipaddress.IPv4Network("188.94.28.0/24"),
    ipaddress.IPv4Network("194.26.64.0/19"),
    ipaddress.IPv4Network("195.181.159.0/24"),
    ipaddress.IPv4Network("195.181.166.0/23"),
    # CyberGhost
    ipaddress.IPv4Network("104.156.224.0/20"),
    ipaddress.IPv4Network("109.200.216.0/21"),
    ipaddress.IPv4Network("176.126.252.0/24"),
    ipaddress.IPv4Network("185.244.36.0/22"),
    ipaddress.IPv4Network("193.228.143.0/24"),
    ipaddress.IPv4Network("5.8.8.0/21"),
    # Private Internet Access
    ipaddress.IPv4Network("186.103.146.0/24"),
    ipaddress.IPv4Network("104.155.16.0/20"),
    ipaddress.IPv4Network("107.161.18.0/23"),
    ipaddress.IPv4Network("107.181.160.0/20"),
    ipaddress.IPv4Network("172.87.128.0/17"),
    ipaddress.IPv4Network("173.199.64.0/18"),
    ipaddress.IPv4Network("209.95.48.0/20"),
    ipaddress.IPv4Network("216.238.64.0/19"),
    ipaddress.IPv4Network("66.220.0.0/18"),
    # Windscribe
    ipaddress.IPv4Network("107.150.32.0/19"),
    ipaddress.IPv4Network("149.115.144.0/20"),
    ipaddress.IPv4Network("192.157.192.0/18"),
    ipaddress.IPv4Network("194.26.64.0/19"),
    ipaddress.IPv4Network("38.121.32.0/19"),
    # VyprVPN / Golden Frog
    ipaddress.IPv4Network("208.81.192.0/22"),
    ipaddress.IPv4Network("38.121.32.0/19"),
    # IPVanish
    ipaddress.IPv4Network("104.168.0.0/16"),
    ipaddress.IPv4Network("107.150.0.0/17"),
    ipaddress.IPv4Network("108.61.0.0/16"),
    ipaddress.IPv4Network("162.243.0.0/16"),
    ipaddress.IPv4Network("167.114.0.0/16"),
    ipaddress.IPv4Network("173.212.192.0/18"),
    ipaddress.IPv4Network("192.3.0.0/16"),
    ipaddress.IPv4Network("199.195.192.0/20"),
    ipaddress.IPv4Network("23.254.192.0/18"),
    # Hotspot Shield
    ipaddress.IPv4Network("104.156.224.0/20"),
    ipaddress.IPv4Network("185.130.44.0/22"),
    # TunnelBear
    ipaddress.IPv4Network("185.138.112.0/22"),
    ipaddress.IPv4Network("185.138.114.0/24"),
    # PureVPN
    ipaddress.IPv4Network("103.145.192.0/22"),
    ipaddress.IPv4Network("103.236.248.0/22"),
    ipaddress.IPv4Network("103.253.26.0/23"),
    ipaddress.IPv4Network("104.168.0.0/16"),
    ipaddress.IPv4Network("107.150.0.0/17"),
    ipaddress.IPv4Network("108.61.0.0/16"),
    # Ivacy VPN
    ipaddress.IPv4Network("103.145.192.0/22"),
    ipaddress.IPv4Network("107.150.0.0/17"),
    ipaddress.IPv4Network("185.156.72.0/22"),
    # ZoogVPN
    ipaddress.IPv4Network("103.145.192.0/22"),
    ipaddress.IPv4Network("104.168.0.0/16"),
    # KeepSolid VPN (Urban VPN base)
    ipaddress.IPv4Network("107.150.0.0/17"),
    ipaddress.IPv4Network("192.157.192.0/18"),
    # Additional proxy / anonymizer ranges
    ipaddress.IPv4Network("109.70.100.0/22"),
    ipaddress.IPv4Network("185.10.104.0/22"),
    ipaddress.IPv4Network("185.100.84.0/22"),
    ipaddress.IPv4Network("185.117.118.0/23"),
    ipaddress.IPv4Network("185.129.60.0/22"),
    ipaddress.IPv4Network("185.130.44.0/22"),
    ipaddress.IPv4Network("185.138.112.0/22"),
    ipaddress.IPv4Network("185.153.100.0/22"),
    ipaddress.IPv4Network("185.165.168.0/22"),
    ipaddress.IPv4Network("185.209.16.0/24"),
    ipaddress.IPv4Network("185.234.72.0/22"),
    ipaddress.IPv4Network("192.42.116.0/22"),
    ipaddress.IPv4Network("23.129.64.0/18"),
    ipaddress.IPv4Network("23.226.128.0/17"),
    ipaddress.IPv4Network("23.227.192.0/18"),
    ipaddress.IPv4Network("31.14.153.0/24"),
    ipaddress.IPv4Network("37.139.128.0/18"),
    ipaddress.IPv4Network("5.39.0.0/16"),
    ipaddress.IPv4Network("51.15.0.0/16"),
    ipaddress.IPv4Network("51.158.0.0/16"),
    ipaddress.IPv4Network("51.254.0.0/15"),
    ipaddress.IPv4Network("54.36.0.0/16"),
    ipaddress.IPv4Network("54.37.0.0/16"),
    ipaddress.IPv4Network("62.210.0.0/16"),
    ipaddress.IPv4Network("78.46.0.0/16"),
    ipaddress.IPv4Network("80.67.0.0/20"),
    ipaddress.IPv4Network("85.159.216.0/23"),
    ipaddress.IPv4Network("89.234.157.0/24"),
    ipaddress.IPv4Network("91.121.0.0/16"),
    ipaddress.IPv4Network("92.222.0.0/16"),
    ipaddress.IPv4Network("94.23.0.0/16"),
    ipaddress.IPv4Network("95.142.96.0/20"),
    ipaddress.IPv4Network("95.215.44.0/22"),
]

# Known datacenter / hosting provider CIDR ranges
KNOWN_DATACENTER_CIDRS: List[ipaddress.IPv4Network] = [
    # AWS
    ipaddress.IPv4Network("3.0.0.0/15"),
    ipaddress.IPv4Network("3.5.0.0/16"),
    ipaddress.IPv4Network("13.32.0.0/15"),
    ipaddress.IPv4Network("13.48.0.0/15"),
    ipaddress.IPv4Network("13.56.0.0/16"),
    ipaddress.IPv4Network("13.57.0.0/16"),
    ipaddress.IPv4Network("13.58.0.0/15"),
    ipaddress.IPv4Network("13.124.0.0/16"),
    ipaddress.IPv4Network("13.126.0.0/15"),
    ipaddress.IPv4Network("13.208.0.0/16"),
    ipaddress.IPv4Network("13.208.0.0/16"),
    ipaddress.IPv4Network("13.208.0.0/16"),
    ipaddress.IPv4Network("13.209.0.0/16"),
    ipaddress.IPv4Network("13.210.0.0/15"),
    ipaddress.IPv4Network("13.212.0.0/15"),
    ipaddress.IPv4Network("13.214.0.0/15"),
    ipaddress.IPv4Network("13.216.0.0/13"),
    ipaddress.IPv4Network("13.224.0.0/14"),
    ipaddress.IPv4Network("13.228.0.0/15"),
    ipaddress.IPv4Network("13.230.0.0/15"),
    ipaddress.IPv4Network("13.232.0.0/14"),
    ipaddress.IPv4Network("13.236.0.0/14"),
    ipaddress.IPv4Network("13.244.0.0/15"),
    ipaddress.IPv4Network("13.246.0.0/15"),
    ipaddress.IPv4Network("13.248.0.0/16"),
    ipaddress.IPv4Network("13.249.0.0/16"),
    ipaddress.IPv4Network("13.250.0.0/15"),
    ipaddress.IPv4Network("13.252.0.0/15"),
    ipaddress.IPv4Network("15.177.0.0/16"),
    ipaddress.IPv4Network("15.184.0.0/15"),
    ipaddress.IPv4Network("15.188.0.0/16"),
    ipaddress.IPv4Network("15.190.0.0/16"),
    ipaddress.IPv4Network("15.192.0.0/12"),
    ipaddress.IPv4Network("15.220.0.0/14"),
    ipaddress.IPv4Network("15.228.0.0/15"),
    ipaddress.IPv4Network("15.230.0.0/15"),
    ipaddress.IPv4Network("15.236.0.0/15"),
    ipaddress.IPv4Network("16.0.0.0/16"),
    ipaddress.IPv4Network("16.12.0.0/16"),
    ipaddress.IPv4Network("16.15.0.0/16"),
    ipaddress.IPv4Network("16.26.0.0/15"),
    ipaddress.IPv4Network("16.50.0.0/15"),
    ipaddress.IPv4Network("16.52.0.0/14"),
    ipaddress.IPv4Network("16.56.0.0/14"),
    ipaddress.IPv4Network("16.62.0.0/15"),
    ipaddress.IPv4Network("16.64.0.0/14"),
    ipaddress.IPv4Network("16.78.0.0/15"),
    ipaddress.IPv4Network("16.84.0.0/15"),
    ipaddress.IPv4Network("16.100.0.0/14"),
    ipaddress.IPv4Network("16.104.0.0/14"),
    ipaddress.IPv4Network("16.108.0.0/15"),
    ipaddress.IPv4Network("16.110.0.0/15"),
    ipaddress.IPv4Network("16.112.0.0/14"),
    ipaddress.IPv4Network("16.116.0.0/15"),
    ipaddress.IPv4Network("16.118.0.0/15"),
    ipaddress.IPv4Network("16.120.0.0/13"),
    ipaddress.IPv4Network("16.128.0.0/14"),
    ipaddress.IPv4Network("16.136.0.0/14"),
    ipaddress.IPv4Network("16.140.0.0/15"),
    ipaddress.IPv4Network("16.142.0.0/15"),
    ipaddress.IPv4Network("16.144.0.0/14"),
    ipaddress.IPv4Network("16.148.0.0/15"),
    ipaddress.IPv4Network("16.150.0.0/15"),
    ipaddress.IPv4Network("16.152.0.0/14"),
    ipaddress.IPv4Network("16.156.0.0/14"),
    ipaddress.IPv4Network("16.160.0.0/14"),
    ipaddress.IPv4Network("16.164.0.0/14"),
    ipaddress.IPv4Network("16.168.0.0/14"),
    ipaddress.IPv4Network("16.172.0.0/15"),
    ipaddress.IPv4Network("16.174.0.0/15"),
    ipaddress.IPv4Network("16.176.0.0/12"),
    ipaddress.IPv4Network("16.192.0.0/13"),
    ipaddress.IPv4Network("16.200.0.0/14"),
    ipaddress.IPv4Network("16.204.0.0/14"),
    ipaddress.IPv4Network("16.208.0.0/14"),
    ipaddress.IPv4Network("16.212.0.0/14"),
    ipaddress.IPv4Network("16.216.0.0/13"),
    ipaddress.IPv4Network("16.224.0.0/12"),
    ipaddress.IPv4Network("16.240.0.0/13"),
    ipaddress.IPv4Network("16.248.0.0/14"),
    ipaddress.IPv4Network("16.252.0.0/15"),
    ipaddress.IPv4Network("16.254.0.0/16"),
    ipaddress.IPv4Network("18.34.0.0/19"),
    ipaddress.IPv4Network("18.88.0.0/18"),
    ipaddress.IPv4Network("18.98.0.0/18"),
    ipaddress.IPv4Network("18.144.0.0/15"),
    ipaddress.IPv4Network("18.162.0.0/15"),
    ipaddress.IPv4Network("18.172.0.0/15"),
    ipaddress.IPv4Network("18.180.0.0/15"),
    ipaddress.IPv4Network("18.188.0.0/16"),
    ipaddress.IPv4Network("18.191.0.0/16"),
    ipaddress.IPv4Network("18.192.0.0/15"),
    ipaddress.IPv4Network("18.194.0.0/15"),
    ipaddress.IPv4Network("18.196.0.0/15"),
    ipaddress.IPv4Network("18.198.0.0/15"),
    ipaddress.IPv4Network("18.200.0.0/16"),
    ipaddress.IPv4Network("18.201.0.0/16"),
    ipaddress.IPv4Network("18.202.0.0/15"),
    ipaddress.IPv4Network("18.208.0.0/13"),
    ipaddress.IPv4Network("18.216.0.0/14"),
    ipaddress.IPv4Network("18.220.0.0/15"),
    ipaddress.IPv4Network("18.224.0.0/14"),
    ipaddress.IPv4Network("18.228.0.0/16"),
    ipaddress.IPv4Network("18.229.0.0/16"),
    ipaddress.IPv4Network("18.231.0.0/16"),
    ipaddress.IPv4Network("18.232.0.0/14"),
    ipaddress.IPv4Network("18.236.0.0/15"),
    ipaddress.IPv4Network("18.246.0.0/16"),
    ipaddress.IPv4Network("18.252.0.0/16"),
    ipaddress.IPv4Network("18.254.0.0/16"),
    ipaddress.IPv4Network("34.192.0.0/12"),
    ipaddress.IPv4Network("34.208.0.0/12"),
    ipaddress.IPv4Network("34.224.0.0/12"),
    ipaddress.IPv4Network("34.240.0.0/13"),
    ipaddress.IPv4Network("34.248.0.0/13"),
    ipaddress.IPv4Network("35.152.0.0/15"),
    ipaddress.IPv4Network("35.154.0.0/16"),
    ipaddress.IPv4Network("35.155.0.0/16"),
    ipaddress.IPv4Network("35.156.0.0/14"),
    ipaddress.IPv4Network("35.160.0.0/13"),
    ipaddress.IPv4Network("35.168.0.0/13"),
    ipaddress.IPv4Network("35.176.0.0/15"),
    ipaddress.IPv4Network("35.178.0.0/15"),
    ipaddress.IPv4Network("35.180.0.0/14"),
    ipaddress.IPv4Network("44.192.0.0/11"),
    ipaddress.IPv4Network("44.224.0.0/11"),
    ipaddress.IPv4Network("50.16.0.0/15"),
    ipaddress.IPv4Network("50.18.0.0/16"),
    ipaddress.IPv4Network("50.19.0.0/16"),
    ipaddress.IPv4Network("50.112.0.0/16"),
    ipaddress.IPv4Network("51.0.0.0/16"),
    ipaddress.IPv4Network("51.16.0.0/15"),
    ipaddress.IPv4Network("51.20.0.0/16"),
    ipaddress.IPv4Network("51.24.0.0/15"),
    ipaddress.IPv4Network("51.44.0.0/16"),
    ipaddress.IPv4Network("51.48.0.0/15"),
    ipaddress.IPv4Network("51.84.0.0/16"),
    ipaddress.IPv4Network("51.85.0.0/16"),
    ipaddress.IPv4Network("51.86.0.0/15"),
    ipaddress.IPv4Network("51.88.0.0/15"),
    ipaddress.IPv4Network("51.90.0.0/15"),
    ipaddress.IPv4Network("51.92.0.0/14"),
    ipaddress.IPv4Network("51.96.0.0/15"),
    ipaddress.IPv4Network("51.98.0.0/15"),
    ipaddress.IPv4Network("51.102.0.0/15"),
    ipaddress.IPv4Network("51.104.0.0/15"),
    ipaddress.IPv4Network("51.106.0.0/15"),
    ipaddress.IPv4Network("51.108.0.0/15"),
    ipaddress.IPv4Network("51.112.0.0/15"),
    ipaddress.IPv4Network("51.114.0.0/15"),
    ipaddress.IPv4Network("51.116.0.0/15"),
    ipaddress.IPv4Network("51.118.0.0/15"),
    ipaddress.IPv4Network("51.120.0.0/16"),
    ipaddress.IPv4Network("51.122.0.0/16"),
    ipaddress.IPv4Network("51.124.0.0/15"),
    ipaddress.IPv4Network("51.126.0.0/15"),
    ipaddress.IPv4Network("51.128.0.0/11"),
    ipaddress.IPv4Network("51.160.0.0/13"),
    ipaddress.IPv4Network("51.168.0.0/14"),
    ipaddress.IPv4Network("51.172.0.0/15"),
    ipaddress.IPv4Network("51.174.0.0/15"),
    ipaddress.IPv4Network("51.176.0.0/13"),
    ipaddress.IPv4Network("51.184.0.0/14"),
    ipaddress.IPv4Network("51.188.0.0/15"),
    ipaddress.IPv4Network("51.190.0.0/15"),
    ipaddress.IPv4Network("51.192.0.0/13"),
    ipaddress.IPv4Network("51.200.0.0/14"),
    ipaddress.IPv4Network("51.204.0.0/15"),
    ipaddress.IPv4Network("51.206.0.0/15"),
    ipaddress.IPv4Network("51.210.0.0/16"),
    ipaddress.IPv4Network("52.0.0.0/15"),
    ipaddress.IPv4Network("52.2.0.0/15"),
    ipaddress.IPv4Network("52.4.0.0/14"),
    ipaddress.IPv4Network("52.8.0.0/15"),
    ipaddress.IPv4Network("52.10.0.0/15"),
    ipaddress.IPv4Network("52.12.0.0/15"),
    ipaddress.IPv4Network("52.14.0.0/16"),
    ipaddress.IPv4Network("52.15.0.0/16"),
    ipaddress.IPv4Network("52.16.0.0/15"),
    ipaddress.IPv4Network("52.18.0.0/15"),
    ipaddress.IPv4Network("52.20.0.0/14"),
    ipaddress.IPv4Network("52.24.0.0/14"),
    ipaddress.IPv4Network("52.28.0.0/15"),
    ipaddress.IPv4Network("52.30.0.0/15"),
    ipaddress.IPv4Network("52.32.0.0/14"),
    ipaddress.IPv4Network("52.36.0.0/14"),
    ipaddress.IPv4Network("52.40.0.0/14"),
    ipaddress.IPv4Network("52.44.0.0/15"),
    ipaddress.IPv4Network("52.46.0.0/15"),
    ipaddress.IPv4Network("52.48.0.0/14"),
    ipaddress.IPv4Network("52.52.0.0/15"),
    ipaddress.IPv4Network("52.54.0.0/15"),
    ipaddress.IPv4Network("52.56.0.0/14"),
    ipaddress.IPv4Network("52.60.0.0/15"),
    ipaddress.IPv4Network("52.62.0.0/15"),
    ipaddress.IPv4Network("52.64.0.0/14"),
    ipaddress.IPv4Network("52.68.0.0/15"),
    ipaddress.IPv4Network("52.70.0.0/15"),
    ipaddress.IPv4Network("52.72.0.0/15"),
    ipaddress.IPv4Network("52.74.0.0/15"),
    ipaddress.IPv4Network("52.76.0.0/15"),
    ipaddress.IPv4Network("52.78.0.0/15"),
    ipaddress.IPv4Network("52.80.0.0/14"),
    ipaddress.IPv4Network("52.84.0.0/15"),
    ipaddress.IPv4Network("52.86.0.0/15"),
    ipaddress.IPv4Network("52.88.0.0/14"),
    ipaddress.IPv4Network("52.92.0.0/14"),
    ipaddress.IPv4Network("52.96.0.0/14"),
    ipaddress.IPv4Network("52.100.0.0/14"),
    ipaddress.IPv4Network("52.104.0.0/14"),
    ipaddress.IPv4Network("52.108.0.0/14"),
    ipaddress.IPv4Network("52.112.0.0/14"),
    ipaddress.IPv4Network("52.119.192.0/20"),
    ipaddress.IPv4Network("52.144.0.0/14"),
    ipaddress.IPv4Network("52.196.0.0/14"),
    ipaddress.IPv4Network("52.200.0.0/13"),
    ipaddress.IPv4Network("52.208.0.0/13"),
    ipaddress.IPv4Network("52.216.0.0/15"),
    ipaddress.IPv4Network("52.218.0.0/15"),
    ipaddress.IPv4Network("52.220.0.0/15"),
    ipaddress.IPv4Network("52.222.0.0/15"),
    ipaddress.IPv4Network("52.228.0.0/15"),
    ipaddress.IPv4Network("52.230.0.0/15"),
    ipaddress.IPv4Network("52.232.0.0/15"),
    ipaddress.IPv4Network("52.234.0.0/15"),
    ipaddress.IPv4Network("52.236.0.0/15"),
    ipaddress.IPv4Network("52.238.0.0/15"),
    ipaddress.IPv4Network("52.240.0.0/14"),
    ipaddress.IPv4Network("52.244.0.0/15"),
    ipaddress.IPv4Network("52.246.0.0/15"),
    ipaddress.IPv4Network("52.248.0.0/14"),
    ipaddress.IPv4Network("52.252.0.0/15"),
    ipaddress.IPv4Network("52.254.0.0/15"),
    ipaddress.IPv4Network("52.255.0.0/16"),
    ipaddress.IPv4Network("54.68.0.0/14"),
    ipaddress.IPv4Network("54.72.0.0/15"),
    ipaddress.IPv4Network("54.74.0.0/15"),
    ipaddress.IPv4Network("54.76.0.0/15"),
    ipaddress.IPv4Network("54.78.0.0/16"),
    ipaddress.IPv4Network("54.79.0.0/16"),
    ipaddress.IPv4Network("54.80.0.0/13"),
    ipaddress.IPv4Network("54.88.0.0/14"),
    ipaddress.IPv4Network("54.92.0.0/14"),
    ipaddress.IPv4Network("54.144.0.0/13"),
    ipaddress.IPv4Network("54.152.0.0/14"),
    ipaddress.IPv4Network("54.156.0.0/14"),
    ipaddress.IPv4Network("54.160.0.0/13"),
    ipaddress.IPv4Network("54.168.0.0/14"),
    ipaddress.IPv4Network("54.172.0.0/15"),
    ipaddress.IPv4Network("54.174.0.0/15"),
    ipaddress.IPv4Network("54.176.0.0/15"),
    ipaddress.IPv4Network("54.178.0.0/15"),
    ipaddress.IPv4Network("54.180.0.0/14"),
    ipaddress.IPv4Network("54.184.0.0/14"),
    ipaddress.IPv4Network("54.188.0.0/15"),
    ipaddress.IPv4Network("54.190.0.0/15"),
    ipaddress.IPv4Network("54.192.0.0/12"),
    ipaddress.IPv4Network("54.208.0.0/13"),
    ipaddress.IPv4Network("54.216.0.0/14"),
    ipaddress.IPv4Network("54.220.0.0/16"),
    ipaddress.IPv4Network("54.221.0.0/16"),
    ipaddress.IPv4Network("54.222.0.0/15"),
    ipaddress.IPv4Network("54.224.0.0/12"),
    ipaddress.IPv4Network("54.240.0.0/12"),
    # Google Cloud
    ipaddress.IPv4Network("8.34.208.0/20"),
    ipaddress.IPv4Network("8.35.192.0/20"),
    ipaddress.IPv4Network("23.236.48.0/20"),
    ipaddress.IPv4Network("23.251.128.0/19"),
    ipaddress.IPv4Network("34.0.0.0/15"),
    ipaddress.IPv4Network("34.2.0.0/15"),
    ipaddress.IPv4Network("34.4.0.0/14"),
    ipaddress.IPv4Network("34.8.0.0/14"),
    ipaddress.IPv4Network("34.12.0.0/14"),
    ipaddress.IPv4Network("34.16.0.0/14"),
    ipaddress.IPv4Network("34.20.0.0/14"),
    ipaddress.IPv4Network("34.24.0.0/14"),
    ipaddress.IPv4Network("34.28.0.0/14"),
    ipaddress.IPv4Network("34.32.0.0/14"),
    ipaddress.IPv4Network("34.36.0.0/14"),
    ipaddress.IPv4Network("34.40.0.0/14"),
    ipaddress.IPv4Network("34.44.0.0/14"),
    ipaddress.IPv4Network("34.48.0.0/14"),
    ipaddress.IPv4Network("34.52.0.0/14"),
    ipaddress.IPv4Network("34.56.0.0/14"),
    ipaddress.IPv4Network("34.60.0.0/14"),
    ipaddress.IPv4Network("34.64.0.0/14"),
    ipaddress.IPv4Network("34.68.0.0/14"),
    ipaddress.IPv4Network("34.72.0.0/14"),
    ipaddress.IPv4Network("34.76.0.0/14"),
    ipaddress.IPv4Network("34.80.0.0/14"),
    ipaddress.IPv4Network("34.84.0.0/14"),
    ipaddress.IPv4Network("34.88.0.0/14"),
    ipaddress.IPv4Network("34.92.0.0/14"),
    ipaddress.IPv4Network("34.96.0.0/14"),
    ipaddress.IPv4Network("34.100.0.0/14"),
    ipaddress.IPv4Network("34.104.0.0/14"),
    ipaddress.IPv4Network("34.108.0.0/14"),
    ipaddress.IPv4Network("34.112.0.0/14"),
    ipaddress.IPv4Network("34.116.0.0/14"),
    ipaddress.IPv4Network("34.120.0.0/14"),
    ipaddress.IPv4Network("34.124.0.0/14"),
    ipaddress.IPv4Network("34.128.0.0/14"),
    ipaddress.IPv4Network("34.132.0.0/14"),
    ipaddress.IPv4Network("34.136.0.0/14"),
    ipaddress.IPv4Network("34.140.0.0/14"),
    ipaddress.IPv4Network("34.144.0.0/14"),
    ipaddress.IPv4Network("34.148.0.0/14"),
    ipaddress.IPv4Network("34.152.0.0/14"),
    ipaddress.IPv4Network("34.156.0.0/14"),
    ipaddress.IPv4Network("34.160.0.0/14"),
    ipaddress.IPv4Network("34.164.0.0/14"),
    ipaddress.IPv4Network("34.168.0.0/14"),
    ipaddress.IPv4Network("34.172.0.0/14"),
    ipaddress.IPv4Network("34.176.0.0/14"),
    ipaddress.IPv4Network("34.180.0.0/14"),
    ipaddress.IPv4Network("34.184.0.0/14"),
    ipaddress.IPv4Network("34.188.0.0/14"),
    ipaddress.IPv4Network("35.184.0.0/14"),
    ipaddress.IPv4Network("35.188.0.0/14"),
    ipaddress.IPv4Network("35.192.0.0/14"),
    ipaddress.IPv4Network("35.196.0.0/14"),
    ipaddress.IPv4Network("35.200.0.0/14"),
    ipaddress.IPv4Network("35.204.0.0/14"),
    ipaddress.IPv4Network("35.208.0.0/14"),
    ipaddress.IPv4Network("35.212.0.0/14"),
    ipaddress.IPv4Network("35.216.0.0/14"),
    ipaddress.IPv4Network("35.220.0.0/14"),
    ipaddress.IPv4Network("35.224.0.0/14"),
    ipaddress.IPv4Network("35.228.0.0/14"),
    ipaddress.IPv4Network("35.232.0.0/14"),
    ipaddress.IPv4Network("35.236.0.0/14"),
    ipaddress.IPv4Network("35.240.0.0/14"),
    ipaddress.IPv4Network("35.244.0.0/14"),
    ipaddress.IPv4Network("35.248.0.0/14"),
    ipaddress.IPv4Network("104.154.0.0/15"),
    ipaddress.IPv4Network("104.196.0.0/14"),
    ipaddress.IPv4Network("104.198.0.0/16"),
    ipaddress.IPv4Network("104.199.0.0/16"),
    ipaddress.IPv4Network("107.178.192.0/18"),
    ipaddress.IPv4Network("108.59.80.0/20"),
    ipaddress.IPv4Network("130.211.0.0/16"),
    ipaddress.IPv4Network("146.148.0.0/17"),
    ipaddress.IPv4Network("162.222.176.0/21"),
    ipaddress.IPv4Network("172.110.32.0/21"),
    ipaddress.IPv4Network("173.255.112.0/20"),
    ipaddress.IPv4Network("192.158.28.0/22"),
    ipaddress.IPv4Network("193.164.197.0/24"),
    ipaddress.IPv4Network("199.192.112.0/22"),
    ipaddress.IPv4Network("199.223.232.0/21"),
    ipaddress.IPv4Network("199.223.236.0/24"),
    ipaddress.IPv4Network("208.68.136.0/21"),
    # Microsoft Azure
    ipaddress.IPv4Network("4.144.0.0/14"),
    ipaddress.IPv4Network("4.148.0.0/14"),
    ipaddress.IPv4Network("4.152.0.0/14"),
    ipaddress.IPv4Network("4.156.0.0/14"),
    ipaddress.IPv4Network("4.160.0.0/14"),
    ipaddress.IPv4Network("4.164.0.0/14"),
    ipaddress.IPv4Network("4.168.0.0/14"),
    ipaddress.IPv4Network("4.172.0.0/14"),
    ipaddress.IPv4Network("4.176.0.0/14"),
    ipaddress.IPv4Network("4.180.0.0/14"),
    ipaddress.IPv4Network("4.184.0.0/14"),
    ipaddress.IPv4Network("4.188.0.0/14"),
    ipaddress.IPv4Network("4.192.0.0/14"),
    ipaddress.IPv4Network("4.196.0.0/14"),
    ipaddress.IPv4Network("4.200.0.0/14"),
    ipaddress.IPv4Network("4.204.0.0/14"),
    ipaddress.IPv4Network("4.208.0.0/14"),
    ipaddress.IPv4Network("4.212.0.0/14"),
    ipaddress.IPv4Network("4.216.0.0/14"),
    ipaddress.IPv4Network("4.220.0.0/14"),
    ipaddress.IPv4Network("4.224.0.0/14"),
    ipaddress.IPv4Network("4.228.0.0/14"),
    ipaddress.IPv4Network("4.232.0.0/14"),
    ipaddress.IPv4Network("4.236.0.0/14"),
    ipaddress.IPv4Network("4.240.0.0/14"),
    ipaddress.IPv4Network("4.244.0.0/14"),
    ipaddress.IPv4Network("4.248.0.0/14"),
    ipaddress.IPv4Network("4.252.0.0/14"),
    ipaddress.IPv4Network("13.64.0.0/11"),
    ipaddress.IPv4Network("13.96.0.0/13"),
    ipaddress.IPv4Network("13.104.0.0/14"),
    ipaddress.IPv4Network("13.112.0.0/12"),
    ipaddress.IPv4Network("13.128.0.0/12"),
    ipaddress.IPv4Network("13.144.0.0/12"),
    ipaddress.IPv4Network("13.160.0.0/12"),
    ipaddress.IPv4Network("13.176.0.0/12"),
    ipaddress.IPv4Network("13.192.0.0/12"),
    ipaddress.IPv4Network("13.208.0.0/13"),
    ipaddress.IPv4Network("13.216.0.0/13"),
    ipaddress.IPv4Network("13.224.0.0/14"),
    ipaddress.IPv4Network("13.228.0.0/15"),
    ipaddress.IPv4Network("13.232.0.0/14"),
    ipaddress.IPv4Network("13.236.0.0/14"),
    ipaddress.IPv4Network("13.240.0.0/14"),
    ipaddress.IPv4Network("13.244.0.0/15"),
    ipaddress.IPv4Network("13.248.0.0/16"),
    ipaddress.IPv4Network("13.250.0.0/15"),
    ipaddress.IPv4Network("20.0.0.0/10"),
    ipaddress.IPv4Network("20.64.0.0/10"),
    ipaddress.IPv4Network("20.128.0.0/10"),
    ipaddress.IPv4Network("20.192.0.0/12"),
    ipaddress.IPv4Network("23.96.0.0/14"),
    ipaddress.IPv4Network("23.100.0.0/15"),
    ipaddress.IPv4Network("40.64.0.0/12"),
    ipaddress.IPv4Network("40.80.0.0/12"),
    ipaddress.IPv4Network("40.96.0.0/12"),
    ipaddress.IPv4Network("40.112.0.0/13"),
    ipaddress.IPv4Network("40.120.0.0/14"),
    ipaddress.IPv4Network("40.124.0.0/15"),
    ipaddress.IPv4Network("40.126.0.0/15"),
    ipaddress.IPv4Network("40.128.0.0/12"),
    ipaddress.IPv4Network("40.160.0.0/12"),
    ipaddress.IPv4Network("40.176.0.0/13"),
    ipaddress.IPv4Network("40.184.0.0/14"),
    ipaddress.IPv4Network("40.188.0.0/15"),
    ipaddress.IPv4Network("40.190.0.0/15"),
    ipaddress.IPv4Network("40.192.0.0/14"),
    ipaddress.IPv4Network("40.196.0.0/14"),
    ipaddress.IPv4Network("40.200.0.0/14"),
    ipaddress.IPv4Network("40.204.0.0/14"),
    ipaddress.IPv4Network("40.208.0.0/13"),
    ipaddress.IPv4Network("40.216.0.0/14"),
    ipaddress.IPv4Network("40.220.0.0/14"),
    ipaddress.IPv4Network("40.224.0.0/14"),
    ipaddress.IPv4Network("40.228.0.0/14"),
    ipaddress.IPv4Network("40.232.0.0/14"),
    ipaddress.IPv4Network("40.236.0.0/14"),
    ipaddress.IPv4Network("40.240.0.0/14"),
    ipaddress.IPv4Network("40.244.0.0/14"),
    ipaddress.IPv4Network("40.248.0.0/14"),
    ipaddress.IPv4Network("40.252.0.0/15"),
    ipaddress.IPv4Network("48.216.0.0/14"),
    ipaddress.IPv4Network("48.220.0.0/14"),
    ipaddress.IPv4Network("48.224.0.0/14"),
    ipaddress.IPv4Network("48.228.0.0/14"),
    ipaddress.IPv4Network("48.232.0.0/14"),
    ipaddress.IPv4Network("48.236.0.0/14"),
    ipaddress.IPv4Network("48.240.0.0/14"),
    ipaddress.IPv4Network("48.244.0.0/14"),
    ipaddress.IPv4Network("48.248.0.0/14"),
    ipaddress.IPv4Network("48.252.0.0/14"),
    ipaddress.IPv4Network("52.96.0.0/14"),
    ipaddress.IPv4Network("52.100.0.0/14"),
    ipaddress.IPv4Network("52.104.0.0/14"),
    ipaddress.IPv4Network("52.108.0.0/16"),
    ipaddress.IPv4Network("52.112.0.0/14"),
    ipaddress.IPv4Network("52.120.0.0/14"),
    ipaddress.IPv4Network("52.124.0.0/16"),
    ipaddress.IPv4Network("52.128.0.0/14"),
    ipaddress.IPv4Network("52.132.0.0/14"),
    ipaddress.IPv4Network("52.136.0.0/14"),
    ipaddress.IPv4Network("52.140.0.0/15"),
    ipaddress.IPv4Network("52.142.0.0/15"),
    ipaddress.IPv4Network("52.144.0.0/14"),
    ipaddress.IPv4Network("52.148.0.0/14"),
    ipaddress.IPv4Network("52.152.0.0/14"),
    ipaddress.IPv4Network("52.156.0.0/14"),
    ipaddress.IPv4Network("52.160.0.0/13"),
    ipaddress.IPv4Network("52.168.0.0/13"),
    ipaddress.IPv4Network("52.176.0.0/14"),
    ipaddress.IPv4Network("52.180.0.0/14"),
    ipaddress.IPv4Network("52.184.0.0/14"),
    ipaddress.IPv4Network("52.188.0.0/14"),
    ipaddress.IPv4Network("52.192.0.0/11"),
    ipaddress.IPv4Network("52.224.0.0/11"),
    ipaddress.IPv4Network("65.52.0.0/14"),
    ipaddress.IPv4Network("65.52.64.0/18"),
    ipaddress.IPv4Network("65.52.128.0/17"),
    ipaddress.IPv4Network("65.52.192.0/18"),
    ipaddress.IPv4Network("70.37.0.0/17"),
    ipaddress.IPv4Network("70.37.128.0/18"),
    ipaddress.IPv4Network("70.37.192.0/18"),
    ipaddress.IPv4Network("91.190.216.0/23"),
    ipaddress.IPv4Network("94.245.104.0/22"),
    ipaddress.IPv4Network("102.133.0.0/16"),
    ipaddress.IPv4Network("104.208.0.0/13"),
    ipaddress.IPv4Network("104.208.0.0/14"),
    ipaddress.IPv4Network("104.212.0.0/14"),
    ipaddress.IPv4Network("104.216.0.0/14"),
    ipaddress.IPv4Network("104.222.0.0/15"),
    ipaddress.IPv4Network("104.224.0.0/14"),
    ipaddress.IPv4Network("104.228.0.0/14"),
    ipaddress.IPv4Network("104.232.0.0/14"),
    ipaddress.IPv4Network("104.236.0.0/14"),
    ipaddress.IPv4Network("104.240.0.0/14"),
    ipaddress.IPv4Network("104.244.0.0/14"),
    ipaddress.IPv4Network("104.248.0.0/14"),
    ipaddress.IPv4Network("104.252.0.0/14"),
    ipaddress.IPv4Network("137.116.0.0/16"),
    ipaddress.IPv4Network("137.117.0.0/16"),
    ipaddress.IPv4Network("137.135.0.0/16"),
    ipaddress.IPv4Network("138.91.0.0/16"),
    ipaddress.IPv4Network("157.55.0.0/16"),
    ipaddress.IPv4Network("157.56.0.0/15"),
    ipaddress.IPv4Network("157.58.0.0/16"),
    ipaddress.IPv4Network("157.59.0.0/16"),
    ipaddress.IPv4Network("168.61.0.0/16"),
    ipaddress.IPv4Network("168.62.0.0/16"),
    ipaddress.IPv4Network("168.63.0.0/16"),
    ipaddress.IPv4Network("168.64.0.0/16"),
    ipaddress.IPv4Network("191.232.0.0/13"),
    ipaddress.IPv4Network("192.48.225.0/24"),
    ipaddress.IPv4Network("192.84.160.0/23"),
    ipaddress.IPv4Network("192.197.157.0/24"),
    ipaddress.IPv4Network("193.149.64.0/19"),
    ipaddress.IPv4Network("193.221.113.0/24"),
    ipaddress.IPv4Network("194.69.96.0/19"),
    ipaddress.IPv4Network("194.69.104.0/22"),
    ipaddress.IPv4Network("198.200.128.0/18"),
    ipaddress.IPv4Network("198.200.192.0/18"),
    ipaddress.IPv4Network("199.242.48.0/21"),
    ipaddress.IPv4Network("199.242.56.0/21"),
    ipaddress.IPv4Network("199.242.64.0/22"),
    ipaddress.IPv4Network("204.79.195.0/25"),
    ipaddress.IPv4Network("204.79.252.0/24"),
    ipaddress.IPv4Network("207.46.0.0/16"),
    ipaddress.IPv4Network("207.46.128.0/17"),
    ipaddress.IPv4Network("209.240.192.0/19"),
    ipaddress.IPv4Network("213.199.128.0/18"),
    # DigitalOcean
    ipaddress.IPv4Network("67.205.128.0/17"),
    ipaddress.IPv4Network("69.55.48.0/20"),
    ipaddress.IPv4Network("104.131.0.0/16"),
    ipaddress.IPv4Network("104.236.0.0/16"),
    ipaddress.IPv4Network("107.170.0.0/16"),
    ipaddress.IPv4Network("128.199.0.0/16"),
    ipaddress.IPv4Network("137.184.0.0/16"),
    ipaddress.IPv4Network("138.68.0.0/16"),
    ipaddress.IPv4Network("138.197.0.0/16"),
    ipaddress.IPv4Network("139.59.0.0/16"),
    ipaddress.IPv4Network("141.0.169.0/24"),
    ipaddress.IPv4Network("142.93.0.0/16"),
    ipaddress.IPv4Network("143.110.0.0/16"),
    ipaddress.IPv4Network("144.126.128.0/17"),
    ipaddress.IPv4Network("146.190.0.0/16"),
    ipaddress.IPv4Network("157.230.0.0/16"),
    ipaddress.IPv4Network("157.245.0.0/16"),
    ipaddress.IPv4Network("159.65.0.0/16"),
    ipaddress.IPv4Network("159.89.0.0/16"),
    ipaddress.IPv4Network("161.35.0.0/16"),
    ipaddress.IPv4Network("162.243.0.0/16"),
    ipaddress.IPv4Network("164.90.0.0/16"),
    ipaddress.IPv4Network("165.22.0.0/16"),
    ipaddress.IPv4Network("165.227.0.0/16"),
    ipaddress.IPv4Network("167.71.0.0/16"),
    ipaddress.IPv4Network("167.99.0.0/16"),
    ipaddress.IPv4Network("170.64.0.0/16"),
    ipaddress.IPv4Network("174.138.0.0/16"),
    ipaddress.IPv4Network("178.62.0.0/16"),
    ipaddress.IPv4Network("178.128.0.0/16"),
    ipaddress.IPv4Network("185.13.220.0/22"),
    ipaddress.IPv4Network("188.166.0.0/16"),
    ipaddress.IPv4Network("192.81.208.0/20"),
    ipaddress.IPv4Network("198.199.64.0/18"),
    ipaddress.IPv4Network("198.199.96.0/19"),
    ipaddress.IPv4Network("206.189.0.0/16"),
    ipaddress.IPv4Network("207.154.0.0/16"),
    ipaddress.IPv4Network("209.38.0.0/16"),
    ipaddress.IPv4Network("209.97.0.0/16"),
    # Linode
    ipaddress.IPv4Network("45.33.0.0/16"),
    ipaddress.IPv4Network("45.56.0.0/16"),
    ipaddress.IPv4Network("45.79.0.0/16"),
    ipaddress.IPv4Network("50.116.0.0/16"),
    ipaddress.IPv4Network("66.175.208.0/20"),
    ipaddress.IPv4Network("69.164.192.0/18"),
    ipaddress.IPv4Network("72.14.176.0/20"),
    ipaddress.IPv4Network("74.207.224.0/20"),
    ipaddress.IPv4Network("96.126.96.0/19"),
    ipaddress.IPv4Network("97.107.128.0/17"),
    ipaddress.IPv4Network("103.3.60.0/22"),
    ipaddress.IPv4Network("104.200.20.0/22"),
    ipaddress.IPv4Network("104.237.128.0/18"),
    ipaddress.IPv4Network("106.187.32.0/20"),
    ipaddress.IPv4Network("139.162.0.0/16"),
    ipaddress.IPv4Network("172.104.0.0/16"),
    ipaddress.IPv4Network("172.105.0.0/16"),
    ipaddress.IPv4Network("173.230.128.0/18"),
    ipaddress.IPv4Network("173.255.192.0/18"),
    ipaddress.IPv4Network("176.58.96.0/19"),
    ipaddress.IPv4Network("178.79.128.0/18"),
    ipaddress.IPv4Network("184.106.128.0/20"),
    ipaddress.IPv4Network("185.3.124.0/22"),
    ipaddress.IPv4Network("192.155.80.0/20"),
    ipaddress.IPv4Network("192.237.128.0/18"),
    ipaddress.IPv4Network("192.46.208.0/20"),
    ipaddress.IPv4Network("192.53.112.0/20"),
    ipaddress.IPv4Network("192.81.128.0/18"),
    ipaddress.IPv4Network("192.155.80.0/20"),
    ipaddress.IPv4Network("194.195.96.0/20"),
    ipaddress.IPv4Network("198.58.96.0/19"),
    ipaddress.IPv4Network("198.74.48.0/20"),
    ipaddress.IPv4Network("198.98.48.0/20"),
    ipaddress.IPv4Network("207.134.224.0/19"),
    ipaddress.IPv4Network("209.141.32.0/19"),
    ipaddress.IPv4Network("216.218.128.0/17"),
    ipaddress.IPv4Network("23.239.0.0/17"),
    ipaddress.IPv4Network("23.92.16.0/20"),
    # Vultr
    ipaddress.IPv4Network("45.32.0.0/16"),
    ipaddress.IPv4Network("45.63.0.0/16"),
    ipaddress.IPv4Network("45.76.0.0/16"),
    ipaddress.IPv4Network("45.77.0.0/16"),
    ipaddress.IPv4Network("45.86.0.0/16"),
    ipaddress.IPv4Network("66.42.0.0/16"),
    ipaddress.IPv4Network("104.156.224.0/20"),
    ipaddress.IPv4Network("104.238.128.0/17"),
    ipaddress.IPv4Network("107.191.32.0/19"),
    ipaddress.IPv4Network("108.61.0.0/16"),
    ipaddress.IPv4Network("136.243.0.0/16"),
    ipaddress.IPv4Network("141.164.0.0/16"),
    ipaddress.IPv4Network("149.28.0.0/16"),
    ipaddress.IPv4Network("155.138.0.0/16"),
    ipaddress.IPv4Network("158.247.0.0/16"),
    ipaddress.IPv4Network("167.179.0.0/16"),
    ipaddress.IPv4Network("168.235.64.0/18"),
    ipaddress.IPv4Network("192.248.128.0/17"),
    ipaddress.IPv4Network("199.247.0.0/16"),
    ipaddress.IPv4Network("207.148.0.0/16"),
    ipaddress.IPv4Network("208.85.0.0/17"),
    ipaddress.IPv4Network("209.222.0.0/17"),
    ipaddress.IPv4Network("216.238.64.0/18"),
    ipaddress.IPv4Network("23.90.32.0/19"),
    # Hetzner
    ipaddress.IPv4Network("5.9.0.0/16"),
    ipaddress.IPv4Network("23.88.0.0/16"),
    ipaddress.IPv4Network("46.4.0.0/16"),
    ipaddress.IPv4Network("49.12.0.0/15"),
    ipaddress.IPv4Network("65.21.0.0/16"),
    ipaddress.IPv4Network("78.46.0.0/16"),
    ipaddress.IPv4Network("88.198.0.0/16"),
    ipaddress.IPv4Network("91.190.216.0/23"),
    ipaddress.IPv4Network("94.130.0.0/16"),
    ipaddress.IPv4Network("95.216.0.0/16"),
    ipaddress.IPv4Network("116.202.0.0/16"),
    ipaddress.IPv4Network("136.243.0.0/16"),
    ipaddress.IPv4Network("138.201.0.0/16"),
    ipaddress.IPv4Network("142.132.0.0/16"),
    ipaddress.IPv4Network("144.76.0.0/16"),
    ipaddress.IPv4Network("148.251.0.0/16"),
    ipaddress.IPv4Network("157.90.0.0/16"),
    ipaddress.IPv4Network("159.69.0.0/16"),
    ipaddress.IPv4Network("162.55.0.0/16"),
    ipaddress.IPv4Network("167.235.0.0/16"),
    ipaddress.IPv4Network("168.119.0.0/16"),
    ipaddress.IPv4Network("171.22.24.0/22"),
    ipaddress.IPv4Network("176.9.0.0/16"),
    ipaddress.IPv4Network("178.63.0.0/16"),
    ipaddress.IPv4Network("188.40.0.0/16"),
    ipaddress.IPv4Network("192.162.0.0/16"),
    ipaddress.IPv4Network("194.13.0.0/16"),
    ipaddress.IPv4Network("195.201.0.0/16"),
    ipaddress.IPv4Network("213.133.0.0/16"),
    # OVH
    ipaddress.IPv4Network("5.135.0.0/16"),
    ipaddress.IPv4Network("8.33.128.0/20"),
    ipaddress.IPv4Network("15.204.0.0/15"),
    ipaddress.IPv4Network("15.235.0.0/16"),
    ipaddress.IPv4Network("37.59.0.0/16"),
    ipaddress.IPv4Network("37.187.0.0/16"),
    ipaddress.IPv4Network("46.105.0.0/16"),
    ipaddress.IPv4Network("51.38.0.0/16"),
    ipaddress.IPv4Network("51.75.0.0/16"),
    ipaddress.IPv4Network("51.81.0.0/16"),
    ipaddress.IPv4Network("51.178.0.0/16"),
    ipaddress.IPv4Network("51.195.0.0/16"),
    ipaddress.IPv4Network("51.210.0.0/16"),
    ipaddress.IPv4Network("51.222.0.0/16"),
    ipaddress.IPv4Network("51.254.0.0/16"),
    ipaddress.IPv4Network("51.255.0.0/16"),
    ipaddress.IPv4Network("54.36.0.0/16"),
    ipaddress.IPv4Network("54.37.0.0/16"),
    ipaddress.IPv4Network("54.38.0.0/16"),
    ipaddress.IPv4Network("54.39.0.0/16"),
    ipaddress.IPv4Network("57.128.0.0/16"),
    ipaddress.IPv4Network("62.210.0.0/16"),
    ipaddress.IPv4Network("87.98.0.0/16"),
    ipaddress.IPv4Network("91.121.0.0/16"),
    ipaddress.IPv4Network("92.222.0.0/16"),
    ipaddress.IPv4Network("94.23.0.0/16"),
    ipaddress.IPv4Network("128.65.0.0/16"),
    ipaddress.IPv4Network("141.94.0.0/16"),
    ipaddress.IPv4Network("142.44.0.0/16"),
    ipaddress.IPv4Network("144.217.0.0/16"),
    ipaddress.IPv4Network("145.239.0.0/16"),
    ipaddress.IPv4Network("146.59.0.0/16"),
    ipaddress.IPv4Network("147.135.0.0/16"),
    ipaddress.IPv4Network("149.56.0.0/16"),
    ipaddress.IPv4Network("151.80.0.0/16"),
    ipaddress.IPv4Network("158.69.0.0/16"),
    ipaddress.IPv4Network("162.19.0.0/16"),
    ipaddress.IPv4Network("163.172.0.0/16"),
    ipaddress.IPv4Network("164.132.0.0/16"),
    ipaddress.IPv4Network("167.114.0.0/16"),
    ipaddress.IPv4Network("176.31.0.0/16"),
    ipaddress.IPv4Network("178.32.0.0/16"),
    ipaddress.IPv4Network("178.33.0.0/16"),
    ipaddress.IPv4Network("185.132.0.0/18"),
    ipaddress.IPv4Network("188.165.0.0/16"),
    ipaddress.IPv4Network("192.95.0.0/16"),
    ipaddress.IPv4Network("193.70.0.0/16"),
    ipaddress.IPv4Network("198.50.0.0/16"),
    ipaddress.IPv4Network("198.100.0.0/16"),
    ipaddress.IPv4Network("198.27.0.0/16"),
    ipaddress.IPv4Network("199.127.0.0/16"),
    ipaddress.IPv4Network("213.32.0.0/16"),
    ipaddress.IPv4Network("213.186.0.0/16"),
    ipaddress.IPv4Network("213.251.0.0/16"),
]

# VPN provider organization name patterns (case-insensitive matching)
VPN_ORG_PATTERNS: List[re.Pattern] = [
    re.compile(r"nordvpn", re.I),
    re.compile(r"express.?vpn", re.I),
    re.compile(r"surfshark", re.I),
    re.compile(r"mullvad", re.I),
    re.compile(r"proton.?vpn", re.I),
    re.compile(r"cyberghost", re.I),
    re.compile(r"ipvanish", re.I),
    re.compile(r"private internet access", re.I),
    re.compile(r"windscribe", re.I),
    re.compile(r"vyprvpn|golden.?frog", re.I),
    re.compile(r"hotspot.?shield", re.I),
    re.compile(r"tunnel.?bear", re.I),
    re.compile(r"pure.?vpn", re.I),
    re.compile(r"ivacy", re.I),
    re.compile(r"zoog.?vpn", re.I),
    re.compile(r"keepsolid|urban.?vpn", re.I),
    re.compile(r"hide.?my.?ass", re.I),
    re.compile(r"anonine", re.I),
    re.compile(r"perfect.?privacy", re.I),
    re.compile(r"air.?vpn", re.I),
    re.compile(r"safer.?vpn", re.I),
    re.compile(r"privatevpn", re.I),
    re.compile(r"tor.?guard", re.I),
    re.compile(r"ivpn", re.I),
    re.compile(r"o.?vpn", re.I),
    re.compile(r"anon.?vpn", re.I),
    re.compile(r"anonymous.?vpn", re.I),
    re.compile(r"vpnanonymous", re.I),
    re.compile(r"btguard", re.I),
    re.compile(r"black.?vpn", re.I),
    re.compile(r"trust.?zone", re.I),
    re.compile(r"vpn\.(ac|lt|unlimited)", re.I),
    re.compile(r"vpnshazam", re.I),
    re.compile(r"vpnonline", re.I),
    re.compile(r"fastestvpn", re.I),
    re.compile(r"hideme", re.I),
    re.compile(r"fly.?vpn", re.I),
    re.compile(r"touch.?vpn", re.I),
    re.compile(r"planet.?vpn", re.I),
    re.compile(r"proxy.?server|proxyserver", re.I),
    re.compile(r"anonymizer", re.I),
    re.compile(r"data.?center|datacenter|hosting", re.I),
]

# Datacenter/hosting provider organization name patterns
DATACENTER_ORG_PATTERNS: List[re.Pattern] = [
    re.compile(r"amazon.?web.?services|aws\b|amazonaws", re.I),
    re.compile(r"google.?cloud|gcp\b|googlecloud", re.I),
    re.compile(r"microsoft.?azure|azure\b|windows.?azure", re.I),
    re.compile(r"digital.?ocean|digitalocean", re.I),
    re.compile(r"linode\b|linode", re.I),
    re.compile(r"vultr\b", re.I),
    re.compile(r"hetzner\b", re.I),
    re.compile(r"ovh\b|ovh\s|sas", re.I),
    re.compile(r"alibaba.?cloud|alicloud", re.I),
    re.compile(r"tencent.?cloud", re.I),
    re.compile(r"oracle.?cloud|oraclecloud", re.I),
    re.compile(r"ibm.?cloud|softlayer", re.I),
    re.compile(r"rackspace\b", re.I),
    re.compile(r"go.?daddy|godaddy", re.I),
    re.compile(r"host.?gator|hostgator", re.I),
    re.compile(r"blue.?host|bluehost", re.I),
    re.compile(r"dream.?host|dreamhost", re.I),
    re.compile(r"site.?ground|siteground", re.I),
    re.compile(r"name.?cheap|namecheap", re.I),
    re.compile(r"contabo\b", re.I),
    re.compile(r"scaleway\b", re.I),
    re.compile(r"up.?cloud|upcloud", re.I),
    re.compile(r"packet\b|equinix", re.I),
    re.compile(r"lease.?web|leaseweb", re.I),
    re.compile(r"online\.net|scaleway", re.I),
    re.compile(r"ikoula\b", re.I),
    re.compile(r"kimsufi\b", re.I),
    re.compile(r"so.?you.?start|soyoustart", re.I),
    re.compile(r"world.?stream|worldstream", re.I),
    re.compile(r"psychz\b", re.I),
    re.compile(r"colocrossing", re.I),
    re.compile(r"multacom\b", re.I),
    re.compile(r"cogent\b|cogentco", re.I),
    re.compile(r"tier.?point|tierpoint", re.I),
    re.compile(r"zayo\b", re.I),
    re.compile(r"gtt\b|gtt.?net", re.I),
    re.compile(r"nlayer\b", re.I),
    re.compile(r"server.?central|servercentral", re.I),
    re.compile(r"i.?web|iweb\b", re.I),
    re.compile(r"netcup\b", re.I),
    re.compile(r"strato\b", re.I),
    re.compile(r"1&1|ionos", re.I),
    re.compile(r"united.?internet|1und1", re.I),
    re.compile(r"verizon.?digital|verizondigital", re.I),
    re.compile(r"edge.?cast|edgecast", re.I),
    re.compile(r"akamai\b", re.I),
    re.compile(r"cloudflare\b", re.I),
    re.compile(r"fastly\b", re.I),
    re.compile(r"stackpath\b", re.I),
    re.compile(r"bunny.?cdn|bunnycdn", re.I),
    re.compile(r"keycdn\b", re.I),
    re.compile(r"cachefly\b", re.I),
    re.compile(r"incapsula|imperva", re.I),
    re.compile(r"dedicated|dedicated.?server", re.I),
    re.compile(r"colo|colocation", re.I),
    re.compile(r"cloud\b.*?(host|server|compute)", re.I),
]


# ---------------------------------------------------------------------------
# IPReputation dataclass
# ---------------------------------------------------------------------------

@dataclass
class IPReputation:
    """IP reputation analysis results with full intelligence data."""
    ip_address: str
    is_vpn: bool = False
    is_proxy: bool = False
    is_tor: bool = False
    is_datacenter: bool = False
    is_residential: bool = False
    threat_level: str = 'low'
    organization: str = None
    country: str = None
    risk_score: float = 0.0
    anonymizer: bool = False
    hosting_provider: bool = False
    mobile: bool = False
    asn: str = None
    asn_org: str = None
    country_code: str = None
    isp: str = None


# ---------------------------------------------------------------------------
# Cache entry with TTL
# ---------------------------------------------------------------------------

class _CacheEntry:
    __slots__ = ('value', 'expires_at')

    def __init__(self, value: IPReputation, ttl_seconds: int):
        self.value = value
        self.expires_at = time.monotonic() + ttl_seconds

    def is_expired(self) -> bool:
        return time.monotonic() > self.expires_at


# ---------------------------------------------------------------------------
# Rate limiter for external API calls
# ---------------------------------------------------------------------------

class _RateLimiter:
    """Simple token-bucket rate limiter for external API calls."""

    def __init__(self, max_calls: int, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._calls: List[float] = []
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds
            self._calls = [t for t in self._calls if t > cutoff]
            if len(self._calls) < self.max_calls:
                self._calls.append(now)
                return True
            return False

    @property
    def remaining(self) -> int:
        with self._lock:
            cutoff = time.monotonic() - self.window_seconds
            self._calls = [t for t in self._calls if t > cutoff]
            return max(0, self.max_calls - len(self._calls))


# ---------------------------------------------------------------------------
# NetworkSecurityValidator
# ---------------------------------------------------------------------------

class NetworkSecurityValidator:
    """
    Production-grade network security validator with:
    - IP reputation analysis (VPN/proxy/TOR/datacenter detection)
    - Embedded threat intelligence (CIDR ranges, org patterns, TOR exit nodes)
    - MaxMind GeoIP2 integration (optional)
    - AbuseIPDB API integration (optional)
    - IPQualityScore integration (optional)
    - In-memory caching with configurable TTL
    - Rate-limited external API calls
    - Mock/development mode with heuristic detection
    """

    # ------------------------------------------------------------------
    # Class-level embedded threat intelligence data
    # ------------------------------------------------------------------
    VPN_PROVIDERS: Set[str] = {
        'nordvpn', 'expressvpn', 'surfshark', 'mullvadvpn', 'protonvpn',
        'cyberghost', 'ipvanish', 'Private Internet Access', 'windscribe',
        'vyprvpn', 'hotspot shield', 'tunnelbear', 'purevpn', 'ivacy',
        'zoogvpn', 'keepsolid', 'hide my ass', 'anonine', 'perfect privacy',
        'airvpn', 'tor guard', 'ivpn', 'btguard',
    }

    DATACENTER_PROVIDERS: Set[str] = {
        'AWS', 'Google Cloud', 'Microsoft Azure', 'DigitalOcean', 'Linode',
        'Vultr', 'Hetzner', 'OVH', 'Alibaba', 'Tencent', 'GCP',
        'Oracle Cloud', 'IBM Cloud', 'Rackspace', 'SoftLayer',
    }

    TOR_EXIT_NODES: Set[str] = set(EMBEDDED_TOR_EXIT_IPS)

    VPN_CIDRS: List[ipaddress.IPv4Network] = KNOWN_VPN_CIDRS
    DATACENTER_CIDRS: List[ipaddress.IPv4Network] = KNOWN_DATACENTER_CIDRS

    def __init__(
        self,
        cache_ttl: int = 300,
        maxmind_db_path: Optional[str] = None,
        abuseipdb_api_key: Optional[str] = None,
        ipqs_api_key: Optional[str] = None,
        abuseipdb_rate_limit: int = 30,
        ipqs_rate_limit: int = 60,
        tor_list_url: str = "https://check.torproject.org/exit-addresses",
    ):
        self.cache_ttl = cache_ttl
        self.maxmind_db_path = maxmind_db_path or os.environ.get("MAXMIND_DB_PATH")
        self.abuseipdb_api_key = abuseipdb_api_key or os.environ.get("ABUSEIPDB_API_KEY")
        self.ipqs_api_key = ipqs_api_key or os.environ.get("IPQS_API_KEY")
        self.tor_list_url = tor_list_url

        self._cache: Dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()
        self._tor_lock = threading.Lock()
        self._maxmind_reader = None

        self._abuseipdb_limiter = _RateLimiter(abuseipdb_rate_limit, 60)
        self._ipqs_limiter = _RateLimiter(ipqs_rate_limit, 60)

        self._mock_mode = os.environ.get("USE_MOCK_NETWORK", "").lower() in ("1", "true", "yes")

        if not self._mock_mode:
            self._try_init_maxmind()

        logger.info(
            "NetworkSecurityValidator initialized "
            f"(mock={self._mock_mode}, cache_ttl={cache_ttl}s, "
            f"abuseipdb={'configured' if self.abuseipdb_api_key else 'not configured'}, "
            f"ipqs={'configured' if self.ipqs_api_key else 'not configured'})"
        )

    # ------------------------------------------------------------------
    # MaxMind init
    # ------------------------------------------------------------------

    def _try_init_maxmind(self):
        """Try to initialize MaxMind GeoIP2 reader."""
        if not self.maxmind_db_path or not os.path.exists(self.maxmind_db_path):
            logger.debug("MaxMind GeoIP2 database not found at %s", self.maxmind_db_path)
            return
        try:
            import geoip2.database
            self._maxmind_reader = geoip2.database.Reader(self.maxmind_db_path)
            logger.info("MaxMind GeoIP2 reader initialized from %s", self.maxmind_db_path)
        except ImportError:
            logger.warning("geoip2 package not installed. Install with: pip install geoip2")
        except Exception as exc:
            logger.error("Failed to initialize MaxMind reader: %s", exc)

    # ------------------------------------------------------------------
    # validate_network (original signature preserved)
    # ------------------------------------------------------------------

    def validate_network(
        self,
        ip_address: Optional[str] = None,
        require_residential: bool = False,
        block_vpn: bool = False,
        block_proxy: bool = False,
        block_tor: bool = False,
    ) -> Tuple[bool, Optional[str], IPReputation]:
        """
        Validate network characteristics against security policies.

        Args:
            ip_address: IP to validate (uses request IP if None)
            require_residential: Only allow residential IPs
            block_vpn: Block VPN connections
            block_proxy: Block proxy connections
            block_tor: Block TOR connections

        Returns:
            (is_valid, error_message, reputation)
        """
        ip = ip_address or self._get_client_ip()
        reputation = self._analyze_ip_reputation(ip)

        # Build blocking message list
        errors: List[str] = []

        if block_vpn and (reputation.is_vpn or reputation.anonymizer):
            logger.warning(
                'VPN access blocked: %s',
                ip,
                extra={'ip': ip, 'provider': reputation.organization},
            )
            errors.append('VPN access not permitted. Please disable VPN to continue.')

        if block_proxy and reputation.is_proxy:
            logger.warning('Proxy access blocked: %s', ip)
            errors.append('Proxy access not permitted.')

        if block_tor and reputation.is_tor:
            logger.warning('TOR access blocked: %s', ip)
            errors.append('TOR network access is not permitted.')

        if require_residential and reputation.is_datacenter:
            logger.warning(
                'Datacenter IP rejected (residential required): %s',
                ip,
                extra={'ip': ip, 'provider': reputation.organization},
            )
            errors.append('This operation requires a residential connection.')

        if reputation.threat_level == 'high' and reputation.risk_score >= 70:
            logger.warning(
                'High threat IP blocked: %s (risk_score=%.1f)',
                ip,
                reputation.risk_score,
                extra={'ip': ip, 'risk_score': reputation.risk_score},
            )
            errors.append('Your network has been flagged as suspicious. Please contact support.')

        if errors:
            return False, ' '.join(errors), reputation

        return True, None, reputation

    # ------------------------------------------------------------------
    # _analyze_ip_reputation (core implementation)
    # ------------------------------------------------------------------

    def _analyze_ip_reputation(self, ip: str) -> IPReputation:
        """
        Analyze IP reputation using multi-layered detection:
        1. Cached result lookup
        2. IP address family validation & private/reserved check
        3. TOR exit node membership
        4. VPN/proxy CIDR range matching
        5. Datacenter CIDR range matching
        6. Organization name pattern matching
        7. MaxMind GeoIP2 lookup (optional)
        8. AbuseIPDB API lookup (optional)
        9. IPQualityScore lookup (optional)
        10. Composite risk score calculation
        """
        # Check cache first
        cached = self._get_cached(ip)
        if cached is not None:
            return cached

        # Create base reputation
        reputation = IPReputation(ip_address=ip)

        # Parse IP
        parsed_ip = self._parse_ip(ip)
        if parsed_ip is None:
            reputation.threat_level = 'medium'
            reputation.risk_score = 50.0
            self._set_cached(ip, reputation)
            return reputation

        # Check private/reserved
        if parsed_ip.is_private or parsed_ip.is_loopback or parsed_ip.is_link_local:
            reputation.is_residential = True
            reputation.threat_level = 'low'
            reputation.risk_score = 0.0
            self._set_cached(ip, reputation)
            return reputation

        # Run detection layers
        self._check_tor(ip, reputation)
        self._check_vpn_proxy_cidr(parsed_ip, reputation)
        self._check_datacenter_cidr(parsed_ip, reputation)
        self._check_org_patterns(ip, reputation)

        # External lookups (rate-limited)
        if not self._mock_mode:
            self._check_maxmind(ip, reputation)
            self._check_abuseipdb(ip, reputation)
            self._check_ipqs(ip, reputation)

        # Determine risk score
        self._calculate_risk_score(reputation)

        # Default: if nothing flagged, assume residential
        if not (reputation.is_datacenter or reputation.is_vpn or
                reputation.is_proxy or reputation.is_tor or
                reputation.anonymizer or reputation.hosting_provider):
            reputation.is_residential = True
            reputation.threat_level = 'low'
            reputation.risk_score = min(reputation.risk_score, 10.0)

        self._set_cached(ip, reputation)
        return reputation

    # ------------------------------------------------------------------
    # Detection layer helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_ip(ip: str) -> Optional[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        """Parse and validate IP address string."""
        try:
            return ipaddress.ip_address(ip.strip())
        except ValueError:
            logger.debug("Invalid IP address: %s", ip)
            return None

    def _check_tor(self, ip: str, reputation: IPReputation):
        """Check if IP is a known TOR exit node."""
        if ip in self.TOR_EXIT_NODES:
            reputation.is_tor = True
            reputation.anonymizer = True
            logger.debug("TOR exit node detected: %s", ip)

    def _check_vpn_proxy_cidr(self, parsed_ip: ipaddress.IPv4Address | ipaddress.IPv6Address, reputation: IPReputation):
        """Check if IP falls within known VPN/proxy provider CIDR ranges."""
        if isinstance(parsed_ip, ipaddress.IPv4Address):
            for cidr in self.VPN_CIDRS:
                if parsed_ip in cidr:
                    reputation.is_vpn = True
                    reputation.anonymizer = True
                    reputation.organization = reputation.organization or str(cidr)
                    logger.debug("VPN CIDR match: %s in %s", parsed_ip, cidr)
                    break

    def _check_datacenter_cidr(self, parsed_ip: ipaddress.IPv4Address | ipaddress.IPv6Address, reputation: IPReputation):
        """Check if IP falls within known datacenter/hosting provider CIDR ranges."""
        if isinstance(parsed_ip, ipaddress.IPv4Address):
            for cidr in self.DATACENTER_CIDRS:
                if parsed_ip in cidr:
                    reputation.is_datacenter = True
                    reputation.hosting_provider = True
                    reputation.organization = reputation.organization or str(cidr)
                    logger.debug("Datacenter CIDR match: %s in %s", parsed_ip, cidr)
                    break

    def _check_org_patterns(self, ip: str, reputation: IPReputation):
        """Check organization name patterns against known VPN/datacenter providers."""
        org = self._get_ip_organization(ip)
        if not org:
            return
        reputation.organization = org
        org_lower = org.lower()

        # Check VPN patterns
        for pattern in VPN_ORG_PATTERNS:
            if pattern.search(org_lower):
                reputation.is_vpn = True
                reputation.anonymizer = True
                break

        # Check datacenter patterns
        for pattern in DATACENTER_ORG_PATTERNS:
            if pattern.search(org_lower):
                reputation.is_datacenter = True
                reputation.hosting_provider = True
                break

    def _check_maxmind(self, ip: str, reputation: IPReputation):
        """Enrich reputation with MaxMind GeoIP2 data if available."""
        if self._maxmind_reader is None:
            return
        try:
            response = self._maxmind_reader.city(ip)
            if response:
                reputation.country = response.country.name
                reputation.country_code = response.country.iso_code
                if response.city:
                    pass
                reputation.asn = str(response.traits.autonomous_system_number) if hasattr(response.traits, 'autonomous_system_number') else None
                reputation.asn_org = response.traits.autonomous_system_organization if hasattr(response.traits, 'autonomous_system_organization') else None
                reputation.isp = response.traits.isp if hasattr(response.traits, 'isp') else None
                if reputation.asn_org:
                    self._check_org_patterns(ip, reputation)
        except Exception as exc:
            logger.debug("MaxMind lookup failed for %s: %s", ip, exc)

    def _check_abuseipdb(self, ip: str, reputation: IPReputation):
        """Check IP against AbuseIPDB if API key configured."""
        if not self.abuseipdb_api_key:
            return
        if not self._abuseipdb_limiter.allow():
            logger.debug("AbuseIPDB rate limit reached, skipping %s", ip)
            return
        try:
            url = f"https://api.abuseipdb.com/api/v2/check?ipAddress={ip}&maxAgeInDays=90"
            req = Request(url, headers={
                "Key": self.abuseipdb_api_key,
                "Accept": "application/json",
            })
            resp = urlopen(req, timeout=5)
            data = json.loads(resp.read().decode())
            record = data.get("data", {})
            if record.get("abuseConfidenceScore", 0) > 0:
                reputation.risk_score += float(record.get("abuseConfidenceScore", 0)) * 0.3
            if record.get("isTor", False):
                reputation.is_tor = True
                reputation.anonymizer = True
            if record.get("isPublic", False) and not record.get("isWhitelisted", False):
                pass
            logger.debug("AbuseIPDB result for %s: score=%s", ip, record.get("abuseConfidenceScore"))
        except Exception as exc:
            logger.debug("AbuseIPDB lookup failed for %s: %s", ip, exc)

    def _check_ipqs(self, ip: str, reputation: IPReputation):
        """Check IP against IPQualityScore if API key configured."""
        if not self.ipqs_api_key:
            return
        if not self._ipqs_limiter.allow():
            logger.debug("IPQS rate limit reached, skipping %s", ip)
            return
        try:
            url = (
                f"https://ipqualityscore.com/api/json/{self.ipqs_api_key}/{ip}"
                "?strictness=1&allow_public_access_points=true&fast=true"
            )
            resp = urlopen(url, timeout=5)
            data = json.loads(resp.read().decode())
            if data.get("success", False):
                fraud_score = float(data.get("fraud_score", 0))
                reputation.risk_score += fraud_score * 0.2
                if data.get("proxy", False):
                    reputation.is_proxy = True
                    reputation.anonymizer = True
                if data.get("vpn", False):
                    reputation.is_vpn = True
                    reputation.anonymizer = True
                if data.get("tor", False):
                    reputation.is_tor = True
                    reputation.anonymizer = True
                if data.get("active_vpn", False):
                    reputation.is_vpn = True
                if data.get("active_tor", False):
                    reputation.is_tor = True
                if data.get("hosting", False):
                    reputation.hosting_provider = True
                    reputation.is_datacenter = True
                if data.get("mobile", False):
                    reputation.mobile = True
                reputation.organization = reputation.organization or data.get("ISP")
                reputation.isp = reputation.isp or data.get("ISP")
                reputation.asn_org = reputation.asn_org or data.get("organization")
                reputation.country_code = reputation.country_code or data.get("country_code")
                logger.debug("IPQS result for %s: fraud_score=%s", ip, fraud_score)
        except Exception as exc:
            logger.debug("IPQS lookup failed for %s: %s", ip, exc)

    # ------------------------------------------------------------------
    # Risk score calculation
    # ------------------------------------------------------------------

    def _calculate_risk_score(self, reputation: IPReputation):
        """Calculate composite risk score (0-100) from all detection signals."""
        score = 0.0

        if reputation.is_tor:
            score += 90.0
        if reputation.is_vpn:
            score += 70.0
        if reputation.is_proxy:
            score += 65.0
        if reputation.anonymizer:
            score += 40.0
        if reputation.is_datacenter:
            score += 30.0
        if reputation.hosting_provider:
            score += 20.0
        if not reputation.is_residential:
            score += 10.0

        score = min(score, 100.0)

        if reputation.risk_score > 0:
            score = max(score, reputation.risk_score)
            score = (score + reputation.risk_score) / 2

        reputation.risk_score = round(score, 2)

        if reputation.risk_score >= 70:
            reputation.threat_level = 'high'
        elif reputation.risk_score >= 30:
            reputation.threat_level = 'medium'
        else:
            reputation.threat_level = 'low'

    # ------------------------------------------------------------------
    # New public API methods
    # ------------------------------------------------------------------

    def get_risk_score(self, ip: Optional[str] = None) -> float:
        """Return 0-100 risk score for the given IP (or request IP)."""
        ip = ip or self._get_client_ip()
        return self._analyze_ip_reputation(ip).risk_score

    def is_anonymizer(self, ip: Optional[str] = None) -> bool:
        """Check if IP is a VPN/proxy/anonymizer."""
        ip = ip or self._get_client_ip()
        rep = self._analyze_ip_reputation(ip)
        return rep.is_vpn or rep.is_proxy or rep.is_tor or rep.anonymizer

    def is_hosting(self, ip: Optional[str] = None) -> bool:
        """Check if IP is a datacenter/hosting provider."""
        ip = ip or self._get_client_ip()
        rep = self._analyze_ip_reputation(ip)
        return rep.is_datacenter or rep.hosting_provider

    def is_tor_exit(self, ip: Optional[str] = None) -> bool:
        """Check if IP is a TOR exit node."""
        ip = ip or self._get_client_ip()
        return self._analyze_ip_reputation(ip).is_tor

    def get_ip_geolocation(self, ip: Optional[str] = None) -> Dict[str, Any]:
        """
        Get geolocation and ASN info for an IP.

        Returns dict with keys: ip, country, country_code, asn, asn_org, isp, organization
        """
        ip = ip or self._get_client_ip()
        rep = self._analyze_ip_reputation(ip)
        return {
            'ip': rep.ip_address,
            'country': rep.country,
            'country_code': rep.country_code,
            'asn': rep.asn,
            'asn_org': rep.asn_org,
            'isp': rep.isp,
            'organization': rep.organization,
            'mobile': rep.mobile,
        }

    def refresh_tor_nodes(self) -> int:
        """
        Update TOR exit node list from remote URL.
        Returns number of nodes added.
        """
        added = 0
        try:
            logger.info("Refreshing TOR exit node list from %s", self.tor_list_url)
            req = Request(self.tor_list_url, headers={"User-Agent": "Attendrix/1.0"})
            resp = urlopen(req, timeout=30)
            content = resp.read().decode()

            with self._tor_lock:
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("ExitAddress "):
                        parts = line.split()
                        if len(parts) >= 2:
                            node_ip = parts[1]
                            if node_ip not in self.TOR_EXIT_NODES:
                                self.TOR_EXIT_NODES.add(node_ip)
                                added += 1

            logger.info("TOR exit node refresh complete: %d new nodes (total: %d)",
                         added, len(self.TOR_EXIT_NODES))
        except Exception as exc:
            logger.warning("Failed to refresh TOR exit nodes: %s", exc)

        return added

    def clear_cache(self):
        """Clear the IP reputation cache."""
        with self._lock:
            self._cache.clear()
        logger.debug("IP reputation cache cleared")

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def _get_cached(self, ip: str) -> Optional[IPReputation]:
        """Retrieve cached reputation if not expired."""
        with self._lock:
            entry = self._cache.get(ip)
            if entry is not None and not entry.is_expired():
                return entry.value
            if entry is not None:
                del self._cache[ip]
        return None

    def _set_cached(self, ip: str, reputation: IPReputation):
        """Store reputation in cache with TTL."""
        with self._lock:
            self._cache[ip] = _CacheEntry(reputation, self.cache_ttl)

    # ------------------------------------------------------------------
    # Client IP extraction
    # ------------------------------------------------------------------

    def _get_client_ip(self) -> str:
        """Get client IP from request, handling proxies."""
        if request:
            if 'CF-Connecting-IP' in request.headers:
                return request.headers['CF-Connecting-IP']
            if 'X-Forwarded-For' in request.headers:
                return request.headers['X-Forwarded-For'].split(',')[0].strip()
            return request.remote_addr or '127.0.0.1'
        return '127.0.0.1'

    # ------------------------------------------------------------------
    # Organization lookup (can be overridden by subclasses)
    # ------------------------------------------------------------------

    def _get_ip_organization(self, ip: str) -> Optional[str]:
        """
        Get ISP/organization for IP address.

        Uses MaxMind GeoIP2 database if available, otherwise returns None.
        """
        if self._maxmind_reader:
            try:
                response = self._maxmind_reader.city(ip)
                if response and hasattr(response.traits, 'autonomous_system_organization'):
                    return response.traits.autonomous_system_organization
            except Exception:
                pass
        return None

    # ------------------------------------------------------------------
    # Legacy proxy heuristic (kept for backward compatibility)
    # ------------------------------------------------------------------

    def _looks_like_proxy(self, ip: str) -> bool:
        """Heuristic check for proxy IPs (legacy, now handled by CIDR matching)."""
        return self.is_anonymizer(ip)

    # ------------------------------------------------------------------
    # get_network_metadata (preserved signature)
    # ------------------------------------------------------------------

    def get_network_metadata(self, ip_address: Optional[str] = None) -> Dict[str, Any]:
        """Get detailed network metadata for logging and auditing."""
        ip = ip_address or self._get_client_ip()
        reputation = self._analyze_ip_reputation(ip)

        return {
            'ip': ip,
            'is_vpn': reputation.is_vpn,
            'is_proxy': reputation.is_proxy,
            'is_tor': reputation.is_tor,
            'is_datacenter': reputation.is_datacenter,
            'is_residential': reputation.is_residential,
            'threat_level': reputation.threat_level,
            'organization': reputation.organization,
            'risk_score': reputation.risk_score,
            'anonymizer': reputation.anonymizer,
            'hosting_provider': reputation.hosting_provider,
            'mobile': reputation.mobile,
            'asn': reputation.asn,
            'asn_org': reputation.asn_org,
            'country_code': reputation.country_code,
            'country': reputation.country,
            'isp': reputation.isp,
        }


# ---------------------------------------------------------------------------
# CampusNetworkValidator
# ---------------------------------------------------------------------------

class CampusNetworkValidator:
    """
    Validates connection to campus network (WiFi/LAN).

    Supports:
    - SSID whitelist validation
    - MAC address prefix validation against known campus APs
    - Signal strength anomaly detection
    - BSSID validation
    """

    # Common campus AP MAC OUI prefixes (first 3 octets)
    CAMPUS_MAC_PREFIXES: List[str] = [
        "00:1A:1E",  # Cisco
        "00:1B:0C",  # Cisco
        "00:1B:D4",  # Aruba
        "00:1B:8F",  # Aruba
        "00:0B:85",  # Cisco Aironet
        "00:0B:86",  # Cisco Aironet
        "00:1C:0E",  # Cisco
        "00:1B:63",  # Extreme Networks
        "00:1B:64",  # Extreme Networks
        "00:1B:65",  # Extreme Networks
        "00:1D:45",  # Aruba
        "00:1D:9E",  # Ruckus Wireless
        "00:1E:58",  # Ruckus Wireless
        "00:1F:1E",  # HP/Aruba
        "00:1F:26",  # Juniper
        "00:1F:27",  # Juniper
        "00:1F:28",  # Juniper
        "00:1F:29",  # Juniper
        "00:1F:6D",  # Motorola
        "00:1F:6E",  # Motorola
        "00:1F:6F",  # Motorola
        "00:1F:70",  # Motorola
        "00:20:5C",  # HP
        "00:20:EF",  # 3Com
        "00:21:1A",  # Cisco
        "00:21:1B",  # Cisco
        "00:21:1C",  # Cisco
        "00:21:1D",  # Cisco
        "00:21:1E",  # Cisco
        "00:21:1F",  # Cisco
        "00:21:6C",  # Meru Networks
        "00:22:10",  # Cisco
        "00:22:11",  # Cisco
        "00:22:12",  # Cisco
        "00:22:13",  # Cisco
        "00:22:14",  # Cisco
        "00:22:15",  # Cisco
        "00:22:BD",  # Aerohive
        "00:22:BE",  # Aerohive
        "00:22:BF",  # Aerohive
        "00:23:04",  # Cisco
        "00:23:05",  # Cisco
        "00:23:08",  # Cisco
        "00:23:0A",  # Cisco
        "00:23:0B",  # Cisco
        "00:23:0C",  # Cisco
        "00:23:0D",  # Cisco
        "00:23:13",  # Juniper
        "00:23:14",  # Juniper
        "00:23:68",  # Meraki
        "00:23:69",  # Meraki
        "00:23:6A",  # Meraki
        "00:23:6B",  # Meraki
        "00:23:6C",  # Meraki
        "00:23:6D",  # Meraki
        "00:23:AC",  # Cisco
        "00:23:AD",  # Cisco
        "00:23:AE",  # Cisco
        "00:23:DB",  # Aerohive
        "00:23:DC",  # Aerohive
        "00:24:14",  # Xirrus
        "00:24:36",  # Alcatel-Lucent
        "00:24:37",  # Alcatel-Lucent
        "00:24:38",  # Alcatel-Lucent
        "00:24:6C",  # Cisco
        "00:24:97",  # Aruba
        "00:24:98",  # Aruba
        "00:25:45",  # Xirrus
        "00:25:46",  # Xirrus
        "00:25:83",  # Cisco
        "00:25:84",  # Cisco
        "00:25:8C",  # Alcatel-Lucent
        "00:25:9C",  # Symbol/Motorola
        "00:25:BA",  # Ruckus Wireless
        "00:25:BB",  # Ruckus Wireless
        "00:25:BC",  # Ruckus Wireless
        "00:25:BD",  # Ruckus Wireless
        "00:26:0B",  # Aruba
        "00:26:0C",  # Aruba
        "00:26:0D",  # Aruba
        "00:26:82",  # Meru Networks
        "00:26:AB",  # D-Link
        "00:26:B6",  # Aerohive
        "00:27:13",  # Juniper
        "00:27:14",  # Juniper
        "00:27:22",  # Xirrus
        "00:27:23",  # Xirrus
    ]

    # Normal signal strength range for campus WiFi (-dBm)
    MIN_SIGNAL_STRENGTH = -85
    MAX_SIGNAL_STRENGTH = -20

    def __init__(self):
        self._lock = threading.Lock()
        self._known_ssids: Set[str] = set()
        logger.info("CampusNetworkValidator initialized")

    def validate_campus_network(
        self,
        mac_address: Optional[str] = None,
        ssid: Optional[str] = None,
        signal_strength: Optional[int] = None,
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Validate connection to authorized campus network.

        Args:
            mac_address: WiFi MAC address (BSSID of AP)
            ssid: Network SSID
            signal_strength: Signal strength in -dBm

        Returns:
            (is_valid, error_message, metadata)
        """
        from flask import current_app

        metadata: Dict[str, Any] = {
            'mac_address': mac_address,
            'ssid': ssid,
            'signal_strength': signal_strength,
            'mac_oui_valid': None,
            'signal_anomaly': None,
        }

        errors: List[str] = []

        # SSID validation
        known_ssids = list(self._known_ssids)
        app_ssids = current_app.config.get('CAMPUS_NETWORK_SSIDS', [])
        if app_ssids:
            known_ssids.extend(app_ssids)
        known_ssids = list(set(known_ssids))
        self._known_ssids = set(known_ssids)

        if ssid and known_ssids:
            if ssid not in known_ssids:
                errors.append(f'Not connected to authorized campus network ({ssid})')
                metadata['ssid_valid'] = False
            else:
                metadata['ssid_valid'] = True
        else:
            metadata['ssid_valid'] = None

        # MAC address OUI validation
        if mac_address:
            mac_clean = mac_address.upper().replace('-', ':').strip()
            # Normalize: ensure colons every 2 chars
            parts = mac_clean.split(':')
            if len(parts) == 6:
                oui = ':'.join(parts[:3])
                metadata['mac_oui'] = oui
                if oui in self.CAMPUS_MAC_PREFIXES:
                    metadata['mac_oui_valid'] = True
                else:
                    metadata['mac_oui_valid'] = False
                    logger.warning("Unknown MAC OUI prefix: %s (MAC: %s)", oui, mac_address)
            else:
                metadata['mac_oui_valid'] = False
                logger.warning("Invalid MAC address format: %s", mac_address)
        else:
            metadata['mac_oui_valid'] = None

        # Signal strength anomaly detection
        if signal_strength is not None:
            if signal_strength > self.MAX_SIGNAL_STRENGTH or signal_strength < self.MIN_SIGNAL_STRENGTH:
                metadata['signal_anomaly'] = True
                errors.append(f'Suspicious signal strength ({signal_strength} dBm)')
            else:
                metadata['signal_anomaly'] = False

        if errors:
            return False, '; '.join(errors), metadata

        return True, None, metadata

    def add_known_ssid(self, ssid: str):
        """Add an SSID to the known campus networks list."""
        with self._lock:
            self._known_ssids.add(ssid)
        logger.info("Added known campus SSID: %s", ssid)

    def remove_known_ssid(self, ssid: str):
        """Remove an SSID from the known campus networks list."""
        with self._lock:
            self._known_ssids.discard(ssid)
        logger.info("Removed known campus SSID: %s", ssid)

    def get_known_ssids(self) -> List[str]:
        """Get list of known campus network SSIDs."""
        return list(self._known_ssids)
