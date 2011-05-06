#!/bin/bash

export JAVA_HOME=/usr/lib/jvm/java-6-sun/
export EC2_HOME=/home/rajesh/tools/ec2-api-tools-1.3-30349
export PATH=$PATH:$EC2_HOME/bin
export EC2_PRIVATE_KEY=/home/rajesh/ec2-keys/riotvine/pk-3WJEDUWE3GC5QKKYJ3TX65SD3BR3TWA7.pem
export EC2_CERT=/home/rajesh/ec2-keys/riotvine/cert-3WJEDUWE3GC5QKKYJ3TX65SD3BR3TWA7.pem

# Open SSH port to server
# ec2-authorize default -P tcp -p 22
# echo "Authorized SSH"

# Close SSH port
ec2-revoke default -P tcp -p 22
echo "Revoked SSH"
