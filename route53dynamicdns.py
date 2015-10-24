#!/usr/bin/env python3

import argparse
import socket
import sys
import time

import boto3

def log(message): print(message)

if len(sys.argv) == 1:
    sys.argv.append('-h')

arg_parser = argparse.ArgumentParser()

arg_parser.add_argument('--public-address', action='store_true',
    help='use public IP address rather than local one')

arg_parser.add_argument('--wait-for-route53-propagation', action='store_true',
    help='wait for update to propagate to all Route53 servers before exiting')

arg_parser.add_argument('host_name',
    help='the host name for the entry to update')

args = arg_parser.parse_args()

if args.public_address:
    import ipify
    ip = ipify.get_ip()
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

log('Getting existing record\'s TTL')

record_set = r53.list_resource_record_sets(
        HostedZoneId=zone_id, StartRecordName=args.host_name, StartRecordType='A', MaxItems='1'
    )['ResourceRecordSets'][0]

records = record_set['ResourceRecords']
if len(records) == 1:
    if records[0]['Value'] == ip:
        log('%s is already set to correct address %s' % (args.host_name, ip))
        sys.exit(0)

ttl = record_set['TTL']

log('Setting %s to point to %s with TTL %d' % (args.host_name, ip, ttl))

response = r53.change_resource_record_sets(
    HostedZoneId = zone_id,
    ChangeBatch = {
        'Changes': [
            {
                'Action': 'UPSERT',
                'ResourceRecordSet': {
                    'Name': args.host_name,
                    'Type': 'A',
                    'TTL': ttl,
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
