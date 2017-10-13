#!/usr/bin/python3

import sharemem
import struct

mem = sharemem.open(3145914, 10)

def unpack(format, offset=0):
	return struct.unpack(format, sharemem.read(mem+offset, struct.calcsize(format)))

def pack(format, *args, offset=0):
	sharemem.write(mem+offset, struct.pack(format, *args))

def read():
	return unpack("hh")

def write(pos):
	pack("hh", *pos);


if __name__ == '__main__':
	import click
	import time

	@click.command()
	@click.option('--count', '-c', default=1, help="Count of measured samles")
	@click.option('--pause', '-p', default=0.1, help="Pause between samples")
	def main(count, pause):
		for _ in range(count):
			print("{} {}".format(*read()))
			time.sleep(pause)
	main()