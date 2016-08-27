#!/usr/bin/env python3

import argparse
import socket
import sys
import time

import boto3

def main():
    def log(message): print(message)

    if len(sys.argv) == 1:
        sys.argv.append('-h')

    arg_parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    arg_parser.add_argument('--public-address', action='store_true',
        help='use public IP address rather than local one')

    arg_parser.add_argument('--wait-for-route53-propagation', action='store_true',
        help='wait for update to propagate to all Route53 servers before exiting')

    arg_parser.add_argument('--ttl', type=int, default=60, # This default is the TTL used by DynDNS, for example.
        help='TTL (Time To Live) value to use for the record')

    arg_parser.add_argument('host_name',
        help='the host name for the entry to update')

    args = arg_parser.parse_args()

    if args.public_address:
        import requests
        ip = requests.get('https://ipv4.myexternalip.com/raw').text.strip()
    else:
        # Get local IP address that is used for Internet access.
        # from: http://stackoverflow.com/a/166589/98286
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 53))
        ip = s.getsockname()[0]
        s.close()

    r53 = boto3.client('route53')

    if not args.host_name.endswith('.'): args.host_name = args.host_name + '.'

    log('Looking for Route53 record for %s' % args.host_name)

    zones = r53.list_hosted_zones()

    zone_id = None

    for zone in zones['HostedZones']:
        if args.host_name.endswith(zone['Name']):
            zone_id = zone['Id']
            break

    if zone_id is None:
        raise Exception('No Route53 zone found for %s' % args.host_name)

    log('Setting %s to point to %s with TTL %d' % (args.host_name, ip, args.ttl))

    response = r53.change_resource_record_sets(
        HostedZoneId = zone_id,
        ChangeBatch = {
            'Changes': [
                {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': args.host_name,
                        'Type': 'A',
                        'TTL': args.ttl,
                        'ResourceRecords' : [
                            {
                                'Value': ip
                            },
                        ],
                    }
                },
            ]
        })

    if args.wait_for_route53_propagation:
        while response['ChangeInfo']['Status'] != 'INSYNC':
            log('Waiting for DNS update to propagate')
            time.sleep(15)
            response = r53.get_change(Id=response['ChangeInfo']['Id'])

if __name__ == '__main__': main()
