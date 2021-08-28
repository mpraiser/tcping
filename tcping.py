#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Use tcp ping host, just like ping comppand
"""

import socket
import time
import click
import sys

from typing import Iterable, Callable, Any
from collections import namedtuple
from functools import partial
from six import print_
from timeit import default_timer as timer
from prettytable import PrettyTable

__version__ = "0.1.2"

Statistics = namedtuple('Statistics', [
    'host',
    'port',
    'successed',
    'failed',
    'success_rate',
    'minimum',
    'maximum',
    'average'])

iprint = partial(print_, flush=True)


def avg(x: list) -> float:
    return sum(x) / float(len(x))


class Socket(object):
    def __init__(
        self, 
        family: socket.AddressFamily,
        sock_type: socket.SocketKind, 
        timeout: float
    ):
        s = socket.socket(family, sock_type)
        s.settimeout(timeout)
        self._s = s

    def connect(self, host: str, port: int):
        self._s.connect((host, int(port)))

    def shutdown(self):
        self._s.shutdown(socket.SHUT_RD)

    def close(self):
        self._s.close()


class Print(object):
    def __init__(self):
        self.table_field_names = []
        self.rows = []

    @property
    def raw(self):
        statistics_group = []
        for row in self.rows:
            total = row.successed + row.failed
            statistics_header = f"\n--- {row.host}[:{row.port}] tcping statistics ---"
            statistics_body = f"\n{total} connections, {row.successed} successed, {row.failed} failed, {row.success_rate} success rate"
            statistics_footer = f"\nminimum = {row.minimum}, maximum = {row.maximum}, average = {row.average}"

            statistics = statistics_header + statistics_body + statistics_footer
            statistics_group.append(statistics)

        return ''.join(statistics_group)

    @property
    def table(self):
        x = PrettyTable()
        x.field_names = self.table_field_names

        for row in self.rows:
            x.add_row(row)

        return '\n' + x.get_string()

    def set_table_field_names(self, field_names: Iterable[str]):
        self.table_field_names = field_names

    def add_statistics(self, row: Statistics):
        self.rows.append(row)


class Timer(object):
    def __init__(self):
        self._start = 0
        self._stop = 0

    def start(self):
        self._start = timer()

    def stop(self):
        self._stop = timer()

    def cost(self, targets: Iterable[tuple[Callable, Any]]):
        self.start()
        for func, arg in targets:
            if arg:
                func(*arg)
            else:
                func()

        self.stop()
        return self._stop - self._start


class Ping(object):
    def __init__(self, host: str, port: int, timeout: float, interval: float):
        self.print_ = Print()
        self.timer = Timer()

        self._successed = 0
        self._failed = 0
        self._conn_times = []
        self._host = host
        self._port = port
        self._timeout = timeout
        self._interval = interval

        self.print_.set_table_field_names(
            ['Host', 'Port', 'Successed', 'Failed', 'Success Rate', 'Minimum', 'Maximum', 'Average'])

    def _create_socket(self, family: socket.AddressFamily, sock_type: socket.SocketKind):
        return Socket(family, sock_type, self._timeout)

    def _success_rate(self):
        count = self._successed + self._failed
        try:
            rate = (float(self._successed) / count) * 100
            rate = f"{rate:.2f}"
        except ZeroDivisionError:
            rate = "0.00"
        return rate

    def statistics(self, n):
        conn_times = self._conn_times if self._conn_times != [] else [0]
        minimum = f"{min(conn_times):.2f} ms"
        maximum = f"{max(conn_times):.2f} ms"
        average = f"{avg(conn_times):.2f} ms"
        success_rate = self._success_rate() + '%'

        self.print_.add_statistics(Statistics(
            self._host,
            self._port,
            self._successed,
            self._failed,
            success_rate,
            minimum,
            maximum,
            average))

    @property
    def result(self):
        return self.print_

    @property
    def status(self):
        return self._successed == 0

    def ping(self, count: int):
        """
        :param count: if 0, it will keep pinging.
        """
        n = 0
        while True:
            s = self._create_socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                time.sleep(self._interval)
                cost_time = self.timer.cost((
                    (s.connect, (self._host, self._port)),
                    (s.shutdown, None)
                ))
                s_runtime = 1000 * (cost_time)
                iprint(f"Connected to {self._host}[:{self._port}]: seq = {n}, time = {s_runtime:.2f} ms")
                self._conn_times.append(s_runtime)

            except socket.timeout:
                iprint(f"Connected to {self._host}[:{self._port}]: seq = {n} time out!")
                self._failed += 1

            except KeyboardInterrupt:
                self.statistics(n - 1)
                raise KeyboardInterrupt()

            else:
                self._successed += 1

            finally:
                s.close()
            
            n += 1
            if count > 0 and n >= count:
                break

        self.statistics(n)


@click.command()
@click.option('--port', '-p', default=80, type=click.INT, help='Tcp port. (default: 80)')
@click.option('--count', '-c', default=0, type=click.INT, help='Try connections counts, 0 for endless pinging. (default: 0).')
@click.option('--timeout', '-t', default=1, type=click.FLOAT, help='Timeout seconds. (default: 1)')
@click.option('--report/--no-report', default=True, help='Show report to replace statistics.')
@click.option('--interval', '-i', default=1, type=click.FLOAT, help='Interval of pinging. (default: 1)')
@click.argument('host')
def cli(host: str, port: int, count: int, timeout: float, report: bool, interval: float):
    ping = Ping(host, port, timeout, interval)
    try:
        ping.ping(count)
    except KeyboardInterrupt:
        pass

    if report:
        iprint(ping.result.table)
    else:
        iprint(ping.result.raw)
    sys.exit(ping.status)


if __name__ == '__main__':
    cli()
