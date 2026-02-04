#mapping-script
from bots import transform


def main(inn, out):
    transform.inn2out(inn, out)  # receive ISA; send out as xml_nocheck
