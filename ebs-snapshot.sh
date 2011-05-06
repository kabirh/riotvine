#!/bin/bash

echo "RiotVine backup started"

export HOSTNAME=`/bin/hostname`
echo $HOME/.keychain/${HOSTNAME}-sh
cat $HOME/.keychain/${HOSTNAME}-sh
source $HOME/.keychain/${HOSTNAME}-sh

export JAVA_HOME=/usr/lib/jvm/java-6-sun/
export EC2_HOME=/home/rajesh/tools/ec2-api-tools-1.3-30349
export PATH=$PATH:$EC2_HOME/bin 
export EC2_PRIVATE_KEY=/home/rajesh/ec2-keys/riotvine/pk-3WJEDUWE3GC5QKKYJ3TX65SD3BR3TWA7.pem
export EC2_CERT=/home/rajesh/ec2-keys/riotvine/cert-3WJEDUWE3GC5QKKYJ3TX65SD3BR3TWA7.pem

# Open SSH port to server
ec2-authorize default -P tcp -p 22
echo "Authorized SSH"

# Database backup
ssh web@rvdb bin/backup.sh
echo "Backed up DB and media"

# Snapshot 10GB db export
ec2-create-snapshot vol-d8e01eb1
echo "Initiated 10GB snapshot"

# Snapshot 30GB db export
ec2-create-snapshot vol-d9e01eb0
echo "Initiated 30GB snapshot"

# Close SSH port
ec2-revoke default -P tcp -p 22
echo "Revoked SSH"

echo "EBS backup done"


