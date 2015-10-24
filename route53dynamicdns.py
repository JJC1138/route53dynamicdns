#!/usr/bin/env python3

import socket
import sys

import boto3

def log(message): print(message)

host_name = sys.argv[1]

# Get local IP address that is used for Internet access.
# from: http://stackoverflow.com/a/166589/98286
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(('8.8.8.8', 53))
ip = s.getsockname()[0]
s.close()

r53 = boto3.client('route53')

if not host_name.endswith('.'): host_name = host_name + '.'

log('Looking for Route53 record for %s' % host_name)

zones = r53.list_hosted_zones()

zone_id = None

for zone in zones['HostedZones']:
	if host_name.endswith(zone['Name']):
		zone_id = zone['Id']
		break

if zone_id is None:
	raise Exception('No Route53 zone found for %s' % host_name)

log('Getting existing record\'s TTL')

ttl = r53.list_resource_record_sets(
		HostedZoneId=zone_id, StartRecordName=host_name, StartRecordType='A', MaxItems='1'
	)['ResourceRecordSets'][0]['TTL']

log('Setting %s to point to %s with TTL %d' % (host_name, ip, ttl))

response = r53.change_resource_record_sets(
	HostedZoneId = zone_id,
	ChangeBatch = {
		'Changes': [
			{
				'Action': 'UPSERT',
				'ResourceRecordSet': {
					'Name': host_name,
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
