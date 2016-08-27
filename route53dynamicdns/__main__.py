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

    arg_parser = argparse.ArgumentParser()

    arg_parser.add_argument('--public-address', action='store_true',
        help='use public IP address rather than local one (only applies to IPv4 addresses)')

    arg_parser.add_argument('--wait-for-route53-propagation', action='store_true',
        help='wait for update to propagate to all Route53 servers before exiting')

    default_ttl = 60 # This default is the TTL used by DynDNS, for example.

    arg_parser.add_argument('--ttl', type=int,
        help="TTL (Time To Live) value to use (if not specified then the default is to use the existing record's value or %d if the record doesn't exist yet)" % default_ttl)

    arg_parser.add_argument('host_name',
        help='the host name for the entry to update')

    args = arg_parser.parse_args()

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

    if args.public_address:
        import requests
        ipv4 = requests.get('https://ipv4.myexternalip.com/raw').text.strip()
    else:
        # Get local IP address that is used for Internet access.
        # from: http://stackoverflow.com/a/166589/98286
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(('8.8.8.8', 53))
                ipv4 = s.getsockname()[0]
        except:
            ipv4 = None

    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as s:
            s.connect(('2001:4860:4860::8888', 53))
            ipv6 = s.getsockname()[0]
    except:
        ipv6 = None
        
    changes = []

    for doing_ipv6_change in (False, True):
        record_type = 'AAAA' if doing_ipv6_change else 'A'
        ip = ipv6 if doing_ipv6_change else ipv4
        ip_version_string = 'IPv6' if doing_ipv6_change else 'IPv4'

        record_sets = r53.list_resource_record_sets(
            HostedZoneId=zone_id, StartRecordName=args.host_name, StartRecordType=record_type, MaxItems='1'
        )['ResourceRecordSets']

        existing_ttl = None

        if len(record_sets) > 0:
            record_set = record_sets[0]
            records = record_set.get('ResourceRecords', [])

            if len(records) == 1:
                existing_ttl = record_set['TTL']
                existing_ip = records[0]['Value']

                if existing_ip == ip and (args.ttl is None or existing_ttl == args.ttl):
                    log('Record is already set to correct %s address %s' % (ip_version_string, ip))
                    continue

            elif len(records) == 0:
                if ip is None:
                    log("No %s address record exists and we don't have an address of that type" % ip_version_string)
                    continue

        if ip:
            ttl = args.ttl or existing_ttl or default_ttl
            log('Setting record to point to %s address %s with TTL %d' % (ip_version_string, ip, ttl))
        else:
            ttl = existing_ttl
            log("Removing record for %s address because we don't have an address of that type" % ip_version_string)

        change = {
            'Action': 'UPSERT' if ip is not None else 'DELETE',
            'ResourceRecordSet': {
                'Name': args.host_name,
                'Type': record_type,
                'TTL': ttl,
                'ResourceRecords': [
                    {
                        'Value': ip or existing_ip,
                    }
                ],
            },
        }

        changes.append(change)

    if len(changes) == 0:
        # All records are correct already.
        sys.exit(0)

    response = r53.change_resource_record_sets(
        HostedZoneId = zone_id,
        ChangeBatch = { 'Changes': changes })

    if args.wait_for_route53_propagation:
        while response['ChangeInfo']['Status'] != 'INSYNC':
            log('Waiting for DNS update to propagate')
            time.sleep(15)
            response = r53.get_change(Id=response['ChangeInfo']['Id'])

if __name__ == '__main__': main()
