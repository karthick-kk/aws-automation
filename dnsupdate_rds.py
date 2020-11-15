import json
import boto3
import datetime
import subprocess
from re import search
from pprint import pprint

# Vars
basestr="prmisc"
domain="dbcluster1.test"
region="ap-south-1"
sendAddr = "somemail@somedomain.com"
currecord=basestr+"."+domain+"."

# Get Current and LastMonth
current_year_short = datetime.datetime.now().strftime('%y')
current_month_text = datetime.datetime.now().strftime('%h')
current_day = datetime.datetime.now().strftime('%d')
today = datetime.date.today()
first = today.replace(day=1)
lastMonth = first - datetime.timedelta(days=1)

# Get ClusterName
dbclustername=basestr+current_month_text.lower()

client = boto3.client('rds', region_name=region)
response2 = client.describe_db_cluster_endpoints()

# Get Current Cluster Endpoint
for r in response2['DBClusterEndpoints']:
    #if r['DBClusterIdentifier'] == dbclustername and r['EndpointType'] == 'WRITER':
    if search(dbclustername, r['DBClusterIdentifier']) and r['EndpointType'] == 'WRITER':
        # print r['Endpoint']
        db_endpoint = r['Endpoint']

client = boto3.client('route53',region_name=region)
response = client.list_hosted_zones_by_name(DNSName=domain+".")
print(response['HostedZones'][0]['Id'])
hostZoneID=response['HostedZones'][0]['Id']


# Get Current CNAME value
paginator = client.get_paginator('list_resource_record_sets')

try:
    source_zone_records = paginator.paginate(HostedZoneId=hostZoneID)
    for record_set in source_zone_records:
        for record in record_set['ResourceRecordSets']:
            if record['Type'] == 'CNAME' and record['Name'] == currecord:
                # print(record['Name'])
                current_CNAME=record['ResourceRecords'][0]['Value']
                # print current_CNAME
except Exception as error:
    print('An error occurred getting source zone records:')
    print(str(error))
    raise

# Create record entry for old CNAME
try:
    Name=basestr+lastMonth.strftime("%h").lower()+current_year_short+"."+domain
    value = current_CNAME
    type='CNAME'
    ttl=300
    action='UPSERT'
    response = client.change_resource_record_sets(
    HostedZoneId=hostZoneID,
    ChangeBatch= {
                    'Comment': 'add %s -> %s' % (Name, value),
                    'Changes': [
                        {
                            'Action': action,
                            'ResourceRecordSet': {
                                'Name': Name,
                                'Type': type,
                                'TTL': ttl,
                                'ResourceRecords': [{'Value': value}]
                        }
                    }]
    })
except Exception as e:
    print(e)    
newrecord=Name
# Update CNAME record to new endpoint
try:
    Name=basestr+"."+domain
    value = db_endpoint
    type='CNAME'
    ttl=300
    action='UPSERT'
    response = client.change_resource_record_sets(
    HostedZoneId=hostZoneID,
    ChangeBatch= {
                    'Comment': 'add %s -> %s' % (Name, value),
                    'Changes': [
                        {
                            'Action': action,
                            'ResourceRecordSet': {
                                'Name': Name,
                                'Type': type,
                                'TTL': ttl,
                                'ResourceRecords': [{'Value': value}]
                        }
                    }]
    })
except Exception as e:
    print(e)


# Send Email to sendAddr
cmd = "echo -e '" + Name + " --> " + value + "\n" + newrecord + " --> " + current_CNAME + "' | mailx -s 'DNS Records Updated' " + sendAddr
print(cmd)
subprocess.Popen(cmd,shell=True,close_fds=True)
